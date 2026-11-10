# GEIDA — IsDB Geoinformatics Data Platform

GEIDA brings Earth Observation into the Islamic Development Bank's project cycle.
Staff onboard a project, record its Results Framework against IsDB Core Result
Indicators (CRIs), and run curated geospatial analyses whose evidence feeds
those indicators from concept note (PCN) to post-evaluation (PPER).

Built by Terra, Expo City Dubai, for the Islamic Development Bank.

| | |
|---|---|
| **Backend** | Django 5 API · GeoDjango · PostGIS / SpatiaLite · Celery + Redis · TiTiler (COG + STAC) — [backend/README.md](backend/README.md) |
| **Frontend** | React 19 · TypeScript · Vite · MapLibre GL · GeoLibre workspace — [frontend/README.md](frontend/README.md) |
| **Docs** | Full documentation site (MkDocs): introduction, architecture, setup, deployment, changelog — [docs/](docs/index.md), see below |
| **Deploy** | Apache, systemd, release script — [deploy/README.md](deploy/README.md) |

## Quick start

Prerequisites: [conda](https://docs.conda.io) (Miniconda or Anaconda), Node 22+, Redis.

```bash
# Backend  → http://127.0.0.1:8000 (API only)
cd backend
conda env create -f environment.yml 
conda activate geida
cp .env.example .env                 # then fill in email settings
python manage.py migrate
python manage.py seed                # reference data (add --boundaries for GADM)
python manage.py runserver

# Frontend → http://localhost:5173 (open this one)
cd frontend
npm install
npm run dev
```

Analysis runs need a worker: `python manage.py run_worker` in a third terminal
(Redis running), or set `CELERY_TASK_ALWAYS_EAGER=true` in `.env` to run them inline.

With `make` installed, `make help` lists the same steps as one-liners.

## Documentation

The documentation site is built from `docs/` with MkDocs:

```bash
conda activate geida
pip install -r docs/requirements.txt   # once
mkdocs serve                          # http://127.0.0.1:8001
```

Start with *Setup → Local development*; record every release in `docs/changelog.md`.

## Repository layout

```
backend/    Django API, analysis modules, seed data
frontend/   React single-page app (GEIDA pages + GeoLibre GIS workspace)
docs/       documentation site (MkDocs): guides, changelog, specs, decision log
deploy/     server configuration and release script
```
