# Water resources category: analysis plan

Status: draft for discussion · 11 November 2026 · planning only, nothing built yet ·
not on the docs site (`docs/planning/` is excluded)

The **Water resources** category (`analyses/water/`) answers where water comes from, where it
goes and how productively it is used in a project area. This plan sets out the 13 analyses in
the category, the data each uses, the tools that compute it, what it produces, and the order
to build them. It follows the framework already in place (Terrain category: `ctx.raster` at
native resolution, run grid in UTM, `add_raster`, tests per analysis).

Related: `docs/planning/analysis-catalogue-plan.md` (all categories),
`docs/planning/analysis-backend-plan.md` (framework), `backend/analyses/planned.yaml`.

---

## 1. Questions the category answers

| Phase | Typical questions |
|---|---|
| **Preparation** (PPRR) | Which catchment feeds the site and how large is it? Where do rivers run? How much rain falls and how much is consumed? Is there a surplus or deficit? Where are water points? How productive is water use, and what could be gained? |
| **Implementation** (PIASR) | Is this year's rain and water use normal? Is surface water expanding or shrinking? Are water points working? |
| **Completion** (PCR) | Did water use, water productivity or surface water change since the baseline? |

## 2. The 13 analyses

| # | Analysis (id) | Phases P / I / C | Wave |
|---|---|---|---|
| 1 | Precipitation (`precipitation`) | ● ● ● | 1 |
| 2 | Evapotranspiration (`evapotranspiration`) | ● ● ● | 1 |
| 3 | Water balance P − ETa (`water_balance`) | ● ● ● | 1 |
| 4 | Surface water occurrence and change (`surface_water`) | ● ● ● | 1 |
| 5 | Rivers, lakes and reservoirs (`water_bodies`) | ● | 1 |
| 6 | Water points (`water_points`) | ● ● ● | 1 |
| 7 | Sub-basins (`sub_basins`) | ● | 1 |
| 8 | Catchment delineation (`catchment`) | ● | 2 |
| 9 | Stream network and order (`stream_network`) | ● | 2 |
| 10 | ET deficit and water stress (`et_deficit`) | ● ● | 2 |
| 11 | Water productivity and gap (`water_productivity`) | ● ○ ● | 2 |
| 12 | Runoff estimate (`runoff`) | ● | 3 |
| 13 | Water accounting summary (`water_accounting`) | ● ○ ● | 3 |

(○ = not in that phase.) Wave 1 uses data already in the catalogue and needs no new engine;
wave 2 adds GRASS GIS for hydrology; wave 3 combines earlier results.

## 3. Data

### 3.1 Already in GEIDA's catalogue (read at native resolution with `ctx.raster`)

| Catalogue id | Dataset | Resolution | Period | Used by |
|---|---|---|---|---|
| `precipitation` | FAO WaPOR v3 L1 precipitation (CHIRPS-based) | ~5 km | Annual 2018–2025 | 1, 3, 13 |
| `eta` | WaPOR v3 L1 actual evapotranspiration and interception (AETI) | 300 m | Annual 2018–2025 | 2, 3, 10, 13 |
| `transpiration`, `evaporation`, `interception` | WaPOR v3 L1 components | 300 m | Annual 2018–2025 | 2, 13 |
| `ret` | WaPOR v3 L1 reference ET | ~25 km | Annual 2018–2025 | 10 |
| `biomass-global` | WaPOR v3 total biomass production (L1, global; GEIDA analyses use L1 only) | 300 m | Annual 2018–2025 | 11 |
| `gbwp`, `nbwp` | WaPOR v3 gross / net biomass water productivity | 300 m | Annual 2018–2025 | 11 |
| `surface-water` | JRC Global Surface Water v1.4, occurrence | 30 m | 1984–2021 | 4 |
| `elevation` | Copernicus DEM GLO-30 | 30 m | Static | 8, 9, 12 |
| `landcover` | ESA WorldCover | 10 m | 2020, 2021 | 12, 13 |
| OSM `waterways`, `water_bodies`, `water_points` | OpenStreetMap (existing extract pipeline) | Vector | Current snapshot | 5, 6, 9 |

WaPOR also publishes monthly and dekadal layers (already readable through the catalogue's
`periods_from`), used for seasonal profiles in 1–3 once the monthly variants are added.

