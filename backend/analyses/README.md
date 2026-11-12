# GEIDA analyses

One folder per analysis, grouped by category. Adding an analysis = adding a folder;
the platform core doesn't change.

```
analyses/<category>/<id>/
  manifest.yaml   what the analysis is, needs and produces (see below)
  run.py          def run(ctx): ...   (ctx = apps.analysis.core.runner.RunContext)
```

- `<category>` is an id from `categories.yaml`; the manifest's `category` must match it.
- `<id>` is unique across all categories and never changes (runs and evidence use it).
- Folders starting with `_` are skipped (`_parked/`, later `_template/`).
- New analysis: `python manage.py new_analysis <category> <id>` (from `_template/`);
  check with `check_analyses`, run with `run_analysis <id> --project <CODE>`, test with
  `python manage.py test analyses.<category>.<id>`.
- Documentation: write `METHOD.md` (method, data, outputs, limitations), then
  `python manage.py document_analyses` rewrites the analysis pages in `docs/analyses/`.
- Shared code: `apps.analysis.ops` (raster, vector, inventory), `apps.analysis.data`
  (datasets, OSM), `apps.analysis.render` (map previews), `apps.analysis.core.errors`
  (`AnalysisError` for messages shown to the user).

The platform reads the manifests (`python manage.py sync_modules`, also on every
module list request), lists modules by theme and phase, checks per project whether
a module is **ready / needs data / not available**, builds the input form from
`parameters`, and surfaces a module first when the project's Results Framework
uses one of its CRI codes.

Runs are queued (`ModuleRun`) on Celery + Redis and executed by the worker
(`python manage.py run_worker`, a shortcut for `celery -A config worker`).

## Modules

The catalogue is OpenStreetMap-only for now (spec: `docs/specs/osm-analysis-catalogue.md`).
Modules are grouped by the eight categories in `categories.yaml`; each manifest names one.
Analyses not built yet are listed in `planned.yaml` (id, title, question, category, phases) and
show as "Planned" in the Analyses tab; a module with the same id replaces its entry.
Plan: `docs/planning/analysis-catalogue-plan.md`.

| id | category | question | data |
|---|---|---|---|
| `area_profile` | Infrastructure and services | What is mapped in the project area? | all OSM layers |
| `schools_inventory` | Infrastructure and services | Which schools are mapped, by level and unit? (CRI 9.3 verify) | OSM schools |
| `health_inventory` | Infrastructure and services | Which health facilities are mapped, by type and unit? (CRI 8.1 verify) | OSM health |
| `buildings` | Infrastructure and services | How many buildings, what kind, how dense? | OSM building footprints |
| `road_network` | Infrastructure and services | Road km by class and surface, density per unit (CRI 2.2 verify) | OSM roads |

**Parked** (`_parked/`): `terrain` (superseded by the terrain analyses). `area_baseline` and
`school_access` were removed (replaced by Population, Slope, Land cover and Access to services). Folders starting with `_` aren't read by the
registry, so parked modules leave the catalogue; their past runs and evidence stay
viewable. Their tests run from `apps/analysis/tests_parked.py` (skipped without rasterio).

Output `name`s must be unique within a module (the map uses them as layer ids); a
run with repeated names fails with a clear error.

## Manifest

Validated by the schema in `apps/analysis/core/manifest.py` (pydantic) when analyses load
and by `python manage.py check_analyses`; errors name the file and field, and a broken
analysis is left out of the catalogue instead of breaking it. Besides the fields below:
`requires: [gdal | grass | whitebox]` (marked *not available* where an engine is missing),
`limits: {max_area_km2: …}` (larger areas are *not available*), `queue: light | raster | heavy`,
`runtime`, and per output `optional: true` or a family name such as `layer_*`.
Every non-optional output must be produced by each run.

```yaml
id: school_reach               # = folder name (example)
version: 0.1.0
title: Population beyond walking distance of a school
question: How many people live more than 5 km from a school?
status: curated                # curated | experimental
category: people               # an id from categories.yaml
themes: [education]
phases: [preparation, implementation, completion]
cri:
  - {code: "9.1", role: estimate}
inputs:
  required:
    - {name: schools, type: vector_point, default: osm_schools, label: Schools}
    - {name: population, type: raster, default: worldpop, label: Population}
parameters:
  - {name: threshold_m, type: number, default: 5000, min: 500, max: 50000, label: Distance threshold (m)}
outputs:
  - {type: table, name: per_zone}
citations: [OpenStreetMap, WorldPop R2025A]
```

Parameter types: `number` (with `min` / `max`), `choice` (with `choices`), `text`, `boolean`,
`point` and `criteria`. A `point` is a location the user picks on the project map in the run form (each click
moves the marker; longitude, latitude can also be typed), stored as `[lon, lat]`. With
`default: null` it is required. It must lie inside the area of influence or within 10 km of it
(a dam or bridge just downstream). In `run.py`, `lon, lat = ctx.point("outlet")`. On the command
line: `--param outlet=34.25,2.31`.

A `criteria` parameter is a list of conditions the user builds in the run form (site suitability): it lists
the `layers` the conditions can use (`{id, label, kind: range | classes, unit, group, classes}`), and each
condition is `{layer, min, max, classes, weight, must}`. The run form shows an editor (layer, limits or
classes, weight, must-have); the API and `run.py` check it with `apps.analysis.core.manifest.parse_criteria`.
See `analyses/planning/suitability/`.

## ctx (what run.py gets)

