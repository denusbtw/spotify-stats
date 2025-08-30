from django.db import models
from django.conf import settings
from django.utils import timezone

from spotify_stats.core.models import TimestampedModel, UUIDModel


class ListeningHistoryQuerySet(models.QuerySet):

    def for_user(self, user):
        return self.filter(user=user)


class ListeningHistory(UUIDModel, TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    track = models.ForeignKey(
        "catalog.Track", on_delete=models.CASCADE, related_name="history"
    )
    played_at = models.DateTimeField()  # 'ts'
    ms_played = models.PositiveIntegerField()

    objects = ListeningHistoryQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "played_at"], name="unique_user_played_at"
            )
        ]

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


class SpotifyProfile(UUIDModel, TimestampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="spotify_profile",
    )
    access_token = models.CharField(max_length=512)
    refresh_token = models.CharField(max_length=512)
    expires_at = models.DateTimeField()
    spotify_id = models.CharField(max_length=64, unique=True)
    scope = models.CharField(max_length=256)

    def __str__(self):
        return f"Spotify Profile for {self.user_id}"

    @property
    def is_token_expired(self):
        return self.expires_at <= timezone.now()
