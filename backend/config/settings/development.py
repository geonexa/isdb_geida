"""Local development: SQLite + SpatiaLite, DEBUG on, emails printed in the console."""
import os

from .base import *  # noqa: F401,F403
from .base import BASE_DIR

DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.spatialite",
        "NAME": BASE_DIR / os.getenv("DATABASE_NAME", "db.sqlite3"),
    }
}
