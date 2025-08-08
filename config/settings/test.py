from .base import *

DEBUG = os.environ.get("DEBUG", "True").lower() in {"true", "1"}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
