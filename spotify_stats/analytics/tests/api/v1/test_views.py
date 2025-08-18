import datetime

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status

from spotify_stats.analytics.models import FileUploadJob


@pytest.fixture
def list_url():
    return reverse("v1:me_upload_list")


@pytest.fixture
def mock_process_file_upload_jobs(mocker):
    return mocker.patch("spotify_stats.analytics.api.v1.views.process_file_upload_jobs")


@pytest.fixture
def top_artists_url():
    return reverse("v1:me_analytics_top_artists")


@pytest.fixture
def top_albums_url():
    return reverse("v1:me_analytics_top_albums")


@pytest.fixture
def top_tracks_url():
    return reverse("v1:me_analytics_top_tracks")


@pytest.fixture
def listening_stats_url():
    return reverse("v1:me_analytics_stats")


@pytest.fixture
def listening_activity_url():
    return reverse("v1:me_analytics_activity")


@pytest.mark.django_db
class TestFileUploadJobListCreateAPIView:

    @pytest.mark.parametrize(
        "method, expected_status",
        [
            ("get", status.HTTP_403_FORBIDDEN),
            ("post", status.HTTP_403_FORBIDDEN),
        ],
    )
    def test_anonymous_user(self, api_client, list_url, method, expected_status):
        response = getattr(api_client, method)(list_url)
        assert response.status_code == expected_status

    # GET
    def test_lists_only_request_user_jobs(
        self, api_client, list_url, user, file_upload_job_factory
    ):
        api_client.force_authenticate(user=user)

        user_job = file_upload_job_factory(user=user)
        file_upload_job_factory()

        response = api_client.get(list_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

        job = FileUploadJob.objects.get(id=response.data["results"][0]["id"])
        assert job.id == user_job.id

    # POST
    def test_error_if_file_size_exceeds_max_file_size(self, api_client, list_url, user):
        api_client.force_authenticate(user=user)

        large_file = SimpleUploadedFile(
            "large.json",
            b"x" * (15 * 1024 * 1024),  # 15 MB
            content_type="application/json",
        )

        data = {"files": [large_file]}
        response = api_client.post(list_url, data, format="multipart")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "size exceeds" in response.data["files"][0]

    def test_error_if_not_supported_file_content_type(
        self, api_client, list_url, user, fake
    ):
        api_client.force_authenticate(user=user)

        file = SimpleUploadedFile(
            "large.json",
            fake.json_file().encode("utf-8"),
            content_type="application/pdf",
        )

        data = {"files": [file]}
        response = api_client.post(list_url, data, format="multipart")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "mime type is not supported" in response.data["files"][0]

    def test_error_if_no_files_provided(self, api_client, list_url, user):
        api_client.force_authenticate(user=user)
        response = api_client.post(list_url, data={"files": []})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["files"][0].code == "required"

    def test_successful_single_file_upload(
        self, api_client, list_url, user, fake, mock_process_file_upload_jobs
    ):
        api_client.force_authenticate(user=user)

        file_content = fake.json_file().encode("utf-8")
        test_file = SimpleUploadedFile(
            "test.json", file_content, content_type="application/json"
        )
        data = {"files": [test_file]}

        response = api_client.post(list_url, data, format="multipart")
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert "Files accepted for processing" in response.data
        assert "Job ids:" in response.data

        assert FileUploadJob.objects.count() == 1
        job = FileUploadJob.objects.first()
        assert job.user == user
        assert job.file == test_file
        assert job.status == FileUploadJob.Status.PENDING

        mock_process_file_upload_jobs.delay.assert_called_once_with([job.id])

    def test_successful_multiple_files_upload(
        self, api_client, list_url, user, fake, mock_process_file_upload_jobs
    ):
        api_client.force_authenticate(user=user)

        files = []
        for i in range(2):
            files.append(
                SimpleUploadedFile(
                    f"test_{i}.json",
                    fake.json_file().encode("utf-8"),
                    content_type="application/json",
                ),
            )

        data = {"files": files}

        response = api_client.post(list_url, data, format="multipart")
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert FileUploadJob.objects.count() == 2

        job_ids = list(FileUploadJob.objects.values_list("id", flat=True))
        mock_process_file_upload_jobs.delay.assert_called_once_with(job_ids)


@pytest.mark.django_db
class TestTopArtistsAPIView:

    def test_anonymous(self, api_client, top_artists_url):
        response = api_client.get(top_artists_url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_authenticated(self, api_client, top_artists_url, user):
        api_client.force_authenticate(user=user)
        response = api_client.get(top_artists_url)
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestTopAlbumsAPIView:

    def test_anonymous(self, api_client, top_albums_url):
        response = api_client.get(top_albums_url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_authenticated(self, api_client, top_albums_url, user):
        api_client.force_authenticate(user=user)
        response = api_client.get(top_albums_url)
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestTopTracksAPIView:

    def test_anonymous(self, api_client, top_tracks_url):
        response = api_client.get(top_tracks_url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_authenticated(self, api_client, top_tracks_url, user):
        api_client.force_authenticate(user=user)
        response = api_client.get(top_tracks_url)
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestListeningStatsAPIView:

    def test_anonymous(self, api_client, listening_stats_url):
        response = api_client.get(listening_stats_url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_authenticated(self, api_client, listening_stats_url, user):
        api_client.force_authenticate(user=user)
        response = api_client.get(listening_stats_url)
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestListeningActivityAPIView:

    def test_anonymous(self, api_client, listening_activity_url):
        response = api_client.get(listening_activity_url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_authenticated(self, api_client, listening_activity_url, user):
        api_client.force_authenticate(user=user)
        response = api_client.get(listening_activity_url, {"type": "daily"})
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.parametrize(
        "activity_type, is_valid",
        [
            ("", False),
            ("daily", True),
            ("monthly", True),
            ("yearly", True),
            ("invalid", False),
        ],
    )
    def test_activity_types(
        self, api_client, listening_activity_url, user, activity_type, is_valid
    ):
        api_client.force_authenticate(user=user)
        response = api_client.get(listening_activity_url, {"type": activity_type})

        if is_valid:
            assert response.status_code == status.HTTP_200_OK
        else:
            assert response.status_code == status.HTTP_400_BAD_REQUEST
