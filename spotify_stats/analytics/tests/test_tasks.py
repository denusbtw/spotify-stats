import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.utils.dateparse import parse_datetime

from spotify_stats.analytics.tasks import (
    process_file_upload_jobs,
    process_single_job,
    process_single_record,
    safe_strip,
)
from spotify_stats.analytics.models import ListeningHistory, FileUploadJob
from spotify_stats.catalog.models import Artist, Album, Track, AlbumArtist


@pytest.fixture
def mock_process_single_job(mocker):
    return mocker.patch("spotify_stats.analytics.tasks.process_single_job")


@pytest.fixture
def valid_record():
    return {
        "ts": "2024-07-25T12:11:10Z",
        "platform": "ios",
        "ms_played": 5181,
        "conn_country": "UA",
        "ip_addr": "45.152.73.185",
        "master_metadata_track_name": "help_urself",
        "master_metadata_album_artist_name": "Ezekiel",
        "master_metadata_album_album_name": "help_urself",
        "spotify_track_uri": "spotify:track:1lethytswFEKkvfNIjdCC1",
        "episode_name": None,
        "episode_show_name": None,
        "spotify_episode_uri": None,
        "audiobook_title": None,
        "audiobook_uri": None,
        "audiobook_chapter_uri": None,
        "audiobook_chapter_title": None,
        "reason_start": "unknown",
        "reason_end": "endplay",
        "shuffle": False,
        "skipped": True,
        "offline": None,
        "offline_timestamp": None,
        "incognito_mode": False,
    }


@pytest.mark.django_db
class TestProcessFileUploadJobs:

    def test_marks_job_as_completed_if_success(
        self, file_upload_job_factory, mock_process_single_job
    ):
        mock_process_single_job.return_value = True
        mock_process_single_job.side_effect = None

        job = file_upload_job_factory(pending=True)
        process_file_upload_jobs(job_ids=[job.id])

        job.refresh_from_db()
        assert job.status == FileUploadJob.Status.COMPLETED

    def test_marks_job_as_failed_if_not_success(
        self, file_upload_job_factory, mock_process_single_job
    ):
        mock_process_single_job.return_value = False
        mock_process_single_job.side_effect = None

        job = file_upload_job_factory(pending=True)

        process_file_upload_jobs(job_ids=[job.id])

        job.refresh_from_db()
        assert job.status == FileUploadJob.Status.FAILED

    def test_marks_job_as_failed_if_exception(
        self, file_upload_job_factory, mock_process_single_job
    ):
        mock_process_single_job.side_effect = Exception

        job = file_upload_job_factory(pending=True)

        process_file_upload_jobs(job_ids=[job.id])

        job.refresh_from_db()
        assert job.status == FileUploadJob.Status.FAILED


@pytest.mark.django_db
class TestProcessSingleJob:

    @pytest.mark.parametrize(
        "content",
        [
            b"invalid json content",
            b'{"missing": "bracket"',
            b"not a json at all",
        ],
    )
    def test_returns_if_invalid_json_file(self, file_upload_job_factory, content):
        file = SimpleUploadedFile(
            "invalid.json", content, content_type="application/json"
        )
        job = file_upload_job_factory(file=file)

        process_single_job(job)

        assert ListeningHistory.objects.count() == 0

    def test_successfully_processes_if_valid_file(
        self, file_upload_job_factory, valid_record
    ):
        file = SimpleUploadedFile(
            "valid.json",
            json.dumps([valid_record]).encode("utf-8"),
            content_type="application/json",
        )
        job = file_upload_job_factory(file=file)

        process_single_job(job)

        assert ListeningHistory.objects.count() == 1


@pytest.mark.django_db
class TestSafeStrip:

    @pytest.mark.parametrize("value", [None, 123, 45.67, [1, 2, 3], (4, 5), {6: 7}])
    def test_none_if_not_str(self, value):
        assert safe_strip(value) is None

    def test_stripped_value_if_str(self):
        assert safe_strip("  va lue   ") == "va lue"
