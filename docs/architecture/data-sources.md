# Data sources

GEIDA does not store global datasets. It reads open data where its producers publish it,
cuts it to the area needed and caches the result. This page lists every source, how it is
read and what it may be used for.

!!! info "Display-only versus analysis-ready"
    Some layers come from map services that deliver *pictures* (coloured tiles). They are
    marked **View only** in the catalogue: they can be shown and printed, but not clipped,
    downloaded or used in analyses. Analyses and downloads use only sources that deliver
    *values* (cloud-optimised GeoTIFFs, OpenStreetMap features).

## Raster layers (Data Catalog and the project's data layers)

Cloud-optimised GeoTIFFs (COGs) are drawn and cut by TiTiler (`TITILER_URL`). Tiled
datasets (WorldCover, Copernicus DEM) are combined per request as an in-line GDAL VRT;
Copernicus DEM tiles are found through the Earth Search STAC API (`STAC_API_URL`).

| Group | Layer | Source | Resolution | Period | Use |
|---|---|---|---|---|---|
| Climate and water | Precipitation | FAO WaPOR v3 L1 (CHIRPS) | 5 km | 2017–2025, annual | Analysis |
| | Actual evapotranspiration, transpiration, evaporation, interception | FAO WaPOR v3 L1 | 300 m | 2018–2025, annual | Analysis |
| | Reference evapotranspiration | FAO WaPOR v3 L1 | 25 km | 2018–2025, annual | Analysis |
| | Surface water occurrence | JRC Global Surface Water | 30 m | 1984–2021 | Display; clips from JRC COG tiles |
| Vegetation and land | Land cover | ESA WorldCover | 10 m | 2020, 2021 | Analysis |
| | Land cover (yearly) | Esri / Impact Observatory | 10 m | 2017–2025 | View only |
| | Cropland, irrigation | ESA WorldCereal | 10 m | 2021 | View only |
| | NDVI, land surface temperature | MODIS via NASA GIBS | 1 km, 5 km | Monthly, 2010 onwards | View only |
| Crop water productivity | Biomass (global, L1; Africa and Near East, L2) | FAO WaPOR v3 | 300 m, 100 m | 2018–2025 | Analysis |
| | Gross and net biomass water productivity | FAO WaPOR v3 L1 | 300 m | 2018–2025 | Analysis |
| Terrain | Elevation, slope, hillshade | Copernicus DEM GLO-30 | 30 m | Static | Analysis |
| Population and imagery | Population | GPW v4 via NASA GIBS | 1 km | 2000–2020 | View only |
| | World Imagery Wayback | Esri | 0.3–1 m | Since 2014 | View only |

### Vector tile layers

| Group | Layer | Source | Resolution | Period | Use |
|---|---|---|---|---|---|
| Agriculture | Field boundaries | Fields of The World, 2nd Edition (CC BY 4.0), via Source Cooperative | Field polygons from Sentinel-2 (10 m) | 2017–2025, yearly | Display |

These are PMTiles archives (`kind: "pmtiles"` in the catalogue), read by the browser with
HTTP range requests: OpenLayers in the Data Catalog, MapLibre's `pmtiles://` protocol on the
project map. Each archive holds two source layers: `cells` (field density: the share of
land in fields, up to zoom 8, drawn on a linear magenta-to-green ramp as in the Fields of The
World app) and `fields` (polygons with a model `score`, from zoom 9, which users can filter by). They are not served or
clipped by GEIDA, so on the project map fields are drawn in full and there is no download.

The catalogue itself is data: `backend/apps/analysis/data/catalog.py` (`CATALOG`, `BASEMAPS`), shared by
the Data Catalog (viewing) and analyses (computing): every layer with cloud-optimised GeoTIFFs
behind it is also an analysis dataset under its id (`elevation`, `eta`, `precipitation`, `landcover`,
`surface-water`, …). For analyses the source files are found as the Data Catalog finds them
(a STAC search on Earth Search for the Copernicus DEM, a URL per year for WaPOR, tile grids for
WorldCover and JRC) and read directly with GDAL at their **native resolution** (30 m DEM, 10 m
WorldCover, 300 m WaPOR L1): only the byte ranges covering the area are fetched over HTTP, then
mosaicked, cut and reprojected to the area's UTM zone in one step (`apps/analysis/data/cog.py`).
WaPOR scale factors are applied. Areas above 150 million pixels are read coarser, and the run log
says so. Clips are cached in `DATA_DIR/<layer>/` and shared by analyses on the same
area. A layer added for viewing is ready for analysis.
A layer's optional `phases` list sets the project phases it is offered in (Analyses →
Data layers); without it, a layer is offered in all three.
Display-only services and their capabilities are documented in
[Open map services](../open-map-services.md).

### Analysis datasets outside the catalogue

Read the same way (in place, by area, native resolution, cached in `DATA_DIR/<id>/`), defined in
`backend/apps/analysis/data/land.py` and `sentinel2.py`:

