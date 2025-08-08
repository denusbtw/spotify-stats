import pytest

from rest_framework.test import APIClient

from spotify_stats.analytics.factories import StreamingHistoryFactory
from spotify_stats.catalog.tests.factories import (
    AlbumFactory,
    ArtistFactory,
    TrackFactory,
)
from spotify_stats.users.tests.factories import UserFactory


@pytest.fixture
def user_factory():
    return UserFactory


@pytest.fixture
def user(db, user_factory):
    return user_factory()


@pytest.fixture
def artist_factory():
    return ArtistFactory


@pytest.fixture
def artist(db, artist_factory):
    return artist_factory()


@pytest.fixture
def album_factory():
    return AlbumFactory


@pytest.fixture
def album(db, album_factory):
    return album_factory()


@pytest.fixture
def track_factory():
    return TrackFactory


@pytest.fixture
def track(db, track_factory):
    return track_factory()


@pytest.fixture
def streaming_history_factory():
    return StreamingHistoryFactory


@pytest.fixture
def invalid_password():
    return "invalid"


@pytest.fixture
def valid_password():
    return "qwerty1337228"


@pytest.fixture
def api_client():
    return APIClient()
