# GEIDA Backend

Django 5 JSON API for the GEIDA platform: authentication, project onboarding and
review, the IsDB CRI library, administrative boundaries, the Data Catalog layer
service (cloud-optimised GeoTIFFs drawn by TiTiler), and the analysis-module engine that turns open
geospatial data into indicator evidence.

Django serves only `/api/...` and `/admin/`. The React app in `../frontend` is a
separate build; Vite (development) or Apache (production) puts both on one origin
so the session cookie and CSRF token work without CORS.

## Contents

- [Architecture](#architecture)
- [Project layout](#project-layout)
- [Domain model](#domain-model)
- [Workflows](#workflows)
- [API reference](#api-reference)
- [Setup](#setup)
- [Configuration](#configuration)
- [Commands](#commands)
- [Testing](#testing)
- [Conventions](#conventions)

## Architecture

```
               ┌───────────────────────── Django (config/) ─────────────────────────┐
  /api/auth ─► │ accounts    session auth, registration, email code, password reset  │
  /api/site ─► │ core        site content, JSON error helpers, seed command          │
/api/geoportal►│ geoportal   layer catalogue, COG tiles (TiTiler) and GeoTIFF clips  │
/api/boundaries│ boundaries  GADM admin units (levels 0–3): search, GeoJSON, union   │
/api/projects ►│ projects    onboarding (wizard, import, form), CRIs, review flow    │
/api/analysis ►│ analysis    module registry, runs, datasets, evidence               │
               └───────┬──────────────────────────────┬──────────────────────────────┘
                       │ ORM (GeoDjango)              │ enqueue run
                       ▼                              ▼
          SpatiaLite (dev) / PostGIS (prod)       Redis ──► Celery worker
                                                           │ loads modules/<id>/run.py
                                                           │ fetches open data → data/cache/
                                                           ▼
                                                   outputs → media/runs/, Evidence rows
```

- **Stateless API, session auth.** Login sets a Django session cookie; the React
  app reads the CSRF cookie and sends `X-CSRFToken` on every write.
- **Long work off the request.** Analysis runs go to Celery (`config/celery.py`);
  the API only creates a `ModuleRun` and the UI polls its status.
- **Modules are plug-ins.** The registry reads `modules/<id>/manifest.yaml` at
  runtime; adding an analysis never touches app code.
- **Data stays data.** CRI codes, module ids and member countries are loaded from
  files (`seeds/`, `modules/`), never hard-coded.

## Project layout

```
backend/
├── config/
│   ├── settings/
│   │   ├── __init__.py      picks development or production from DJANGO_ENV
│   │   ├── base.py          shared settings, paths, Celery, email
│   │   ├── development.py   SQLite + SpatiaLite, DEBUG
│   │   └── production.py    PostgreSQL + PostGIS, secure cookies
│   ├── urls.py              /admin and /api/* routing
│   ├── celery.py            Celery app (worker: `manage.py run_worker`)
│   └── wsgi.py / asgi.py
├── apps/
│   ├── accounts/            auth views, email-or-username backend, OTP codes
│   ├── core/                site content, API helpers, startup checks, `seed`
│   ├── geoportal/           layer CATALOG, COG/STAC/TiTiler layer service (raster.py), saved areas
│   ├── boundaries/          AdminUnit model, `load_admin_units`
│   ├── projects/            Project, ProjectArea, Indicator, CRI, documents, importer
│   └── analysis/            Module, ModuleRun, Evidence; registry, runner, datasets
├── modules/                 analysis modules: <id>/manifest.yaml + run.py
├── seeds/                   reference data committed to git (see seeds/README.md)
│   └── data/                isdb_cri_2025_seed.csv, isdb_member_countries.geojson
├── data/                    large local datasets, git-ignored (see data/README.md)
├── scripts/                 one-off data preparation (prepare_gadm.py)
├── templates/               email templates
├── media/                   uploads and run outputs (git-ignored)
├── environment.yml          conda env "geida" (GDAL, PROJ, GEOS from conda-forge)
└── requirements.txt         Python packages (installed by environment.yml)
```

Each app follows the same shape: `models.py`, `views.py` (plain JSON views),
`urls.py`, `admin.py`, `tests.py`, and `management/commands/` for loaders.

## Domain model

```
CRI (library, 77 rows)                 AdminUnit (GADM, levels 0–3)
   ▲ cri code                              ▲ picked as area
   │                                       │
Project ──1:1── ProjectArea (MultiPolygon, EPSG:4326, area_km2)
   │  code, country, sector, cycle stage, status, source
   ├──1:n── Indicator (level, tier, baseline, target, geo role, CRI)
   ├──1:n── ProjectDocument (SharePoint links)
   ├──1:n── ProjectLog (review history)
   └──1:n── ModuleRun (module, phase, params, status, outputs)
                 └──1:n── Evidence (value, unit, role, method, data, caveats,
                                    status: pending → accepted / rejected)
Module (synced from modules/<id>/manifest.yaml)
```

- **Project status:** `draft` → `review` → `published`. Only published projects
  are visible to everyone; owners see their drafts, reviewers see all.
- **Project source:** `manual` (wizard), `import` (Excel/CSV), `form` (Project
  Data Submission Form). A duplicate project code updates the existing record.
- **Geometries** are validated and repaired on upload, reprojected to EPSG:4326,
  and their area computed. Problems are reported to the user, never silently fixed.

## Workflows

### Project onboarding

1. **Wizard** (`POST /api/projects/`, then `PUT .../area/`, `.../indicators/`,
   `.../documents/`): identity → area (upload, draw, admin units, point + buffer)
   → themes and components → Results Framework with CRI codes → document links.
2. **Bulk import**: download the template (`import/template/`), upload it to
   `import/preview/` to see row-level errors, then `import/commit/`.
3. **Submit and review**: `POST .../submit/` moves a draft to review; a reviewer
   publishes it (`.../publish/`) or returns it to draft with a comment (`.../return/`).

### Analysis run

1. `GET /api/analysis/modules/?project=CODE` lists modules with availability
   (`ready`, `needs data`, `not available`), CRI matches first.
2. `POST /api/analysis/runs/` queues a `ModuleRun` for a project phase.
3. The Celery worker loads `modules/<id>/run.py`, fetches inputs through the
   dataset registry (local override in `data/datasets/`, else download to
   `data/cache/`), and writes layers, tables and previews to `media/runs/<id>/`.
   OpenStreetMap layers come from the country's Geofabrik extract in `data/osm/`,
   cut per area with GDAL (`apps/analysis/osm/`), with Overpass as fallback.
4. Results linked to a project indicator create `Evidence` rows. A user accepts
   or rejects each value; nothing is written to the Results Framework on its own.

### Roles

| Role | How | Can |
|---|---|---|
| Visitor | not signed in | browse published projects and the Geo-Portal |
| User | registered and verified | create projects, edit own drafts, run analyses on them |
| Analyst | group `GEIDA analysts` | + Analytics workspace (full GIS toolbox) |
| Reviewer | group `GEIDA reviewers` or staff | + see and edit all projects, publish, review evidence |

Groups are created by migration `projects/0002_user_groups`; assign people in `/admin`.

## API reference

All responses are JSON. Writes need the `X-CSRFToken` header (`GET /api/auth/csrf/`
sets the cookie). Unknown `/api/` paths return a JSON 404.

| Area | Endpoints |
|---|---|
| Auth | `GET csrf/` · `GET me/` · `POST sign-in/` · `POST sign-out/` · `POST register/` · `GET,POST verify/` · `POST verify/resend/` · `POST password-reset/` · `GET,POST password-reset/<uid>/<token>/` |
| Site | `GET /api/site/` |
| Geo-Portal | `GET config/` · `GET basemaps/` · `GET layers/<id>/tiles/?year=` · `POST layers/<id>/clip/` · `GET,POST areas/` · `PATCH,DELETE areas/<id>/` |
| Boundaries | `GET units/?iso3=&level=&parent=&q=` · `GET units/geojson/` · `GET units/<gid>/` · `GET at/?lon=&lat=` · `POST union/` |
| Projects | `GET,POST /` · `GET meta/` · `GET cri/?q=` · `POST area/preview/` · `GET import/template/` · `POST import/preview/` · `POST import/commit/` · `GET,PATCH,DELETE <code>/` · `PUT <code>/area/` · `PUT <code>/indicators/` · `PUT <code>/documents/` · `POST <code>/<submit|return|publish>/` |
| Analysis | `GET datasets/` · `GET modules/?project=` · `GET,POST runs/` · `GET runs/<id>/` · `POST runs/<id>/cancel/` · `GET runs/<id>/files/<name>` · `GET evidence/` · `POST evidence/<id>/<accept|reject>/` |

Prefixes: `/api/auth/`, `/api/geoportal/`, `/api/boundaries/`, `/api/projects/`,
`/api/analysis/`.

## Setup

Requires conda. GDAL, PROJ, GEOS, SpatiaLite and rasterio must come from one
channel (conda-forge); mixing pip wheels or Homebrew loads two PROJ/GEOS builds
and GeoDjango fails at import.

```bash
cd backend
conda env create -f environment.yml          # creates "geida"
conda activate geida
cp .env.example .env
python manage.py migrate
python manage.py seed                        # CRI library + analysis modules
python manage.py seed --boundaries           # optional: GADM units (files in data/boundaries/)
python manage.py createsuperuser             # optional: /admin
python manage.py runserver                   # http://127.0.0.1:8000
python manage.py run_worker                  # second terminal, needs Redis
```

After pulling dependency changes: `conda env update -f environment.yml --prune`.

**Troubleshooting.** `Symbol not found: _GEOS...` or `proj.db ... DATABASE.LAYOUT`
means a library from outside the env was loaded. Open a fresh terminal (or
`unset DYLD_LIBRARY_PATH DYLD_FALLBACK_LIBRARY_PATH`), activate `geida`, and
check `python manage.py check`; the startup check `geida.E001` reports PROJ mismatches.

## Configuration

`backend/.env` (template: `.env.example`). The main keys:

| Key | Purpose |
|---|---|
| `DJANGO_ENV` | `development` (default) or `production` |
| `DJANGO_SECRET_KEY` | required in production |
| `DATABASE_NAME` | SQLite file in development |
| `POSTGRES_*` | database in production |
| `TITILER_URL` | tile server that draws the raster layers (default `https://titiler.waterinag.org`) |
| `STAC_API_URL` | STAC catalogue for tiled datasets (default Earth Search on AWS) |
| `REDIS_URL` | Celery broker |
| `CELERY_TASK_ALWAYS_EAGER` | run analyses inline (no worker) |
| `DATA_DIR` | large datasets, default `backend/data` |
| `EMAIL_*` | SMTP; empty prints emails to the console |

## Commands

| Command | What it does |
|---|---|
| `seed [--boundaries] [--countries UGA,AZE]` | load all reference data (idempotent) |
| `load_cri [csv]` | CRI library only |
| `sync_modules` | register `modules/*` manifests |
| `load_admin_units [--countries] [--levels] [--replace]` | GADM units only |
| `run_worker [-c N] [--noreload]` | Celery worker (auto-reload in DEBUG) |
| `requeue_runs [--stale N]` | re-queue runs stuck in `queued` (e.g. after Redis restarted); with `--stale`, also runs `running` for over N minutes |

## Testing

```bash
python manage.py test                        # all apps
python manage.py test apps.analysis          # one app
python manage.py makemigrations --check --dry-run
```

Analysis tests run modules eagerly against small fixture datasets in a temp
`DATA_DIR`, so they need neither Redis nor network access.

## Conventions

- **Views** return `JsonResponse`; raise `apps.core.api.BadRequest` for 400s and
  use `json_body(request)` to parse input.
- **Migrations** for every schema change; data changes to reference tables go
  through `seed`, not migrations.
- **New analysis**: add `modules/<id>/` (see `modules/README.md`), then
  `python manage.py sync_modules`.
- **New reference data**: file in `seeds/data/`, loader command in its app, step
  in `apps/core/management/commands/seed.py`.
- Python style: PEP 8, 120-character lines, docstrings on modules and public functions.
