# Configuration

All server-side configuration lives in **`backend/.env`**, read at start-up by
`config/settings/base.py`. The template is `backend/.env.example`; copy it and fill in
the values. Never commit `.env`.

After changing `.env`, restart the API and the worker (in development, stop and start
`runserver` and `run_worker`; on a server, see [Operations](../deploy/operations.md)).

## Environment

| Variable | Default | Description |
|---|---|---|
| `DJANGO_ENV` | `development` | `development` (SQLite + SpatiaLite, debug on) or `production` (PostgreSQL + PostGIS, debug off, secure cookies) |
| `DJANGO_SECRET_KEY` | development-only value | **Required in production**; the API refuses to start without it. Generate with `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,geida.terrawatch.net,www.geida.terrawatch.net` | Comma-separated host names the API answers to |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://geida.terrawatch.net,http://localhost:5173,http://127.0.0.1:5173` | Comma-separated origins allowed to send writes |
| `FRONTEND_URL` | empty | Public address of the web app, used in emailed links. Empty uses the address the request came in on |

## Database

| Variable | Default | Description |
|---|---|---|
| `DATABASE_NAME` | `db.sqlite3` | Development only: SQLite file in `backend/` |
| `POSTGRES_DB` | `geida` | Production database name |
| `POSTGRES_USER` | `geida` | Production database user |
| `POSTGRES_PASSWORD` | empty | Production database password |
| `POSTGRES_HOST` | `localhost` | Database host |
| `POSTGRES_PORT` | `5432` | Database port |

## Data services

| Variable | Default | Description |
|---|---|---|
| `TITILER_URL` | `https://titiler.waterinag.org` | TiTiler instance that draws raster tiles and cuts GeoTIFF downloads. Point it at IsDB's own TiTiler when hosted there |
| `STAC_API_URL` | `https://earth-search.aws.element84.com/v1` | STAC API used to find tiled datasets (Copernicus DEM) |
| `DATA_DIR` | `backend/data` | Folder for large datasets: boundaries, OSM extracts, overrides, cache. Put it on a large disk on servers |
| `OSM_SOURCE` | `geofabrik` | `geofabrik` (country extracts, Overpass as fallback) or `overpass` (live API only) |
| `OVERPASS_URL` | `https://overpass-api.de/api/interpreter` | Overpass endpoint for the fallback |

## Analysis runs

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker |
| `CELERY_TASK_ALWAYS_EAGER` | `false` | `true` runs analyses inside the web request (no Redis or worker). Development only |
| `ANALYSIS_TIME_LIMIT` | `3600` | Hard time limit for one run, in seconds. A soft limit 60 seconds earlier lets the module stop cleanly |

## Email

| Variable | Default | Description |
|---|---|---|
| `EMAIL_HOST_USER` | empty | SMTP user. **Empty prints emails to the console** instead of sending them |
| `EMAIL_HOST_PASSWORD` | empty | SMTP password (for Gmail, an app password) |
| `EMAIL_HOST` | `smtp.gmail.com` | SMTP server |
| `EMAIL_PORT` | `587` | SMTP port |
| `EMAIL_USE_TLS` | `true` | Use STARTTLS |
| `DEFAULT_FROM_EMAIL` | the SMTP user | Sender, for example `GEIDA <no-reply@geida.terrawatch.net>` |

Emails are sent for account verification codes and password resets.

## Library paths

Only needed if GeoDjango cannot find its native libraries (seen on some macOS setups):

| Variable | Example (macOS, Anaconda) |
|---|---|
| `GDAL_LIBRARY_PATH` | `/opt/anaconda3/envs/geida/lib/libgdal.dylib` |
| `GEOS_LIBRARY_PATH` | `/opt/anaconda3/envs/geida/lib/libgeos_c.dylib` |
| `SPATIALITE_LIBRARY_PATH` | `/opt/anaconda3/envs/geida/lib/mod_spatialite.dylib` |

## Example: production `.env`

```ini
DJANGO_ENV=production
DJANGO_SECRET_KEY=<50+ random characters>
DJANGO_ALLOWED_HOSTS=geida.terrawatch.net
DJANGO_CSRF_TRUSTED_ORIGINS=https://geida.terrawatch.net
FRONTEND_URL=https://geida.terrawatch.net

POSTGRES_DB=geida
POSTGRES_USER=geida
POSTGRES_PASSWORD=<database password>

DATA_DIR=/srv/geida-data
REDIS_URL=redis://localhost:6379/0

EMAIL_HOST_USER=<smtp user>
EMAIL_HOST_PASSWORD=<smtp password>
DEFAULT_FROM_EMAIL=GEIDA <no-reply@geida.terrawatch.net>
```

## Frontend configuration

The frontend has no secrets and no `.env`. Its only setting is the backend address for
the development proxy: `GEIDA_BACKEND` (default `http://127.0.0.1:8000`), read by
`frontend/vite.config.ts`. Basemaps and layers come from the API at run time.

## Adding a new setting

1. Read it in `config/settings/base.py` with `os.getenv("NAME", default)` (or
   `env_bool` / `env_list`), with a default that works for development.
2. Add it, commented, to `backend/.env.example`.
3. Add a row to this page and an entry to the [Changelog](../changelog.md).
