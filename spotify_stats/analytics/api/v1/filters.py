from django_filters import rest_framework as filters

from spotify_stats.analytics.models import StreamingHistory
from spotify_stats.catalog.models import Track, Album, Artist


class BaseStreamingHistoryFilterSet(filters.FilterSet):
    played_at = filters.DateFromToRangeFilter()
    year = filters.NumberFilter(field_name="played_at", lookup_expr="year")
    month = filters.NumberFilter(field_name="played_at", lookup_expr="month")
    day = filters.NumberFilter(field_name="played_at", lookup_expr="day")
    hour = filters.NumberFilter(field_name="played_at", lookup_expr="hour")
    week_day = filters.NumberFilter(field_name="played_at", lookup_expr="week_day")
    ms_played_min = filters.NumberFilter(field_name="ms_played", lookup_expr="gte")
    ms_played_max = filters.NumberFilter(field_name="ms_played", lookup_expr="lte")

    class Meta:
        model = StreamingHistory
        fields = []


class StreamingHistoryFilterSet(BaseStreamingHistoryFilterSet):

    class Meta:
        model = StreamingHistory
        fields = [
            "played_at",
            "year",
            "month",
            "day",
            "hour",
            "week_day",
            "ms_played_min",
            "ms_played_max",
        ]


class ListeningFilterSet(BaseStreamingHistoryFilterSet):
    artist = filters.CharFilter(
        field_name="track__artists__name", lookup_expr="icontains"
    )
    album = filters.CharFilter(
        field_name="track__albums__name", lookup_expr="icontains"
    )
    track = filters.CharFilter(field_name="track", lookup_expr="icontains")

    class Meta:
        model = StreamingHistory
        fields = [
            "played_at",
            "year",
            "month",
            "day",
            "hour",
            "week_day",
            "artist",
            "album",
            "track",
            "ms_played_min",
            "ms_played_max",
        ]


class BaseTopItemsFilterSet(filters.FilterSet):
    total_ms_played_min = filters.NumberFilter(
        field_name="total_ms_played", lookup_expr="gte"
    )
    total_ms_played_max = filters.NumberFilter(
        field_name="total_ms_played", lookup_expr="lte"
    )

    play_count_min = filters.NumberFilter(field_name="play_count", lookup_expr="gte")
    play_count_max = filters.NumberFilter(field_name="play_count", lookup_expr="lte")


class TopArtistsFilterSet(BaseTopItemsFilterSet):

    class Meta:
        model = Artist
        fields = [
            "total_ms_played_min",
            "total_ms_played_max",
            "play_count_min",
            "play_count_max",
        ]


class TopTracksFilterSet(BaseTopItemsFilterSet):

    class Meta:
        model = Track
        fields = [
            "total_ms_played_min",
            "total_ms_played_max",
            "play_count_min",
            "play_count_max",
        ]


class TopAlbumsFilterSet(BaseTopItemsFilterSet):

    class Meta:
        model = Album
        fields = [
            "total_ms_played_min",
            "total_ms_played_max",
            "play_count_min",
            "play_count_max",
        ]
