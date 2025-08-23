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
        assert isinstance(album_.name, str)


@pytest.mark.django_db
class TestAlbumArtistFactory:

    def test_creates_valid_instance(self, album_artist_factory):
        album_artist = album_artist_factory()
        assert isinstance(album_artist.album, Album)
        assert isinstance(album_artist.artist, Artist)


@pytest.mark.django_db
class TestTrackFactory:

    def test_creates_valid_instance(self, track_factory):
        track_ = track_factory()
        assert isinstance(track_, Track)
        assert isinstance(track_.name, str)
        assert isinstance(track_.spotify_id, str)


@pytest.mark.django_db
class TestTrackArtistFactory:

    def test_creates_valid_instance(self, track_artist_factory):
        track_artist = track_artist_factory()
        assert isinstance(track_artist.track, Track)
        assert isinstance(track_artist.artist, Artist)


@pytest.mark.django_db
class TestTrackAlbumFactory:

    def test_creates_valid_instance(self, track_album_factory):
        track_album = track_album_factory()
        assert isinstance(track_album.track, Track)
        assert isinstance(track_album.album, Album)
