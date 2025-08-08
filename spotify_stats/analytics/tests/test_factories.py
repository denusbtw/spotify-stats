import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from spotify_stats.analytics.models import StreamingHistory
from spotify_stats.catalog.models import Track

User = get_user_model()


@pytest.mark.django_db
class TestStreamingHistoryFactory:

    def test_creates_valid_instance(self, streaming_history_factory):
        st_hi = streaming_history_factory()
        assert isinstance(st_hi, StreamingHistory)
        assert isinstance(st_hi.user, User)
        assert isinstance(st_hi.track, Track)
        assert isinstance(st_hi.played_at, datetime.datetime)
        assert timezone.is_aware(st_hi.played_at)

        assert isinstance(st_hi.ms_played, int)