| | |
|---|---|
| `ctx.params`, `ctx.area`, `ctx.area_geojson`, `ctx.area_km2`, `ctx.iso3`, `ctx.bbox(buffer_m)` | inputs |
| `ctx.point(name)` | a `point` parameter as `(lon, lat)`; a clear error if it is missing |
| `ctx.dataset(name, bbox)` / `ctx.try_dataset(...)` | local file for a manifest input (downloaded and cached in `DATA_DIR/<dataset>/`) |
| `ctx.zones(level)` | admin units clipped to the area (GADM, from `apps.boundaries`) |
| `ctx.features(name, bbox)` / `ctx.try_features(...)` | a vector input as `vector.Layer` (geometry in metres, `ctx.frame`) |
| `ctx.vzones(level)` | `vector.Zones`: `assign()` features to units, `count()`, `measure()` km / km² per unit |
| `ctx.snapshot()` | OSM snapshot date(s) used so far, for summaries and evidence `reference_date` |
| `ctx.log()`, `ctx.progress(pct)` | shown live in the UI |
| `ctx.raster(name, year=None, buffer_m=0)` | a raster input clipped to the area as a `Raster` (float32, NaN = no data) on the **run grid**: the area's UTM zone, set by the first raster read; later rasters are resampled onto it. Catalogue layers (`elevation`, `eta`, `precipitation`, `landcover`, …) are read for `year`, at native resolution, straight from their COGs (GDAL range reads) |
| `ctx.grid`, `ctx.epsg`, `ctx.area_mask(raster)`, `ctx.area_in(epsg)`, `ctx.zone_masks(raster, level)` | the run grid, its UTM zone, the area (and admin units) as pixel masks or GeoJSON in that zone |
| `ctx.cached(name, parts, compute)` | a derived raster from the cache (`data/cache/derived/`), or `compute()` it and store it; `parts` lists what it depends on |
| `ctx.add_raster(name, title, raster, legend=None, unit="")` | a raster result: values as a cloud-optimised GeoTIFF (download), a PNG preview on the map, legend (a dict, a file such as `legend.yaml`, or a ramp from the data) and statistics inside the area. Ramp legends are shown as value ranges with readable bounds; `open_max: true` adds a "max and above" row |
| `ctx.add_metric/add_table/add_image/add_vector/add_file`, `ctx.summary(text)` | results |
| `ctx.propose_evidence(cri, label, value, unit, role, caveats, reference_date)` | evidence records (users accept them; nothing is written into the Results Framework automatically) |
| `raise AnalysisError("…")` | clear failure message for the user (`apps.analysis.core.errors`) |

Helpers: `apps/analysis/ops/grid.py` (`Raster`, `Grid`, `read`, `write`, `reproject`),
`apps/analysis/render/legend.py` (ramp and classes legends, colours),
`apps/analysis/ops/vector.py` (shapely 2: equal-area projection around the area,
zone assignment, nearest, distance bands, lengths, density grid, GeoJSON/CSV writers)
and `apps/analysis/ops/inventory.py` (the standard outputs of a facility inventory).

### Vector styles

`ctx.add_vector(name, title, file, style)`; points, lines and polygons are all drawn.

| key | |
|---|---|
| `color`, `radius`, `width`, `opacity` | single colour; point radius, line width (px), polygon fill opacity |
| `property` + `classes: [{value, color, label, radius?, width?}]` | colour by a feature property's value (legend lists the classes) |
| `property` + `steps: [{from, color, label}]` | colour by a numeric property (lowest `from` first) |

## Datasets

Registered in `backend/apps/analysis/data/registry.py`:

- **Rasters**: every Data Catalog layer with files (`elevation`, `landcover`, `eta`, `biomass-global`, …), `copernicus_dem_30`,
  `esa_worldcover_2021`; land (`lulc_annual`, `hansen_*`, `ftw_fields_*`) and people (`worldpop`, `worldpop_<age group>`,
  `ghsl_pop`, `ghsl_smod`, `ghsl_built`, `map_tt_*`) datasets in `data/land.py` and `data/people.py`.
- **OpenStreetMap**: one dataset per layer of `geida_static_data/OSM_Taxonomy/osm_taxonomy.yaml`, named
  `osm_<layer>`: `osm_schools`, `osm_health`, `osm_markets`, `osm_worship`,
  `osm_public_services`, `osm_finance`, `osm_buildings`, `osm_places`, `osm_roads`,
  `osm_paths`, `osm_railways`, `osm_waterways`, `osm_water_bodies`, `osm_water_points`,
  `osm_power_lines`, `osm_power_assets`. Polygon layers also have `osm_<layer>_points`
  (one point on each surface) for counting and distances.

OSM layers come from the Geofabrik extract for the project's country (downloaded once
to `DATA_DIR/osm/`, cut per area with GDAL, cached in `DATA_DIR/osm/`),
with the live Overpass API as fallback; see `apps/analysis/data/osm/`. The run records the
extract's snapshot date in its datasets list, so evidence names the exact OSM state.
To change what a layer contains, edit the taxonomy file, not module code.

Put a file in `DATA_DIR/datasets/<dataset id>/<ISO3>.tif` (or `.geojson`) to use
local data instead of downloading (e.g. the Moroto course data, or census-adjusted population).

Tests: `apps/analysis/tests.py` runs every catalogue module on a small offline fixture
(two admin units, local GeoJSON layers) and checks that per-unit numbers add up to the
area totals. Moroto acceptance values apply to the parked raster modules (C2.5).
