# Testing

## Backend

```bash
cd backend
conda activate geida
python manage.py test                       # every app
python manage.py test apps.analysis         # one app
python manage.py test apps.analysis.tests_osm.RegionTests   # one test class
python manage.py makemigrations --check --dry-run            # schema changes have migrations
python manage.py check                      # Django system checks
```

| Test module | Covers |
|---|---|
| `apps/projects/tests.py` | Project onboarding: projects, areas, indicators, review workflow |
| `apps/boundaries/tests.py` | World outlines for small-scale maps |
| `apps/geoportal/tests.py` | Catalogue, basemaps, raster tiles and clips, project data-catalog endpoints, view-only layers |
| `apps/analysis/tests.py` | Every catalogue module on an offline fixture; per-unit totals add up |
| `apps/analysis/tests_osm.py` | OSM taxonomy, Geofabrik region choice, extracts, Overpass fallback |
| `apps/analysis/tests_vector.py` | shapely helpers: zones, distances, lengths, equal-area projection |
| `apps/analysis/tests_parked.py` | Parked raster modules (skipped without rasterio data) |

Tests need neither Redis nor network access: analyses run eagerly against small fixture
datasets in a temporary `DATA_DIR`, and external services are mocked.

## Frontend

```bash
cd frontend
npx tsc -p tsconfig.app.json --noEmit       # GEIDA type-check, seconds
npm run typecheck                           # GEIDA + GeoLibre
npm run test:gis                            # GeoLibre unit tests
npm run build                               # full production build
```

## Before every release

Run `make check && make test` from the repository root (with `geida` active), or the
commands above. The checklist is in [Releasing an update](../deploy/releases.md).

## Manual checks

After a change to the interface, check in a browser:

| Area | Check |
|---|---|
| Home | Loads; navbar shows the IsDB and GEIDA logos; footer shows "Powered by" Terra · Expo City Dubai |
| Projects | List, wizard (draw an area), a project workspace |
| Project workspace | Analyses → Data layers: a layer on and off; Layers panel: change a palette and range, restyle a run output; map export to PDF with the overview showing the country boundary |
| Data Catalog | A raster layer draws; area drawing and clip download |
| Analytics | Workspace opens |
| Accounts | Sign in, sign out |
