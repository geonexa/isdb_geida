# Land, vegetation and agriculture: analysis plan

Status: wave 1 being built (2026-11-11). Category `land` in `backend/analyses/land/`.
Catalogue plan: [analysis-catalogue-plan.md](analysis-catalogue-plan.md) §4.3.

## 1. What is built now

Every analysis here reads open data where it is published (cloud-optimised GeoTIFFs or
GeoParquet over HTTP range requests); nothing is downloaded in bulk or stored.

| # | Analysis (id) | Answers | P / I / C | Data (read in place) |
|---|---|---|---|---|
| 1 | Land cover composition (`land_cover`) | Area and share of each class, per admin unit | ● ● ● | ESA WorldCover 10 m (2020, 2021) or Esri / Impact Observatory annual 10 m (2017–2023) |
| 2 | Land cover change (`land_cover_change`) | What became what between two years (transition matrix), gains and losses per class | ● ● ● | Esri / Impact Observatory annual 10 m, 2017–2023 (Microsoft Planetary Computer) |
| 3 | Vegetation indices (`vegetation_indices`) | How green / moist the vegetation is in a chosen period: NDVI, EVI, SAVI, NDMI, classes, per admin unit and per land cover class | ● ● ● | Sentinel-2 L2A (Earth Search STAC, AWS), cloud-masked median composite |
| 4 | Biomass production (`biomass`) | Total and mean biomass for a year, on cropland and per admin unit, change against a comparison year | ● ● ● | FAO WaPOR v3 L1 300 m, global (2018–2025), WorldCover cropland mask |
| 5 | Forest cover and loss (`forest_loss`) | Tree cover in 2000, loss per year 2001–2024, per admin unit | ● ● ● | Hansen / UMD Global Forest Change v1.12, 30 m |
| 6 | Field boundaries (`field_boundaries`) | Number of fields, size classes, land in fields, per admin unit | ● ● ● | Fields of The World 2nd edition (GeoParquet per UTM zone, 2023–2025) |

## 2. Method notes

- **Native resolution, one UTM run grid** as for terrain. Large areas are read coarser (logged).
- **Sentinel-2 composite** (`apps/analysis/data/sentinel2.py`): STAC search for the period and
  area, scenes below a cloud limit, at most N scenes per MGRS tile (least cloudy first); each
  band warped from the COG straight onto the run grid (overviews used when coarser);
  pixels masked with the scene classification (no data, saturated, cloud shadow, clouds,
  cirrus, snow); index per scene, then the median per pixel. Reflectance scale and offset
  from the STAC metadata (collection 1 harmonised). Resolution 10 m up to about 1,500 km²,
  coarser above (kept under ~16 M pixels).
- **Land cover classes** keep each product's own legend (11 WorldCover classes, 9 Esri
  classes); the change matrix uses the Esri product only (same method every year; WorldCover
  2020 and 2021 used different algorithms and should not be compared).
- **Forest**: tree cover ≥ threshold (default 30 %) in 2000 is forest; loss year 1–24 →
  2001–2024. Gain is not reported (product stops in 2012).
- **Fields**: polygons are model predictions (score 0–100, default minimum 0); counted where
  their representative point falls in the area; areas from the product's `metrics:area`.

## 3. Needs that the framework gains

| Addition | For |
|---|---|
| `CatalogRaster.source_files()` hook, so a dataset can supply its own files per period | 1, 2, 5 |
| `data/land.py`: Esri annual land cover (Planetary Computer, anonymous SAS token), Hansen GFC tiles | 1, 2, 5 |
| `data/sentinel2.py`: STAC search + cloud-masked median composite on the run grid | 3 |
| `data/ftw.py`: Fields of The World GeoParquet read by bounding box (GDAL Parquet driver: `libgdal-arrow-parquet` in `environment.yml`) | 6 |
| `ops/landcover.py`: class areas, per-zone shares, transition matrix | 1, 2, 4, 5 |

## 4. Later (not in this wave)

| Analysis | Waiting for |
|---|---|
| Seasonal profile and anomaly (MODIS 250 m, 2000 onwards) | Time-series helpers and a chart output (water plan step 1) |
| Per-field statistics (NDVI, biomass per field) | 3 and 6 built; a zonal helper per polygon |
| Cropland and irrigated area (ESA WorldCereal) | A readable copy of WorldCereal (only a WMTS picture is used today) |
| Cropland / urban expansion | Uses 2 plus GHSL; after 2 |
| Forest loss in the tropics with JRC TMF | Licence and access check |

## 5. Licences

WorldCover, Esri / IO annual land cover, WaPOR, Hansen GFC and Fields of The World are CC BY 4.0
(credit in each run's citations). Sentinel-2: Copernicus open licence.
