from rest_framework import serializers

from spotify_stats.catalog.models import Track, Album, Artist


class ArtistNestedSerializer(serializers.ModelSerializer):

    class Meta:
        model = Artist
        fields = ("id", "name", "cover_url")


class AlbumNestedSerializer(serializers.ModelSerializer):

    class Meta:
        model = Album
        fields = ("id", "name", "cover_url")


class BaseTopSerializer(serializers.Serializer):
    total_ms_played = serializers.IntegerField(read_only=True)
    total_mins_played = serializers.SerializerMethodField(read_only=True)
    play_count = serializers.IntegerField(read_only=True)

    def get_total_mins_played(self, obj):
        return round(obj.total_ms_played / 60_000, 2)


class TopArtistsSerializer(BaseTopSerializer, serializers.ModelSerializer):

    class Meta:
        model = Artist
        fields = ("id", "name", "total_ms_played", "total_mins_played", "play_count")
        read_only_fields = fields


class TopAlbumsSerializer(BaseTopSerializer, serializers.ModelSerializer):
    artists = serializers.ListSerializer(child=ArtistNestedSerializer())

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


class TopTracksSerializer(BaseTopSerializer, serializers.ModelSerializer):
    artists = serializers.ListSerializer(child=ArtistNestedSerializer())
    album = AlbumNestedSerializer()

    class Meta:
        model = Track
        fields = (
            "id",
            "artists",
            "album",
            "name",
            "spotify_id",
            "total_ms_played",
            "total_mins_played",
            "play_count",
        )
        read_only_fields = fields
