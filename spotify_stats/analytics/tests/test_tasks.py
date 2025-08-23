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
class TestProcessSingleRecord:

    @pytest.mark.parametrize(
        "record",
        [
            ("this is", "not record"),
            {"this is", "not record"},
            3,
            "this is not record",
            12.2,
            True,
        ],
    )
    def test_returns_false_if_record_is_not_dict(self, user, record):
        result = process_single_record(record, user)
        assert result is False
        assert len(connection.queries) == 0

    @pytest.mark.parametrize(
        "key_to_remove, is_required",
        [
            ("ts", True),
            ("ms_played", True),
            ("master_metadata_track_name", True),
            ("master_metadata_album_artist_name", True),
            ("master_metadata_album_album_name", True),
            ("spotify_track_uri", True),
            ("spotify_track_uri", True),
            ("platform", False),
        ],
    )
    def test_returns_false_if_missing_required_field(
        self, user, valid_record, key_to_remove, is_required
    ):
        record = valid_record.copy()
        del record[key_to_remove]

        result = process_single_record(record, user)
        assert result is False if is_required else True

        if is_required:
            assert len(connection.queries) == 0
        else:
            assert ListeningHistory.objects.count() == 1

    @pytest.mark.parametrize(
        "ts, is_valid",
        [
            ("2024-07-55T12:11:10Z", False),
            ("2024-07-25T33:11:10Z", False),
            ("2024-07T12:11:10Z", False),
            ("invalid_format", False),
            ("2024-07-55", False),
            ("2024-07-25T12:11:10Z", True),
        ],
    )
    def test_returns_false_if_invalid_ts(self, user, valid_record, ts, is_valid):
        record = valid_record.copy()
        record["ts"] = ts

        result = process_single_record(record, user)
        assert result == is_valid

        if is_valid:
            assert ListeningHistory.objects.count() == 1
        else:
            assert len(connection.queries) == 0

    @pytest.mark.parametrize(
        "ms_played, is_valid",
        [
            (-10, False),
            ("invalid", False),
            ([1, 2], False),
            ((3, 4), False),
            ({5: 6}, False),
            ({7, 8}, False),
            ("72", True),
            (35, True),
            (48.5, True),
        ],
    )
    def test_returns_false_if_invalid_ms_played(
        self, user, valid_record, ms_played, is_valid
    ):
        record = valid_record.copy()
        record["ms_played"] = ms_played

        result = process_single_record(record, user)
        assert result == is_valid

        if is_valid:
            assert ListeningHistory.objects.count() == 1
        else:
            assert len(connection.queries) == 0

    def test_success_case(self, user, valid_record):
        process_single_record(valid_record, user)

        assert Artist.objects.count() == 1
        assert Album.objects.count() == 1
        assert Track.objects.count() == 1
        assert ListeningHistory.objects.count() == 1

        artist = Artist.objects.first()
        assert artist.name == valid_record["master_metadata_album_artist_name"]

        album = Album.objects.first()
        assert album.primary_artist == artist
        assert album.name == valid_record["master_metadata_album_album_name"]

        assert AlbumArtist.objects.filter(album=album).count() == 0

        track = Track.objects.first()
        assert track.artists.contains(artist)
        assert track.albums.contains(album)
        assert track.name == valid_record["master_metadata_track_name"]
        assert track.spotify_uri == valid_record["spotify_track_uri"]

        history_obj = ListeningHistory.objects.first()
        assert history_obj.user == user
        assert history_obj.track == track
        assert history_obj.played_at == parse_datetime(valid_record["ts"])
        assert history_obj.ms_played == valid_record["ms_played"]

    def test_handles_duplicate_records(self, user, valid_record):
        process_single_record(valid_record, user)
        process_single_record(valid_record, user)

        assert ListeningHistory.objects.count() == 1


@pytest.mark.django_db
class TestSafeStrip:

    @pytest.mark.parametrize("value", [None, 123, 45.67, [1, 2, 3], (4, 5), {6: 7}])
    def test_none_if_not_str(self, value):
        assert safe_strip(value) is None

    def test_stripped_value_if_str(self):
        assert safe_strip("  va lue   ") == "va lue"
