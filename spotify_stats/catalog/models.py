from django.db import models

from spotify_stats.core.models import TimestampedModel, UUIDModel


class Artist(UUIDModel, TimestampedModel):
    name = models.CharField(max_length=255)


class Album(UUIDModel, TimestampedModel):
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name="albums")
    name = models.CharField(max_length=255)


class Track(UUIDModel, TimestampedModel):
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name="tracks")
    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name="tracks")
    name = models.CharField(max_length=255)
    spotify_track_uri = models.CharField(max_length=50, unique=True)
