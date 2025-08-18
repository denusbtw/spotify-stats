from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import (
    generics,
    response,
    status,
    permissions,
    filters,
)

from ..filters import (
    TopArtistsFilterSet,
    StreamingHistoryFilterSet,
    TopAlbumsFilterSet,
    TopTracksFilterSet,
    ListeningFilterSet,
)
from ..serializers import TopArtistsSerializer, TopAlbumsSerializer, TopTracksSerializer
from spotify_stats.analytics.models import StreamingHistory
from spotify_stats.analytics.service import StreamingAnalyticsService

User = get_user_model()


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

    def get_base_queryset(self) -> QuerySet[StreamingHistory]:
        return StreamingHistory.objects.for_user(self.request.user)

    def get_filtered_streaming_history(self) -> QuerySet[StreamingHistory]:
        base_queryset = self.get_base_queryset()
        filterset = StreamingHistoryFilterSet(self.request.query_params, base_queryset)
        return filterset.qs


class UserTopArtistsListView(BaseUserTopItemsListView):
    serializer_class = TopArtistsSerializer
    filterset_class = TopArtistsFilterSet
    search_fields = ["name"]

    def get_queryset(self):
        queryset = self.get_filtered_streaming_history()
        return StreamingAnalyticsService.top_artists(queryset)


class UserTopAlbumsListView(BaseUserTopItemsListView):
    serializer_class = TopAlbumsSerializer
    filterset_class = TopAlbumsFilterSet
    search_fields = ["name", "artists__name"]

    def get_queryset(self):
        queryset = self.get_filtered_streaming_history()
        return StreamingAnalyticsService.top_albums(queryset)


class UserTopTracksListView(BaseUserTopItemsListView):
    serializer_class = TopTracksSerializer
    filterset_class = TopTracksFilterSet
    search_fields = [
        "name",
        "artists__name",
        "albums__name",
    ]

    def get_queryset(self):
        queryset = self.get_filtered_streaming_history()
        return StreamingAnalyticsService.top_tracks(queryset)


class BaseUserListeningView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return StreamingHistory.objects.for_user(self.request.user)


class UserListeningStatsView(BaseUserListeningView):
    filter_backends = [DjangoFilterBackend]
    filterset_class = ListeningFilterSet

    def get(self, request, *args, **kwargs):
        streaming_history_qs = self.filter_queryset(self.get_queryset())
        stats = StreamingAnalyticsService.listening_stats(streaming_history_qs)
        return response.Response(stats)


class UserListeningActivityView(BaseUserListeningView):
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["tracks_played", "total_ms_played"]

    def get(self, request, *args, **kwargs):
        streaming_history_qs = self.get_filtered_streaming_history()

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

    def get_filtered_streaming_history(self) -> QuerySet[StreamingHistory]:
        streaming_history_qs = self.get_queryset()
        filterset = ListeningFilterSet(self.request.query_params, streaming_history_qs)
        return filterset.qs
