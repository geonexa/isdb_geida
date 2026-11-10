# GEIDA development phases

Status as of 4 Nov 2026. Source: *GEIDA Platform Development Working Plan* (Sajid, 27 Oct 2026),
updated for the OSM rework (`docs/specs/osm-analysis-catalogue.md`).
Cycle 1 ends at the mid-November demo (assumed week of 16 Nov; date to agree with IsDB);
Cycle 2 at 31 December 2026.

## Done

| Phase | What |
|---|---|
| 0 | React + Django split, Geo-Portal at `/geoportal` |
| 1 | Project onboarding: wizard (Route A), bulk/template import (B), submission-form import (C), CRI library, review workflow (submit → review queue → publish / return with comment) — `docs/specs/project-onboarding.md` |
| 1b | GADM admin boundaries levels 0–3 (`apps.boundaries`) |
| 2a | Module system: manifests + registry, availability per project, Celery + Redis queue (`run_worker` with auto-reload in DEBUG), evidence accept/reject, open-data fetchers; modules `area_baseline`, `school_access`, `terrain`, `schools_inventory`, `buildings` — `docs/specs/analysis-modules.md` |
| 2r.1 | OSM data layer: Geofabrik extracts read with GDAL, per-area cache, tag taxonomy (16 layers), snapshot date, Overpass fallback (step 1 of the OSM catalogue) |
| 2r.2 | Project workspace: one persistent map, rail (Overview, Results, Data catalog, Analyses, Evidence, Documents, Activity); satellite layers clipped to the area with GeoTIFF download in the Data catalog tab |
| 2r.3 | Map layout editor (QGIS-style): items on a page (maps with graticule, overview, legend, scale bar, north arrow, colour bar, text with fields, pictures, shapes), templates + saved templates, snapping, undo; SVG / PNG / PDF up to 600 dpi — replaces the GeoLibre print bridge |
| 2r.4 | One React app: GeoLibre workspace mounted at `/analytics` (no iframe, no second dev server), one Vite 8 build, CSS scoping between GEIDA and GeoLibre |
| C1.2 | Vector helpers (`apps/analysis/vector.py`, shapely 2, equal-area projection per area) with unit tests; categories as data (`modules/categories.yaml`); catalogue grouped by category with filter chips; raster modules parked in `modules/_parked/` (runs still open; tests in `tests_parked.py`); vector layers on the map drawn as points, lines or polygons, coloured by class or step |
| C1.3 | `schools_inventory` 0.2 and `buildings` 0.2 ported to vector (OSM only); new `area_profile`, `health_inventory`, `road_network`; shared inventory outputs (`apps/analysis/inventory.py`); fixture tests check per-unit totals add up. Still to do: a timed run on UGA1072 with the real Geofabrik extract (C1.0 machine) |
| 2r.5 | Themed confirm dialog and toast bridge replace browser `confirm`/`alert`; GDAL/PROJ startup check and conda-forge-only `environment.yml` |

## Cycle 1 — to the demo (4 → 13 Nov)

Goal: a stable build on staging, the OSM analysis catalogue running on real projects, and a
rehearsed 20-minute walkthrough. Each step ends with tests passing and a check on staging.

| # | Step | Deliverable | Done when | Target |
|---|---|---|---|---|
| C1.0 | **Stabilise** | `geida-react` conda env on every machine; `npm install` on Vite 8; `manage.py check` clean; a Playwright smoke script (home, projects, project workspace, layout export, Analytics, Geo-Portal) | Smoke script green on Aman's Mac and staging | Thu 5 Nov |
| C1.1 | **Decisions** (see below) | Sajid confirms OSM-only for the demo, buildings-as-proxy wording, shapely dependency | Recorded in `decisions.md` | Thu 5 Nov |
| C1.2 | OSM catalogue steps 2–3 | `vector.py` helpers (shapely 2) with unit tests; `categories.yaml`; catalogue grouped by category in the Analyses tab; raster modules moved to `_parked/` (old runs still open) | 5 categories listed; parked runs viewable | Fri 6 Nov |
| C1.3 | OSM catalogue step 4 | Port `schools_inventory`, `buildings` to vector; new `area_profile`, `health_inventory`, `road_network` | Each passes its fixture test and runs on UGA1072 in < 1 min | Mon 9 Nov |
| C1.4 | OSM catalogue steps 5–6 | `facility_proximity` (distance bands), `neighbourhood_profile` (point picked on the map), `road_access`, `community_facilities`, `utilities_inventory`; result viewer: feature popups with OSM links, table ↔ map highlight, "OSM snapshot" badge | All 10 modules run on UGA1072 and AZE1028; band counts add up | Wed 11 Nov |
| C1.5 | Run → map | "Make a map" on a finished run opens the layout editor with the run's layers, legend, summary paragraph and sources pre-placed (Run report template) | One click from a run to a 300 dpi PDF | Wed 11 Nov |
| C1.6 | Review workflow | Email to reviewers on submit, to the owner on return/publish; the submitter can't publish their own project | Tested with two accounts | Thu 12 Nov |
| C1.7 | Staging deploy | PostGIS, Gunicorn + Celery worker + Redis as systemd services, Apache (`deploy/apache.conf`, `/gis-assets/`), `seed` + GADM + Geofabrik cache, HTTPS; build machine ≥ 6 GB RAM | `geida.terrawatch.net` serves all pages; a module run completes there | Thu 12 Nov |
| C1.8 | Demo content | Nine hub projects seeded with areas, results frameworks and 2–3 runs each; one saved layout per showcase project; demo script in `docs/demo.md`; rehearsal | Walkthrough rehearsed on staging | Fri 13 Nov |

