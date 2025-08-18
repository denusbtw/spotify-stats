from django.db import models

from spotify_stats.core.models import TimestampedModel, UUIDModel


class Artist(UUIDModel, TimestampedModel):
    name = models.CharField(max_length=255)


class Album(UUIDModel, TimestampedModel):
    name = models.CharField(max_length=255)
    primary_artist = models.ForeignKey(
        Artist, on_delete=models.RESTRICT, related_name="primary_albums"
    )
    artists = models.ManyToManyField(
        Artist, through="AlbumArtist", related_name="albums"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name", "primary_artist"],
                name="unique_album_name_primary_artist",
            )
        ]


class Track(UUIDModel, TimestampedModel):
    name = models.CharField(max_length=255)
    spotify_uri = models.CharField(max_length=50, unique=True)
    artists = models.ManyToManyField(
        Artist, through="TrackArtist", related_name="tracks"
    )
    albums = models.ManyToManyField(Album, through="TrackAlbum", related_name="tracks")


class AlbumArtist(UUIDModel, TimestampedModel):
    album = models.ForeignKey(Album, on_delete=models.CASCADE)
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["album", "artist"], name="unique_album_artist"
            )
        ]


class TrackArtist(UUIDModel, TimestampedModel):
    track = models.ForeignKey(Track, on_delete=models.CASCADE)
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["track", "artist"], name="unique_track_artist"
            )
        ]


class TrackAlbum(UUIDModel, TimestampedModel):
    track = models.ForeignKey(Track, on_delete=models.CASCADE)
    album = models.ForeignKey(Album, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["track", "album"], name="unique_track_album"
            )
        ]
