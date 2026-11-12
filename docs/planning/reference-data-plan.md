# Reference data pipeline: plan (v2)

Status: draft for discussion · 11 November 2026 · planning only ·
not on the docs site (`docs/planning/` is excluded)

v2 changes: the storage rule (§1), PostGIS in development as in production (done), PostGIS core
tables plus GeoParquet master copies (§4), OSM and other API / cloud-optimised data left out (§2).

GEIDA needs some **static reference datasets** that analyses and maps use again and again and that
can't be read efficiently where they are published. This plan sets up one pipeline to
**download → prepare → load → verify** them, run once when a GEIDA installation is set up (and
again when a new version is published), with every source documented in the repository.

It generalises what already exists for admin boundaries
(`backend/scripts/prepare_gadm.py` → `backend/data/boundaries/*.gpkg` →
`manage.py load_admin_units` → `AdminUnit` table, now in PostGIS).

---

> **Update (11 Nov 2026):** the raw data now lives outside the project in
> `/Users/amanchaudhary/Desktop/Terra_ECD/GEIDA_Platform/geida_static_data/` (`REFERENCE_DATA_DIR`),
> one folder per dataset as published, with **`catalog.json`** (all dataset metadata: files,
> counts, database table and core column mapping, source links, licence, citation, status) and a
> `README.md`. The import command reads `catalog.json`; a copy is kept in the repository as
> `backend/reference/catalog.json` for the record. This replaces the per-dataset YAML source
> records described below.


## 1. The rule: what GEIDA stores and what it reads in place

| Data is… | GEIDA does | Examples |
|---|---|---|
| Served by an **API** that answers queries for an area | Calls the API per area, caches the answer with its date | OpenStreetMap (Geofabrik / Overpass, existing pipeline), WPdx+ water points, STAC searches |
| **Cloud-optimised** (COG, GeoParquet, PMTiles) and publicly hosted | Reads only the part covering the area, in place, caches per area | Copernicus DEM, WaPOR, ESA WorldCover, JRC surface water, CHIRPS, Overture, Open Buildings, Fields of The World |
| **Neither**: published as zipped shapefiles, geodatabases, CSV or plain GeoTIFF files, with no API | **Downloads once, prepares, stores** (this pipeline) | GADM, HydroATLAS (basins, rivers, lakes), dams, power plants, power lines, ports, soil groups |

Only the third kind goes through this pipeline. A stored dataset is reviewed when its publisher
releases a new version.

## 2. Datasets

### In the pipeline

| Dataset | Format as published | Why stored | GEIDA store | Priority |
|---|---|---|---|---|
| **GADM 4.1** admin boundaries | GeoPackage download | No API, no cloud-optimised copy | PostGIS `AdminUnit` (done) | Done; brought under the pipeline |
| **BasinATLAS v1.0** (HydroBASINS levels 1–12 + attributes) | Shapefiles / geodatabase (you have it: 11 GB) | No API; shapefiles must be read whole | PostGIS `Basin` + GeoParquet | 1 |
| **RiverATLAS v1.0** (HydroRIVERS + attributes) | Shapefiles per region (you have it: 12 GB, 8.5 million reaches) | Same | PostGIS `River` + GeoParquet | 1 |
| **LakeATLAS v1.0** (HydroLAKES + attributes) | Shapefiles, polygons and pour points (you have it: 6 GB, 1.4 million lakes) | Same | PostGIS `Lake` + GeoParquet | 1 |
| Global Dam Watch v1.0 (dams, reservoirs) | Shapefiles / geodatabase download | Same | PostGIS `Dam` | 2 |
| WRI Global Power Plant Database | CSV | Small CSV, no API | PostGIS `PowerPlant` | 3 |
| Gridfinder power lines (World Bank) | GeoPackage download | Same | PostGIS `PowerLine` | 3 |
| World Port Index (NGA), OurAirports | CSV / shapefile | Same | PostGIS `Port`, `Airport` | 3 |
| HYSOGs250m hydrologic soil groups | Plain GeoTIFF | Not cloud-optimised | Converted to COG in the data folder, read like other rasters | 3 |
| GHSL population / built-up, WorldPop | Zipped tiles / plain GeoTIFF per country | Not cloud-optimised | Converted to COG per country | Later |
| WDPA protected areas | Shapefile / geodatabase (API needs a token) | ⚠ licence to clear first | PostGIS `ProtectedArea` | After clearance |

### Not in the pipeline (read in place or by API)

