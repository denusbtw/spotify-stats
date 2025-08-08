from django.db import models

from spotify_stats.core.models import UUIDModel, TimestampedModel


class StreamingHistory(UUIDModel, TimestampedModel):
    user = models.ForeignKey("users.User", on_delete=models.CASCADE)
    track = models.ForeignKey(
        "catalog.Track",
        on_delete=models.CASCADE,
        related_name="history"
    )
    played_at = models.DateTimeField() # 'ts'
    ms_played = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.user.username} - {self.track.name}: {self.played_at.strftime('%Y/%m/%d, %H:%M:%S')}"
