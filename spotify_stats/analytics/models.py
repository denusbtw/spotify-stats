from django.db import models
from django.conf import settings

from spotify_stats.core.models import TimestampedModel, UUIDModel


class StreamingHistoryQuerySet(models.QuerySet):

    def for_user(self, user):
        return self.filter(user=user)


class StreamingHistory(UUIDModel, TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    track = models.ForeignKey(
        "catalog.Track", on_delete=models.CASCADE, related_name="history"
    )
    played_at = models.DateTimeField()  # 'ts'
    ms_played = models.PositiveIntegerField()

    objects = StreamingHistoryQuerySet.as_manager()

    def __str__(self):
        return f"{self.user.username} - {self.track.name}: {self.played_at.strftime('%Y/%m/%d, %H:%M:%S')}"


class FileUploadJob(UUIDModel, TimestampedModel):
    class Status(models.TextChoices):
        PENDING = ("pending", "Pending")
        PROCESSING = ("processing", "Processing")
        COMPLETED = ("completed", "Completed")
        FAILED = ("failed", "Failed")

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    file = models.FileField()
    status = models.CharField(max_length=15, choices=Status.choices)
