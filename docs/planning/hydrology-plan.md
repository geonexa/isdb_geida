# Hydrology from the DEM: watershed delineation, streams, sub-catchments

Status: all four steps built (2026-11-12). Engine: **WhiteboxTools** (GRASS was benchmarked and dropped, see §5). Category `water`. Detail of wave 2 of
[water-resources-plan.md](water-resources-plan.md) (analyses 7, 8, 9), brought forward.
Everything here runs on the Copernicus DEM (30 m, already read in place); HydroATLAS is
optional and only improves results once it is uploaded.

## 1. Analyses

| # | Analysis (id) | Answers | Phases | Needs |
|---|---|---|---|---|
| H1 | Stream network and order (`stream_network`) | Where streams run, km per Strahler order, drainage density per admin unit; compared with OSM waterways | P | DEM, WhiteboxTools |
| H2 | Sub-catchments in the area (`sub_basins`) | The drainage units the area splits into, their size, slope and outlets; where water leaves the area | P | DEM, WhiteboxTools |
| H3 | Catchment from a point (`catchment`) | Which land drains to a chosen point (a dam, intake, bridge, road crossing), how big, how steep | P | DEM, WhiteboxTools, a point on the map |
| later | Height above nearest drainage (HAND), wetness index | Low-lying, flood-prone land near streams | P, I | H1 (hazards category) |

## 2. Method

1. **DEM clip with a margin.** Catchments extend beyond the area: the DEM is read for the
   area plus a margin (default 5 km) in the area's UTM zone at 30 m (`ctx.raster`, cached).
2. **WhiteboxTools** (`apps/analysis/engines/whitebox.py`, the `whitebox` Python package; MIT): one
   small executable, called in-process, no separate GIS install. The DEM is conditioned by least-cost
   breaching of depressions (Lindsay 2016) with filling of what remains, then D8 flow direction and
   accumulation (`BreachDepressionsLeastCost`, `D8Pointer`, `D8FlowAccumulation`). Cached per DEM
   clip, so the three analyses share it.
3. **Streams (H1).** `ExtractStreams` where upstream area exceeds a threshold (default 1 km²),
   `StrahlerStreamOrder`, `RasterStreamsToVector` (one line per link with its order); km per order,
   drainage density per admin unit; OSM waterways length alongside.
4. **Sub-catchments (H2).** `Subbasins` on streams above a size (units cut at confluences; units under
   a fifth of that size merged downstream), vectorised and clipped to the area: area, mean slope, elevation range, outlet point; plus the outlets where
   streams leave the area.
5. **Catchment (H3).** The outlet moves onto the nearest stream of 1 km² or more (default 300 m,
   Jenson 1991, done in numpy, then onto the largest stream within two cells), then `Watershed`.
   If the catchment touches the clip edge, the clip doubles on each side it reaches, up to a maximum
   (default 25,000 km²; 90 m beyond 45,000 km² of clip); beyond it the run says so (later:
   HydroBASINS). Profile: area, elevation and slope, longest flow path and Kirpich time of
   concentration, streams. Rainfall, ETa, land cover and people were left out (decision 12 Nov
   2026): the analysis does the delineation only, from the DEM alone.

## 3. Framework and app additions

| Addition | For |
|---|---|
| `engines/whitebox.py` (run a tool, errors into the run, plain GeoTIFF inputs) | H1–H3 |
| `ops/hydro.py`: cached flow, streams with order, reading vector output back | H1–H3 |
| `point` parameter type in the manifest schema | H3 |
| Run form: **pick the outlet on the map** (click to place a marker; coordinates editable) | H3 |
| Server: `pip install whitebox` (requirements.txt) and fetch the executable once, or set `WHITEBOX_DIR` | deployment |

## 4. Build order

| Step | Content | Size |
|---|---|---|
| 1 | WhiteboxTools engine + flow cache + `stream_network` (done) | M |
| 2 | `sub_basins` (done) | S |
| 3 | `point` parameter and map picker in the run form (done) | M |
| 4 | `catchment` with its profile (done) | M |

Each step: tests on synthetic DEMs (a tilted plane, a V-shaped valley with a known catchment),
a live run on the test projects, a check in the app, docs and changelog.

## 5. Engine choice (benchmark, 12 Nov 2026)

Same Copernicus DEM clips, full chain (conditioning, flow, streams from 1 km², order, vectors):

| Clip | WhiteboxTools 2.4 | GRASS 8.4 |
|---|---|---|
| 9 M cells (60 m) | 0.8 s | 11 s |
| 36.8 M cells (30 m, Afghan mountains) | 3.1 s | 77 s |
| Stream cells found (36.8 M) | 677,372 | 670,706 |

Results agree within 1%; WhiteboxTools is about 25 times faster here, is one small executable with no
separate GIS install or environment conflicts, has every tool needed (snapping, watersheds,
subbasins, HAND, cost distance, viewshed, geomorphons), and is the same engine as the browser
Toolbox. GRASS is not used; it stays an option for a tool WhiteboxTools lacks.

## 6. Decisions

1. Outlet: picked on the map (recommended), with typed coordinates as an alternative.
2. Default thresholds: streams from 1 km² upstream area, sub-catchments from 25 km², catchments up
   to 25,000 km².
3. Server: install the `whitebox` package and fetch its executable once (or copy it and set
   `WHITEBOX_DIR` if the server has no internet).
