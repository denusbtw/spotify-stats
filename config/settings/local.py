import socket
from datetime import timedelta

from .base import *

DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in {"true", "1"}

INSTALLED_APPS = [*INSTALLED_APPS, "debug_toolbar"]

MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware", *MIDDLEWARE]


hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())

INTERNAL_IPS = [
    "127.0.0.1",
    "host.docker.internal",
]

INTERNAL_IPS += [ip[: ip.rfind(".")] + ".1" for ip in ips]

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=7),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
}