OpenStreetMap (all themes), Overture Maps, Google–Microsoft Open Buildings, Fields of The World,
Copernicus DEM, WaPOR, ESA WorldCover, JRC Global Surface Water, CHIRPS, WPdx+ water points.

### On hold

**World_Basin** (in `static_Data/`, 50,225 polygons with `NAME_BASIN`): source and licence
unknown. It stays out until its download link and licence are known.

## 3. Where things live

| What | Where | In git? |
|---|---|---|
| Pipeline code: dataset definitions, prepare and load steps, `refdata` command, models | `backend/apps/reference/` (new Django app) | Yes |
| Source records: one YAML per dataset with links, licence, citation, version, download date, checksums, processing notes | `backend/reference/sources/<dataset>.yaml` + `backend/reference/README.md` | Yes |
| Raw downloads as published, with the publisher's documentation (PDFs, legends) | `<REFERENCE_DATA_DIR>/raw/<dataset>/<version>/` | No |
| Prepared files: GeoParquet master copy (all attributes) and GeoPackage for loading | `<REFERENCE_DATA_DIR>/prepared/<dataset>/<version>/` | No |
| Loaded data | PostgreSQL + PostGIS (development and production) | — |

`REFERENCE_DATA_DIR` defaults to `backend/data/reference/` (git-ignored) and can point to a larger
disk in `backend/.env`. Today's `static_Data/` (29 GB, git-ignored) moves to
`backend/data/reference/raw/`, organised as:

```
backend/data/reference/raw/
├── hydrobasins/v10/   BasinATLAS_v10_lev01–12.shp, BasinATLAS_Catalog_v10.pdf, HydroATLAS_TechDoc_v10.pdf, legends
├── hydrorivers/v10/   RiverATLAS_v10_{af,ar,as,au,eu,gr,na,sa_north,sa_south,si}.shp, RiverATLAS_Catalog_v10.pdf, …
└── hydrolakes/v10/    LakeATLAS_v10_{pol,pnt}_{east,west}.shp, LakeATLAS_Catalog_v10.pdf, …
```

## 4. Storage design

Two copies per vector dataset, each for what it does best:

| Copy | Holds | Used for |
|---|---|---|
| **GeoParquet** (prepared, one file per version, spatially sorted) | Every feature in the region kept and **all** attributes (RiverATLAS: about 300 per reach) | Archive and reproducibility; analyses that need many attributes (read by id or area with DuckDB); building map tiles |
| **PostGIS table** | Core columns only, spatially indexed | "What is in this area" in milliseconds; following river and basin networks (`next_down`); joins with projects, admin units and runs; the API and maps |

Maps can later use PMTiles generated from the GeoParquet copy, so large layers don't load from the
database.

**Region kept**: IsDB member countries plus a 200 km margin (keeps basins and rivers that cross
borders). Configurable; `--countries` and `--bbox` load a subset when a quick test load is enough.

### Tables

**`ReferenceDataset`**: one row per dataset version loaded (the provenance every analysis cites).

| Field | Example |
|---|---|
| `dataset`, `version` | `hydrorivers`, `v10` |
| `title`, `publisher` | RiverATLAS v1.0 (HydroATLAS), WWF / McGill University |
| `source_url`, `docs_url`, `licence`, `citation` | from the source record |
| `region`, `features`, `extent` | IsDB members + 200 km · 3.9 million · bbox |
| `prepared_file`, `checksum` | path and SHA-256 of the GeoParquet |
| `loaded`, `loaded_by`, `status`, `report` | load date, user, verify report |

**Dataset tables** (core columns; everything else in GeoParquet, joined by id):

| Table | Core columns | Rows (member region, approx.) |
|---|---|---|
| `AdminUnit` (exists) | gid, level, iso3, names, area, geom, geom_display | 195,286 |
| `Basin` | hybas_id, level, next_down, next_sink, main_bas, pfaf_id, sub_area_km2, up_area_km2, endo, coast, order, geom, geom_display | ~1.3 million (all 12 levels) |
| `River` | hyriv_id, next_down, main_riv, length_km, dist_dn_km, dist_up_km, catch_km2, upland_km2, dis_av_cms, ord_stra, ord_clas, ord_flow, endorheic, hybas_l12, geom | ~4 million |
| `Lake` | hylak_id, name, country, type (lake / reservoir / regulated), area_km2, vol_total_mcm, depth_avg_m, dis_avg_cms, res_time_days, elevation_m, hybas_l12, geom, pour_point | ~0.6 million |

