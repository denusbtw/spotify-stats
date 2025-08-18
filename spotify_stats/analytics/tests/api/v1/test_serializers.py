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
