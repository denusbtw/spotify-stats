from django.db import models

from spotify_stats.core.models import TimestampedModel, UUIDModel


class Artist(UUIDModel, TimestampedModel):
    name = models.CharField(max_length=255)


class Album(UUIDModel, TimestampedModel):
    name = models.CharField(max_length=255)
    primary_artist = models.ForeignKey(
        Artist, on_delete=models.RESTRICT, related_name="primary_albums", null=True
    )


class AlbumArtist(UUIDModel, TimestampedModel):
    album = models.ForeignKey(
        Album, on_delete=models.CASCADE, related_name="album_artists"
    )
    artist = models.ForeignKey(
        Artist, on_delete=models.CASCADE, related_name="featured_albums"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["album", "artist"], name="unique_album_artist"
            )
        ]


class Track(UUIDModel, TimestampedModel):
    artist = models.ForeignKey(
        Artist, on_delete=models.CASCADE, null=True, related_name="tracks"
    )
    album = models.ForeignKey(
        Album, on_delete=models.CASCADE, null=True, related_name="tracks"
    )
    name = models.CharField(max_length=255)
    spotify_track_uri = models.CharField(max_length=50, unique=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["spotify_track_uri", "artist", "album"],
                name="unique_artist_album_spotify_track_uri",
            )
        ]
