import factory
from django.utils import timezone
from faker import Faker

from spotify_stats.analytics.models import StreamingHistory
from spotify_stats.catalog.tests.factories import TrackFactory
from spotify_stats.users.tests.factories import UserFactory

fake = Faker()


class StreamingHistoryFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    track = factory.SubFactory(TrackFactory)
    played_at = factory.LazyFunction(
        lambda: timezone.make_aware(fake.date_time_this_decade())
    )
    ms_played = factory.LazyFunction(lambda: fake.random_int(100_000, 400_000, 1))

    class Meta:
        model = StreamingHistory
