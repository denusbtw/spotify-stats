from datetime import timedelta

import pytest
from django.utils import timezone

from conftest import listening_history_factory
from spotify_stats.analytics.models import ListeningHistory
from spotify_stats.analytics.service import StreamingAnalyticsService


@pytest.fixture
def user1(user_factory):
    return user_factory(username="user1")


@pytest.fixture
def user2(user_factory):
    return user_factory(username="user2")


@pytest.fixture
def artist1(artist_factory):
    return artist_factory(name="artist1")


@pytest.fixture
def artist2(artist_factory):
    return artist_factory(name="artist2")


@pytest.fixture
def artist3(artist_factory):
    return artist_factory(name="artist3")


@pytest.fixture
def album1(album_factory, artist1):
    return album_factory(name="album1", primary_artist=artist1)


@pytest.fixture
def album2(album_factory, artist2):
    return album_factory(name="album2", primary_artist=artist2)


@pytest.fixture
def album3(album_factory, artist3):
    return album_factory(name="album3", primary_artist=artist3)


@pytest.fixture
def track1(
    track_factory,
    track_artist_factory,
    artist1,
    album1,
):
    track = track_factory(name="track1", album=album1, spotify_id="1")
    track_artist_factory(track=track, artist=artist1)
    return track


@pytest.fixture
def track2(
    track_factory,
    track_artist_factory,
    artist1,
    album1,
):
    track = track_factory(name="track2", album=album1, spotify_id="2")
    track_artist_factory(track=track, artist=artist1)
    return track


@pytest.fixture
def track3(track_factory, track_artist_factory, artist2, album2):
    track = track_factory(name="track3", album=album2, spotify_id="3")
    track_artist_factory(track=track, artist=artist2)
    return track


@pytest.fixture
def track4(track_factory, track_artist_factory, artist3, album3):
    track = track_factory(name="track4", album=album3, spotify_uri="spotify:track:4")
    track_artist_factory(track=track, artist=artist3)
    return track


@pytest.fixture
def base_date():
    return timezone.now().replace(year=2024, month=12, day=28)


