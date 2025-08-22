from .base import *

DEBUG = os.environ.get("DJANGO_DEBUG", "False").lower() in {"true", "1"}

ALLOWED_HOSTS = (
    os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if not DEBUG else ["*"]
)

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
]
