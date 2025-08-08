import factory
from faker import Faker

from spotify_stats.catalog.models import Album, Artist, Track

fake = Faker()


class ArtistFactory(factory.django.DjangoModelFactory):
    name = factory.LazyFunction(lambda: fake.user_name())

    class Meta:
        model = Artist


class AlbumFactory(factory.django.DjangoModelFactory):
    artist = factory.SubFactory(ArtistFactory)
    name = factory.LazyFunction(lambda: fake.word())

    class Meta:
        model = Album


class TrackFactory(factory.django.DjangoModelFactory):
    artist = factory.SubFactory(ArtistFactory)
    album = factory.SubFactory(AlbumFactory)
    name = factory.LazyFunction(lambda: fake.word())
    spotify_track_uri = factory.Sequence(lambda n: f"spotify:track:test_track_{n}")

    class Meta:
        model = Track
