import pytest

from spotify_stats.catalog.models import Album, Artist, Track


@pytest.mark.django_db
class TestArtistFactory:

    def test_creates_valid_instance(self, artist_factory):
        artist_ = artist_factory()
        assert isinstance(artist_, Artist)
        assert isinstance(artist_.name, str)


@pytest.mark.django_db
class TestAlbumFactory:

    def test_creates_valid_instance(self, album_factory):
        album_ = album_factory()
        assert isinstance(album_, Album)
        assert isinstance(album_.artist, Artist)
        assert isinstance(album_.name, str)


@pytest.mark.django_db
class TestTrackFactory:

    def test_creates_valid_instance(self, track_factory):
        track_ = track_factory()
        assert isinstance(track_, Track)
        assert isinstance(track_.artist, Artist)
        assert isinstance(track_.album, Album)
        assert isinstance(track_.name, str)
        assert isinstance(track_.spotify_track_uri, str)

    def test_valid_spotify_track_uri(self, track_factory):
        track_ = track_factory()
        assert "spotify:track:test_track_" in track_.spotify_track_uri
