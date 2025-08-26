import logging
import uuid

from celery import shared_task
from django.contrib.auth import get_user_model

from spotify_stats.analytics.services import FileProcessingService, SpotifyProcessor
from spotify_stats.catalog.models import Track

log = logging.getLogger()

User = get_user_model()


@shared_task
def process_file_upload_jobs(job_ids: list[uuid.UUID]) -> None:
    service = FileProcessingService()
    service.process_file_upload_jobs(job_ids)

    track_ids = list(Track.objects.values_list("spotify_id", flat=True))
    enrich_spotify_metadata.delay(track_ids)


@shared_task(soft_time_limit=300, time_limit=360)
def enrich_spotify_metadata(track_ids: list):
    service = SpotifyProcessor()
    service.enrich_spotify_metadata(track_ids)
