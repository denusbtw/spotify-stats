import pytest
from django.urls import reverse
from rest_framework import status


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
