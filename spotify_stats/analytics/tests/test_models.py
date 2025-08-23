import pytest

from spotify_stats.analytics.models import ListeningHistory


@pytest.mark.django_db
class TestListeningHistoryQuerySet:

    def test_for_user_returns_correct_data(
        self, user_factory, listening_history_factory
    ):
        user_1 = user_factory()
        user_2 = user_factory()

        listening_history_factory.create_batch(2, user=user_1)
        listening_history_factory.create_batch(3, user=user_2)

        qs = ListeningHistory.objects.for_user(user=user_1)
        assert qs.count() == 2
