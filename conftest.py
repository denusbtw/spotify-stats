import pytest
from faker import Faker
from faker_file.providers.txt_file import TxtFileProvider
from faker_file.providers.json_file import JsonFileProvider

from rest_framework.test import APIClient

from spotify_stats.analytics.tests.factories import (
    ListeningHistoryFactory,
    FileUploadJobFactory,
)
from spotify_stats.catalog.tests.factories import (
    AlbumFactory,
    ArtistFactory,
    TrackFactory,
    AlbumArtistFactory,
    TrackArtistFactory,
    TrackAlbumFactory,
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
def album_artist_factory():
    return AlbumArtistFactory


@pytest.fixture
def track_factory():
    return TrackFactory


@pytest.fixture
def track(db, track_factory):
    return track_factory()


@pytest.fixture
def track_artist_factory():
    return TrackArtistFactory


@pytest.fixture
def track_album_factory():
    return TrackAlbumFactory


@pytest.fixture
def listening_history_factory():
    return ListeningHistoryFactory


@pytest.fixture
def invalid_password():
    return "invalid"


@pytest.fixture
def valid_password():
    return "qwerty1337228"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture(scope="function", autouse=True)
def override_media_root(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture(scope="session")
def fake():
    faker_instance = Faker()

    COMMON_PROVIDERS = [TxtFileProvider, JsonFileProvider]

    for provider in COMMON_PROVIDERS:
        faker_instance.add_provider(provider)

    return faker_instance


@pytest.fixture
def file_upload_job_factory():
    return FileUploadJobFactory
