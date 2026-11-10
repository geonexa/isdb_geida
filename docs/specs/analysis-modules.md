# Analysis modules (phase 2a)

Status: built · Oct 2026

Implements "Module system", "Evidence records" and the first two of the "First four
module specs" from the development plan.

## How it fits

```
backend/modules/<id>/manifest.yaml + run.py      (one folder per analysis)
        │ sync_modules (also on each module list request)
        ▼
Module ──► ModuleRun (queued → running → done/failed)  ◄── Celery worker (Redis queue)
                │ outputs: metrics, tables, map previews (PNG), points (GeoJSON), files
                └─► Evidence (proposed → accepted/rejected) ──► Indicator (by CRI code)
```

- Availability per project: *ready*, *needs data* (e.g. no area yet) or *not available*
  (dataset doesn't cover the country). Optional inputs that are missing are listed.
- Modules whose CRIs are in the project's Results Framework are listed first.
- Evidence is never written into the Results Framework automatically; the project
  owner or a reviewer accepts it. The project page shows the latest accepted value
  per indicator ("GEIDA evidence").
- Each run keeps module version, parameters, datasets (with versions, licences and
  citations), log, and outputs in `media/runs/<id>/`.

## Datasets

| id | Source | Notes |
|---|---|---|
| `copernicus_dem_30` | AWS open COG tiles (1°) | read at native 30 m, coarsened above 25 Mpx |
| `esa_worldcover_2021` | AWS open COG tiles (3°) | mode resampling when coarsened |
| `worldpop_2020` | data.worldpop.org per-country 100 m | totals kept when coarsened |
| `osm_schools`, `osm_health` | Overpass API | `OVERPASS_URL` in `.env` to use another server |

Downloads are clipped to the area (+ buffer) and cached in `backend/data/cache/<id>/`.
A file in `backend/data/datasets/<id>/<ISO3>.tif|.geojson` is used instead of
downloading (Moroto course data, national datasets).

## Modules

**area_baseline** — slope (from DEM), share steeper than a threshold, elevation range,
land-cover class areas, population; per admin unit (level 1-3); map previews of slope and
land cover. Context for all sectors; no CRI evidence. Moroto acceptance: corridor 11%
steeper than 15°, mean slope 5.8°.

**school_access** — Euclidean distance from every population cell to the nearest school
(schools within the threshold outside the area count), people beyond the threshold per
admin unit, map preview, schools layer. Evidence: CRI 9.1 (estimate: people within the
threshold — proxy for reach) and 9.3 (verify: schools mapped in the area). Moroto
acceptance: about 14,800 people (11%) beyond 5 km; Tapac 41%.

## API

```
GET  /api/analysis/datasets/
GET  /api/analysis/modules/?project=CODE
GET  /api/analysis/runs/?project=CODE          POST {project, module, phase, params}
GET  /api/analysis/runs/<id>/                  POST /api/analysis/runs/<id>/cancel/
GET  /api/analysis/runs/<id>/files/<name>[?download=1]
GET  /api/analysis/evidence/?project=CODE      POST /api/analysis/evidence/<id>/accept|reject/
```

## Running

```
conda install -c conda-forge rasterio scipy pyyaml celery redis-py   # same GDAL as Django (don't pip-install rasterio)
brew install redis && brew services start redis                     # broker (Linux: apt install redis-server)
python manage.py migrate
python manage.py sync_modules
python manage.py run_worker          # = celery -A config worker (--pool solo on macOS)
```

Queue: Celery + Redis (`REDIS_URL`, default `redis://localhost:6379/0`). A run is
queued when its row is committed; the task claims it atomically (queued → running), so
a run never executes twice. `acks_late` + `reject_on_worker_lost`: a run whose worker
died is delivered again. Hard time limit `ANALYSIS_TIME_LIMIT` (default 1 h). If Redis
is down, the run is marked failed with "is Redis running?". `python manage.py
requeue_runs [--stale 90]` re-sends queued runs (e.g. after Redis lost its queue).
`CELERY_TASK_ALWAYS_EAGER=true` runs tasks inline (tests, quick tries without Redis).

Server: run `celery -A config worker -l info -c 2` as a systemd service next to Apache.

```

```

Tests: `python manage.py test apps.analysis` (synthetic rasters: slope of a 10% ramp,
people within 5 km of one school vs the circle area).

## Not yet

Whitebox tools (numpy/scipy implement the same steps for now), health_access and
road_corridor, census inputs, print maps.
