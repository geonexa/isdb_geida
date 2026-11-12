# CLAUDE.md

Read the README in the folder you
work in (`backend/`, `frontend/`, `deploy/`) before changing it.

## Project

GEIDA, the IsDB Geoinformatics Data Platform, is built by Terra (Expo City Dubai)
for the Islamic Development Bank. The IsDB project cycle (PCN → PPRR → PAD/RRM →
PIASR → PCR → PPER) is the spine: every analysis belongs to a phase, and its
evidence flows back to the project's Results Framework indicators (CRI codes).
The plan is `docs/plan.md`; specs are in `docs/specs/`.

## Stack and commands

- Backend: Django 5 + GeoDjango, conda env `geida` (`backend/environment.yml`).
  PostgreSQL + PostGIS in development and production. Celery + Redis run analyses.
- Frontend: React 19 + TypeScript + Vite 8 + MapLibre. `frontend/gis/` is the
  GeoLibre workspace (MIT, vendored and ours to change).

| Task | Command |
|---|---|
| Backend checks / tests | `cd backend && python manage.py check && python manage.py test` |
| Missing migrations | `cd backend && python manage.py makemigrations --check --dry-run` |
| Frontend type-check | `cd frontend && npx tsc -p tsconfig.app.json --noEmit` (GEIDA only, fast) or `npm run typecheck` (all) |
| Frontend build | `cd frontend && npm run build` |
| Reference data | `cd backend && python manage.py seed` |

## Where things go

- New Django feature → an app in `backend/apps/<name>/` (models, views, urls, tests).
- New analysis → a folder in `backend/analyses/<category>/<id>/` (`manifest.yaml` + `run.py`);
  no platform code changes. See `backend/analyses/README.md`.
- Reference data a fresh database needs → a folder in `REFERENCE_DATA_DIR` (`geida_static_data/`, outside the repo) plus an entry in its `catalog.json` with a `load` block; files read at run time via `apps.reference.catalog.dataset_file(id)`.
- Seeding: one catalogue, `REFERENCE_DATA_DIR/catalog.json`, one `manage.py seed` (also registers the analyses). Runtime cache in `DATA_DIR` (`isdb_geida/.cache/`, git-ignored). Never commit rasters or GADM.
- New page or feature in the UI → `frontend/src/features/<name>/`; reusable
  pieces → `frontend/src/shared/`; app shell and routes → `frontend/src/app/`.
- Import with the `@/` alias across features; relative imports only within one.

## Rules

- Never change the schema without a migration; run `makemigrations --check` before finishing.
- Never hard-code CRI codes, module ids or country lists; they are data.
- Never write a value into a project's Results Framework automatically; evidence
  stays evidence until a user accepts it.
- Never commit secrets: `.env`, `cred/*`, keys. `local/` is personal and ignored.
- Don't edit `frontend/gis/` beyond what a feature needs; keep GeoLibre changes
  small so upstream fixes can still be merged.
- Analyses run only where the data allows; say so in the UI when they can't.
- Settings: shared values in `config/settings/base.py`, environment differences in
  `development.py` / `production.py`. `DJANGO_ENV` picks one.

## Workflow

Spec first (`docs/specs/`), plan approved, then code with tests. Finish with a
list of the files changed.
Every change that alters behaviour, settings, setup or deployment also updates the
documentation site (`docs/`, MkDocs; nav in `mkdocs.yml`): the affected pages, an entry
in `docs/changelog.md` (under `## Unreleased`, moved to a dated heading at release), and
an update note in `docs/updates/` when administrators must act. Check with
`mkdocs build` (strict); see `docs/development/documentation.md`.
Record choices IMDT (IsDB IT) will ask about —
hosting, authentication, data sources, licences — in `docs/decisions.md`.