Indexes: GiST on geometries; B-tree on ids, `level`, `next_down`, `main_riv` / `main_bas`,
`ord_stra`. Upstream / downstream queries use recursive SQL over `next_down`.

## 5. The pipeline

| Step | What it does |
|---|---|
| **1. Download** | Fetches the files in the source record (resume, checksum), or, for files downloaded by hand (as yours), checks they are in `raw/<dataset>/<version>/` and records their size and SHA-256. |
| **2. Prepare** | Reads the raw files with GDAL / DuckDB; keeps the region; renames fields to GEIDA's names; repairs invalid geometries; makes types consistent (MultiPolygon, LineString); computes areas and lengths; builds simplified display geometries for basins; writes the GeoParquet master copy (spatially sorted, zstd) and the GeoPackage of core columns. |
| **3. Load** | Loads the core GeoPackage into its PostGIS table with `ogr2ogr` / `COPY` (fast bulk load, not row by row), in a transaction that replaces only that dataset's previous version; builds indexes; records `ReferenceDataset`. |
| **4. Verify** | Counts and extent against the prepared file; null and range checks; sample lookups (the basin and nearest river at known points); differences from the previous version. |

Every step is repeatable and skips what is already done for the same version unless `--force`.

```bash
python manage.py refdata list                      # datasets, versions on disk / loaded
python manage.py refdata status hydrorivers
python manage.py refdata download hydrorivers      # fetch, or check hand-downloaded files
python manage.py refdata prepare hydrorivers [--countries AFG,UGA | --bbox …]
python manage.py refdata load hydrorivers
python manage.py refdata verify hydrorivers
python manage.py refdata setup [--only gadm,hydrobasins]   # everything, for a new installation
```

## 6. Source records

`backend/reference/sources/hydrorivers.yaml`:

```yaml
id: hydrorivers
title: RiverATLAS v1.0 (HydroATLAS), river reaches with hydro-environmental attributes
publisher: WWF and McGill University (HydroSHEDS)
version: v10
landing_page: https://www.hydrosheds.org/hydroatlas
download:
  - {url: "<figshare link of RiverATLAS_Data_v10_shp.zip>", manual: true}
docs: [RiverATLAS_Catalog_v10.pdf, HydroATLAS_TechDoc_v10.pdf, HydroATLAS_v10_Legends.xlsx]
licence: CC BY 4.0
licence_url: https://creativecommons.org/licenses/by/4.0/
citation: >
  Linke, S., Lehner, B., et al. (2019). Global hydro-environmental sub-basin and river reach
  characteristics at high spatial resolution. Scientific Data 6, 283.
downloaded: {date: 2026-11-11, by: Aman Chaudhary}
files: []                    # filled in by `refdata download`: name, bytes, sha256 of each raw file
region: IsDB member countries + 200 km
processing: >
  Reaches intersecting the region kept from all regional files; core fields as PostGIS
  columns; all attributes in hydrorivers_v10.parquet.
used_by: [water_bodies, stream_network, catchment, river_crossings]
```

The links and licences are checked against the publishers' pages when each record is written.

## 7. Build order

| Step | Work | Done when |
|---|---|---|
| 1 | `apps/reference`: `ReferenceDataset`, registry, shared steps, `refdata` command; `backend/reference/` README and source-record format; `REFERENCE_DATA_DIR`; move `static_Data/` into `raw/` | `refdata list` shows the datasets and files on disk |
| 2 | GADM under the pipeline: source record, wrapper around `load_admin_units`, provenance row | `refdata status gadm` reports the current load |
| 3 | BasinATLAS: prepare (all 12 levels), `Basin` table, load, verify | Basins load; the level-8 basin at a known point is found |
| 4 | RiverATLAS: prepare (10 regional files), `River` table, load, verify | Rivers load; nearest river and its downstream path at a known point |
| 5 | LakeATLAS: prepare, `Lake` table, load, verify | Lakes load |
| 6 | `ctx.reference("rivers")` and `ctx.reference_attributes(...)` for analyses; docs (setup guide, data sources, deployment); tests on small sample files | An analysis reads basins and rivers for its area |

Everything runs locally first; loading on the server is a separate, agreed step.

## 8. Decisions needed

1. Move `static_Data/` into `backend/data/reference/raw/<dataset>/v10/` (recommended), or keep it
   in place with `REFERENCE_DATA_DIR` pointing to it?
2. Region: IsDB member countries plus 200 km (recommended), or the whole world?
3. Basins: all 12 levels (recommended: analyses pick the level), or a subset such as 4–10?
4. Source of `World_Basin`, or drop it?
