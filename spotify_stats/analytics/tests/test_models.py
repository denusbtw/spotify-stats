import pytest

from spotify_stats.analytics.models import StreamingHistory


@pytest.mark.django_db
class TestStreamingHistoryQuerySet:

    def test_for_user_returns_correct_data(self, user_factory, streaming_history_factory):
        user_1 = user_factory()
        user_2 = user_factory()

        streaming_history_factory.create_batch(2, user=user_1)
        streaming_history_factory.create_batch(3, user=user_2)

        qs = StreamingHistory.objects.for_user(user=user_1)
        assert qs.count() == 2
