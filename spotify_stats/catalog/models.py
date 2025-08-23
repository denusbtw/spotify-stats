from django.db import models

from spotify_stats.core.models import TimestampedModel, UUIDModel


class Artist(UUIDModel, TimestampedModel):
    name = models.CharField(max_length=255)


class Album(UUIDModel, TimestampedModel):
    name = models.CharField(max_length=255)
    artists = models.ManyToManyField(
        Artist, through="AlbumArtist", related_name="albums"
    )


class Track(UUIDModel, TimestampedModel):
    album = models.ForeignKey(
        "Album", on_delete=models.SET_NULL, related_name="tracks", null=True
    )
    name = models.CharField(max_length=255)
    spotify_id = models.CharField(max_length=62, unique=True)
    artists = models.ManyToManyField(
        Artist, through="TrackArtist", related_name="tracks"
    )


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
