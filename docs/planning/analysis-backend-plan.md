# GEIDA analysis backend: architecture plan

Status: draft for discussion · 11 November 2026 · not on the docs site (`docs/planning/` is excluded)

How the server will run the analyses in the catalogue plan
(`docs/planning/analysis-catalogue-plan.md`): one folder per analysis, a shared toolkit
underneath, and a runner that queues, executes and records every run. The aim is that
adding analysis number 70 is as easy as adding number 6, and every result can be
traced back to its data, parameters and code.

All work happens in the local project folder. Nothing is installed or changed on the
server until that is agreed separately.

---

## 1. Where we start from

GEIDA already has a working module framework (`backend/apps/analysis/`, `backend/modules/`):

| Piece | Today | Keep / change |
|---|---|---|
| One folder per module (`manifest.yaml` + `run.py`) | 5 modules, flat in `backend/modules/` | **Keep the idea**, group folders by category |
| Registry reads manifests, validates category, syncs `Module` rows | `registry.py` | Keep; add a schema and nested folders |
| `RunContext` (inputs, zones, outputs, evidence, log, progress) | `runner.py`, one class | Keep the API; split its helpers into a toolkit |
| Queue: Celery + Redis, one run at a time, time limits, redelivery | `tasks.py` | Keep; add queues by weight |
| Datasets: Copernicus DEM, WorldCover, WorldPop, OSM layers | `datasets/registry.py` | Unify with the Data Catalog (one source of truth) |
| Helpers: vector, raster, inventory | `vector.py`, `raster.py`, `inventory.py` | Move into toolkit packages |
| Outputs: metric, table, image (PNG), vector (GeoJSON), file | `runner.py` | Add raster (COG), chart, report text |
| Evidence for CRIs, phase-stamped | `Evidence` model | Keep |
| Planned analyses list | `modules/planned.yaml` | Keep |

What is missing for 60+ analyses: a folder structure that scales, a manifest schema,
one data layer shared with the Data Catalog, wrappers for GRASS / WhiteboxTools,
reusable algorithms (zonal statistics, terrain, hydrology, distance, change, multi-criteria),
caching of intermediate products, per-analysis tests, and developer commands.

## 2. Design principles

1. **An analysis is a folder.** Everything specific to it (description, inputs, parameters,
   code, legend, tests, method note) lives in its folder. Nothing outside it changes when an
   analysis is added.
2. **Thin analyses, rich toolkit.** `run.py` describes *what* to compute in a few dozen
   lines; the toolkit does the *how* (clipping, reprojection, zonal statistics, GRASS calls,
   previews). Algorithms written once, tested once, reused everywhere.
3. **Declarative first.** The manifest says what the analysis needs and produces; the
   platform builds the form, checks availability, filters by phase and validates inputs
   before anything runs.
4. **One data catalogue.** The Data Catalog (`apps/geoportal/catalog.py`) and analyses read
   the same dataset definitions, so a layer added for viewing is ready for analysis.
5. **Local metric grid.** Every run works in the area's UTM zone on an aligned grid, so
   areas, distances and pixel counts are correct.
6. **Reproducible.** Each run records dataset versions and dates, parameters, analysis
   version, engine versions and the code commit.
7. **Safe and bounded.** Area and pixel limits per analysis, time limits per queue,
   no shell strings (subprocess with argument lists), work in a per-run folder.
8. **Tested.** Each analysis ships tests on tiny synthetic data; a contract test checks
   every manifest.

## 3. Target layout

