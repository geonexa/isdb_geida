# Changelog

All notable changes to GEIDA, newest first. Each release is identified by its date.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/): changes are
grouped as **Added**, **Changed**, **Fixed**, **Removed** and **Security**.

Releases that need action from administrators have an [Update note](updates/index.md).
How to add an entry: [Maintaining the documentation](development/documentation.md#recording-a-change).

## Unreleased

Changes merged but not yet deployed go here, then move under a dated heading at release.

### Changed
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
  World outlines come from `GET /api/boundaries/world/` (GADM level 0, simplified, cached). It is the default for
  new overview maps and templates; saved layouts keep their own setting.

### Fixed
- Frontend build on a fresh clone: `npm run build` failed the type-check ("Cannot find module
  '@geolibre/embed'") because the package's `dist/` is git-ignored and was never built.
  `scripts/predev.mjs` now compiles it (always on build, when missing in dev).
- Data Catalog: the IsDB member countries layer (on by default) now draws; its file path
  pointed to a location the server doesn't serve.

### Added
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
  and fill; basemap on/off and background colour. Kept per project in the browser.

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
