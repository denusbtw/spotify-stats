import json

import factory
from django.core.files.uploadedfile import SimpleUploadedFile
from faker import Faker
from django.utils import timezone
from faker_file.providers.json_file import JsonFileProvider

from spotify_stats.analytics.models import ListeningHistory, FileUploadJob
from spotify_stats.catalog.tests.factories import TrackFactory
from spotify_stats.users.tests.factories import UserFactory

fake = Faker()

fake.add_provider(JsonFileProvider)


class ListeningHistoryFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    track = factory.SubFactory(TrackFactory)
    played_at = factory.LazyFunction(
        lambda: timezone.make_aware(fake.date_time_this_decade())
    )
    ms_played = factory.LazyFunction(lambda: fake.random_int(100_000, 400_000, 1))

    class Meta:
        model = ListeningHistory


class FileUploadJobFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    file = factory.LazyFunction(
        lambda: SimpleUploadedFile(
            "test.json",
            json.dumps({"test": "data"}).encode(),
            content_type="application/json",
        )
    )
    status = factory.LazyFunction(
        lambda: fake.random_element([s[0] for s in FileUploadJob.Status.choices])
    )

    class Meta:
        model = FileUploadJob

    class Params:
        pending = factory.Trait(status=FileUploadJob.Status.PENDING)
        processing = factory.Trait(status=FileUploadJob.Status.PROCESSING)
        completed = factory.Trait(status=FileUploadJob.Status.COMPLETED)
        failed = factory.Trait(status=FileUploadJob.Status.FAILED)
