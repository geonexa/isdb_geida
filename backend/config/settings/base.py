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
# JSON request bodies up to 10 MB: map export layouts can hold pictures (apps/projects/map_layouts.py).
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
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
    "apps.toolbox",
    "apps.reference",
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
# REFERENCE_DATA_DIR: all data GEIDA seeds or reads as reference, outside the repository
#   (default: geida_static_data next to the repository folder): one folder per dataset and one
#   catalog.json describing them (CRI library, member countries, OSM taxonomy, GADM, HydroATLAS,
#   ...). `manage.py seed` loads it; some files (member countries, OSM taxonomy) are read at run time.
# DATA_DIR: the runtime cache (dataset clips per area, OSM extracts, derived products), inside the
#   repository folder as .cache/ (git-ignored, safe to delete).
REFERENCE_DATA_DIR = Path(os.getenv("REFERENCE_DATA_DIR") or BASE_DIR.parent.parent / "geida_static_data")
DATA_DIR = Path(os.getenv("DATA_DIR") or BASE_DIR.parent / ".cache")
# Analyses: one folder per analysis, analyses/<category>/<id>/ (manifest.yaml + run.py); see analyses/README.md.
ANALYSES_DIR = BASE_DIR / "analyses"
# OpenStreetMap: "geofabrik" (country extracts in DATA_DIR/osm/, Overpass as fallback)
# or "overpass" (live queries only). See apps/analysis/osm/.
OSM_SOURCE = os.getenv("OSM_SOURCE", "geofabrik").strip().lower()
OVERPASS_URL = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
# Raster layers (Data Catalog, project Data catalog tab): cloud-optimised GeoTIFFs
# read where they are hosted, found through STAC and rendered by TiTiler.
# See apps/geoportal/raster.py and docs/specs/gee-replacement.md.
TITILER_URL = os.getenv("TITILER_URL", "https://titiler.waterinag.org").rstrip("/")
STAC_API_URL = os.getenv("STAC_API_URL", "https://earth-search.aws.element84.com/v1").rstrip("/")
# Place search on the maps (apps/geoportal/search.py): a Nominatim geocoder, called by the server only
# when the user presses Enter (the public OpenStreetMap instance forbids search-as-you-type).
GEOCODER_URL = os.getenv("GEOCODER_URL", "https://nominatim.openstreetmap.org/search")
GEOCODER_USER_AGENT = os.getenv("GEOCODER_USER_AGENT", "GEIDA geoinformatics platform (Islamic Development Bank)")
# WorldPop API (population and age-sex per 100 m, 2015–2030) for the people analyses. Works without a key
# (1,000 requests a day, areas up to 100,000 km²); a free key from https://api.worldpop.org/v3/register raises the limits.
WORLDPOP_API_URL = os.getenv("WORLDPOP_API_URL", "https://api.worldpop.org/v3").rstrip("/")
WORLDPOP_API_KEY = os.getenv("WORLDPOP_API_KEY", "")
# WhiteboxTools executable folder (hydrology analyses). Empty: the whitebox package downloads it on first use.
WHITEBOX_DIR = os.getenv("WHITEBOX_DIR", "")
# Toolbox engine (GeoLibre WASI program run with wasmtime): a path to geolibre-cli.wasm, or empty to fetch it once
# into DATA_DIR/engines (apps/toolbox/engine.py).
GEOLIBRE_WASM = os.getenv("GEOLIBRE_WASM", "")
TOOLBOX_TIME_LIMIT = int(os.getenv("TOOLBOX_TIME_LIMIT", 600))  # seconds per Toolbox tool run

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
for _name in ("GDAL_LIBRARY_PATH", "GEOS_LIBRARY_PATH"):
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
