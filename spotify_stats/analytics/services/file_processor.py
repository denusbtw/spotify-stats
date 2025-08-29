import datetime
import json
import logging
import uuid

from django.utils.dateparse import parse_datetime

from spotify_stats.analytics.models import FileUploadJob, ListeningHistory
from spotify_stats.catalog.models import Track

log = logging.getLogger()


class FileProcessingService:

    def process_file_upload_jobs(self, job_ids: list[uuid.UUID]) -> None:
        jobs = FileUploadJob.objects.filter(id__in=job_ids)

        for job in jobs:
            job.status = FileUploadJob.Status.PROCESSING
            job.save(update_fields=["status"])

            try:
                success = self.process_single_job(job)
                job_succeeded = success

                if success:
                    log.info("Job %s completed successfully" % job.id)
                else:
                    log.warning("Job %s failed during processing" % job.id)
            except Exception as e:
                log.error("Job %s crashed with exception: %s" % (job.id, e))
                job_succeeded = False

            job.status = (
                FileUploadJob.Status.COMPLETED
                if job_succeeded
                else FileUploadJob.Status.FAILED
            )
            job.save(update_fields=["status"])

    def process_single_job(self, job: FileUploadJob) -> bool:
        streaming_records = self.validate_job_file_content(job)
        if streaming_records is None:
            return False

        existing_track_spotify_ids = set(
            Track.objects.values_list("spotify_id", flat=True)
        )

        tracks_to_create = []
        listening_history_data = []

        for record in streaming_records:
            record = self.validate_record(record)
            if record is None:
                continue

            track_name = record["track_name"]
            spotify_track_uri = record["spotify_track_uri"]
            played_at = record["played_at"]
            ms_played = record["ms_played"]

            spotify_id = spotify_track_uri.split(":")[-1]
            if spotify_id not in existing_track_spotify_ids:
                tracks_to_create.append(
                    Track(
                        spotify_id=spotify_id,
                        name=track_name,
                    )
                )
                existing_track_spotify_ids.add(spotify_id)

            listening_history_data.append(
                {
                    "spotify_id": spotify_id,
                    "played_at": played_at,
                    "ms_played": ms_played,
                }
            )

        Track.objects.bulk_create(
            tracks_to_create, batch_size=500, ignore_conflicts=True
        )

        all_spotify_ids = [data["spotify_id"] for data in listening_history_data]
        tracks_map = {
            track.spotify_id: track
            for track in Track.objects.filter(spotify_id__in=all_spotify_ids)
        }

        listening_history_to_create = []
        for data in listening_history_data:
            track = tracks_map.get(data["spotify_id"])
            if track:
                listening_history_to_create.append(
                    ListeningHistory(
                        user=job.user,
                        track=track,
                        played_at=data["played_at"],
                        ms_played=data["ms_played"],
                    )
                )

        ListeningHistory.objects.bulk_create(
            listening_history_to_create, batch_size=500, ignore_conflicts=True
        )

        log.info(
            "Created %d listening history records." % len(listening_history_to_create)
        )

        return True

    def validate_job_file_content(self, job: FileUploadJob) -> list | None:
        try:
            streaming_records = json.load(job.file)
        except json.JSONDecodeError as e:
            log.error("Invalid JSON in job %s: %s" % (job.id, e))
            return None

        if not isinstance(streaming_records, list):
            log.error(
                "Job %s: Expected list, got %s" % (job.id, type(streaming_records))
            )
            return None

        return streaming_records

    def validate_record(self, record: dict) -> dict | None:
        if not isinstance(record, dict):
            # log.warning("Invalid record type: %s" % type(record))
            return None

        track_name = self.safe_strip(record.get("master_metadata_track_name"))
        spotify_track_uri = self.safe_strip(record.get("spotify_track_uri"))
        ts = self.safe_strip(record.get("ts"))
        ms_played = record.get("ms_played")

        missing_fields = self.get_missing_fields(
            track_name, spotify_track_uri, ts, ms_played
        )

        if missing_fields:
            # log.warning("Missing required fields: %s" % ", ".join(missing_fields))
            return None

        ms_played = self.validate_ms_played(ms_played)
        if ms_played is None:
            return None

        played_at = self.validate_played_at(ts)
        if played_at is None:
            return None

        record_ = {
            "track_name": track_name,
            "spotify_track_uri": spotify_track_uri,
            "played_at": played_at,
            "ms_played": ms_played,
        }

        return record_

    def get_missing_fields(
        self, track_name: str, spotify_track_uri: str, ts: str, ms_played: int
    ) -> list:
        missing_fields = []
        if not ts:
            missing_fields.append("ts")
        if not ms_played:
            missing_fields.append("ms_played")
        if not track_name:
            missing_fields.append("track_name")
        if not spotify_track_uri:
            missing_fields.append("spotify_track_uri")

        return missing_fields

    def validate_ms_played(self, ms_played: int) -> int | None:
        try:
            ms_played = int(ms_played)
            if ms_played < 0:
                # log.warning("Negative ms_played: %d" % ms_played)
                return None
        except (ValueError, TypeError) as e:
            # log.warning("Invalid ms_played '%s': %s" % (ms_played, e))
            return None

        return ms_played

    def validate_played_at(self, played_at: str) -> datetime.datetime | None:
        try:
            played_at = parse_datetime(played_at)
            if played_at is None:
                # log.warning("Invalid datetime format: %s" % played_at)
                return None
        except ValueError as e:
            # log.warning("Datetime parsing error for '%s': '%s'" % (played_at, e))
            return None

        return played_at

    def split_into_batches(self, items: list, batch_size: int):
        for i in range(0, len(items), batch_size):
            yield items[i : i + batch_size]

    def safe_strip(self, value: str) -> str | None:
        return value.strip() if isinstance(value, str) else None
