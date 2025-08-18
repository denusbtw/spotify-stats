from rest_framework import serializers

from spotify_stats.catalog.api.v1.serializers import ArtistSerializer, AlbumSerializer
from spotify_stats.catalog.models import Track, Album, Artist


class BaseTopSerializer(serializers.ModelSerializer):
    total_ms_played = serializers.IntegerField(read_only=True)
    total_mins_played = serializers.SerializerMethodField(read_only=True)
    play_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = None

    def get_total_mins_played(self, obj):
        return round(obj.total_ms_played / 60_000, 2)


class TopArtistsSerializer(BaseTopSerializer):

    class Meta:
        model = Artist
        fields = ("id", "name", "total_ms_played", "total_mins_played", "play_count")
        read_only_fields = fields


class TopAlbumsSerializer(BaseTopSerializer):
    artists = serializers.ListSerializer(child=ArtistSerializer())

    class Meta:
        model = Album
        fields = (
            "id",
            "artists",
            "name",
            "total_ms_played",
            "total_mins_played",
            "play_count",
        )
        read_only_fields = fields


class TopTracksSerializer(BaseTopSerializer):
    artists = serializers.ListSerializer(child=ArtistSerializer())
    albums = serializers.ListSerializer(child=AlbumSerializer())

    class Meta:
        model = Track
        fields = (
            "id",
            "artists",
            "albums",
            "name",
            "spotify_uri",
            "total_ms_played",
            "total_mins_played",
            "play_count",
        )
        read_only_fields = fields
