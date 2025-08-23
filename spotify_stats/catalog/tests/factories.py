import factory
from faker import Faker

from spotify_stats.catalog.models import (
    Album,
    Artist,
    Track,
    AlbumArtist,
    TrackArtist,
    TrackAlbum,
)

fake = Faker()


class ArtistFactory(factory.django.DjangoModelFactory):
    name = factory.LazyFunction(lambda: fake.user_name())

    class Meta:
        model = Artist


class AlbumFactory(factory.django.DjangoModelFactory):
    name = factory.LazyFunction(lambda: fake.word())
    primary_artist = factory.SubFactory(ArtistFactory)

    class Meta:
        model = Album


class AlbumArtistFactory(factory.django.DjangoModelFactory):
    album = factory.SubFactory(AlbumFactory)
    artist = factory.SubFactory(ArtistFactory)

    class Meta:
        model = AlbumArtist


class TrackFactory(factory.django.DjangoModelFactory):
    name = factory.LazyFunction(lambda: fake.word())
    spotify_id = factory.Sequence(lambda n: str(n + 1))

    class Meta:
        model = Track


class TrackArtistFactory(factory.django.DjangoModelFactory):
    track = factory.SubFactory(TrackFactory)
    artist = factory.SubFactory(ArtistFactory)

    class Meta:
        model = TrackArtist


class TrackAlbumFactory(factory.django.DjangoModelFactory):
    track = factory.SubFactory(TrackFactory)
    album = factory.SubFactory(AlbumFactory)

    class Meta:
        model = TrackAlbum
