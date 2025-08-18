from .base import *

DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in {"true", "1"}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
