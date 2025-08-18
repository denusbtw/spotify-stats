from django.contrib.auth import get_user_model
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


class TopArtistsAPIView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TopArtistsSerializer
    filter_backends = [
        filters.OrderingFilter,
        filters.SearchFilter,
        DjangoFilterBackend,
    ]
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
    filter_backends = [
        filters.OrderingFilter,
        filters.SearchFilter,
        DjangoFilterBackend,
    ]
    filterset_class = TopAlbumsFilterSet
    search_fields = ["name", "artists__name"]
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
    filter_backends = [
        filters.OrderingFilter,
        filters.SearchFilter,
        DjangoFilterBackend,
    ]
    filterset_class = TopTracksFilterSet
    search_fields = [
        "name",
        "artists__name",
        "albums__name",
    ]
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
                {
                    "detail": f"Invalid activity type. Allowed: {list(activity_types_mapping.keys())}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        method_name = activity_types_mapping.get(activity_type)
        activity = getattr(StreamingAnalyticsService, method_name)(streaming_history_qs)

        filtered_activity = self.filter_queryset(activity)
        return response.Response(filtered_activity)
