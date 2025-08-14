import json
import logging

from celery import shared_task
from django.utils.dateparse import parse_datetime

from spotify_stats.analytics.models import FileUploadJob, StreamingHistory
from spotify_stats.catalog.models import Track, Artist, Album

log = logging.getLogger(__name__)


@shared_task
def process_file_upload_jobs(job_ids):
    jobs = FileUploadJob.objects.filter(id__in=job_ids)

    for job in jobs:
        job.status = FileUploadJob.Status.PROCESSING
        job.save(update_fields=["status"])

        try:
            success = process_single_job(job)
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
            if job_succeeded else FileUploadJob.Status.FAILED
        )
        job.save(update_fields=["status"])


def process_single_job(job):
    try:
        streaming_records = json.load(job.file)
    except json.JSONDecodeError as e:
        log.error("Invalid JSON in job %s: %s" % (job.id, e))
        return False

    if not isinstance(streaming_records, list):
        log.error("Job %s: Expected list, got %s" % (job.id, type(streaming_records)))
        return False

    for record in streaming_records:
        process_single_record(record, job.user)

    return True


def process_single_record(record, user):
    if not isinstance(record, dict):
        log.debug("Invalid record type: %s" % type(record))
        return False

    ts = safe_strip(record.get("ts"))
    ms_played = record.get("ms_played")
    track_name = safe_strip(record.get("master_metadata_track_name"))
    artist_name = safe_strip(record.get("master_metadata_album_artist_name"))
    album_name = safe_strip(record.get("master_metadata_album_album_name"))
    spotify_track_uri = safe_strip(record.get("spotify_track_uri"))

    missing_fields = []
    if not ts: missing_fields.append("ts")
    if not ms_played: missing_fields.append("ms_played")
    if not track_name: missing_fields.append("track_name")
    if not artist_name: missing_fields.append("artist_name")
    if not album_name: missing_fields.append("album_name")
    if not spotify_track_uri: missing_fields.append("spotify_track_uri")

    if missing_fields:
        log.debug("Missing required fields: %s" % ", ".join(missing_fields))
        return False

    try:
        played_at = parse_datetime(ts)
        if played_at is None:
            log.debug("Invalid datetime format: %s" % ts)
            return False
    except ValueError as e:
        log.debug("Datetime parsing error for '%s': '%s'" % (ts, e))
        return False

    try:
        ms_played = int(ms_played)
        if ms_played < 0:
            log.debug("Negative ms_played: %d" % ms_played)
            return False
    except (ValueError, TypeError) as e:
        log.debug("Invalid ms_played '%s': %s" % (ms_played, e))
        return False

    try:
        artist, _ = Artist.objects.get_or_create(name=artist_name)
        album, _ = Album.objects.get_or_create(artist=artist, name=album_name)
        track, _ = Track.objects.get_or_create(
            spotify_track_uri=spotify_track_uri,
            defaults={
                "artist": artist,
                "album": album,
                "name": track_name
            }
        )

        StreamingHistory.objects.get_or_create(
            user=user,
            track=track,
            played_at=played_at,
            defaults={
                "ms_played": ms_played
            }
        )
    except Exception as e:
        log.error("Database error processing record: %s" % e)
        log.error(
            "Record data: track='%s', artist='%s', uri='%s'"
            % (track_name, artist_name, spotify_track_uri)
        )

    return True


def safe_strip(value) -> str | None:
    return value.strip() if isinstance(value, str) else None
