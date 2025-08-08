from django.contrib.auth.models import AbstractUser

from spotify_stats.core.models import UUIDModel


class User(UUIDModel, AbstractUser):
    pass