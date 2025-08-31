import asyncio
import logging
import uuid

from celery import shared_task
from django.contrib.auth import get_user_model

from spotify_stats.analytics.services import (
    FileProcessingService,
    SpotifyAPIProcessor,
    SpotifyClient,
    SpotifyDBService,
    SpotifyAPIParser,
    StreamingDataValidator,
)
from spotify_stats.catalog.models import Track

log = logging.getLogger()

User = get_user_model()


@shared_task
def process_file_upload_jobs(job_ids: list[uuid.UUID]) -> None:
    db_service = SpotifyDBService()
    validator = StreamingDataValidator()
    service = FileProcessingService(db_service=db_service, validator=validator)
    service.process_file_upload_jobs(job_ids)

    track_ids = list(Track.objects.values_list("spotify_id", flat=True))
    enrich_spotify_metadata.delay(track_ids)


@shared_task(soft_time_limit=300, time_limit=360, ignore_result=True)
def enrich_spotify_metadata(track_ids: list):
    spotify_client = SpotifyClient()
    db_service = SpotifyDBService()
    parser = SpotifyAPIParser()

    service = SpotifyAPIProcessor(
        spotify_client=spotify_client,
        db_service=db_service,
        parser=parser,
    )
    asyncio.run(service.enrich_spotify_metadata(track_ids))
