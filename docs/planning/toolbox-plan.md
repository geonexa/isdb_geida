# Toolbox: saved data-processing tools, and deleting results

Status: built (12 Nov 2026), all steps of §6. Decisions taken: server only (no browser engine); owner and
reviewers delete; a curated list of 186 tools (not all 1,065). User guide: [Toolbox](../introduction/toolbox.md).

What changed from the plan while building:
- GeoLibre's GeoPackage and FlatGeobuf files don't always survive a round trip with GDAL, so inputs go to the
  engine as GeoPackage (written by GDAL, plain layer names) and vector outputs come back as GeoJSON (lon/lat).
- The engine's `dissolve` returns no features and its `zonal_statistics` needs a zones raster: GEIDA's own
  **Dissolve** and **Zonal statistics by polygon** (Python) replace them in the list.
- Some manifests describe value parameters as raster inputs; `catalog.PARAM_OVERRIDES` corrects them.
- Point and line tools refuse multi-part layers, so inputs keep their own geometry type.
- Rasters given to one run are aligned to the first one's grid.
- Each run is stopped after `TOOLBOX_TIME_LIMIT` (600 s): the engine's buffer is very slow on detailed polygons.
- Not done: Toolbox results as inputs to analyses (only to other tools); listing dependent runs before a delete.


## 1. The split

| Section | What it holds | Examples |
|---|---|---|
| **Analyses** | Answers to project questions: a documented method, defaults set for the purpose, tests, metrics, tables, maps, evidence for CRIs | Slope, aspect, hillshade, contours, stream network, sub-catchments, catchment, land cover, population… |
| **Toolbox** | General GIS processing on the project's data: the user chooses the inputs and settings; one result layer (or table) per tool | Buffer, clip, merge, dissolve, intersect, zonal statistics, reclassify, raster to polygons, measurements |

The terrain and hydrology tools now in the Toolbox (`slope`, `aspect`, `hillshade`, `contours_from_raster`,
`fill_depressions`, `d8_pointer`, `d8_flow_accum`, `extract_streams`, `watershed`) are removed from it: the
matching analyses do the same job, saved and reviewable.

## 2. Where the Toolbox should run: server, with the same GeoLibre engine

Today the Toolbox runs GeoLibre (whitebox_next_gen in Rust, compiled to WebAssembly) **in the browser**. The
server cuts the input layer to the area (at most about 9 million pixels, so large areas get coarser) and
sends it to the browser. Results stay in browser memory and are lost on reload.

| | Browser (WebAssembly, today) | **Server (recommended)** |
|---|---|---|
| Results saved, shared, deletable | No (would need uploading the result afterwards) | **Yes**, stored like analysis runs |
| Input data | Cut and downloaded to the browser; coarser for large areas | Read on the server at full resolution (COGs, OSM layers, analysis outputs) |
| Data size | WebAssembly limit about 4 GB of memory, single thread; the user's laptop | Server memory and CPU; heavy tools on the heavy queue |
| Inputs from other results | Only what is open in this tab | Any saved analysis output or Toolbox result in the project |
| Reproducible (tool, version, settings, inputs recorded) | No | **Yes** |
| Speed | Instant for small data, no queue | A few seconds of queue and transfer for small jobs |
| Page weight | About 31 MB of WebAssembly downloaded the first time | Nothing extra in the browser |
| Server load | None | Yes (limits per tool and per user) |

**Recommendation: run the Toolbox on the server, using the same GeoLibre engine.** The engine is a WASI
program (`geolibre-cli.wasm`, MIT), so the server can run it unchanged with **wasmtime** (a Python package,
no compiling). The tool ids, settings and parameter descriptions stay the same as in the browser today.
If WebAssembly's 4 GB or single thread become limiting, the same Rust code (opengeos/geolibre-rust) can be
built as a native Linux program later, with no changes to GEIDA.

Why GeoLibre on the server rather than Python libraries (geopandas, shapely, rasterio):

- **1,065 tools with machine-readable manifests:** each tool's parameters, types and defaults come with
  it, so the run form is generated, not written by hand per tool. Adding a tool to the Toolbox is one line.
- **The tools on your list all exist:** see §3.
- **Python stays for Analyses**, where each method is written and tested for its purpose.

