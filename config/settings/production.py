from .base import *

DEBUG = os.environ.get("DEBUG", "False").lower() in {"true", "1"}

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "").split(",") if not DEBUG else ["*"]
