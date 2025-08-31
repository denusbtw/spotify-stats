from rest_framework import (
    mixins,
    generics,
    permissions,
    filters,
    parsers,
    response,
    status,
)

from spotify_stats.analytics.api.v1.serializers import (
    UserFileUploadJobListSerializer,
    UserFileUploadJobCreateSerializer,
)
from spotify_stats.analytics.models import FileUploadJob
from spotify_stats.analytics.tasks import process_file_upload_jobs


class UserFileUploadJobListCreateView(mixins.ListModelMixin, generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserFileUploadJobListSerializer
    filter_backends = [filters.OrderingFilter]
    parser_classes = [parsers.MultiPartParser]
    ordering = "-created_at"

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def get_queryset(self):
        return FileUploadJob.objects.filter(user=self.request.user)

    def post(self, request, *args, **kwargs):
        serializer = UserFileUploadJobCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        files = serializer.validated_data["files"]
        jobs = [
            FileUploadJob(
                user=request.user, file=file, status=FileUploadJob.Status.PENDING
            )
            for file in files
        ]

        created_jobs = FileUploadJob.objects.bulk_create(jobs)
        job_ids = [job.id for job in created_jobs]
        process_file_upload_jobs.delay(job_ids)

        return response.Response(
            "Files accepted for processing."
            f" Job ids: {', '.join([str(job.id) for job in jobs]) }",
            status=status.HTTP_202_ACCEPTED,
        )


class UserFileUploadJobDetailView(generics.RetrieveDestroyAPIView):
    pass
