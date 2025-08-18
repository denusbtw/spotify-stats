import pytest

from spotify_stats.analytics.api.v1.serializers import TopAlbumsSerializer


@pytest.mark.django_db
class TestTopAlbumsSerializer:

    def test_expected_fields(self, album):
        album.total_ms_played = 0
        album.play_count = 0

        serializer = TopAlbumsSerializer(album)
        expected_fields = {
            "id",
            "artists",
            "name",
            "total_ms_played",
            "total_mins_played",
            "play_count",
        }
        assert set(serializer.data.keys()) == expected_fields

    def test_total_mins_played_correct(self, album):
        album.total_ms_played = 120_000
        album.play_count = 1

        serializer = TopAlbumsSerializer(album)
        assert serializer.data["total_mins_played"] == 2

    def test_artists_include_primary_artist_and_featured(
        self, album_factory, artist_factory, album_artist_factory
    ):
        primary_artist = artist_factory()
        featured_artist = artist_factory()

        album = album_factory(primary_artist=primary_artist)
        album_artist_factory(album=album, artist=featured_artist)

        album.total_ms_played = 0
        album.play_count = 0

        serializer = TopAlbumsSerializer(album)

        actual_artist_ids = [a["id"] for a in serializer.data["artists"]]
        expected_artist_ids = [str(primary_artist.id), str(featured_artist.id)]
        assert actual_artist_ids == expected_artist_ids