### 3.2 To add

| Dataset | What for | Format and access | Licence | Used by |
|---|---|---|---|---|
| **CHIRPS v2.0** monthly, 1981–present (UCSB Climate Hazards Center) | Long-term rainfall normals, anomalies and trends (WaPOR only starts in 2018) | COGs over HTTP, read like other catalogue layers | Public, attribution | 1, 3 |
| **HydroRIVERS v1.0** (HydroSHEDS) | River network with Strahler order and long-term discharge estimate | Vector; download once per region, convert to GeoParquet in `backend/data/datasets/`, read the area with DuckDB | HydroSHEDS licence (free with attribution; to confirm) | 5, 9 |
| **HydroBASINS v1.c** levels 1–12 | Nested basin units for planning and reporting | Same as above | Same | 7, 8, 13 |
| **HydroLAKES v1.0** | Lakes and reservoirs with area, volume, depth | Same as above | CC BY 4.0 | 5 |
| **Global Dam Watch (GDW) v1.0** (successor of GRanD) | Dams and reservoirs with capacity and purpose | Vector, as above | CC BY 4.0 | 5, 13 |
| **JRC GSW seasonality, change, transitions** | Permanent vs seasonal water; gains and losses 1984–2021 | 30 m COG tiles in the same bucket as occurrence | Free, attribution | 4 |
| **WPdx+ (Water Point Data Exchange)** | Water points with type, source and functionality | Public API (Socrata, no key for small queries), cached per area | CC BY 4.0 | 6 |
| **HYSOGs250m** (ORNL DAAC) | Hydrologic soil groups for curve numbers | 250 m GeoTIFF, stored once | NASA open data | 12 |
| MERIT Hydro / FABDEM | Hydrologically conditioned DEM alternatives | — | ⚠ non-commercial terms: only if cleared | (optional for 8, 9) |

All of it is read for the area only and cached in `backend/data/cache/`; vector datasets that
can't be read in place are converted once into GeoParquet under `backend/data/datasets/`
(local, git-ignored; nothing goes to the server until agreed).

## 4. Tools

| Tool | Used for | Status |
|---|---|---|
| GDAL / rasterio / NumPy | Reading rasters at native resolution, zonal statistics, P − ETa, ratios, classes, previews | In place |
| xarray (to add) | Year and month stacks, means, anomalies, trends (Sen's slope, Mann–Kendall) | New |
| **GRASS GIS 8.4** (installed locally) | `r.fill.dir` / `r.watershed` (flow direction, accumulation, basins), `r.water.outlet` (catchment from a point), `r.stream.extract` (streams); add-ons `r.stream.order` (Strahler) and `r.stream.snap` (snap the outlet) via `g.extension` | New: `engines/grass.py` |
| DuckDB (spatial) + GeoPandas (to add) | Reading HydroSHEDS / GDW GeoParquet for the area; vector overlays | New: `data/parquet.py` |
| Existing OSM pipeline | Waterways, water bodies, water points from OpenStreetMap | In place |
| WPdx client (new, small) | Area query to the WPdx+ API, cached | New: `data/wpdx.py` |

**GRASS in a run** (`engines/grass.py`): a temporary GRASS project in the run folder with the
area's UTM CRS; the DEM from `ctx.raster("dem")` is imported, modules run through
`grass.script`, results exported as GeoTIFF / GeoPackage and read back into the run grid;
the project is removed at the end. The DEM's flow products (filled DEM, flow direction,
accumulation) go into the derived-product cache (`ctx.cached`), so catchment, streams and
runoff on the same area compute them once.

## 5. Analyses in detail

Common to all: area of influence from the project, admin units for per-unit tables, results
stored as metrics, tables, maps (COG + preview + legend) and downloads, and the datasets used
recorded with each run. Volumes are reported in m³ as well as mm
(1 mm over 1 km² = 1,000 m³).

### Wave 1: catalogue data, no new engine

**1. Precipitation** · P, I, C
- Data: WaPOR L1 precipitation (2018–2025); CHIRPS v2.0 for 1981–present once added.
- Method: annual total per year (area mean, per unit); mean of the period; this year vs the
  mean (anomaly, %); trend over the years; optional monthly profile.
