import json
import logging
import uuid

from django.utils.dateparse import parse_datetime

from spotify_stats.analytics.exceptions import (
    InvalidFileContentError,
    InvalidRecordError,
)
from spotify_stats.analytics.models import FileUploadJob
from .utils import safe_strip

log = logging.getLogger()


class StreamingDataValidator:

    def validate_file_content(self, file):
        try:
            streaming_records = json.load(file)
        except json.JSONDecodeError as e:
            log.error(f"Invalid JSON in file: {e}")
            raise InvalidFileContentError("Invalid JSON format.")

        if not isinstance(streaming_records, list):
            log.error(f"Expected a list, got {type(streaming_records)}")
            raise InvalidFileContentError("Expected a list of records.")

        return streaming_records

    def validate_record(self, record: dict):
        if not isinstance(record, dict):
            return None

        track_name = safe_strip(record.get("master_metadata_track_name"))
        spotify_track_uri = safe_strip(record.get("spotify_track_uri"))
        ts = safe_strip(record.get("ts"))
        ms_played = record.get("ms_played")

        missing_fields = self._get_missing_fields(
            track_name, spotify_track_uri, ts, ms_played
        )

        if missing_fields:
            return None

        try:
            ms_played = self._validate_ms_played(ms_played)
            played_at = self._validate_played_at(ts)
            spotify_track_uri = self._validate_spotify_track_uri(spotify_track_uri)
        except InvalidRecordError:
            return None

        return {
            "track_name": track_name,
            "spotify_track_uri": spotify_track_uri,
            "played_at": played_at,
            "ms_played": ms_played,
        }

    def _get_missing_fields(
        self, track_name: str, spotify_track_uri: str, ts: str, ms_played: int
    ):
        missing_fields = []
        if not track_name:
            missing_fields.append("track_name")
        if not spotify_track_uri:
            missing_fields.append("spotify_track_uri")
        if not ts:
            missing_fields.append("ts")
        if ms_played is None:
            missing_fields.append("ms_played")
        return missing_fields

    def _validate_ms_played(self, ms_played):
        try:
            ms_played = int(ms_played)
            if ms_played < 0:
                raise InvalidRecordError("ms_played must be non-negative.")
            return ms_played
        except (ValueError, TypeError):
            raise InvalidRecordError("Invalid ms_played value.")

    def _validate_played_at(self, played_at_str: str):
        try:
            parsed_datetime = parse_datetime(played_at_str)
            if parsed_datetime is None:
                raise InvalidRecordError("played_at is not well formatted.")
            return parsed_datetime
        except ValueError:
            raise InvalidRecordError("Invalid played_at value.")

    def _validate_spotify_track_uri(self, spotify_track_uri: str):
        if not spotify_track_uri.startswith("spotify:track:"):
            raise InvalidRecordError("Invalid spotify_track_uri.")
        return spotify_track_uri


class FileProcessingService:

    def __init__(self, validator, db_service):
        self.validator = validator
        self.db_service = db_service

    def process_file_upload_jobs(self, job_ids: list[uuid.UUID]) -> None:
        jobs = FileUploadJob.objects.filter(id__in=job_ids)

        for job in jobs:
            job.status = FileUploadJob.Status.PROCESSING
            job.save(update_fields=["status"])

            job_succeeded = self.process_single_job(job)

            job.status = (
                FileUploadJob.Status.COMPLETED
                if job_succeeded
                else FileUploadJob.Status.FAILED
            )
            job.save(update_fields=["status"])

    def process_single_job(self, job: FileUploadJob) -> bool:
        try:
            streaming_records = self.validator.validate_file_content(job.file)
        except InvalidFileContentError as e:
            log.error(f"Job {job.id} failed: {e}")
            return False

        tracks_data = {}
        listening_history_data = []

        for record in streaming_records:
            validated_record = self.validator.validate_record(record)
            if validated_record is None:
                continue

            spotify_id = validated_record["spotify_track_uri"].split(":")[-1]
            tracks_data[spotify_id] = {
                "spotify_id": spotify_id,
                "name": validated_record["track_name"],
            }
            listening_history_data.append(
                {
                    "track_spotify_id": spotify_id,
                    "played_at": validated_record["played_at"],
                    "ms_played": validated_record["ms_played"],
                }
            )

        try:
            self.db_service.bulk_create_tracks(list(tracks_data.values()))
            self.db_service.bulk_create_listening_history(
                job.user, listening_history_data
            )
            return True
        except Exception as e:
            log.error(f"Failed to save data for job {job.id}: {e}")
            return False
