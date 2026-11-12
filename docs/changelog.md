# Changelog

All notable changes to GEIDA, newest first. Each release is identified by its date.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/): changes are
grouped as **Added**, **Changed**, **Fixed**, **Removed** and **Security**.

Releases that need action from administrators have an [Update note](updates/index.md).
How to add an entry: [Maintaining the documentation](development/documentation.md#recording-a-change).

## Unreleased

Changes merged but not yet deployed go here, then move under a dated heading at release.

### Added
- **Site suitability** (`backend/analyses/planning/suitability/`, Site selection and planning): users set their
  own conditions in the run form (slope, elevation, land cover classes, rainfall, ETa, biomass, surface water,
  tree cover, population density, travel time, distance to roads / rivers / places / power lines / schools /
  health facilities), each with limits or classes, a weight and an optional must-have. Every 30 m cell gets a
  score (weighted share of conditions met); outputs: suitability classes and score maps, suitable land per admin
  unit, the area meeting each condition, and the largest suitable sites as polygons. New `criteria` parameter
  type with its editor in the run form. Earth Map's suitability builder was used as reference.
- **Server Toolbox with saved results** (`backend/apps/toolbox/`, `frontend/src/features/toolbox/`): 186
  vector and raster tools in 16 categories (overlay, geometry, measurement, attributes, grids, spatial
  statistics, networks, raster statistics, raster calculation, reclassify and mask, conversion, distance,
  neighbourhood, interpolation, classification, visibility), run on the server with the GeoLibre engine
  (`geolibre-cli.wasm` under wasmtime) plus GEIDA's own **Zonal statistics by polygon** and **Dissolve**.
  Inputs: area and admin units, Data Catalog rasters, OSM layers, analysis results, earlier Toolbox results
  and uploaded files (new **Files** view). Every run is saved (`ToolRun`); results show on the map, download as
  GeoPackage / GeoJSON / GeoTIFF / CSV, chain into other tools, can be renamed and deleted (one or several).
  Forms are built from the engine's manifests, with GEIDA's corrections; raster inputs are aligned to a common
  grid; each run is stopped after `TOOLBOX_TIME_LIMIT` (600 s). **Needs `pip install wasmtime` and
  `python manage.py migrate`** (toolbox 0001). Guide: `docs/introduction/toolbox.md`.
- **Delete analysis runs**: the person who started a run, or a reviewer, can delete it once finished, from the
  run (bin icon) or several at once (**Select** in the runs list). Files and proposed / rejected evidence go
  with it; runs with accepted evidence are kept. Deletions are recorded in the Activity log.
- **Analyses documentation** (`docs/analyses/`): one page per category describing every analysis (question,
  input data, settings, workflow, method, outputs, data sources and licences, limitations), generated from the
  manifests and `METHOD.md` files by `python manage.py document_analyses` (`--check` for CI). `METHOD.md` added
  for the five infrastructure analyses.
- Run results: the data sources sit behind **Show data sources (N)**, next to **Show run log**, one line per
  dataset with its years as ranges.
- `ctx.scratch(name)`: a temporary folder for intermediate files, deleted when the run ends.
- **Map export layouts kept in the user's account** (`apps/projects/map_layouts.py`, models `MapLayout`,
  `MapTemplate`, `MapSettings`): the last layout of each project, saved templates and the export
  resolution follow signed-in users to any computer or browser. Layouts this browser kept before
  are moved into the account the first time the export dialog opens. Users not signed in keep them
  in the browser. Other display preferences (basemap, layer styles, panels) stay in the browser.
  **Needs `python manage.py migrate`** (projects 0003); JSON request bodies may now be up to 10 MB
  (`DATA_UPLOAD_MAX_MEMORY_SIZE`).
- **Catchment from a point** (`backend/analyses/water/catchment/`): pick a dam, intake or crossing
  on the map; the outlet moves onto the nearest stream and the catchment is traced with
  WhiteboxTools, enlarging the elevation clip until it fits (up to 25,000 km²). Profile: area and
  share in the area of influence, elevation, slope, longest flow path, Kirpich time of
  concentration, streams by order; map of the catchment, its streams and the outlet. Elevation
  data only.