- Outputs: metrics (mean annual rainfall mm and m³, latest year, anomaly %), table per year,
  table per unit, map of mean annual rainfall, chart of the yearly series.
- Parameters: years (range), reference period, zone level.

**2. Evapotranspiration** · P, I, C
- Data: WaPOR L1 AETI and its parts (transpiration, evaporation, interception).
- Method: annual ETa per year, mean, split into T / E / I (share of beneficial transpiration),
  per land cover class (WorldCover) and per unit.
- Outputs: metrics (mean ETa mm and m³, T share %), tables per year / per unit / per land
  cover, map of mean ETa, chart.

**3. Water balance (P − ETa)** · P, I, C
- Data: WaPOR precipitation and AETI (resampled onto the AETI 300 m grid).
- Method: P − ETa per pixel and year; areas in surplus vs deficit; area totals (mm and m³);
  per unit. Notes that P − ETa ignores inflows from upstream and groundwater (stated in the
  method and the result).
- Outputs: metrics (mean P − ETa, deficit share), table per year, map (diverging legend),
  chart.

**4. Surface water occurrence and change** · P, I, C
- Data: JRC GSW occurrence, seasonality, change and transitions (30 m).
- Method: area of permanent water (occurrence ≥ 90 %), seasonal water, ever-water; change
  between 1984–1999 and 2000–2021 (gains and losses); per unit.
- Outputs: metrics (permanent / seasonal water km²), transitions table, maps (occurrence,
  change).

**5. Rivers, lakes and reservoirs** · P
- Data: HydroRIVERS (order, discharge), HydroLAKES, GDW dams; OSM waterways and water bodies.
- Method: inventory inside the area and within a buffer: river km by Strahler order, largest
  rivers by discharge, lakes and reservoirs by area and volume, dams by capacity and purpose;
  distance from the area's centre to the nearest permanent river.
- Outputs: metrics, tables, map layers (rivers styled by order, lakes, dams).

**6. Water points** · P, I, C
- Data: WPdx+ (type, water source, functionality, last reported date); OSM water points.
- Method: count by type and functional status, per unit; people per water point (with
  population once available); distance to the nearest functional point.
- Outputs: metrics, tables, map layer (points coloured by status). Reuses `ops/inventory.py`.

**7. Sub-basins** · P
- Data: HydroBASINS (level chosen, default 8).
- Method: basins intersecting the area, share of the area in each, upstream area of each
  basin; Pfafstetter codes for reporting.
- Outputs: table, map layer, metric (number of basins, main basin).

### Wave 2: GRASS GIS for hydrology

**8. Catchment delineation** · P
- Data: Copernicus DEM 30 m (filled), optional HydroRIVERS to guide snapping.
- Input: an outlet point picked on the map (new *point* parameter type), or the area's lowest
  point by default.
- Method: fill sinks; flow direction and accumulation (`r.watershed`); snap the outlet to the
  highest accumulation within a radius (`r.stream.snap`); delineate the catchment
  (`r.water.outlet`); vectorise. Large catchments (beyond the area) are read with a wider DEM
  clip, capped by a maximum catchment size; above it, fall back to HydroBASINS upstream units.
- Outputs: catchment polygon (map, GeoPackage), metrics (area km², mean slope, elevation
  range), catchment profile table (rainfall, ETa, land cover inside the catchment, reusing
  wave 1 code).

**9. Stream network and order** · P
- Data: DEM 30 m; HydroRIVERS and OSM waterways for comparison.
- Method: streams from flow accumulation above a threshold (`r.stream.extract`, threshold in
  km² of upstream area), Strahler order (`r.stream.order`); km per order, drainage density
  (km / km²).
- Outputs: stream lines styled by order (map, GeoPackage), table by order, metrics.

**10. ET deficit and water stress** · P, I
- Data: WaPOR AETI and RET.
- Method: relative ET (ETa / RET) and ET deficit (RET − ETa) per year; stressed share of
  cropland (with WorldCereal / WorldCover masks).
- Outputs: maps, tables per year and unit, metrics.

**11. Water productivity and gap** · P, C
- Data: WaPOR biomass and gross / net biomass water productivity (GBWP, NBWP).
- Method: mean water productivity (kg/m³) over cropland; target = 95th percentile in the area
  (or per land cover / irrigated mask); gap per pixel; potential biomass gain at current water
  use, or water saving at current output.
