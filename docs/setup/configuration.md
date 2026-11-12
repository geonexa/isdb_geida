# Configuration

All server-side configuration lives in **`backend/.env`**, read at start-up by
`config/settings/base.py`. The template is `backend/.env.example`; copy it and fill in
the values. Never commit `.env`.

After changing `.env`, restart the API and the worker (in development, stop and start
`runserver` and `run_worker`; on a server, see [Operations](../deploy/operations.md)).

## Environment

| Variable | Default | Description |
|---|---|---|
| `DJANGO_ENV` | `development` | `development` (debug on, emails in the console) or `production` (debug off, secure cookies); both use PostgreSQL + PostGIS |
| `DJANGO_SECRET_KEY` | development-only value | **Required in production**; the API refuses to start without it. Generate with `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,geida.terrawatch.net,www.geida.terrawatch.net` | Comma-separated host names the API answers to |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://geida.terrawatch.net,http://localhost:5173,http://127.0.0.1:5173` | Comma-separated origins allowed to send writes |
| `FRONTEND_URL` | empty | Public address of the web app, used in emailed links. Empty uses the address the request came in on |

## Database

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_DB` | `geida` | Database name |
| `POSTGRES_USER` | `geida` (development: your system user) | Database user |
| `POSTGRES_PASSWORD` | empty | Database password (none needed for Postgres.app on a Mac) |
| `POSTGRES_HOST` | `localhost` | Database host |
| `POSTGRES_PORT` | `5432` | Database port |

## Data services

| Variable | Default | Description |
|---|---|---|
| `TITILER_URL` | `https://titiler.waterinag.org` | TiTiler instance that draws raster tiles and cuts GeoTIFF downloads. Point it at IsDB's own TiTiler when hosted there |
| `STAC_API_URL` | `https://earth-search.aws.element84.com/v1` | STAC API used to find tiled datasets (Copernicus DEM) |
| `WORLDPOP_API_URL` | `https://api.worldpop.org/v3` | WorldPop API for the people analyses (population and age-sex per 100 m, 2015–2030) |
| `WORLDPOP_API_KEY` | (empty) | Optional key (free, from https://api.worldpop.org/v3/register, approved by WorldPop): 10,000 requests a day instead of 1,000 and larger areas |
| `WHITEBOX_DIR` | (empty) | Folder of the WhiteboxTools executable for the hydrology analyses; empty: the `whitebox` package downloads it on first use |
| `GEOCODER_URL` | `https://nominatim.openstreetmap.org/search` | Nominatim search endpoint for the maps' place search (called by the server when the user presses Enter; results cached for a day). Point it to an IsDB-hosted Nominatim for heavy use |
| `GEOCODER_USER_AGENT` | `GEIDA geoinformatics platform (Islamic Development Bank)` | User-Agent sent to the geocoder (Nominatim's usage policy asks for an identifying one) |
| `REFERENCE_DATA_DIR` | `geida_static_data/` next to the repository | Large reference datasets (GADM, HydroATLAS) with their `catalog.json`, seeded once. Put it on a large disk on servers |
| `DATA_DIR` | `.cache/` in the repository | Runtime cache: dataset clips per area, OSM extracts, derived products, local dataset overrides. Safe to delete |
| `OSM_SOURCE` | `geofabrik` | `geofabrik` (country extracts, Overpass as fallback) or `overpass` (live API only) |
| `OVERPASS_URL` | `https://overpass-api.de/api/interpreter` | Overpass endpoint for the fallback |

## Analysis runs

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker |
| `CELERY_TASK_ALWAYS_EAGER` | `false` | `true` runs analyses inside the web request (no Redis or worker). Development only |
| `ANALYSIS_TIME_LIMIT` | `3600` | Hard time limit for one run, in seconds. A soft limit 60 seconds earlier lets the module stop cleanly |
| `TOOLBOX_TIME_LIMIT` | `600` | Time limit for one Toolbox tool run, in seconds; the engine is stopped and the run fails with a clear message |
| `GEOLIBRE_WASM` | (empty) | Path to the Toolbox engine, `geolibre-cli.wasm` (GeoLibre 1.7.1). Empty: copied from `frontend/node_modules/geolibre-wasm` on a developer machine, otherwise downloaded once from the npm CDN into `DATA_DIR/engines/`. Set it on servers without internet access |

Toolbox runs use the same queue and worker as analyses. The worker needs the `wasmtime` Python package
(`requirements.txt`). JSON request bodies may be up to 10 MB (`DATA_UPLOAD_MAX_MEMORY_SIZE`, set in
`config/settings/base.py`), for map export layouts with pictures; Toolbox uploads (multipart) may be up to 200 MB.

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

REFERENCE_DATA_DIR=/srv/geida_static_data
DATA_DIR=/srv/isdb_geida/.cache
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
