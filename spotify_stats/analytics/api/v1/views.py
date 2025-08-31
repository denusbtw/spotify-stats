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
from rest_framework.exceptions import APIException
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
        method_name = self._get_method_name_by_activity_type(activity_type)
        if method_name is None:
            return response.Response(
                {
                    "detail": "Invalid activity type. Allowed: %s"
                    % ", ".join(self._get_allowed_activity_types_mapping().keys())
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        activity = getattr(StreamingAnalyticsService, method_name)(streaming_history_qs)
        filtered_activity = self.filter_queryset(activity)
        return response.Response(filtered_activity)

    def _get_method_name_by_activity_type(self, activity_type: str) -> str | None:
        mapping = self._get_allowed_activity_types_mapping()
        return mapping.get(activity_type)

    def _get_allowed_activity_types_mapping(self) -> dict[str, str]:
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


class SpotifyLoginView(views.APIView):

    def get(self, request, *args, **kwargs):
        url = SpotifyAuthService.get_auth_url()
        return redirect(url)


class SpotifyServiceError(APIException):
    pass


class SpotifyCallbackView(views.APIView):

    def get(self, request, *args, **kwargs):
        code = request.query_params.get("code")
        if not code:
            log.error("Spotify callback: 'code' is missing.")
            return response.Response(
                {"error": "Authorization code not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            tokens = self._get_spotify_tokens(code)
            user_data = self._get_user_data(tokens.get("access_token"))
            user = self._get_or_create_user(user_data)
            self._update_or_create_spotify_profile(user, tokens, user_data.get("id"))
            jwt_tokens = self._generate_jwt_tokens(user)

            return response.Response(jwt_tokens, status=status.HTTP_200_OK)

        except SpotifyServiceError as e:
            return response.Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_spotify_tokens(self, code: str):
        tokens = SpotifyAuthService.get_user_tokens(code)
        if not tokens:
            raise SpotifyServiceError("Failed to get tokens from Spotify.")
        return tokens

    def _get_user_data(self, access_token: str):
        user_data = SpotifyAuthService.get_user_info(access_token)
        if not user_data:
            raise SpotifyServiceError("Failed to get user info from Spotify.")
        return user_data

    def _get_or_create_user(self, user_data: dict):
        email = user_data.get("email")
        display_name = user_data.get("display_name")
        if not all([display_name, email]):
            raise SpotifyServiceError("Missing user data from Spotify.")

        user, _ = User.objects.get_or_create(
            email=email, defaults={"username": display_name}
        )
        return user

    def _update_or_create_spotify_profile(self, user, tokens: dict, spotify_id: str):
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        expires_in = tokens.get("expires_in")
        scope = tokens.get("scope")

        if not all([access_token, refresh_token, expires_in, scope]):
            raise SpotifyServiceError("Missing required token data from Spotify.")

        expires_at = timezone.now() + timedelta(seconds=expires_in)
        SpotifyProfile.objects.update_or_create(
            user=user,
            defaults={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "spotify_id": spotify_id,
                "scope": scope,
            },
        )

    def _generate_jwt_tokens(self, user):
        refresh = RefreshToken.for_user(user)
        return {"access": str(refresh.access_token), "refresh": str(refresh)}
