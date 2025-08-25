import json
import logging
import uuid

from celery import shared_task
from django.utils.dateparse import parse_datetime
from django.contrib.auth import get_user_model

from spotify_stats.analytics.models import FileUploadJob, ListeningHistory
from spotify_stats.analytics.spotify_client import SpotifyClient
from spotify_stats.catalog.models import Track, Album, Artist, AlbumArtist, TrackArtist

log = logging.getLogger()

User = get_user_model()


@shared_task(soft_time_limit=300, time_limit=360)
def process_file_upload_jobs(job_ids: list[uuid.UUID]) -> None:
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
            if job_succeeded
            else FileUploadJob.Status.FAILED
        )
        job.save(update_fields=["status"])


def process_single_job(job: FileUploadJob) -> bool:
    try:
        streaming_records = json.load(job.file)
    except json.JSONDecodeError as e:
        log.error("Invalid JSON in job %s: %s" % (job.id, e))
        return False

    if not isinstance(streaming_records, list):
        log.error("Job %s: Expected list, got %s" % (job.id, type(streaming_records)))
        return False

    batch_size = 500

    for i in range(0, len(streaming_records), batch_size):
        batch = streaming_records[i : i + batch_size]

        tracks_to_create = []
        listening_history_data = []

        existing_tracks_spotify_ids = set(
            Track.objects.values_list("spotify_id", flat=True)
        )

        for record in batch:
            if not isinstance(record, dict):
                log.warning("Invalid record type: %s" % type(record))
                continue

            ts = safe_strip(record.get("ts"))
            ms_played = record.get("ms_played")
            track_name = safe_strip(record.get("master_metadata_track_name"))
            spotify_track_uri = safe_strip(record.get("spotify_track_uri"))

            missing_fields = []
            if not ts:
                missing_fields.append("ts")
            if not ms_played:
                missing_fields.append("ms_played")
            if not track_name:
                missing_fields.append("track_name")
            if not spotify_track_uri:
                missing_fields.append("spotify_track_uri")

            if missing_fields:
                log.warning("Missing required fields: %s" % ", ".join(missing_fields))
                continue

            try:
                played_at = parse_datetime(ts)
                if played_at is None:
                    log.warning("Invalid datetime format: %s" % ts)
                    continue
            except ValueError as e:
                log.warning("Datetime parsing error for '%s': '%s'" % (ts, e))
                continue

            try:
                ms_played = int(ms_played)
                if ms_played < 0:
                    log.warning("Negative ms_played: %d" % ms_played)
                    continue
            except (ValueError, TypeError) as e:
                log.warning("Invalid ms_played '%s': %s" % (ms_played, e))
                continue

            spotify_id = spotify_track_uri.split(":")[-1]
            if spotify_id not in existing_tracks_spotify_ids:
                tracks_to_create.append(
                    Track(
                        spotify_id=spotify_id,
                        name=track_name,
                    )
                )
                existing_tracks_spotify_ids.add(spotify_id)

            listening_history_data.append(
                {
                    "spotify_id": spotify_id,
                    "played_at": played_at,
                    "ms_played": ms_played,
                }
            )

        Track.objects.bulk_create(tracks_to_create, ignore_conflicts=True)

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
            listening_history_to_create, ignore_conflicts=True
        )

        log.info(
            "Created %d listening history records." % len(listening_history_to_create)
        )

    return True


def safe_strip(value: str) -> str | None:
    return value.strip() if isinstance(value, str) else None


@shared_task
def enrich_spotify_metadata(track_ids: list):
    spotify_client = SpotifyClient()

    n = 50
    track_ids_batch = track_ids[:n]
    while track_ids_batch:
        tracks = Track.objects.filter(id__in=track_ids_batch)
        spotify_ids = list(tracks.values_list("spotify_id", flat=True))

        tracks_data = spotify_client.get_tracks(spotify_ids)
        tracks_data = {track["id"]: track for track in tracks_data["tracks"]}

        for track in tracks:
            track_data = tracks_data.get(track.spotify_id)
            album_data = track_data["album"]

            album, _ = Album.objects.get_or_create(
                spotify_id=album_data["id"],
                defaults={
                    "name": album_data["name"],
                    "cover_url": (
                        album_data["images"][0]["url"] if album_data["images"] else ""
                    ),
                },
            )

            track.name = track_data["name"]
            track.album = album

            for artist_data in album_data["artists"]:
                artist, _ = Artist.objects.get_or_create(
                    spotify_id=artist_data["id"],
                    defaults={
                        "name": artist_data["name"],
                    },
                )
                AlbumArtist.objects.get_or_create(album=album, artist=artist)

            for artist_data in track_data["artists"]:
                artist, _ = Artist.objects.get_or_create(
                    spotify_id=artist_data["id"],
                    defaults={
                        "name": artist_data["name"],
                    },
                )
                TrackArtist.objects.get_or_create(track=track, artist=artist)

                artist_response = spotify_client.get_artist(artist_data["id"])
                artist.cover_url = (
                    artist_response["images"][0]["url"]
                    if artist_response["images"]
                    else ""
                )
                artist.save(update_fields=["cover_url"])

        Track.objects.bulk_update(tracks, fields=["name", "album"])

        n += 50
        track_ids_batch = track_ids[n - 50 : n]
