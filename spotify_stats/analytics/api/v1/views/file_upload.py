from rest_framework import (
    mixins,
    generics,
    permissions,
    filters,
    parsers,
    response,
    status,
)

from spotify_stats.analytics.models import FileUploadJob
from ..serializers import FileUploadJobListSerializer, FileUploadJobCreateSerializer
from spotify_stats.analytics.tasks import process_file_upload_jobs


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
                FileUploadJob(user=user, file=file, status=FileUploadJob.Status.PENDING)
            )

        jobs = FileUploadJob.objects.bulk_create(objs_to_create)

        job_ids = [job.id for job in jobs]
        process_file_upload_jobs.delay(job_ids)

        return response.Response(
            "Files accepted for processing."
            f" Job ids: {', '.join([str(job.id) for job in jobs]) }",
            status=status.HTTP_202_ACCEPTED,
        )


# TODO:
class FileUploadJobDetailAPIView(generics.RetrieveDestroyAPIView):
    pass
