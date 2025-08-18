import pytest
from django.utils import timezone

from spotify_stats.analytics.models import StreamingHistory
from spotify_stats.analytics.service import StreamingAnalyticsService
from spotify_stats.catalog.models import TrackArtist, TrackAlbum


@pytest.fixture
def artist_1(artist_factory):
    return artist_factory()


@pytest.fixture
def artist_2(artist_factory):
    return artist_factory()


@pytest.fixture
def album_1(album_factory, artist_1):
    return album_factory(primary_artist=artist_1)


@pytest.fixture
def album_2(album_factory, artist_2):
    return album_factory(primary_artist=artist_2)


@pytest.fixture
def track_1(track_factory, artist_1, album_1):
    track = track_factory()
    TrackAlbum.objects.create(track=track, album=album_1)
    TrackArtist.objects.create(track=track, artist=artist_1)
    return track


@pytest.fixture
def track_2(track_factory, artist_2, album_2):
    track = track_factory(album=album_2)
    TrackAlbum.objects.create(track=track, album=album_2)
    TrackArtist.objects.create(track=track, artist=artist_2)
    return track


class TestStreamingAnalyticsService:

    def test_top_artists_returns_correct_data(self, user, artist_1, track_1):
        StreamingHistory.objects.create(
            user=user, track=track_1, ms_played=30000, played_at=timezone.now()
        )

        qs = StreamingHistory.objects.for_user(user)
        top_artists = StreamingAnalyticsService.top_artists(qs)
        assert top_artists.count() == 1

        artist = top_artists.get(id=artist_1.id)
        assert artist.total_ms_played == 30000
        assert artist.play_count == 1

    def test_top_albums_returns_correct_data(self, user, artist_1, album_1, track_1):
        StreamingHistory.objects.create(
            user=user, track=track_1, ms_played=30000, played_at=timezone.now()
        )

        qs = StreamingHistory.objects.for_user(user)
        top_albums = StreamingAnalyticsService.top_albums(qs)
        assert top_albums.count() == 1

        album = top_albums.get(id=album_1.id)
        assert album.total_ms_played == 30000
        assert album.play_count == 1

    def test_top_tracks_returns_correct_data(self, user, artist_1, album_1, track_1):
        StreamingHistory.objects.create(
            user=user, track=track_1, ms_played=30000, played_at=timezone.now()
        )

        qs = StreamingHistory.objects.for_user(user)
        top_tracks = StreamingAnalyticsService.top_tracks(qs)
        assert top_tracks.count() == 1

        track = top_tracks.get(id=track_1.id)
        assert track.total_ms_played == 30000
        assert track.play_count == 1
