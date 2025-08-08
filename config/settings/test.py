from .base import *

DEBUG = os.environ.get("DEBUG", "False").lower() in {"true", "1"}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
