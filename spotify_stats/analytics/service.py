from typing import Any

from django.db.models import Sum, Count, FloatField, Avg, Min, Max, QuerySet
from django.db.models.functions import (
    Coalesce,
    Round,
    Cast,
    TruncYear,
    TruncMonth,
    TruncDate,
)

from spotify_stats.analytics.models import ListeningHistory
from spotify_stats.catalog.models import Artist, Album, Track


class StreamingAnalyticsService:

    @staticmethod
    def top_artists(base_queryset: QuerySet[ListeningHistory]) -> QuerySet[Artist]:
        return Artist.objects.filter(tracks__history__in=base_queryset).annotate(
            total_ms_played=Sum("tracks__history__ms_played"),
            play_count=Count("tracks__history__id"),
        )

    @staticmethod
    def top_albums(base_queryset: QuerySet[ListeningHistory]) -> QuerySet[Album]:
        return (
            Album.objects.filter(tracks__history__in=base_queryset)
            .select_related("primary_artist")
            .prefetch_related("artists")
            .annotate(
                total_ms_played=Sum("tracks__history__ms_played"),
                play_count=Count("tracks__history__id"),
            )
        )

    @staticmethod
    def top_tracks(base_queryset: QuerySet[ListeningHistory]) -> QuerySet[Track]:
        return (
            Track.objects.filter(history__in=base_queryset)
            .select_related("album")
            .prefetch_related("artists")
            .annotate(
                total_ms_played=Sum("history__ms_played"),
                play_count=Count("history__id"),
            )
        )

    @staticmethod
    def listening_stats(base_queryset: QuerySet[ListeningHistory]) -> dict[str, Any]:
        return base_queryset.aggregate(
            total_ms_played=Coalesce(Sum("ms_played"), 0),
            total_mins_played=Coalesce(
                Round(Cast(Sum("ms_played"), FloatField()) / 1000 / 60, 2),
                0,
                output_field=FloatField(),
            ),
            total_hours_played=Coalesce(
                Round(Cast(Sum("ms_played"), FloatField()) / 1000 / 60 / 60, 2),
                0,
                output_field=FloatField(),
            ),
            total_tracks_played=Count("id"),
            unique_tracks=Count("track_id", distinct=True),
            unique_artists=Count("track__artists__id", distinct=True),
            unique_albums=Count("track__album_id", distinct=True),
            average_ms_played=Coalesce(Avg("ms_played"), 0, output_field=FloatField()),
            average_mins_played=Coalesce(
                Round(Cast(Avg("ms_played"), FloatField()) / 1000 / 60, 2),
                0,
                output_field=FloatField(),
            ),
            average_hours_played=Coalesce(
                Round(Cast(Avg("ms_played"), FloatField()) / 1000 / 60 / 60, 2),
                0,
                output_field=FloatField(),
            ),
            first_play=Min("played_at"),
            last_play=Max("played_at"),
        )

    @staticmethod
    def yearly_activity(
        base_queryset: QuerySet[ListeningHistory],
    ):
        return (
            base_queryset.annotate(year=TruncYear("played_at"))
            .values("year")
            .annotate(
                total_ms_played=Sum("ms_played"),
                total_mins_played=Coalesce(
                    Round(Cast(Sum("ms_played"), FloatField()) / 1000 / 60, 2),
                    0,
                    output_field=FloatField(),
                ),
                total_hours_played=Coalesce(
                    Round(Cast(Sum("ms_played"), FloatField()) / 1000 / 60 / 60, 2),
                    0,
                    output_field=FloatField(),
                ),
                tracks_played=Count("id"),
            )
            .order_by("year")
        )

    @staticmethod
    def monthly_activity(base_queryset: QuerySet[ListeningHistory]):
        return (
            base_queryset.annotate(month=TruncMonth("played_at"))
            .values("month")
            .annotate(
                total_ms_played=Sum("ms_played"),
                total_mins_played=Coalesce(
                    Round(Cast(Sum("ms_played"), FloatField()) / 1000 / 60, 2),
                    0,
                    output_field=FloatField(),
                ),
                total_hours_played=Coalesce(
                    Round(Cast(Sum("ms_played"), FloatField()) / 1000 / 60 / 60, 2),
                    0,
                    output_field=FloatField(),
                ),
                tracks_played=Count("id"),
            )
            .order_by("month")
        )

    @staticmethod
    def daily_activity(base_queryset: QuerySet[ListeningHistory]):
        return (
            base_queryset.annotate(date=TruncDate("played_at"))
            .values("date")
            .annotate(
                total_ms_played=Sum("ms_played"),
                total_mins_played=Coalesce(
                    Round(Cast(Sum("ms_played"), FloatField()) / 1000 / 60, 2),
                    0,
                    output_field=FloatField(),
                ),
                total_hours_played=Coalesce(
                    Round(Cast(Sum("ms_played"), FloatField()) / 1000 / 60 / 60, 2),
                    0,
                    output_field=FloatField(),
                ),
                tracks_played=Count("id"),
            )
            .order_by("date")
        )
