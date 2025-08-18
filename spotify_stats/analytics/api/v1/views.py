from django.contrib.auth import get_user_model
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import (
    serializers,
    mixins,
    generics,
    parsers,
    response,
    status,
    permissions,
    filters,
)

from .filters import (
    ListeningFilterSet,
    StreamingHistoryFilterSet,
    TopArtistsFilterSet,
    TopAlbumsFilterSet,
    TopTracksFilterSet
)
from .serializers import (
    TopTracksSerializer,
    TopAlbumsSerializer,
    TopArtistsSerializer
)
from spotify_stats.analytics.models import FileUploadJob, StreamingHistory
from spotify_stats.analytics.tasks import process_file_upload_jobs
from spotify_stats.analytics.service import StreamingAnalyticsService

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


class TopArtistsAPIView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TopArtistsSerializer
    filter_backends = [filters.OrderingFilter, filters.SearchFilter, DjangoFilterBackend]
    filterset_class = TopArtistsFilterSet
    search_fields = ["name"]
    ordering_fields = ["total_ms_played", "play_count"]
    ordering = "-play_count"

    def get_queryset(self):
        base_queryset = StreamingHistory.objects.for_user(self.request.user)
        filterset = StreamingHistoryFilterSet(self.request.query_params, base_queryset)
        queryset = filterset.qs
        return StreamingAnalyticsService.top_artists(queryset)


class TopAlbumsAPIView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TopAlbumsSerializer
    filter_backends = [filters.OrderingFilter, filters.SearchFilter, DjangoFilterBackend]
    filterset_class = TopAlbumsFilterSet
    search_fields = ["name", "artist__name"]
    ordering_fields = ["total_ms_played", "play_count"]
    ordering = "-play_count"

    def get_queryset(self):
        base_queryset = StreamingHistory.objects.for_user(self.request.user)
        filterset = StreamingHistoryFilterSet(self.request.query_params, base_queryset)
        queryset = filterset.qs
        return StreamingAnalyticsService.top_albums(queryset)


class TopTracksAPIView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TopTracksSerializer
    filter_backends = [filters.OrderingFilter, filters.SearchFilter, DjangoFilterBackend]
    filterset_class = TopTracksFilterSet
    search_fields = ["name", "artist__name", "album__name", "album__artist__name"]
    ordering_fields = ["total_ms_played", "play_count"]
    ordering = "-play_count"

    def get_queryset(self):
        base_queryset = StreamingHistory.objects.for_user(self.request.user)
        filterset = StreamingHistoryFilterSet(self.request.query_params, base_queryset)
        queryset = filterset.qs
        return StreamingAnalyticsService.top_tracks(queryset)


class ListeningStatsAPIView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = ListeningFilterSet

    def get_queryset(self):
        return StreamingHistory.objects.for_user(self.request.user)

    def get(self, request, *args, **kwargs):
        filtered_queryset = self.filter_queryset(self.get_queryset())
        stats = StreamingAnalyticsService.listening_stats(filtered_queryset)
        return response.Response(stats)


class ListeningActivityAPIView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["tracks_played", "total_ms_played"]

    def get_queryset(self):
        return StreamingHistory.objects.for_user(self.request.user)

    def get(self, request, *args, **kwargs):
        filtered_streaming_history = ListeningFilterSet(
            self.request.query_params, self.get_queryset()
        )
        streaming_history_qs = filtered_streaming_history.qs

        activity_types_mapping = {
            "yearly": "yearly_activity",
            "monthly": "monthly_activity",
            "daily": "daily_activity",
        }

        activity_type = request.query_params.get("type")
        if activity_type not in activity_types_mapping:
            return response.Response(
                {"detail": f"Invalid activity type. Allowed: {list(activity_types_mapping.keys())}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        method_name = activity_types_mapping.get(activity_type)
        activity = getattr(StreamingAnalyticsService, method_name)(streaming_history_qs)

        filtered_activity = self.filter_queryset(activity)
        return response.Response(filtered_activity)
