# Toolbox

The Toolbox (a project's **Toolbox** tab) holds general GIS processing tools for vector and raster data:
buffer, clip, intersect, dissolve, zonal statistics, reclassify, raster to polygons, distances, grids,
interpolation and more. You choose the inputs and settings; each run gives one or more result layers or
tables. **Analyses** answer project questions with a documented method (slope, catchments, land cover,
population…); the Toolbox is for the processing in between. See [Analyses](../analyses/index.md).

| | Analyses | Toolbox |
|---|---|---|
| Purpose | Answer a project question (method, defaults, tests) | General processing you configure |
| Where it runs | Server (queued) | Server (queued) |
| Saved | Yes, each run with settings, data and log | Yes, each run with settings, inputs and log |
| Evidence for CRIs | Yes, proposed for review | No |
| Delete | Owner of the run or a reviewer (not if it has accepted evidence) | Owner of the run or a reviewer |

## Tools

186 tools in 16 categories, chosen from the 1,065 of the GeoLibre engine:

| Category | Examples |
|---|---|
| Vector: overlay | Clip, intersect, union, difference, erase, spatial join, select by location |
| Vector: geometry | Buffer, multiple ring buffer, dissolve, merge, centroid, convex hull, simplify, Voronoi |
| Vector: measure and summarise | Area, length and perimeter, near / near table, summary statistics |
| Attributes and tables | Select by attribute, field calculator, add / rename / delete fields, join tables |
| Grids and sampling | Hexagon and square grids, hex binning, random and balanced sample points |
| Spatial statistics | Hot spots (Getis-Ord Gi*), Moran's I, nearest neighbour index, clustering |
| Networks and routing | Shortest path, service areas, closest facility, connected components |
| Raster: statistics | **Zonal statistics by polygon**, raster statistics, zonal histogram, cross tabulation, values at points |
| Raster: calculate and overlay | Raster calculator, add / subtract / multiply / divide, weighted overlay and sum |
| Raster: reclassify and mask | Reclassify, equal intervals, clip raster to polygons, erase, majority filter |
| Convert, resample and reproject | Raster to polygons / points / lines, points or lines to raster, resample, mosaic |
| Distance and cost | Euclidean distance and allocation, cost distance and pathway |
| Neighbourhood and filters | Focal and block statistics, mean / median filters, line density |
| Interpolation and density | IDW, natural neighbour, kriging, TIN, heat map |
| Classification and change | k-means, random forest, minimum distance, change detection |
| Visibility | Viewshed, visibility index |

Terrain and hydrology tools (slope, aspect, hillshade, contours, flow, streams, watersheds) are not in the
Toolbox: the matching analyses do the same job, saved and reviewable.

## Using a tool

1. **Tools**: search or open a category, pick a tool. The form is built from the tool's own description:
   layers to pick, values to type (with the engine's defaults), optional settings behind "Show optional settings".
2. **Inputs** can be:
   - the area of influence and its admin units (levels 1–3, cut to the area);
   - Data Catalog rasters, with a year where the layer has several;
   - OpenStreetMap layers (schools, roads, health facilities, rivers…);
   - results of analysis runs (vector and raster outputs);
   - results of earlier Toolbox runs, so tools can be chained;
   - files added under **Files**.

   Inputs are taken for the extent of the area of influence (its bounding box plus 1 km) and put in its UTM
   zone, so distances and areas are in metres. Use Clip to keep only what is inside the area. When a tool
   combines several rasters, they are aligned to the first one's grid automatically.
3. **Run**: the run is queued on the server and appears under **Results**.

## Results

Each result shows its tool, date, who ran it and its size. Open it to:

- show each layer on the map (eye button) and set its opacity in the Layers panel;
- download vectors as GeoPackage or GeoJSON, rasters as GeoTIFF, tables as CSV;
- see figures the tool reports (e.g. raster statistics) and a preview of tables;
- rename it, see the run log, or delete it.

**Select** deletes several results at once. Deleting removes the files and is recorded in the project's
Activity log; results made from a deleted result are kept.

## Files

**Files** keeps files you add for the Toolbox: GeoJSON, GeoPackage, KML/KMZ, zipped shapefile, FlatGeobuf,
GeoTIFF or CSV, up to 200 MB each. They are kept with the project until deleted (by the person who added
them or a reviewer).

## Who can do what

| Action | Who |
|---|---|
| See tools and results | Anyone who can open the project |
| Run tools, add files | The project's owner, editors and reviewers |
| Rename or delete a result, delete a file | The person who made it, or a reviewer |

## How it works

The tools are GeoLibre's (whitebox_next_gen in Rust plus GeoLibre's own tools, MIT licence), compiled to a
single WebAssembly program, `geolibre-cli.wasm`. The server runs it with **wasmtime** in the analysis worker,
in a temporary folder per run; GEIDA prepares the inputs (cut, reprojected, as GeoPackage and GeoTIFF), and keeps
the outputs (GeoPackage + GeoJSON for vectors, GeoTIFF + PNG preview and legend for rasters, CSV for tables).
A few tools are GEIDA's own, in Python: **Zonal statistics by polygon** and **Dissolve** (the engine's dissolve
returns no features in version 1.7.1).

- Code: `backend/apps/toolbox/` (engine, catalogue, inputs, runner, API) and `frontend/src/features/toolbox/`.
- Records: `ToolRun` and `ToolUpload` tables; files in `media/tools/<run id>/` and `media/tools/uploads/<id>/`.
- A run is stopped after 10 minutes (`TOOLBOX_TIME_LIMIT`). Some engine tools are slow on very detailed
  polygons (e.g. buffering district boundaries); simplify them first.
- The tool list and its corrections to the engine's descriptions are in `backend/apps/toolbox/catalog.py`.
  To add a tool, add its id to a category there; the form is built automatically.

Settings: [Configuration](../setup/configuration.md) (`GEOLIBRE_WASM`, `TOOLBOX_TIME_LIMIT`).
