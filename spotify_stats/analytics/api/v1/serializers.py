from rest_framework import serializers

from spotify_stats.catalog.api.v1.serializers import ArtistSerializer
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
    artists = serializers.SerializerMethodField(read_only=True)

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

    def get_artists(self, album):
        serialized_artists = []

        if album.primary_artist:
            serialized_artists.append(ArtistSerializer(album.primary_artist).data)

        serialized_artists += ArtistSerializer(
            [aa.artist for aa in album.album_artists.all()], many=True
        ).data
        return serialized_artists


class TopTracksSerializer(BaseTopSerializer):
    artists = serializers.ListSerializer(child=ArtistSerializer())
    album = serializers.CharField(source="album.name", read_only=True)

    class Meta:
        model = Track
        fields = (
            "id",
            "artists",
            "album",
            "name",
            "spotify_track_uri",
            "total_ms_played",
            "total_mins_played",
            "play_count",
        )
        read_only_fields = fields
