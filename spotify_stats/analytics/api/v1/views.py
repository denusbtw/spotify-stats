from django.contrib.auth import get_user_model
from rest_framework import serializers, mixins, generics, parsers, response, status, permissions, filters

from spotify_stats.analytics.models import FileUploadJob
from spotify_stats.analytics.tasks import process_file_upload_jobs

User = get_user_model()


class FileUploadJobListSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileUploadJob
        fields = ("id", "file", "status", "created_at", "updated_at")


class FileUploadJobCreateSerializer(serializers.Serializer):
    files = serializers.ListField(
        child=serializers.FileField()
    )

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


class FileUploadJobAPIView(mixins.ListModelMixin, generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = FileUploadJobListSerializer
    filter_backends = [filters.OrderingFilter]
    parser_classes = [parsers.MultiPartParser]
    ordering = "-created_at"

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def get_queryset(self):
        return FileUploadJob.objects.filter(user=self.request.user)

    def post(self, request, *args, **kwargs):
        serializer = FileUploadJobCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        files = serializer.validated_data["files"]
        objs_to_create = []
        for file in files:
            user = self.request.user

            objs_to_create.append(
                FileUploadJob(
                    user=user,
                    file=file,
                    status=FileUploadJob.Status.PENDING
                )
            )

        jobs = FileUploadJob.objects.bulk_create(objs_to_create)

        job_ids = [job.id for job in jobs]
        process_file_upload_jobs.delay(job_ids)

        return response.Response(
            "Files accepted for processing."
            f" Job ids: {', '.join([str(job.id) for job in jobs]) }",
            status=status.HTTP_202_ACCEPTED
        )


#TODO:
class FileUploadJobDetailAPIView(generics.RetrieveDestroyAPIView):
    pass