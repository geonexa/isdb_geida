"""
Settings shared by every environment.

Django serves only the JSON API (/api/...) and the admin (/admin/). The React
frontend (../frontend) is a separate app; in development Vite forwards /api and
/admin to this server, in production Apache does.

Environment-specific values live in development.py and production.py; the
package __init__ picks one from DJANGO_ENV. Secrets and machine-specific values
come from backend/.env (see .env.example).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
load_dotenv(BASE_DIR / ".env")


def env_list(name, default=""):
    return [v.strip() for v in os.getenv(name, default).split(",") if v.strip()]


def env_bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# DJANGO_ENV: "development" (default) or "production".
DJANGO_ENV = os.getenv("DJANGO_ENV", "development").strip().lower()
IS_PRODUCTION = DJANGO_ENV == "production"

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me")

ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,geida.terrawatch.net,www.geida.terrawatch.net"
)
CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "https://geida.terrawatch.net,http://localhost:5173,http://127.0.0.1:5173",
)
# Public address of the React app, used in emailed links (password reset).
# Leave empty to use the address the request came in on.
FRONTEND_URL = os.getenv("FRONTEND_URL", "").rstrip("/")

# Behind Apache: trust X-Forwarded-Proto so Django knows the request was HTTPS.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# The React app reads the CSRF cookie and sends it back in X-CSRFToken.
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "apps.core",
    "apps.accounts",
    "apps.geoportal",
    "apps.boundaries",
    "apps.projects",
    "apps.analysis",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        # Only the admin and the email templates use Django templates.
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --- Project folders --------------------------------------------------------
# Reference data committed to git and loaded into a fresh database by
# `manage.py seed` (CRI library, member-country outlines). See seeds/README.md.
SEEDS_DIR = BASE_DIR / "seeds"
# Large local datasets (GADM boundaries, dataset overrides, download cache):
# git-ignored, copied onto each machine. DATA_DIR in .env points elsewhere
# (STATIC_DATA_DIR is the older name and still read).
DATA_DIR = Path(os.getenv("DATA_DIR") or os.getenv("STATIC_DATA_DIR") or BASE_DIR / "data")
# Analysis modules: one folder per module (manifest.yaml + run.py), see modules/README.md.
MODULES_DIR = BASE_DIR / "modules"
# OpenStreetMap: "geofabrik" (country extracts in DATA_DIR/osm/, Overpass as fallback)
# or "overpass" (live queries only). See apps/analysis/osm/.
OSM_SOURCE = os.getenv("OSM_SOURCE", "geofabrik").strip().lower()
OVERPASS_URL = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
# Raster layers (Data Catalog, project Data catalog tab): cloud-optimised GeoTIFFs
# read where they are hosted, found through STAC and rendered by TiTiler.
# See apps/geoportal/raster.py and docs/specs/gee-replacement.md.
TITILER_URL = os.getenv("TITILER_URL", "https://titiler.waterinag.org").rstrip("/")
STAC_API_URL = os.getenv("STAC_API_URL", "https://earth-search.aws.element84.com/v1").rstrip("/")

# --- Celery + Redis ---------------------------------------------------------
# Background queue for analysis runs. Results live in ModuleRun, so no result
# backend is needed. CELERY_TASK_ALWAYS_EAGER=true runs tasks inline (tests, or
# a quick try without Redis).
CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_ACKS_LATE = True  # a run whose worker dies is delivered again
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # runs are long: take one at a time
CELERY_TASK_TIME_LIMIT = int(os.getenv("ANALYSIS_TIME_LIMIT", 60 * 60))  # hard stop, seconds
CELERY_TASK_SOFT_TIME_LIMIT = CELERY_TASK_TIME_LIMIT - 60
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER")
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_TRANSPORT_OPTIONS = {"visibility_timeout": CELERY_TASK_TIME_LIMIT + 600}

# Only if GeoDjango can't find its libraries (macOS conda: $CONDA_PREFIX/lib/...).
for _name in ("SPATIALITE_LIBRARY_PATH", "GDAL_LIBRARY_PATH", "GEOS_LIBRARY_PATH"):
    if os.getenv(_name):
        globals()[_name] = os.getenv(_name)

# --- Auth -------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.EmailOrUsernameBackend"]
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24  # reset links last 24 hours

OTP_TTL_SECONDS = 600
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN = 60

# --- Locale, static, media --------------------------------------------------
LANGUAGE_CODE = "en"
TIME_ZONE = "Asia/Riyadh"
USE_I18N = True
USE_TZ = True

# Static files are only the admin's; the React app has its own build.
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Email ------------------------------------------------------------------
# SMTP when credentials are set, otherwise printed in the runserver console.
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend" if EMAIL_HOST_USER
    else "django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "GEIDA <no-reply@geida.local>")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"apps": {"handlers": ["console"], "level": "INFO"}},
}