@pytest.mark.django_db
class TestStreamingAnalyticsService:

    class TestTopArtistsMethod:

        def test_single_artist_aggregation(
            self,
            user1,
            track1,
            track2,
            base_date,
            listening_history_factory,
            artist1,
        ):
            listening_history_factory(
                user=user1,
                track=track1,
                played_at=base_date,
                ms_played=180_000,
            )
            listening_history_factory(
                user=user1,
                track=track1,
                played_at=base_date + timedelta(hours=1),
                ms_played=120_000,
            )
            listening_history_factory(
                user=user1,
                track=track2,
                played_at=base_date + timedelta(hours=2),
                ms_played=240_000,
            )

            base_queryset = ListeningHistory.objects.for_user(user1)
            result = StreamingAnalyticsService.top_artists(base_queryset)

            assert result.count() == 1

            artist_stats = result.get(pk=artist1.pk)
            assert artist_stats.play_count == 3
            assert artist_stats.total_ms_played == 540_000  # 180000 + 120000 + 240000

        def test_multiple_artists_aggregation(
            self,
            track1,
            track2,
            track3,
            artist1,
            artist2,
            user1,
            listening_history_factory,
            base_date,
        ):
            listening_history_factory(
                user=user1,
                track=track1,
                played_at=base_date,
                ms_played=180_000,
            )

            listening_history_factory(
                user=user1,
                track=track2,
                played_at=base_date + timedelta(hours=1),
                ms_played=120_000,
            )

            listening_history_factory(
                user=user1,
                track=track3,
                played_at=base_date + timedelta(hours=2),
                ms_played=150_000,
            )
            listening_history_factory(
                user=user1,
                track=track3,
                played_at=base_date + timedelta(hours=3),
                ms_played=140_000,
            )
            listening_history_factory(
                user=user1,
                track=track3,
                played_at=base_date + timedelta(hours=4),
                ms_played=130_000,
            )

            base_queryset = ListeningHistory.objects.for_user(user1)
            result = StreamingAnalyticsService.top_artists(base_queryset)

            assert result.count() == 2

            artist1_ = result.get(pk=artist1.pk)
            assert artist1_.play_count == 2
            assert artist1_.total_ms_played == 300_000

            artist2_ = result.get(pk=artist2.pk)
            assert artist2_.play_count == 3
            assert artist2_.total_ms_played == 420_000

        def test_users_isolation(
            self,
            user1,
            user2,
            track1,
            listening_history_factory,
            base_date,
            artist1,
        ):
            listening_history_factory(
                user=user1,
                track=track1,
                played_at=base_date,
                ms_played=180_000,
            )

            for i in range(5):
                listening_history_factory(
                    user=user2,
                    track=track1,
                    played_at=base_date + timedelta(hours=i),
                    ms_played=200_000,
                )

            base_queryset = ListeningHistory.objects.for_user(user1)
            result = StreamingAnalyticsService.top_artists(base_queryset)

            artist1_ = result.get(pk=artist1.pk)
            assert artist1_.play_count == 1
            assert artist1_.total_ms_played == 180_000

        def test_date_filtering(
            self,
            user1,
            track1,
            base_date,
            listening_history_factory,
            artist1,
        ):
            old_date = base_date.replace(year=2023)
            for i in range(5):
                listening_history_factory(
                    user=user1,
                    track=track1,
                    played_at=old_date + timedelta(hours=i),
                    ms_played=200_000,
                )

            listening_history_factory(
                user=user1,
                track=track1,
                played_at=base_date,
                ms_played=100_000,
            )

            base_queryset = ListeningHistory.objects.for_user(user1).filter(
                played_at__year=2024
            )
            result = StreamingAnalyticsService.top_artists(base_queryset)

            artist1_ = result.get(pk=artist1.pk)
            assert artist1_.play_count == 1
            assert artist1_.total_ms_played == 100_000

        def test_empty_queryset(self):
            empty_queryset = ListeningHistory.objects.none()
            result = StreamingAnalyticsService.top_artists(empty_queryset)
            assert result.count() == 0

        def test_artists_without_listening_history(
            self,
            user1,
            track1,
            listening_history_factory,
            base_date,
            artist1,
        ):
            listening_history_factory(
                user=user1,
                track=track1,
                played_at=base_date,
                ms_played=180_000,
            )

            base_queryset = ListeningHistory.objects.for_user(user1)
            result = StreamingAnalyticsService.top_artists(base_queryset)

            assert result.count() == 1
            assert result.first().pk == artist1.pk

        def test_zero_duration_plays(
            self,
            user1,
            track1,
            base_date,
            listening_history_factory,
            artist1,
        ):
            listening_history_factory(
                user=user1,
                track=track1,
                played_at=base_date,
                ms_played=0,
            )
            listening_history_factory(
                user=user1,
                track=track1,
                played_at=base_date + timedelta(hours=1),
                ms_played=180_000,
            )

            base_queryset = ListeningHistory.objects.for_user(user1)
            result = StreamingAnalyticsService.top_artists(base_queryset)

            artist1_ = result.get(pk=artist1.pk)
            assert artist1_.play_count == 2
            assert artist1_.total_ms_played == 180_000

    class TestTopAlbumsMethod:

        def test_single_album_aggregation(
            self,
            user1,
            album1,
            track1,
            listening_history_factory,
            base_date,
        ):
            listening_history_factory(
                user=user1,
                track=track1,
                played_at=base_date + timedelta(hours=1),
                ms_played=120_000,
            )
            listening_history_factory(
                user=user1,
                track=track1,
                played_at=base_date + timedelta(hours=2),
                ms_played=240_000,
            )

            base_queryset = ListeningHistory.objects.for_user(user1)
            result = StreamingAnalyticsService.top_albums(base_queryset)

            assert result.count() == 1

            album = result.get(pk=album1.pk)
            assert album.play_count == 2
            assert album.total_ms_played == 360_000

        def test_multiple_albums_aggregation(
            self,
            listening_history_factory,
            user1,
            track2,
            track3,
            base_date,
            album1,
            album2,
        ):
            listening_history_factory(
                user=user1, track=track2, played_at=base_date, ms_played=180_000
            )
            listening_history_factory(
                user=user1,
                track=track2,
                played_at=base_date + timedelta(hours=1),
                ms_played=120_000,
            )

            for i in range(3):
                listening_history_factory(
                    user=user1,
                    track=track3,
                    played_at=base_date + timedelta(hours=i + 2),
                    ms_played=150_000,
                )

            base_queryset = ListeningHistory.objects.for_user(user1)
            result = StreamingAnalyticsService.top_albums(base_queryset)

            assert result.count() == 2

            album1_ = result.get(pk=album1.pk)
            assert album1_.play_count == 2
            assert album1_.total_ms_played == 300_000

            album2_ = result.get(pk=album2.pk)
            assert album2_.play_count == 3
            assert album2_.total_ms_played == 450_000

        def test_users_isolation(
            self,
            user1,
            user2,
            album2,
            track3,
            listening_history_factory,
            base_date,
        ):
            listening_history_factory(
                user=user1,
                track=track3,
                played_at=base_date,
                ms_played=180_000,
            )

            for i in range(3):
                listening_history_factory(
                    user=user2,
                    track=track3,
                    played_at=base_date + timedelta(hours=i),
                    ms_played=200_000,
                )

            base_queryset = ListeningHistory.objects.for_user(user1)
            result = StreamingAnalyticsService.top_albums(base_queryset)

            album = result.get(pk=album2.pk)
            assert album.play_count == 1
            assert album.total_ms_played == 180_000

        def test_date_filtering(
            self,
            user1,
            album2,
            track3,
            listening_history_factory,
            base_date,
        ):
            old_date = base_date.replace(year=2023)
            for i in range(3):
                listening_history_factory(
                    user=user1,
                    track=track3,
                    played_at=old_date + timedelta(hours=i),
                    ms_played=200_000,
                )

            listening_history_factory(
                user=user1,
                track=track3,
                played_at=base_date,
                ms_played=100_000,
            )

            base_queryset = ListeningHistory.objects.for_user(user1).filter(
                played_at__year=2024
            )
            result = StreamingAnalyticsService.top_albums(base_queryset)

            album = result.get(pk=album2.pk)
            assert album.play_count == 1
            assert album.total_ms_played == 100_000

        def test_empty_queryset(self):
            empty_queryset = ListeningHistory.objects.none()
            result = StreamingAnalyticsService.top_albums(empty_queryset)
            assert result.count() == 0

        def test_album_without_listening_history(
            self,
            user1,
            album2,
            album1,
            track3,
            listening_history_factory,
            base_date,
        ):
            listening_history_factory(
                user=user1,
                track=track3,
                played_at=base_date,
                ms_played=180_000,
            )

            base_queryset = ListeningHistory.objects.for_user(user1)
            result = StreamingAnalyticsService.top_albums(base_queryset)

            assert result.count() == 1
            assert result.first().pk == album2.pk

    class TestTopTracksMethod:

        def test_single_track_aggregation(
            self,
            user1,
            track1,
            base_date,
            listening_history_factory,
        ):
            listening_history_factory(
                user=user1, track=track1, played_at=base_date, ms_played=180_000
            )
            listening_history_factory(
                user=user1,
                track=track1,
                played_at=base_date + timedelta(hours=1),
                ms_played=120_000,
            )

            base_queryset = ListeningHistory.objects.for_user(user1)
            result = StreamingAnalyticsService.top_tracks(base_queryset)

            assert result.count() == 1

            track = result.get(pk=track1.pk)
            assert track.play_count == 2
            assert track.total_ms_played == 300_000

        def test_multiple_tracks_aggregation(
            self,
            user1,
            track1,
            track2,
            base_date,
            listening_history_factory,
        ):
            listening_history_factory(
                user=user1, track=track1, played_at=base_date, ms_played=200_000
            )
            listening_history_factory(
                user=user1,
                track=track2,
                played_at=base_date + timedelta(hours=1),
                ms_played=150_000,
            )
            listening_history_factory(
                user=user1,
                track=track2,
                played_at=base_date + timedelta(hours=2),
                ms_played=100_000,
            )

            base_queryset = ListeningHistory.objects.for_user(user1)
            result = StreamingAnalyticsService.top_tracks(base_queryset)

            assert result.count() == 2

            track1_ = result.get(pk=track1.pk)
            assert track1_.play_count == 1
            assert track1_.total_ms_played == 200_000

            track2_ = result.get(pk=track2.pk)
            assert track2_.play_count == 2
            assert track2_.total_ms_played == 250_000

        def test_users_isolation(
            self,
            user1,
            user2,
            track1,
            base_date,
            listening_history_factory,
        ):
            listening_history_factory(
                user=user1, track=track1, played_at=base_date, ms_played=200_000
            )

            for i in range(3):
                listening_history_factory(
                    user=user2,
                    track=track1,
                    played_at=base_date + timedelta(hours=i),
                    ms_played=300_000,
                )

            base_queryset = ListeningHistory.objects.for_user(user1)
            result = StreamingAnalyticsService.top_tracks(base_queryset)

            track1_ = result.get(pk=track1.pk)
            assert track1_.play_count == 1
            assert track1_.total_ms_played == 200_000

        def test_date_filtering(
            self,
            user1,
            track1,
            base_date,
            listening_history_factory,
        ):
            old_date = base_date.replace(year=2023)
            for i in range(2):
                listening_history_factory(
                    user=user1,
                    track=track1,
                    played_at=old_date + timedelta(hours=i),
                    ms_played=100_000,
                )

            listening_history_factory(
                user=user1,
                track=track1,
                played_at=base_date,
                ms_played=150_000,
            )

            base_queryset = ListeningHistory.objects.for_user(user1).filter(
                played_at__year=2024
            )
            result = StreamingAnalyticsService.top_tracks(base_queryset)

            track1_ = result.get(pk=track1.pk)
            assert track1_.play_count == 1
            assert track1_.total_ms_played == 150_000

        def test_empty_queryset(self):
            empty_queryset = ListeningHistory.objects.none()
            result = StreamingAnalyticsService.top_tracks(empty_queryset)
            assert result.count() == 0

        def test_tracks_without_listening_history(
            self,
            user1,
            track1,
            track2,
            base_date,
            listening_history_factory,
        ):
            listening_history_factory(
                user=user1, track=track1, played_at=base_date, ms_played=200_000
            )

            base_queryset = ListeningHistory.objects.for_user(user1)
            result = StreamingAnalyticsService.top_tracks(base_queryset)

            assert result.count() == 1
            assert result.first().pk == track1.pk

        def test_zero_duration_plays(
            self,
            user1,
            track1,
            base_date,
            listening_history_factory,
        ):
            listening_history_factory(
                user=user1, track=track1, played_at=base_date, ms_played=0
            )
            listening_history_factory(
                user=user1,
                track=track1,
                played_at=base_date + timedelta(hours=1),
                ms_played=180_000,
            )

            base_queryset = ListeningHistory.objects.for_user(user1)
            result = StreamingAnalyticsService.top_tracks(base_queryset)

            track1_ = result.get(pk=track1.pk)
            assert track1_.play_count == 2
            assert track1_.total_ms_played == 180_000

    class TestListeningStatsMethod:

        def test_basic_aggregation(
            self,
            user1,
            track1,
            track3,
            artist1,
            artist2,
            album1,
            album2,
            listening_history_factory,
            base_date,
        ):
            listening_history_factory(
                user=user1,
                track=track1,
                played_at=base_date,
                ms_played=180_000,
            )
            listening_history_factory(
                user=user1,
                track=track1,
                played_at=base_date + timedelta(hours=1),
                ms_played=120_000,
            )
            listening_history_factory(
                user=user1,
                track=track3,
                played_at=base_date + timedelta(hours=2),
                ms_played=240_000,
            )

            base_queryset = ListeningHistory.objects.for_user(user1)
            result = StreamingAnalyticsService.listening_stats(base_queryset)

            assert result["total_ms_played"] == 540_000
            assert result["total_mins_played"] == 9.0
            assert result["total_hours_played"] == 0.15
            assert result["total_tracks_played"] == 3
            assert result["unique_tracks"] == 2
            assert result["unique_artists"] == 2
            assert result["unique_albums"] == 2
            assert result["average_ms_played"] == 180_000
            assert result["average_mins_played"] == 3.0
            assert result["average_hours_played"] == 0.05
            assert result["first_play"] == base_date
            assert result["last_play"] == base_date + timedelta(hours=2)

        def test_empty_queryset(self):
            empty_queryset = ListeningHistory.objects.none()
            result = StreamingAnalyticsService.listening_stats(empty_queryset)

            assert result["total_ms_played"] == 0
            assert result["total_mins_played"] == 0
            assert result["total_hours_played"] == 0
            assert result["total_tracks_played"] == 0
            assert result["unique_tracks"] == 0
            assert result["unique_artists"] == 0
            assert result["unique_albums"] == 0
            assert result["average_ms_played"] == 0
            assert result["average_mins_played"] == 0
            assert result["average_hours_played"] == 0
            assert result["first_play"] is None
            assert result["last_play"] is None

        def test_zero_duration_plays(
            self,
            user1,
            track1,
            base_date,
            listening_history_factory,
        ):
            listening_history_factory(
                user=user1,
                track=track1,
                played_at=base_date,
                ms_played=0,
            )
            listening_history_factory(
                user=user1,
                track=track1,
                played_at=base_date + timedelta(minutes=10),
                ms_played=0,
            )

            base_queryset = ListeningHistory.objects.for_user(user1)
            result = StreamingAnalyticsService.listening_stats(base_queryset)

            assert result["total_ms_played"] == 0
            assert result["total_tracks_played"] == 2
            assert result["unique_tracks"] == 1
            assert result["average_ms_played"] == 0
            assert result["first_play"] == base_date
            assert result["last_play"] == base_date + timedelta(minutes=10)

        def test_multiple_users_isolation(
            self,
            user1,
            user2,
            track1,
            track2,
            base_date,
            listening_history_factory,
        ):
            listening_history_factory(
                user=user1,
                track=track1,
                played_at=base_date,
                ms_played=100_000,
            )
            listening_history_factory(
                user=user2,
                track=track2,
                played_at=base_date + timedelta(hours=1),
                ms_played=500_000,
            )

            base_queryset = ListeningHistory.objects.for_user(user1)
            result = StreamingAnalyticsService.listening_stats(base_queryset)

            assert result["total_ms_played"] == 100_000
            assert result["total_tracks_played"] == 1
            assert result["unique_tracks"] == 1

    class TestYearlyActivityMethod:

        def test_single_year_aggregation(
            self,
            user1,
            track1,
            base_date,
            listening_history_factory,
        ):
            listening_history_factory(
                user=user1, track=track1, played_at=base_date, ms_played=1_000_000
            )
            listening_history_factory(
                user=user1,
                track=track1,
                played_at=base_date + timedelta(hours=1),
                ms_played=500_000,
            )

            base_queryset = ListeningHistory.objects.for_user(user1)
            result = list(StreamingAnalyticsService.yearly_activity(base_queryset))

            assert len(result) == 1
            year_data = result[0]

            assert year_data["year"].year == base_date.year
            assert year_data["total_ms_played"] == 1_500_000
            assert year_data["total_mins_played"] == 25
            assert year_data["total_hours_played"] == 0.42
            assert year_data["tracks_played"] == 2

        def test_multiple_years_aggregation(
            self,
            user1,
            track1,
            base_date,
            listening_history_factory,
        ):

            old_date = base_date.replace(year=2023, month=6, day=1)
            listening_history_factory(
                user=user1, track=track1, played_at=old_date, ms_played=100_000
            )

            listening_history_factory(
                user=user1, track=track1, played_at=base_date, ms_played=200_000
            )

            base_queryset = ListeningHistory.objects.for_user(user1)
            result = list(StreamingAnalyticsService.yearly_activity(base_queryset))

            assert len(result) == 2
            assert [row["year"].year for row in result] == [2023, 2024]

            year2023 = result[0]
            assert year2023["total_ms_played"] == 100_000
            assert year2023["tracks_played"] == 1

            year2024 = result[1]
            assert year2024["total_ms_played"] == 200_000
            assert year2024["tracks_played"] == 1

        def test_users_isolation(
            self,
            user1,
            user2,
            track1,
            base_date,
            listening_history_factory,
        ):
            listening_history_factory(
                user=user1, track=track1, played_at=base_date, ms_played=100_000
            )
            listening_history_factory(
                user=user2, track=track1, played_at=base_date, ms_played=500_000
            )

            base_queryset = ListeningHistory.objects.for_user(user1)
            result = list(StreamingAnalyticsService.yearly_activity(base_queryset))

            assert len(result) == 1
            data = result[0]
            assert data["total_ms_played"] == 100_000
            assert data["tracks_played"] == 1

        def test_empty_queryset(self):
            empty_queryset = ListeningHistory.objects.none()
            result = list(StreamingAnalyticsService.yearly_activity(empty_queryset))
            assert result == []

    class TestMonthlyActivityMethod:

        def test_single_month_aggregation(
            self,
            user1,
            track1,
            base_date,
            listening_history_factory,
        ):
            listening_history_factory(
                user=user1, track=track1, played_at=base_date, ms_played=1_000_000
            )
            listening_history_factory(
                user=user1,
                track=track1,
                played_at=base_date + timedelta(hours=1),
                ms_played=500_000,
            )

            base_queryset = ListeningHistory.objects.for_user(user1)
            result = list(StreamingAnalyticsService.monthly_activity(base_queryset))

            assert len(result) == 1
            month_data = result[0]

            assert month_data["month"].month == base_date.month
            assert month_data["total_ms_played"] == 1_500_000
            assert month_data["total_mins_played"] == 25
            assert month_data["total_hours_played"] == 0.42
            assert month_data["tracks_played"] == 2

        def test_multiple_months_aggregation(
            self,
            user1,
            track1,
            base_date,
            listening_history_factory,
        ):

            old_date = base_date.replace(year=2023, month=11, day=1)
            listening_history_factory(
                user=user1, track=track1, played_at=old_date, ms_played=100_000
            )

            listening_history_factory(
                user=user1, track=track1, played_at=base_date, ms_played=200_000
            )

            base_queryset = ListeningHistory.objects.for_user(user1)
            result = list(StreamingAnalyticsService.monthly_activity(base_queryset))

            assert len(result) == 2
            assert [row["month"].month for row in result] == [11, 12]

            month11 = result[0]
            assert month11["total_ms_played"] == 100_000
            assert month11["tracks_played"] == 1

            month22 = result[1]
            assert month22["total_ms_played"] == 200_000
            assert month22["tracks_played"] == 1

        def test_users_isolation(
            self,
            user1,
            user2,
            track1,
            base_date,
            listening_history_factory,
        ):
            listening_history_factory(
                user=user1, track=track1, played_at=base_date, ms_played=100_000
            )
            listening_history_factory(
                user=user2, track=track1, played_at=base_date, ms_played=500_000
            )

            base_queryset = ListeningHistory.objects.for_user(user1)
            result = list(StreamingAnalyticsService.monthly_activity(base_queryset))

            assert len(result) == 1
            data = result[0]
            assert data["total_ms_played"] == 100_000
            assert data["tracks_played"] == 1

        def test_empty_queryset(self):
            empty_queryset = ListeningHistory.objects.none()
            result = list(StreamingAnalyticsService.monthly_activity(empty_queryset))
            assert result == []

    class TestDailyActivityMethod:

        def test_single_month_aggregation(
            self,
            user1,
            track1,
            base_date,
            listening_history_factory,
        ):
            listening_history_factory(
                user=user1, track=track1, played_at=base_date, ms_played=1_000_000
            )
            listening_history_factory(
                user=user1,
                track=track1,
                played_at=base_date + timedelta(hours=1),
                ms_played=500_000,
            )

            base_queryset = ListeningHistory.objects.for_user(user1)
            result = list(StreamingAnalyticsService.daily_activity(base_queryset))

            assert len(result) == 1
            month_data = result[0]

            assert month_data["date"].day == base_date.day
            assert month_data["total_ms_played"] == 1_500_000
            assert month_data["total_mins_played"] == 25
            assert month_data["total_hours_played"] == 0.42
            assert month_data["tracks_played"] == 2

        def test_multiple_months_aggregation(
            self,
            user1,
            track1,
            base_date,
            listening_history_factory,
        ):

            old_date = base_date.replace(year=2023, month=12, day=27)
            listening_history_factory(
                user=user1, track=track1, played_at=old_date, ms_played=100_000
            )

            listening_history_factory(
                user=user1, track=track1, played_at=base_date, ms_played=200_000
            )

            base_queryset = ListeningHistory.objects.for_user(user1)
            result = list(StreamingAnalyticsService.daily_activity(base_queryset))

            assert len(result) == 2
            assert [row["date"].day for row in result] == [27, 28]

            day27 = result[0]
            assert day27["total_ms_played"] == 100_000
            assert day27["tracks_played"] == 1

            day28 = result[1]
            assert day28["total_ms_played"] == 200_000
            assert day28["tracks_played"] == 1

        def test_users_isolation(
            self,
            user1,
            user2,
            track1,
            base_date,
            listening_history_factory,
        ):
            listening_history_factory(
                user=user1, track=track1, played_at=base_date, ms_played=100_000
            )
            listening_history_factory(
                user=user2, track=track1, played_at=base_date, ms_played=500_000
            )

            base_queryset = ListeningHistory.objects.for_user(user1)
            result = list(StreamingAnalyticsService.daily_activity(base_queryset))

            assert len(result) == 1
            data = result[0]
            assert data["total_ms_played"] == 100_000
            assert data["tracks_played"] == 1

        def test_empty_queryset(self):
            empty_queryset = ListeningHistory.objects.none()
            result = list(StreamingAnalyticsService.daily_activity(empty_queryset))
            assert result == []
