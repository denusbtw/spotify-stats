from rest_framework import serializers

from spotify_stats.analytics.models import FileUploadJob
from spotify_stats.catalog.models import Artist, Album, Track


class UserFileUploadJobListSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileUploadJob
        fields = ("id", "file", "status", "created_at", "updated_at")


class UserFileUploadJobCreateSerializer(serializers.Serializer):
    files = serializers.ListField(child=serializers.FileField())

    def validate_files(self, files):
        ALLOWED_MIME_TYPES = ["application/json", "test/json"]
        MAX_FILE_SIZE_MB = 13
        MAX_FILE_SIZE_B = MAX_FILE_SIZE_MB * 1024 * 1024

        for file in files:
            if file.size > MAX_FILE_SIZE_B:
                raise serializers.ValidationError(
                    f"File {file.name} size exceeds {MAX_FILE_SIZE_MB}mb limit."
                )

            if file.content_type not in ALLOWED_MIME_TYPES:
                raise serializers.ValidationError(
                    f"File {file.name} mime type is not supported. "
                    f"Supported mime types: {','.join(ALLOWED_MIME_TYPES)}"
                )

        return files


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
        fields = (
            "id",
            "name",
            "total_ms_played",
            "total_mins_played",
            "play_count",
            "cover_url",
        )
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