| Dataset id | Content | Source and access | Resolution | Period | Licence |
|---|---|---|---|---|---|
| `lulc_annual` | Land use / land cover, 9 classes | Esri / Impact Observatory v02, Microsoft Planetary Computer (STAC search, anonymous SAS token) | 10 m | 2017–2023, yearly | CC BY 4.0 |
| `hansen_treecover2000`, `hansen_lossyear` | Tree canopy cover 2000, year of forest loss | Hansen / UMD Global Forest Change v1.12, Google Cloud Storage (10° tiles) | 30 m | 2000–2024 | CC BY 4.0 |
| `ftw_fields_2023` … `2025` | Field boundary polygons with model score and area | Fields of The World 2nd edition, Source Cooperative (GeoParquet per UTM zone, read by bounding box with GDAL's Parquet driver) | from 10 m imagery | 2023–2025 | CC BY 4.0 |
| Sentinel-2 L2A | Cloud-masked median composites of vegetation indices, built per run | Earth Search STAC (collection `sentinel-2-c1-l2a`), AWS Open Data COGs | 10 m (coarser for large areas) | 2017 onwards | Copernicus open data |

| `worldpop`, `worldpop_under_5`, `worldpop_age_5_14`, `worldpop_women_15_49`, `worldpop_age_65_plus` | People per cell, everyone or an age / sex group | WorldPop API v3 (`POST /raster`, cut to the area; groups and pyramids from `/groups`, `/agesex`, `/batch`, `/trend`); without a key 1,000 requests a day and areas up to 100,000 km² (`WORLDPOP_API_KEY` raises them) | 100 m | 2015–2030, yearly | CC BY 4.0 |
| `ghsl_pop`, `ghsl_smod`, `ghsl_built` | Residents per cell, degree of urbanisation (8 classes), built-up surface | GHSL R2023A (JRC): zipped Mollweide tiles downloaded once per area into `DATA_DIR/ghsl/` (no partial reads on JRC's server), read inside the zip; population resampled with sum | 100 m, 1 km, 100 m | 1975–2030, every 5 years | CC BY 4.0 |
| `map_tt_cities`, `map_tt_health_motor`, `map_tt_health_walk` | Travel time (minutes) to cities of 50,000+, to health care by car or on foot | Malaria Atlas Project WCS, cut to the area | ~1 km | 2015, 2019 | CC BY 4.0 |

A year-specific local override, `DATA_DIR/datasets/<id>/<ISO3>_<year>.tif`, replaces one period
of a multi-year dataset (used by tests).

### How project layers are clipped

For a project, GEIDA serves its own tile route
(`/api/projects/<code>/satellite/<id>/xyz/<z>/<x>/<y>.png`): tiles wholly inside the area
of influence are redirected to TiTiler, tiles on the boundary are masked by GEIDA, and
tiles outside are returned empty. Downloads are cut by TiTiler in the local UTM zone at
native resolution, with GEIDA setting the nodata value and the area mask.

## OpenStreetMap

OpenStreetMap (OSM) is the source of every analysis module today.

| Aspect | How GEIDA does it |
|---|---|
| Source | Geofabrik country extracts (`.osm.pbf`), downloaded once into `DATA_DIR/osm/` |
| Region choice | The smallest Geofabrik region that contains the area; never a continent. An area crossing a border uses the country containing its centre and is flagged *partial* |
| Reading | GDAL's OSM driver, cut per area into a GeoPackage under `data/cache/osm/<region>/<snapshot>/` |
| Themes | 16 layers (schools, health, buildings, roads, water points, power, …) defined in `geida_static_data/OSM_Taxonomy/osm_taxonomy.yaml` |
| Reproducibility | The extract's snapshot date is read from its header and stored with every run |
| Fallback | The live Overpass API, if no extract can be used (`OSM_SOURCE=overpass` forces it) |
| Licence | ODbL: credit "© OpenStreetMap contributors" on every map and table |

To refresh a country, delete its `.osm.pbf`; the next run downloads the current extract.

## Administrative boundaries

GADM 4.1, levels 0–3, loaded into the `AdminUnit` table by `seed` (dataset `gadm` in
`REFERENCE_DATA_DIR/catalog.json`) from GeoPackages in `geida_static_data/Admin_Boundaries/`
(not in git, about 4.5 GB). GADM is free for
non-commercial use; its use at IsDB is an open licensing question.

## Reference data in the repository

| File | Content |
|---|---|
| `IsDB_CRI_Library/isdb_cri_2025_seed.csv` | The 77 IsDB Core Result Indicators (2025 list) |
| `IsDB_Member_Countries/isdb_member_countries.geojson` | Outlines of the 57 IsDB member countries |
| `OSM_Taxonomy/osm_taxonomy.yaml` | OSM tag rules for the 16 themed layers |
| `backend/analyses/categories.yaml` | Analysis categories |

## Local overrides

A file in `DATA_DIR/datasets/<dataset id>/<ISO3>.tif` (or `.geojson`) replaces the
downloaded data for that country, for example an official facility list. Datasets are
registered in `backend/apps/analysis/data/registry.py`.
