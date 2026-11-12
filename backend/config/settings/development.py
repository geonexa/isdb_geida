"""Local development: PostgreSQL + PostGIS (as in production), DEBUG on, emails printed in the console.

The database comes from POSTGRES_* in backend/.env; the defaults suit Postgres.app on a Mac
(database `geida`, your macOS user, no password, localhost:5432). Create it once with
`createdb geida && psql -d geida -c "CREATE EXTENSION postgis"`.
"""
import getpass
import os

from .base import *  # noqa: F401,F403

DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": os.getenv("POSTGRES_DB", "geida"),
        "USER": os.getenv("POSTGRES_USER", getpass.getuser()),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}