```
backend/
├── analyses/                          the catalogue: one folder per analysis (was modules/)
│   ├── categories.yaml                the 8 categories
│   ├── planned.yaml                   analyses not built yet
│   ├── _template/                     copied by `manage.py new_analysis`
│   ├── terrain/
│   │   ├── slope/
│   │   │   ├── manifest.yaml          identity, phases, inputs, parameters, outputs, limits
│   │   │   ├── run.py                 def run(ctx): …
│   │   │   ├── legend.yaml            classes / palette for map outputs (optional)
│   │   │   ├── METHOD.md              method, sources, limitations (shown in the app)
│   │   │   └── tests/
│   │   │       ├── test_slope.py
│   │   │       └── fixtures/          tiny DEM (e.g. 64 × 64 px)
│   │   ├── aspect/
│   │   └── contours/
│   ├── water/
│   │   ├── catchment/
│   │   └── water_balance/
│   ├── land/  hazards/  people/  infrastructure/  planning/  monitoring/
│   └── _parked/                       not listed (as today)
│
└── apps/analysis/                     the Django app: models, API, runner, toolkit
    ├── models.py  views.py  urls.py  tasks.py  admin.py
    ├── core/                          the framework
    │   ├── registry.py                discover analyses/*/*/manifest.yaml, sync Module rows
    │   ├── manifest.py                manifest schema (pydantic) and validation
    │   ├── context.py                 AnalysisContext: what run(ctx) works with
    │   ├── runner.py                  execute a run: prepare, call run(ctx), save, errors
    │   ├── outputs.py                 output types and how they are stored
    │   ├── evidence.py                CRI evidence proposals
    │   └── errors.py                  AnalysisError (user-facing), DataUnavailable
    ├── data/                          getting data for the area
    │   ├── catalog.py                 dataset definitions shared with the Data Catalog
    │   ├── cog.py                     COG read clipped to the area (rasterio / TiTiler)
    │   ├── stac.py                    STAC search and mosaics (Sentinel-2, MODIS)
    │   ├── parquet.py                 GeoParquet for the area (DuckDB: Overture, Open Buildings, FTW)
    │   ├── osm/                       OSM extracts (exists, moves here)
    │   ├── uploads.py                 project-uploaded national data
    │   └── cache.py                   dataset and derived-product cache
    ├── ops/                           reusable algorithms (pure functions, numpy / shapely)
    │   ├── grid.py                    UTM grid aligned to the area, area mask, resampling
    │   ├── raster.py                  clip, reproject, reclassify, stats (from raster.py)
    │   ├── vector.py                  frame, layers, nearest, within, grids (from vector.py)
    │   ├── zonal.py                   exact zonal statistics per area / admin unit
    │   ├── terrain.py                 slope, aspect, hillshade, contours, TPI / TRI
    │   ├── hydrology.py               fill, flow, accumulation, watershed, streams
    │   ├── distance.py                proximity, cost distance, travel time
    │   ├── timeseries.py              stacks, seasonal means, anomalies, trends
    │   ├── change.py                  two-date comparison, transition matrices
    │   ├── indices.py                 NDVI, EVI, SAVI, NDMI, NDWI with cloud masks
    │   ├── mcda.py                    rescale, weight (incl. AHP), constrain, combine, rank
    │   └── inventory.py               feature inventories by type and unit (exists)
    ├── engines/                       external tools behind one interface
    │   ├── gdal.py                    gdaldem, gdal_contour, warp, proximity
    │   ├── grass.py                   temporary GRASS project per run, run modules, export
    │   └── whitebox.py                WhiteboxTools (optional alternative)
    ├── render/                        map outputs
    │   ├── preview.py                 PNG previews and bounds for the map
    │   ├── legend.py                  legends from legend.yaml or classes
    │   └── styles.py                  vector styles (from the module styles today)
    └── management/commands/
        ├── new_analysis.py            scaffold analyses/<category>/<id>/ from _template
        ├── run_analysis.py            run one analysis for a project locally, without Celery
        ├── check_analyses.py          validate every manifest, legend and test folder
        └── sync_modules.py            (exists)
```

Notes:

- **Category from the folder.** `analyses/<category>/<id>/`; the manifest's `category` must
  match its parent folder, checked by the registry.
- **IDs stay global and stable.** Existing modules keep their ids
  (`area_profile`, `buildings`, `road_network`, `schools_inventory`, `health_inventory`), so
  past runs and evidence keep working. They move to `analyses/infrastructure/`.
- **No new top-level Python package.** The toolkit lives inside the existing `apps/analysis`
  app, split into packages; `analyses/` holds only analysis folders.

## 4. The analysis contract

### 4.1 Manifest (schema v2)