Cut line if time runs short: C1.6 and the last two modules in C1.4 (`community_facilities`,
`utilities_inventory`) move to Cycle 2; C1.0, C1.3, C1.7 and C1.8 are not negotiable.

## Cycle 2 — to 31 December

| # | Deliverable | Notes |
|---|---|---|
| C2.1 | Roles: Curated vs Advanced | Role-based tool registry; Analytics for analysts (the gate is in place, switched off); GeoLibre interface profiles for curated tools |
| C2.2 | Indicator tracker | In the project workspace (Results tab; no separate Indicators page, removed 5 Nov): baseline, progress points, target per indicator; chart + table; accepted evidence feeds it; export in PPRR / PIASR / PCR logframe layout |
| C2.3 | Country data | Upload and field-mapping wizard (census tables, facility lists); Uganda NPHC 2024 first (district / sub-county join to GADM via a name-matching table) |
| C2.4 | Rasters return via STAC / COG | **Started 6 Nov:** Earth Engine removed; Data Catalog layers read as COGs in place and drawn by TiTiler (WaPOR, WorldCover, Copernicus DEM via STAC, JRC water). Still to do: NDVI, ERA5 temperature and long CHIRPS series processed into GEIDA's bucket; Sentinel-2 by date; population; un-park `terrain`, `area_baseline`, `school_access` (people-based CRIs 9.1, 8.3) |
| C2.5 | Acceptance against Moroto | Moroto course results within tolerance once population and census are back (`specs/moroto-case-study-gap-analysis.md`) |
| C2.6 | Corridor and health access | `road_corridor` (line input, 1 km buffer) and `health_access` (HC III+ via facility lists) |
| C2.7 | Network distance | Road-network distance (OSRM or pgRouting on the same extract) for the access modules |
| C2.8 | Imagery by date and vector tiles | Sentinel-2 / Esri Wayback slider for Verify roles; PMTiles for reference layers, `ST_AsMVT` for project layers |
| C2.9 | Agriculture and water modules | Irrigated area (3.2), water productivity (3.4, 7.6), WaPOR biomass, water-harvesting storage (7.8) |
| C2.10 | Hand-over | 15 projects loaded, case studies, admin and user guides, CI (backend tests + smoke script), IsDB SSO if IMDT confirms |

## Decisions needed

| # | Question | Recommendation | Owner | Needed by |
|---|---|---|---|---|
| 1 | OSM-only modules for the demo instead of `health_access` / `road_corridor` with population | Yes; rasters return in C2.4 | Sajid | 5 Nov |
| 2 | Buildings within X km as a proxy for people (CRIs 9.1, 8.3, 7.1, 2.1) | Propose as evidence with role *estimate* and a stated caveat | Sajid | 5 Nov |
| 3 | Add shapely 2 to the environment | Yes (100k+ buildings are too slow with GEOS loops) | Aman | 5 Nov |
| 4 | Demo date and audience | Agree two weeks ahead | Sajid / IsDB | asap |
| 5 | Staging host spec (RAM ≥ 8 GB, disk for Geofabrik extracts ~5 GB) | — | IMDT | 10 Nov |
| 6 | CRI units (3.2, 3.7, 8.5, 17.6) and sex-disaggregation flags | — | Bakhodir | Cycle 2 |
| 7 | Licences: GADM non-commercial use at IsDB | — | Sajid | Cycle 2 |

## Risks

- **Environment drift** (mixed conda channels, Homebrew PROJ): use only `environment.yml`; the startup check stops Django with the fix.
- **Build memory**: the frontend build needs ~6 GB; build on the staging box or upload `dist/`.
- **OSM completeness** varies by country: every result says "mapped features" and shows its snapshot date.
- **Single developer**: keep the cut line above; no new features after Wed 11 Nov except demo fixes.
