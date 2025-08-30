import logging
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from django.shortcuts import redirect
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import (
    generics,
    permissions,
    filters,
    response,
    status,
    mixins,
    parsers,
    views,
)
from rest_framework_simplejwt.tokens import RefreshToken

from spotify_stats.analytics.api.v1.filters import (
    ListeningHistoryFilterSet,
    TopArtistsFilterSet,
    TopAlbumsFilterSet,
    TopTracksFilterSet,
    ListeningStatsActivityFilterSet,
)
from spotify_stats.analytics.api.v1.serializers import (
    TopArtistsSerializer,
    TopAlbumsSerializer,
    TopTracksSerializer,
    UserFileUploadJobListSerializer,
    UserFileUploadJobCreateSerializer,
)
from spotify_stats.analytics.models import (
    ListeningHistory,
    FileUploadJob,
    SpotifyProfile,
)
from spotify_stats.analytics.services import (
    StreamingAnalyticsService,
    SpotifyAuthService,
)
from spotify_stats.analytics.tasks import process_file_upload_jobs

User = get_user_model()

log = logging.getLogger()


class BaseUserTopItemsListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = None
    filter_backends = [
        filters.OrderingFilter,
        filters.SearchFilter,
        DjangoFilterBackend,
    ]
    filterset_class = None
    search_fields = []
    ordering_fields = ["total_ms_played", "play_count"]
    ordering = "-play_count"

    def get_base_queryset(self) -> QuerySet[ListeningHistory]:
        return ListeningHistory.objects.for_user(self.request.user)

    def get_filtered_listening_history(self) -> QuerySet[ListeningHistory]:
        base_queryset = self.get_base_queryset()
        filterset = ListeningHistoryFilterSet(self.request.query_params, base_queryset)
        return filterset.qs


class UserTopArtistsListView(BaseUserTopItemsListView):
    serializer_class = TopArtistsSerializer
    filterset_class = TopArtistsFilterSet
    search_fields = ["name"]

    def get_queryset(self):
        queryset = self.get_filtered_listening_history()
        return StreamingAnalyticsService.top_artists(queryset)


class UserTopAlbumsListView(BaseUserTopItemsListView):
    serializer_class = TopAlbumsSerializer
    filterset_class = TopAlbumsFilterSet
    search_fields = ["name", "artists__name"]

    def get_queryset(self):
        queryset = self.get_filtered_listening_history()
        return StreamingAnalyticsService.top_albums(queryset)


class UserTopTracksListView(BaseUserTopItemsListView):
    serializer_class = TopTracksSerializer
    filterset_class = TopTracksFilterSet
    search_fields = [
        "name",
        "artists__name",
        "album__name",
    ]

    def get_queryset(self):
        queryset = self.get_filtered_listening_history()
        return StreamingAnalyticsService.top_tracks(queryset)


class BaseUserListeningView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ListeningHistory.objects.for_user(self.request.user)


class UserListeningStatsView(BaseUserListeningView):
    filter_backends = [DjangoFilterBackend]
    filterset_class = ListeningStatsActivityFilterSet

    def get(self, request, *args, **kwargs):
        streaming_history_qs = self.filter_queryset(self.get_queryset())
        stats = StreamingAnalyticsService.listening_stats(streaming_history_qs)
        return response.Response(stats)


class UserListeningActivityView(BaseUserListeningView):
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["tracks_played", "total_ms_played"]

    def get(self, request, *args, **kwargs):
        streaming_history_qs = self.get_filtered_listening_history()

        activity_type = request.query_params.get("type")
        method_name = self.get_method_name_by_activity_type(activity_type)
        if method_name is None:
            return response.Response(
                {
                    "detail": "Invalid activity type. Allowed: %s"
                    % ", ".join(self.get_allowed_activity_types_mapping().keys())
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        activity = getattr(StreamingAnalyticsService, method_name)(streaming_history_qs)
        filtered_activity = self.filter_queryset(activity)
        return response.Response(filtered_activity)

    def get_method_name_by_activity_type(self, activity_type: str) -> str | None:
        mapping = self.get_allowed_activity_types_mapping()
        return mapping.get(activity_type)

    def get_allowed_activity_types_mapping(self) -> dict[str, str]:
        return {
            "yearly": "yearly_activity",
            "monthly": "monthly_activity",
            "daily": "daily_activity",
        }

    def get_filtered_listening_history(self) -> QuerySet[ListeningHistory]:
        streaming_history_qs = self.get_queryset()
        filterset = ListeningStatsActivityFilterSet(
            self.request.query_params, streaming_history_qs
        )
        return filterset.qs


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


class UserFileUploadJobDetailView(generics.RetrieveDestroyAPIView):
    pass


class SpotifyLoginView(views.APIView):

    def get(self, request, *args, **kwargs):
        url = SpotifyAuthService.get_auth_url()
        return redirect(url)


class SpotifyCallbackView(views.APIView):

    def get(self, request, *args, **kwargs):
        code = request.query_params.get("code")

        if not code:
            log.error("Spotify callback: 'code' is missing.")
            return response.Response(
                {"error": "Authorization code not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_data = SpotifyAuthService.get_user_tokens(code)
        if not response_data:
            return response.Response(
                {"error": "Failed to get tokens from Spotify"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        access_token = response_data.get("access_token")
        refresh_token = response_data.get("refresh_token")
        expires_in = response_data.get("expires_in")
        scope = response_data.get("scope")

        if not all([access_token, refresh_token, expires_in, scope]):
            return response.Response(
                {"error": "Missing required token data from Spotify."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        user_data = SpotifyAuthService.get_user_info(access_token)
        if not user_data:
            return response.Response(
                {"error": "Failed to get user info from Spotify"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        spotify_id = user_data.get("id")
        email = user_data.get("email")

        user, _ = User.objects.get_or_create(
            email=email,
            defaults={
                "username": f"spotify_{spotify_id}",
            },
        )

        expires_at = timezone.now() + timedelta(seconds=expires_in)

        spotify_profile, _ = SpotifyProfile.objects.update_or_create(
            user=user,
            defaults={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "spotify_id": spotify_id,
                "scope": scope,
            },
        )

        refresh = RefreshToken.for_user(user)
        return response.Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_200_OK,
        )
