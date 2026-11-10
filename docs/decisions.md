# Decision log

Choices IMDT (IsDB IT) and partners will ask about. Newest first. Each entry:
what was decided, why, and what would change it.

| Date | Decision | Why | Status |
|---|---|---|---|
| 2026-11-06 | Outside map services used for display only: Terrascope WMS draws WorldCover and the 90 m DEM below the COG layers' minzoom, terrestris SRTM hillshade likewise; view-only catalogue layers (`kind: tiles`) from NASA GIBS (NDVI, land surface temperature, GPW population), Terrascope (WorldCereal 2021), Esri (10 m land cover 2017–2025, World Imagery Wayback). Marked "View only": no clip, download or analysis. Analyses stay on COG + TiTiler | Fills display gaps without hosting or processing; values stay on data GEIDA controls | Done (`docs/open-map-services.md`) |
| 2026-11-06 | Google Earth Engine removed. Raster layers are cloud-optimised GeoTIFFs read where their producers host them (FAO WaPOR on GCS, ESA WorldCover and Copernicus DEM on AWS, DEM tiles found through Earth Search STAC), drawn and cut by TiTiler (`titiler.waterinag.org`, `TITILER_URL`); tiled datasets are combined per request as an in-line GDAL VRT. Data that isn't available as COG (MODIS NDVI annual, ERA5-Land, CHIRPS before 2017) is processed into GEIDA's bucket in the next step. WorldCereal dropped (only in Earth Engine) | No Google key or quotas in the request path; works at IsDB with any TiTiler; no copies of global data to store | Done (`specs/gee-replacement.md`) |
| 2026-11-04 | shapely 2 added (conda-forge, same GEOS as GDAL) for vector analyses; distances and areas in a spherical Lambert azimuthal equal-area projection centred on each project area | Vectorised point-in-polygon, nearest and lengths on 100k+ buildings; equal-area keeps km² exact and straight-line distances within 0.1% at district scale | Done (decision 3 in `plan.md`) |
| 2026-11-04 | Analysis categories held as data (`backend/modules/categories.yaml`); each manifest names one; folders starting with `_` aren't modules (parking) | Staff browse by question, not by dataset; parking keeps code, runs and evidence | Done |
| 2026-11-03 | Browser `confirm`/`alert` replaced by a themed dialog (`shared/components/Confirm.tsx`) and a toast event bridge for plain-JS code | One look across the platform | Done |
| 2026-11-03 | Map export rebuilt as a GEIDA layout editor (items on a page, SVG renderer, templates); the GeoLibre print-engine bridge is no longer used | Publication-quality maps need free placement, grids, overview maps and editable styles, which a fixed layout can't give | Done (supersedes 2026-11-02 map-export entry) |
| 2026-11-01 | GeoLibre merged into the GEIDA React app (one Vite 8 build, mounted at `/analytics`), with build-time CSS scoping | One app and dev server; GeoLibre is now GEIDA code, no upstream merges | Done |
| 2026-11-02 | Map export reuses GeoLibre's print-layout engine unchanged (bridge `virtual:gis-print`); GEIDA owns capture (off-screen map at page size and DPI), legend, logos, sources and presets | A mature, tested renderer (preview, PNG/PDF, editable SVG from one set of drawing commands) without forking it; GEIDA-specific parts stay in `features/print` | Superseded 2026-11-03 |
| 2026-11-02 | OSM extracts: never download a continent; a box crossing a border uses the country holding its centre, flagged `partial` in the run | Moroto + 10 km crosses into Kenya and started a multi-GB Africa download; country extracts stay small | Done |
| 2026-11-02 | OSM data from Geofabrik country extracts read with GDAL's OSM driver, Overpass only as fallback; tag taxonomy held as data (`seeds/data/osm_taxonomy.yaml`) | Reliable at district scale, reproducible (snapshot date per run), mirrorable at IsDB; no new parser to maintain | Done (step 1 of `specs/osm-analysis-catalogue.md`) |
| 2026-11-02 | Raster modules parked; next modules use OpenStreetMap only | Faster, explainable results for the demo; raster analyses return in a later phase | Agreed (Aman); Sajid to confirm |
| 2026-11-02 | Repository split into `backend/` (Django, modules, seeds) and `frontend/` (React), with `docs/`, `deploy/`, and git-ignored `local/` and `cred/` | Clear ownership, independent builds, credentials kept out of git | Done |
| 2026-11-02 | Reference data loaded by an idempotent `manage.py seed`, not data migrations | Same command for a new server and for updates; CRI list changes don't need a migration | Done |
| 2026-11-02 | Settings split into base / development / production, selected by `DJANGO_ENV` | One entry point (`config.settings`) for WSGI, Celery and manage.py | Done |
| 2026-10-27 | Front end on React + MapLibre GL, with GeoLibre tools switched on per role | Same stack as GeoLibre, so its components can be reused; GEIDA stays its own app | Agreed (working plan) |
| 2026-10-27 | Analyses as modules (`manifest.yaml` + `run.py`) that run only where data allows | New analyses without platform changes; honest about data gaps | Agreed (working plan) |
| 2026-10-27 | CRI codes held as data (seed CSV), never in code | IsDB revises the list; numbering has gaps | Agreed (working plan) |
| 2026-10-27 | Training LMS (Tutor LMS) stays a separate, linked system | Different product and hosting cycle | Agreed (working plan) |

## Open

| Topic | Question | Owner |
|---|---|---|
| Hosting | IMDT server spec, tile server (TiTiler vs GeoServer), PostGIS version | Aman / IMDT |
| Authentication | Local accounts now; IsDB SSO (Azure AD / Entra ID) at handover? | IMDT |
| Licences | GADM is non-commercial; GeoLibre MIT; Whitebox components to check. OSM is ODbL (credit "© OpenStreetMap contributors"; shared derived databases stay ODbL). Code adapted from Aleph (MIT, © 2026 Belluxx) keeps its notice: `apps/analysis/osm/pbf_header.py`, `geofabrik.py`, taxonomy | Sajid |
| CRI units | 3.2 km² vs ha, 3.7 unit, missing 8.5 and 17.6 units, sex disaggregation flags | Bakhodir |
