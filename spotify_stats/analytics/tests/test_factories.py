import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from spotify_stats.analytics.models import StreamingHistory, FileUploadJob
from spotify_stats.catalog.models import Track

User = get_user_model()


@pytest.mark.django_db
class TestStreamingHistoryFactory:

    def test_creates_valid_instance(self, streaming_history_factory):
        st_hi = streaming_history_factory()
        assert isinstance(st_hi, StreamingHistory)
        assert isinstance(st_hi.user, User)
        assert isinstance(st_hi.track, Track)
        assert isinstance(st_hi.played_at, datetime.datetime)
        assert timezone.is_aware(st_hi.played_at)

        assert isinstance(st_hi.ms_played, int)


@pytest.mark.django_db
class TestFileUploadJobFactory:

    def test_creates_valid_instance(self, file_upload_job_factory):
        job = file_upload_job_factory()
        assert isinstance(job, FileUploadJob)
        assert isinstance(job.user, User)
        assert job.file is not None
        assert job.status in {s[0] for s in FileUploadJob.Status.choices}

    def test_pending_param(self, file_upload_job_factory):
        job = file_upload_job_factory(pending=True)
        assert job.status == FileUploadJob.Status.PENDING

    def test_processing_param(self, file_upload_job_factory):
        job = file_upload_job_factory(processing=True)
        assert job.status == FileUploadJob.Status.PROCESSING

    def test_completed_param(self, file_upload_job_factory):
        job = file_upload_job_factory(completed=True)
        assert job.status == FileUploadJob.Status.COMPLETED

    def test_failed_param(self, file_upload_job_factory):
        job = file_upload_job_factory(failed=True)
        assert job.status == FileUploadJob.Status.FAILED