- Outputs: maps (WP, gap), metrics (mean WP, gap %, potential gains), tables per unit and year.

### Wave 3: combinations

**12. Runoff estimate** · P
- Data: CHIRPS rainfall (event or annual), WorldCover, HYSOGs soil groups, DEM for slope.
- Method: SCS curve number per pixel (land cover × soil group, slope-adjusted); runoff depth
  for a design rainfall (parameter) or annual rainfall; volume for the area or a catchment
  from analysis 8.
- Outputs: curve-number map, runoff map, metrics (runoff coefficient, volume).

**13. Water accounting summary** · P, C
- Data: results of 1–3, 7–9 and WaPOR components.
- Method: a WA+ style resource-base summary for a catchment or basin: gross inflow (P),
  landscape consumption (ETa split into beneficial T and non-beneficial E / I, by land use),
  remaining outflow (P − ETa as an upper bound); per year.
- Outputs: summary table, simplified water-account diagram, yearly table. Clearly marked as
  a satellite-based estimate, not a measured balance.

## 6. Framework additions needed

| Addition | Why | For |
|---|---|---|
| `ops/zonal.py` | Per-unit and per-class statistics in one place (mean, sum, area; exact area weights later with exactextract) | 1–4, 7, 10, 11 |
| `ops/timeseries.py` + `ctx.raster_series(input, years)` | Read several years onto one grid, means, anomalies, trends | 1, 2, 3, 10, 11 |
| `chart` output + a small chart in the run result (frontend) | Yearly series and profiles (no chart library in the frontend yet) | 1, 2, 3, 10, 11 |
| `period` parameter type (from a dataset's periods) | Pick years / reference periods in the form | 1–4, 10, 11 |
| `point` parameter type + map picker in the run form | Catchment outlet | 8 |
| `engines/grass.py` + GRASS add-ons (`r.stream.order`, `r.stream.snap`) | Hydrology | 8, 9, 12 |
| `data/parquet.py` (DuckDB) | HydroSHEDS, GDW and later Overture / Open Buildings | 5, 7, 9 |
| `data/wpdx.py` | Water points | 6 |
| Diverging legend preset | P − ETa, anomalies, change | 1, 3, 4 |
| Volume helper (mm × area → m³) | Consistent units | All |

## 7. Build order and effort (indicative)

| Step | Content | Size |
|---|---|---|
| 1 | `ops/zonal.py`, `ops/timeseries.py`, `ctx.raster_series`, `period` parameter, `chart` output (backend + frontend) | M |
| 2 | Precipitation, Evapotranspiration, Water balance (WaPOR) | M |
| 3 | Surface water (JRC layers added to the catalogue) | S |
| 4 | `data/parquet.py`; HydroRIVERS / HydroBASINS / HydroLAKES / GDW stored locally; Rivers, lakes and reservoirs; Sub-basins | M |
| 5 | `data/wpdx.py`; Water points | S |
| 6 | `engines/grass.py` (+ add-ons, local only); `point` parameter and map picker; Catchment; Stream network | L |
| 7 | ET deficit; Water productivity and gap | M |
| 8 | CHIRPS long series; HYSOGs; Runoff; Water accounting summary | L |

Each step ends with tests on synthetic data, a live run on the test project, a check in the
app, and docs and changelog updates.

## 8. Decisions needed

1. Rainfall source for long-term normals: add CHIRPS v2.0 (1981–present) alongside WaPOR
   (2018–2025)? Recommended.
2. HydroSHEDS / GDW: download once per region into `backend/data/datasets/` as GeoParquet
   (local only for now; size a few GB for all regions, much less per region)?
3. GRASS add-ons (`r.stream.order`, `r.stream.snap`) installed locally with `g.extension`,
   or use core GRASS only (snap in NumPy, order computed in Python)?
4. Catchment outlet: map picker (recommended) or coordinates typed in the form?
5. Water productivity target: 95th percentile within the area, or per irrigated / rainfed
   mask, or per land cover class?
6. WPdx coverage is strongest in Africa and parts of Asia; elsewhere water points come from
   OSM only. Acceptable?
7. Which three analyses first? Recommended: Precipitation, Evapotranspiration, Water balance.
