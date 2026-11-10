"""Server: PostgreSQL + PostGIS behind Apache over HTTPS, DEBUG off."""
import os

from .base import *  # noqa: F401,F403
from .base import SECRET_KEY

DEBUG = False

if SECRET_KEY.startswith("dev-only"):
    raise RuntimeError("Set DJANGO_SECRET_KEY in .env for production.")

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": os.getenv("POSTGRES_DB", "geida"),
        "USER": os.getenv("POSTGRES_USER", "geida"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
