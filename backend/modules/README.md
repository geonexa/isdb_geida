# GEIDA analysis modules

One folder per module. Adding an analysis = adding a folder; the platform core
doesn't change.

```
modules/<id>/
  manifest.yaml   what the module is, needs and produces (see below)
  run.py          def run(ctx): ...   (ctx = apps.analysis.runner.RunContext)
```

The platform reads the manifests (`python manage.py sync_modules`, also on every
module list request), lists modules by theme and phase, checks per project whether
a module is **ready / needs data / not available**, builds the input form from
`parameters`, and surfaces a module first when the project's Results Framework
uses one of its CRI codes.

Runs are queued (`ModuleRun`) on Celery + Redis and executed by the worker
(`python manage.py run_worker`, a shortcut for `celery -A config worker`).

## Modules

The catalogue is OpenStreetMap-only for now (spec: `docs/specs/osm-analysis-catalogue.md`).
Modules are grouped by the categories in `categories.yaml`; each manifest names one.

| id | category | question | data |
|---|---|---|---|
| `area_profile` | Area profile | What is mapped in the project area? | all OSM layers |
| `schools_inventory` | Social services | Which schools are mapped, by level and unit? (CRI 9.3 verify) | OSM schools |
| `health_inventory` | Social services | Which health facilities are mapped, by type and unit? (CRI 8.1 verify) | OSM health |
| `buildings` | Built environment | How many buildings, what kind, how dense? | OSM building footprints |
| `road_network` | Infrastructure networks | Road km by class and surface, density per unit (CRI 2.2 verify) | OSM roads |

**Parked** (`_parked/`, raster-based; back in Cycle 2 when rasters return via STAC/COG):
`area_baseline`, `terrain`, `school_access`. Folders starting with `_` aren't read by the
registry, so parked modules leave the catalogue; their past runs and evidence stay
viewable. Their tests run from `apps/analysis/tests_parked.py` (skipped without rasterio).

Output `name`s must be unique within a module (the map uses them as layer ids); a
run with repeated names fails with a clear error.

## Manifest

```yaml
id: school_access              # = folder name
version: 0.1.0
title: Population beyond walking distance of a school
question: How many people live more than 5 km from a school?
status: curated                # curated | experimental
category: access               # an id from categories.yaml
themes: [education]
phases: [preparation, implementation, completion]
cri:
  - {code: "9.1", role: estimate}
inputs:
  required:
    - {name: schools, type: vector_point, default: osm_schools, label: Schools}
    - {name: population, type: raster, default: worldpop_2020, label: Population}
parameters:
  - {name: threshold_m, type: number, default: 5000, min: 500, max: 50000, label: Distance threshold (m)}
outputs:
  - {type: table, name: per_zone}
citations: [OpenStreetMap, WorldPop 2020]
```

## ctx (what run.py gets)

| | |
|---|---|
| `ctx.params`, `ctx.area`, `ctx.area_geojson`, `ctx.area_km2`, `ctx.iso3`, `ctx.bbox(buffer_m)` | inputs |
| `ctx.dataset(name, bbox)` / `ctx.try_dataset(...)` | local file for a manifest input (downloaded and cached in `backend/data/cache/`) |
| `ctx.zones(level)` | admin units clipped to the area (GADM, from `apps.boundaries`) |
| `ctx.features(name, bbox)` / `ctx.try_features(...)` | a vector input as `vector.Layer` (geometry in metres, `ctx.frame`) |
| `ctx.vzones(level)` | `vector.Zones`: `assign()` features to units, `count()`, `measure()` km / km² per unit |
| `ctx.snapshot()` | OSM snapshot date(s) used so far, for summaries and evidence `reference_date` |
| `ctx.log()`, `ctx.progress(pct)` | shown live in the UI |
| `ctx.add_metric/add_table/add_image/add_vector/add_file`, `ctx.summary(text)` | results |
| `ctx.propose_evidence(cri, label, value, unit, role, caveats, reference_date)` | evidence records (users accept them; nothing is written into the Results Framework automatically) |
| `raise ModuleError("…")` | clear failure message for the user |

Helpers: `apps/analysis/vector.py` (shapely 2: equal-area projection around the area,
zone assignment, nearest, distance bands, lengths, density grid, GeoJSON/CSV writers)
and `apps/analysis/inventory.py` (the standard outputs of a facility inventory).

### Vector styles

`ctx.add_vector(name, title, file, style)`; points, lines and polygons are all drawn.

| key | |
|---|---|
| `color`, `radius`, `width`, `opacity` | single colour; point radius, line width (px), polygon fill opacity |
| `property` + `classes: [{value, color, label, radius?, width?}]` | colour by a feature property's value (legend lists the classes) |
| `property` + `steps: [{from, color, label}]` | colour by a numeric property (lowest `from` first) |

## Datasets

Registered in `backend/apps/analysis/datasets/registry.py`:

- **Rasters**: `copernicus_dem_30`, `esa_worldcover_2021`, `worldpop_2020` (used only by the parked modules).
- **OpenStreetMap**: one dataset per layer of `backend/seeds/data/osm_taxonomy.yaml`, named
  `osm_<layer>`: `osm_schools`, `osm_health`, `osm_markets`, `osm_worship`,
  `osm_public_services`, `osm_finance`, `osm_buildings`, `osm_places`, `osm_roads`,
  `osm_paths`, `osm_railways`, `osm_waterways`, `osm_water_bodies`, `osm_water_points`,
  `osm_power_lines`, `osm_power_assets`. Polygon layers also have `osm_<layer>_points`
  (one point on each surface) for counting and distances.

OSM layers come from the Geofabrik extract for the project's country (downloaded once
to `backend/data/osm/`, cut per area with GDAL, cached in `backend/data/cache/osm/`),
with the live Overpass API as fallback; see `apps/analysis/osm/`. The run records the
extract's snapshot date in its datasets list, so evidence names the exact OSM state.
To change what a layer contains, edit the taxonomy file, not module code.

Put a file in `backend/data/datasets/<dataset id>/<ISO3>.tif` (or `.geojson`) to use
local data instead of downloading (e.g. the Moroto course data, or census-adjusted population).

Tests: `apps/analysis/tests.py` runs every catalogue module on a small offline fixture
(two admin units, local GeoJSON layers) and checks that per-unit numbers add up to the
area totals. Moroto acceptance values apply to the parked raster modules (C2.5).