```yaml
id: slope
version: 1.0.0                      # semantic version; bump on any change to results
title: Slope and slope classes
question: How steep is the land, and how much of it falls in each slope class?
category: terrain                   # must match the parent folder
phases: [preparation]               # one or more of preparation, implementation, completion
themes: [infrastructure, agriculture, water]
cri: []                             # [{code: "2.2", role: verify | context}]

inputs:
  dem: {dataset: copernicus_dem_30, label: Elevation}     # a dataset id from data/catalog.py

parameters:
  - {name: units, type: choice, default: degrees, choices: [degrees, percent], label: Units}
  - {name: classes, type: number_list, default: [2, 5, 10, 15, 30], label: Class breaks}
  - {name: zone_level, type: zone_level, default: 2, label: Summarise by}

outputs:                            # what the run must produce (checked after the run)
  - {type: raster, name: slope, legend: legend.yaml}
  - {type: table, name: classes}
  - {type: table, name: per_zone}
  - {type: metric, name: mean_slope}

requires: [gdal]                    # engines: gdal, grass, whitebox
limits: {max_area_km2: 50000, max_pixels: 400_000_000}
queue: raster                       # light | raster | heavy
runtime: "under 1 minute for 10,000 km²"
citations: [Copernicus DEM GLO-30]
```

Validated by a pydantic model in `core/manifest.py` when the registry loads analyses and in
`check_analyses`; a bad manifest is reported with the file and field, and the analysis is
left out of the catalogue rather than breaking it.

### 4.2 run.py

```python
"""Slope and slope classes from the elevation model, per admin unit."""
from apps.analysis.ops import terrain, zonal


def run(ctx):
    dem = ctx.raster("dem")                       # clipped to the area, UTM, aligned grid
    ctx.progress(30)
    slope = terrain.slope(dem, units=ctx.params["units"])
    classes = zonal.classes(slope, ctx.params["classes"], mask=ctx.area_mask(dem))
    per_zone = zonal.stats(slope, ctx.zones(), ["mean", "max"])
    ctx.progress(80)

    ctx.add_raster("slope", "Slope", slope, legend="legend.yaml")
    ctx.add_table("classes", "Area by slope class", classes)
    ctx.add_table("per_zone", "Slope per admin unit", per_zone)
    ctx.add_metric("mean_slope", "Mean slope", round(float(slope.mean()), 1), ctx.params["units"])
    ctx.summary(f"Mean slope {slope.mean():.1f}°; {classes.share_above(15):.0%} of the area is steeper than 15°.")
```

An analysis only talks to `ctx` and the toolkit (`ops`, `engines`); it never opens database
connections, network sessions or file paths outside its work folder.

### 4.3 AnalysisContext (what `ctx` offers)

| Group | Methods | Notes |
|---|---|---|
| Area | `area`, `area_geojson`, `area_km2`, `iso3`, `phase`, `bbox(buffer_m)`, `area_mask(raster)` | As today, plus the phase |
| Grid | `grid(resolution_m)` | UTM grid aligned to the area, shared by all rasters in a run |
| Data | `raster(input, year=…)`, `vector(input)`, `stac(collection, period, bands)`, `table(input)`, `try_*` variants | From `data/`; records each dataset used |
| Zones | `zones(level)` | Admin units clipped to the area (exists) |
| Engines | `grass()`, `gdal`, `whitebox()` | GRASS session in the run folder, closed at the end |
| Earlier results | `previous(analysis_id, phase=…)` | Latest successful run, e.g. a baseline for change since baseline |
| Outputs | `add_raster`, `add_vector`, `add_table`, `add_metric`, `add_chart`, `add_file`, `summary` | Stored per run, shown on the map / in the result |
| Evidence | `propose_evidence(cri, …)` | Unchanged |
| Run | `params`, `log`, `progress`, `path(name)`, `cache` | As today |

## 5. Data layer

**One catalogue.** Dataset definitions move to `apps/analysis/data/catalog.py` and are read
by both the Data Catalog (viewing) and analyses (computing). Each dataset says:

| Field | Example |
|---|---|
| `id` | `copernicus_dem_30`, `wapor_eta_l1`, `chirps_annual`, `esa_worldcover`, `osm_roads`, `overture_buildings`, `ftw_fields` |
| `kind` | `cog`, `stac`, `parquet`, `osm`, `pmtiles`, `upload` |
| `source` | URL template / STAC collection / parquet path |
| `periods` | years, months, dates available |
| `units`, `scale`, `nodata`, `classes` | for correct values and legends |
| `citation`, `licence`, `version` | recorded with every run |
| `view` | Data Catalog display settings (palette, legend), when the layer is also viewable |

**Access paths** (all clipped to the area's bounding box plus a margin, cached):

| Kind | How | Library |
|---|---|---|
| COG | Windowed read at native resolution, reprojected to the run grid | rasterio (GDAL), or GEIDA's existing TiTiler clip |
| STAC | Search items by area and period, mosaic, cloud mask | pystac-client, rasterio / xarray |
| GeoParquet | Spatial filter on bounding box | DuckDB (spatial extension) |
| OSM | Geofabrik extracts (exists) | GDAL OSM driver |
| Upload | National data attached to the project | GDAL |

**Caching.** Two levels, both in `DATA_DIR/cache/` (local disk, size-capped, oldest removed
first): raw dataset clips (exists today) and **derived products** keyed by
dataset + area + parameters + code version (for example a conditioned DEM and flow
accumulation, reused by catchment, streams and runoff).

## 6. Engines

| Engine | Used for | How it runs |
|---|---|---|
| GDAL / rasterio | Clip, warp, slope / aspect / hillshade, contours, proximity, statistics | Python bindings and `gdal*` commands (argument lists) |
| GRASS GIS | Hydrology (`r.watershed`, `r.water.outlet`, `r.stream.*`), cost distance (`r.cost`, `r.walk`), landforms (`r.geomorphon`), viewshed, `r.mapcalc` | A temporary GRASS project in the run folder with the run's UTM CRS; inputs imported, modules run through `grass.script`, results exported as GeoTIFF; removed afterwards |
| WhiteboxTools | Alternative hydrology and terrain tools | `whitebox` Python package, run folder as working directory |
| NumPy / SciPy / shapely | Band maths, zonal statistics, classification, vector operations | Pure functions in `ops/` |

`engines/grass.py` hides the GRASS specifics behind calls such as
`g = ctx.grass(); g.import_raster(dem); g.run("r.watershed", elevation="dem", accumulation="acc", drainage="dir"); acc = g.export("acc")`.
Each engine reports its version into the run record, and `requires:` in the manifest lets the
catalogue mark an analysis *not available* when an engine is missing on a machine.

## 7. Outputs and storage

| Type | Stored as | Shown as |
|---|---|---|
| `raster` | Cloud-optimised GeoTIFF (values) + PNG preview + legend + statistics | Map layer with legend; GeoTIFF download; later served through TiTiler for full zoom |
| `vector` | GeoJSON (small) or FlatGeobuf (large) + style | Map layer, download |
| `table` | Rows in the run record + CSV | Table drawer, CSV download |
| `metric` | Value, unit, note | Result card |
| `chart` | Series data (time series, histogram, bars) | Chart in the result |
| `file` | Any file (e.g. contours GeoPackage) | Download |
| `summary` | Short text | Top of the result |

Files live in `MEDIA_ROOT/runs/<run id>/` (as today). After a run the runner checks that the
outputs declared in the manifest were produced, so a broken analysis fails clearly.

## 8. Running

**Queues by weight** (Celery routing from the manifest's `queue`):

| Queue | For | Time limit | Concurrency |
|---|---|---|---|
| `light` | Vector inventories, table joins | 10 min | several |
| `raster` | Clipping and raster maths, zonal statistics | 30 min | 2 |
| `heavy` | Hydrology, cost distance, time series, suitability | 60 min | 1 |

**Lifecycle:** queued → running (progress %) → done / failed / cancelled. Before queueing,
the API checks phase, availability, parameters and the area limit. Failures carry a clear
user message (`AnalysisError`), and the full traceback stays in the log for developers.
Cancelling a run stops it at the next progress update.

**Reproducibility:** each run stores the analysis id and version, parameters, datasets (id,
version, period, citation), engine versions and the git commit, and these are copied into
any evidence it proposes. Results can be re-run with the same inputs.

## 9. Developer workflow

```bash
# scaffold a new analysis from the template (manifest, run.py, METHOD.md, tests)
python manage.py new_analysis terrain slope

# validate every manifest, legend and test folder
python manage.py check_analyses

# run one analysis for a project on this machine, without the queue
python manage.py run_analysis slope --project ABDCSD --phase preparation --param units=percent

# tests: one analysis, or all
python manage.py test analyses.terrain.slope
python manage.py test apps.analysis
```

Adding an analysis = scaffold, write `run.py` against `ctx` and `ops`, add a small fixture
test, fill in `METHOD.md`, run `check_analyses`. If the id is in `planned.yaml`, the new
analysis replaces the planned card automatically.

**Testing levels:** toolkit unit tests (`ops/`, `engines/`) on synthetic arrays; one test per
analysis on fixtures with known answers (e.g. a tilted-plane DEM has a known slope); a
contract test over all manifests; a few end-to-end runs per category with cached data.

## 10. Migration (no behaviour change first)

| Step | Work | Done when |
|---|---|---|
| **0. Restructure** | Rename `modules/` → `analyses/<category>/<id>/`; move existing modules to `infrastructure/`; registry reads nested folders; split `runner.py`, `raster.py`, `vector.py`, `inventory.py` into `core/`, `ops/`, `render/` with the same behaviour | All 95 backend tests pass; existing runs and evidence still open |
| **1. Contract and tools** | Manifest schema (pydantic), `check_analyses`, `new_analysis` with `_template/`, `run_analysis`, per-analysis `tests/`, output check after run | A dummy analysis scaffolds, runs and tests locally |
| **2. Data layer** | `data/catalog.py` shared with the Data Catalog; `ctx.raster` over COGs on the run grid; derived-product cache; `add_raster` (COG + preview + legend) | The Data Catalog reads its layers from the shared catalogue; one raster output end to end |
| **3. First category: Terrain** | elevation profile, slope, aspect, hillshade, contours (GDAL) | Five terrain analyses ready in Preparation |
| **4. Zonal and time series** | `ops/zonal.py` (exactextract), `ops/timeseries.py`; Water accounting (precipitation, ETa, water balance) and Land (land cover composition and change) | Wave 1 water and land analyses ready |
| **5. GRASS engine** | `engines/grass.py`; catchment, stream network; `ops/distance.py` for access and travel time | Catchment delineation runs locally |
| **6. Queues and limits** | Celery routing by `queue`, per-queue time limits, area limits, cancellation | Heavy runs don't block light ones |

Steps 0–2 are groundwork; from step 3 each category is a batch of folders on the same base.

## 11. Local environment

Installed in the local `geida` conda environment only (the server is a separate decision):

| Package | For |
|---|---|
| pydantic | Manifest schema |
| geopandas, pyproj | Vector work and CRS handling |
| exactextract | Exact zonal statistics |
| pystac-client, xarray, rioxarray | STAC search, time series |
| duckdb (spatial) | GeoParquet reads |
| GRASS GIS 8 (already at `/usr/local/bin/grass`) | Hydrology, cost distance, landforms |
| whitebox (optional) | Alternative terrain / hydrology tools |

`apps/analysis/envcheck.py` grows into a full check (`check_analyses --env`) that lists
which engines and packages are present, so the catalogue marks analyses that can't run
on a given machine.

## 12. Decisions needed

1. Folder name: `backend/analyses/` (recommended) or keep `backend/modules/`.
2. Category sub-folders (`analyses/<category>/<id>/`) as proposed.
3. Manifest validation with pydantic (recommended) or JSON Schema.
4. Primary engine for hydrology and cost distance: GRASS GIS (recommended) or WhiteboxTools.
5. Raster outputs as COG served through TiTiler (full-resolution zoom) from the start, or PNG
   previews first and COG serving later.
6. Start with steps 0–2 (groundwork) before the first terrain analyses.