- `ctx.raster(..., bbox=, res=)`: read a raster input for any lon/lat box and set the run grid's
  resolution.
- `point` parameter type for analyses: the run form picks the point on the project map (each
  click moves the marker; longitude, latitude can also be typed); the API checks it lies within
  10 km of the area of influence; `ctx.point(name)` in `run.py`. For the coming catchment analysis.
- **Stream network and order** (`backend/analyses/water/stream_network/`): streams derived from the
  Copernicus 30 m DEM with WhiteboxTools (depressions breached, D8 flow, streams from a chosen
  upstream area, Strahler order): km per order, drainage density per admin unit, OSM waterways for
  comparison, streams map by order. First hydrology analysis (plan: `docs/planning/hydrology-plan.md`).
- **Sub-catchments in the area** (`backend/analyses/water/sub_basins/`): drainage units cut at stream
  confluences (WhiteboxTools Subbasins, small units merged downstream), with area, slope, elevation
  range and drained area at each outlet, and the points where streams leave the area for good.
- WhiteboxTools as the hydrology engine (`apps/analysis/engines/whitebox.py`, `ops/hydro.py`, cached
  flow per DEM clip); `whitebox` in `requirements.txt`, optional `WHITEBOX_DIR`. Benchmarked against
  GRASS GIS (same results, about 25 times faster, no separate install).
- **People and socio-economics analyses** (`backend/analyses/people/`): Population and density
  and Population change (GHSL GHS-POP R2023A, 100 m, epochs 1975–2030), Settlements and
  urbanisation (GHS-SMOD degree of urbanisation + OSM named places), Access to services
  (people by straight-line distance to OSM schools, health facilities, markets, water points or
  roads) and Travel time to cities and health care (Malaria Atlas Project, population-weighted).
  Each with METHOD.md and tests. Plan: `docs/planning/people-plan.md`.
- New data access `apps/analysis/data/people.py` (GHSL tiles cached in `DATA_DIR/ghsl/`, MAP WCS),
  `apps/analysis/ops/people.py`, and per-dataset resampling (`sum` for counts) in catalogue clips.
- **WorldPop is the main population source** (WorldPop API v3, Global2 R2025A, 100 m, every year
  2015–2030): Population and density adds age and sex (under 5, school age, youth, working age,
  women 15–49, 65+, the age pyramid) for the area and per unit; Population change gives any two
  years and a year-by-year table; Access to services and Travel time can count an age / sex group
  (e.g. school-age children within 2 km of a school). GHSL stays for years before 2015, settlement
  types and as a fallback when the WorldPop API is unavailable. Settings `WORLDPOP_API_URL`,
  `WORLDPOP_API_KEY` (optional).
- **Place search on every project map**: a search button below fullscreen opens a search box; admin
  units (GADM, our database) are suggested while typing, Enter also searches towns and other places
  (Nominatim via `GET /api/geoportal/search/`, cached; settings `GEOCODER_URL`, `GEOCODER_USER_AGENT`).
  Choosing a result zooms the map to it.
- **Land, vegetation and agriculture analyses** (`backend/analyses/land/`): Land cover
  composition (ESA WorldCover or Esri / Impact Observatory yearly maps), Land cover change
  (Esri yearly maps, 2017–2023: transitions, gains and losses), Vegetation indices (NDVI, EVI,
  SAVI, NDMI from a cloud-masked Sentinel-2 median composite for a chosen year and season),
  Biomass production (FAO WaPOR v3 L1, global 300 m; totals, cropland mean, change against another year), Forest
  cover and loss (Hansen Global Forest Change v1.12, loss per year) and Field boundaries (Fields
  of The World 2nd edition: counts, size classes, density grid). Each with METHOD.md and tests.
  Plan: `docs/planning/land-vegetation-plan.md`.
