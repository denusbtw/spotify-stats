from rest_framework import serializers

from spotify_stats.analytics.models import FileUploadJob


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