Python only wraps the engine: it prepares inputs (cut to the area, in the area's UTM zone), runs the tool,
stores outputs with statistics, styles them and records the run.

## 3. Proposed Toolbox (GeoLibre ids)

**Vector: overlay**
`clip`, `intersect`, `union`, `difference`, `erase`, `symmetrical_difference`, `spatial_join`, `select_by_location`

**Vector: geometry**
`buffer_vector`, `multiple_ring_buffer`, `dissolve`, `merge_vectors`, `centroid_vector`, `minimum_convex_hull`,
`simplify_features`, `voronoi_diagram`, `split_by_attributes`, `reproject_vector`

**Vector: measure and summarise**
`add_geometry_attributes` (area, length, perimeter), `polygon_area`, `polygon_perimeter`, `near`,
`generate_near_table`, `count_overlapping_features`, `vector_summary_statistics`, `summarize_nearby`

**Vector: grids and sampling**
`hexagonal_grid_from_vector_base`, `rectangular_grid_from_vector_base`, `random_points_in_polygon`

**Attributes**
`extract_by_attribute`, `field_calculator`, `join_tables`

**Raster: statistics**
`raster_summary_stats` (min, max, mean, standard deviation and count of the area), `zonal_statistics`
(per polygon: mean, min, max, median, sum…), `zonal_histogram` (class areas per polygon),
`extract_raster_values_at_points`

**Raster: reclassify, mask, calculate**
`reclass`, `reclass_equal_interval`, `clip_raster_to_polygon`, `erase_polygon_from_raster`, `raster_calculator`

**Raster: convert and resample**
`raster_to_vector_polygons`, `raster_to_vector_points`, `vector_points_to_raster`, `vector_lines_to_raster`,
`resample`, `reproject_raster`, `mosaic`

**Raster: distance**
`euclidean_distance`, `cost_distance`

That is about 50 tools, all with "open" licences in GeoLibre. "Show all tools" can stay for the other
1,000 (engine manifests), behind an "advanced" switch.

**Inputs a tool can take:**
- the area of influence and admin units;
- Data Catalog rasters (read on the server for the area, any year);
- OSM layers (schools, roads, health…);
- outputs of saved analysis runs and of earlier Toolbox runs;
- uploaded files (GeoJSON, KML/KMZ, GeoPackage, zipped shapefile, GeoTIFF), kept with the project.

## 4. Saving and deleting results

### Toolbox runs

New table `ToolRun`:
- project, user, tool id, engine version;
- name (editable), settings, inputs (references to layers, runs or uploads);
- status, log, outputs (files, type, style, statistics), created and finished times.

Files go in `media/tools/<id>/`. Runs are queued like analyses (light queue by default) and listed under the
Toolbox: name, tool, date, who made it, size.

Each result can be:
- shown on the map, styled, and downloaded (GeoJSON, GeoPackage, GeoTIFF, CSV);
- used as input to another tool;
- renamed;
- deleted.

### Deleting (Toolbox runs and analysis runs)

| Rule | Why |
|---|---|
| The person who made a run, or a reviewer, can delete it | Same rule as deleting a draft project |
| Confirmation shows what goes: files, map layers, size | No surprises |
| **Analysis runs with accepted evidence can't be deleted**; reject the evidence first (reviewers) | Accepted evidence is the project's record |
| Proposed or rejected evidence is deleted with its run | Already how the database links them |
| Files are removed from disk at once; the project's Activity log records "deleted run #124 (Catchment from a point)" with who and when | Frees storage, keeps an audit trail |
| Select several runs and delete them together | Clearing old test runs |
| Results others use as inputs: the dependent Toolbox runs are listed in the confirmation | Avoids broken chains |

Analysis runs have no delete today (only cancelling a queued run).

## 5. Fix first: hydrology runs keep their working files

Catchment, Stream network and Sub-catchments keep WhiteboxTools' intermediate rasters in the run folder
(`hydro*`). One Daykundi catchment run uses **4.3 GB**, and the 130 runs on this machine take **14 GB**. Only
a few MB are outputs. Fix: write intermediates to a temporary folder deleted at the end of the run (the
cached flow in `.cache` is unaffected), and remove the `hydro*` folders from existing runs.

## 6. Build order

| Step | Content | Size |
|---|---|---|
| 0 | Hydrology working files to a temporary folder; clean existing runs | S |
| 1 | Delete analysis runs (rules above, Activity log, bulk) | S |
| 2 | Server Toolbox engine: wasmtime + `geolibre-cli.wasm`, input preparation, `ToolRun`, queue | M |
| 3 | Toolbox page: the curated list (§3), forms generated from manifests, inputs from the project, runs list with map, download, rename, delete | M |
| 4 | Uploads kept with the project; results as inputs to tools and analyses | M |
| 5 | Remove the browser engine (31 MB) once the server path covers the curated tools | S |

## 7. Decisions needed

1. Server Toolbox with GeoLibre via wasmtime (recommended), or keep the browser engine for quick previews too.
2. The curated list in §3: add or remove tools.
3. Who can delete: owner and reviewers (recommended), or reviewers only.
4. Whether "Show all tools" (1,000+) stays visible to everyone or only to analysts.