- New analysis data sources read in place: Esri annual land cover (Planetary Computer), Hansen
  forest change tiles, Fields of The World GeoParquet, Sentinel-2 L2A scenes
  (`apps/analysis/data/land.py`, `sentinel2.py`); class-map helpers `apps/analysis/ops/landcover.py`;
  `ctx.record_dataset()`; year-specific local overrides (`<ISO3>_<year>.tif`) and
  `open_min` legends.
- `libgdal-arrow-parquet` in `backend/environment.yml` (GDAL's GeoParquet driver), needed by
  Field boundaries. Existing environments: `conda env update -f backend/environment.yml`.

### Removed
- The browser-side Toolbox engine (`features/toolbox/engine.js`, `render.ts`, the processing worker, the
  `public/vendor` copy and `scripts/copy-engine.mjs`, about 31 MB downloaded by users) and the Toolbox list in
  the Geo-Portal config (`toolbox`, `clippable`, `tool_count`). Terrain and hydrology tools left the Toolbox:
  the matching analyses do the same job, saved.
- The old `worldpop_2020` dataset (WorldPop 2020 country files) and the parked `school_access` and
  `area_baseline` modules that used it; Population, Access to services, Slope and Land cover replace them.

### Changed
- **Seeding is one pipeline with one catalogue.** `REFERENCE_DATA_DIR/catalog.json` (outside the
  repository, default `geida_static_data/` next to it) lists every dataset: CRI library, member
  countries, OSM taxonomy, GADM, HydroATLAS; the analysis registry is a built-in step. One command, `manage.py seed`
  (`list`, `--only`, `--path`, `--countries`, `--force`, `--dry-run`), loads each dataset as its
  catalogue's `load` block says and records every step in the new `reference.ReferenceDataset`
  table. Large datasets load once and are skipped while unchanged. `backend/data/` and
  `backend/scripts/` are gone: the runtime cache moved to `DATA_DIR` (default `.cache/` in the
  repository), and `prepare_gadm.py` to `apps/reference/prepare/`. `seed --boundaries`
  is replaced by `seed` / `seed --only gadm`; `load_admin_units` reads from
  `REFERENCE_DATA_DIR/Admin_Boundaries/`.
- **Development uses PostgreSQL + PostGIS**, like production; SQLite / SpatiaLite support is
  removed (settings, the SpatiaLite WKB workaround in `apps/core`, `SPATIALITE_LIBRARY_PATH`,
  `DATABASE_NAME`, `libspatialite` in `environment.yml`). Development defaults: database `geida`
  on localhost as your own user (Postgres.app). Setup: `createdb geida`, `CREATE EXTENSION postgis`,
  `migrate`. Existing SQLite data can be moved with `dumpdata` / `loaddata` (admin units reloaded
  with `load_admin_units`).
- Analyses read catalogue rasters at their **native resolution** (30 m for the Copernicus DEM,
  10 m WorldCover, 300 m WaPOR L1) straight from the source COGs with GDAL (range reads, mosaic,
  cut and reprojection in one step), instead of a TiTiler picture capped at about 9 million
  pixels (which gave about 60 m on large areas). WaPOR scale factors are applied; very large areas
  (over 150 million pixels) are read coarser and the log says so. Cached clips from before are
  refreshed automatically.
- Raster legends show **value ranges** (e.g. 1,500–2,000 m), each with the colour at its middle,
  instead of single values; "and above" only where values go beyond the legend's maximum.
- Analysis backend restructured (no change in behaviour): analyses now live in
  `backend/analyses/<category>/<id>/` (was `backend/modules/<id>/`; the five existing ones are
  in `infrastructure/`, ids unchanged so past runs and evidence still open). The framework in
  `backend/apps/analysis/` is split into `core/` (registry, runner, errors, environment check),
  `data/` (datasets, OSM), `ops/` (raster, vector, inventory) and `render/` (map previews).
  The registry checks that each manifest's category matches its folder and that analysis ids
  are unique. Setting `MODULES_DIR` is now `ANALYSES_DIR`.
- Analyses → *Runs in this phase*: compact one-line rows (status, analysis, run number and
  date, a thin progress bar while running), newest first; the latest five are shown with
  *Show all*, and status filters (All, Done, Running, Failed) appear once there are more.
- Analyses are grouped in **eight broad categories** (terrain and site conditions; water resources;
  land, vegetation and agriculture; climate and natural hazards; people and socio-economics;
  infrastructure and services; site selection and planning; monitoring and impact). The 66
  analyses in the catalogue plan are listed as **Planned** under their category, each in the
  phases it serves (`backend/analyses/planned.yaml`, served as `planned` by
  `GET /api/analysis/modules/`). The five existing modules now sit in *Infrastructure and services*.
- The processing **Toolbox** moved from the Data Catalog to the project workspace, as its own
  tab after Analyses. It runs on the area of influence (no drawing needed); results go onto the
  project map and the Layers panel (opacity, legend, download, remove), with rasters shown cut
  to the area. The Data Catalog is now for browsing, inspecting and visualising data only.
  Code: `frontend/src/features/toolbox/` (engine, view, GeoTIFF rendering for MapLibre).
- Analyses → Analysis modules: each category is a collapsible section showing its module count
  (and how many are ready), replacing the category chips; *Recommended for this project*
  stays open and a search opens every section with matches.
- Deployment: the server copy lives at `/home/ecduser/isdb_geida` (was `geida_platform_react`
  in the docs and unit files). geida.terrawatch.net moves from the old template app
  (`isdb-geida`, `runserver` on :8011 in a screen) to this stack: Apache serves the React
  build, Gunicorn (`geida-api`, 127.0.0.1:8012) and Celery (`geida-worker`) run under systemd.
  On terrawatch the Apache site file is `geida-platform.conf`.
- Project workspace: the project bar above the map (code, status, title, actions) moved
  into the top of the side panel, so the map uses the full height of the page.
- The footer shows the GEIDA logo in place of the "GEIDA" text.
- The project Data catalog tab is merged into Analyses, which now has two views:
  *Analysis modules* and *Data layers* (the catalogue's rasters by section, cut to the area).
  The phase is picked first; each phase lists its own modules and data layers (a data
  layer's optional `phases` list in the catalogue; default all phases).
- Map export: overview maps draw the country boundary, and can show the province/region
  that holds the area instead of the whole country.
- Map export: new **Globe** overview: an orthographic globe centred on the project country,
  the country highlighted, a graticule and a marker for the project area, drawn as vectors.
  World outlines come from `GET /api/boundaries/world/` (GADM level 0, simplified, cached). Overview maps
  have a **Style** choice, *Globe (3D)* (the default, also for layouts saved earlier) or
  *2D map* (country, region or around the main map).

### Fixed
- Catchment from a point (0.2.0): a point clicked beside a stream gave a tiny catchment without explanation
  (e.g. 0.3 km² for a slope 1.2 km from a 313 km² river). New **Snap to** setting: the nearest stream (as before)
  or the largest stream within the snapping distance (now up to 5 km). When the outlet drains under 1 km², the
  summary and profile warn that it isn't on a stream and say where the nearest and the biggest streams are.
- An analysis run interrupted while it was cutting a raster (e.g. the worker restarting) left an empty file in
  the data cache, and every later run on that area failed with "not recognized as being in a supported file
  format". Raster clips and downloads (catalogue layers, WorldPop, tiled datasets, field boundaries) are now
  written to a temporary name and renamed when complete, and a damaged cached clip is read again.
- Satellite and Streets basemaps showed grey "Map data not yet available" tiles when zoomed in past Esri's
  imagery (zoom 17–18 in many rural areas). The tile URLs now ask Esri for an error instead of a placeholder
  (`blankTile=false`), so the maps keep showing the last available imagery, enlarged.
- Hydrology analyses (Stream network, Sub-catchments, Catchment) kept WhiteboxTools' intermediate rasters in the
  run folder (up to 4.3 GB per run); they now go to a temporary folder. Existing runs were cleaned (14 GB to
  under 1 GB on the development machine).
- Population counts read onto a finer run grid (e.g. 30 m, set by the DEM) were repeated in every
  cell instead of shared between them; totals are now kept on any grid.
- The hydrology flow cache now follows the DEM file itself (size and date), so a replaced DEM is
  never matched to an old flow result.
- `seed --boundaries` on PostgreSQL: loading full-resolution countries (adm0) in batches of
  500 sent one INSERT larger than PostgreSQL's 1 GB message limit and the connection was
  dropped. `load_admin_units` now also flushes a batch at 64 MB of geometry.
- Frontend build on a fresh clone: `npm run build` failed the type-check ("Cannot find module
  '@geolibre/embed'") because the package's `dist/` is git-ignored and was never built.
  `scripts/predev.mjs` now compiles it (always on build, when missing in dev).
- Data Catalog: the IsDB member countries layer (on by default) now draws; its file path
  pointed to a location the server doesn't serve.

### Added
- **Terrain analyses** (Preparation), on the Copernicus DEM GLO-30 in the area's UTM zone:
  **Slope and slope classes** (mean slope, steep share, six classes, per unit; degrees or
  percent), **Aspect** (eight directions and flat, main direction, south-facing share),
  **Hillshade and relief** (sun direction and height, vertical exaggeration; local relief per
  unit) and **Contours** (chosen or automatic interval, index contours, optional smoothing;
  map layer and GeoPackage). All five Terrain analyses read one cached DEM clip, so after the
  first run the others take seconds. Toolkit: `apps/analysis/ops/terrain.py`.
- Analysis framework, step 2 (data layer and raster outputs): the layer catalogue moved to
  `apps/analysis/data/catalog.py` and is shared by the Data Catalog and analyses; every layer
  with COGs behind it (elevation, WaPOR ET / precipitation / biomass / water productivity,
  land cover, surface water) is an analysis dataset, clipped to the area through the same
  service or from a local file. `ctx.raster()` reads inputs onto one UTM grid per run;
  `ctx.cached()` stores derived products; `ctx.add_raster()` produces a cloud-optimised
  GeoTIFF, a map preview, legend and statistics, shown on the project map and downloadable.
- First raster analysis: **Elevation profile** (Terrain, Preparation): lowest, mean and highest
  elevation, area by elevation band, per admin unit, and an elevation map (Copernicus DEM GLO-30).
- Analysis framework, step 1: a manifest schema (pydantic; errors name the file and field;
  a broken analysis is left out instead of breaking the catalogue); a check after every run
  that the declared outputs were produced; `limits.max_area_km2` and `requires` (engines)
  shown as *not available*; developer commands `new_analysis` (scaffold from
  `analyses/_template/`, prefilled from the planned list), `check_analyses` (with `--env`)
  and `run_analysis` (run without the queue); per-analysis tests with `AnalysisTestCase`,
  found by `manage.py test`. New dependency: pydantic.
- Documentation is published to GitHub Pages (<https://geonexa.github.io/isdb_geida/>) by the
  `Docs` GitHub Actions workflow on every push to `main` that changes the docs.
- **Field boundaries (Fields of The World, 2nd Edition)** in the Data Catalog (Agriculture)
  and in the project's Data layers: about 1.24 billion field polygons from Sentinel-2,
  yearly 2017–2025, CC BY 4.0. Read in the browser straight from the PMTiles archives on
  Source Cooperative (new catalogue kind `pmtiles`): field density (% of land in fields,
  on the Fields of The World app's magenta-to-green ramp) up to zoom 8, field polygons
  from zoom 9. On the project map the Layers panel
  adds a *minimum score* filter. Fields are drawn in full (not cut to the area) and have no
  GeoTIFF download.
- Layer display settings in the map's Layers panel: opacity for every layer; palette,
  reverse and value range for continuous data layers (`cmap` and `range` on the project
  tile endpoints); colour or palette, size and outline for analysis outputs; area outline
  and fill. Kept per project in the browser. (The basemap is picked with the button at the
  bottom left of the map; it has no row in the Layers panel.)

## 2026-11-09

### Added
- Documentation site (MkDocs, Material theme) in `docs/`: introduction, architecture,
  setup, deployment, development guides, changelog and update notes.
  [Update note](updates/2026-11-09.md)

### Changed
- Navbar shows the IsDB logo and the new GEIDA logo. The Terra and Expo City Dubai logos
  moved to the footer, on the left, as "Powered by".
- The documentation site uses the GEIDA logo.

## 2026-11-06

### Added
- View-only catalogue layers from open map services: NASA GIBS (NDVI, land surface
  temperature, GPW population), Terrascope (WorldCereal 2021), Esri (10 m land cover
  2017–2025, World Imagery Wayback). Marked "View only": no clip, download or analysis.
- Terrascope and terrestris services draw WorldCover, the DEM and hillshade below the
  zoom levels where the COG layers start.
- FAO WaPOR v3 layers: transpiration, evaporation, interception, reference ET, global
  biomass, gross and net biomass water productivity.

### Changed
- Raster layers are served as cloud-optimised GeoTIFFs read where their producers host
  them, drawn and cut by TiTiler (`TITILER_URL`).
  [Update note](updates/2026-11-06.md)
- ESA WorldCereal is offered as a view-only layer.

## 2026-11-05

### Changed
- The separate Indicators page was removed; indicators live in the project's Results tab.

## 2026-11-04

### Added
- Vector analysis helpers (`apps/analysis/vector.py`) on shapely 2, with distances and
  areas in an equal-area projection centred on each project area.
- Analysis categories as data (`backend/modules/categories.yaml`); the Analyses tab groups
  modules by category with filter chips.
- Vector run outputs drawn as points, lines or polygons, coloured by class or step.
- Analysis modules `area_profile`, `health_inventory` and `road_network`.
- Shared inventory outputs (`apps/analysis/inventory.py`).

### Changed
- `schools_inventory` 0.2 and `buildings` 0.2 use OpenStreetMap only, computed with
  vector operations.
- Raster modules (`area_baseline`, `terrain`, `school_access`) parked in
  `backend/modules/_parked/`; their past runs and evidence stay viewable.

## 2026-11-03

### Added
- Map layout editor for map export: maps with graticule and overview, legend, scale bar,
  north arrow, colour bar, text with fields, pictures, shapes; templates and saved
  templates; snapping; undo; SVG, PNG and PDF up to 600 dpi.
- Themed confirmation dialog and toasts, replacing the browser's `confirm` and `alert`.
- GDAL/PROJ start-up check (`geida.E001`) and a conda-forge-only `environment.yml`.

### Removed
- The GeoLibre print-engine bridge used by the first map export (superseded by the
  layout editor).

## 2026-11-02

### Added
- OpenStreetMap data layer: Geofabrik country extracts read with GDAL, per-area cache, tag
  taxonomy as data (`seeds/data/osm_taxonomy.yaml`, 16 layers), snapshot date per run,
  Overpass fallback.
- Project workspace map: basemaps shared with the Data Catalog, satellite layers clipped
  to the area of influence with GeoTIFF download, first map export.
- Idempotent `manage.py seed` command for reference data.

### Changed
- Repository restructured into `backend/`, `frontend/`, `docs/`, `deploy/`, with
  git-ignored `local/` and `cred/`. Settings split into base, development and production.
  [Update note](updates/2026-11-02.md)
- Conda environment renamed from `geida-react` to `geida`.

### Fixed
- An area crossing a national border no longer downloads a continent-sized OSM extract;
  the country containing the area's centre is used and the run is flagged *partial*.

## 2026-11-01

### Changed
- The GeoLibre GIS workspace is part of the GEIDA web app, mounted at `/analytics` (one
  Vite build, no iframe), with styles scoped between GEIDA and GeoLibre.

## October 2026

### Added
- React frontend and Django API split; Data Catalog (Geo-Portal) at `/geoportal`.
- Project onboarding: wizard, bulk import, submission-form import, CRI library (77
  indicators), review workflow (submit, publish, return with comment).
- GADM administrative boundaries, levels 0–3.
- Analysis module system: manifests and registry, availability per project, Celery +
  Redis queue, evidence accept/reject, open-data fetchers.
