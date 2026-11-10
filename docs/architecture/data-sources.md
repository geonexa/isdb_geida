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

The catalogue itself is data: `backend/apps/geoportal/catalog.py` (`CATALOG`, `BASEMAPS`).
A layer's optional `phases` list sets the project phases it is offered in (Analyses →
Data layers); without it, a layer is offered in all three.
Display-only services and their capabilities are documented in
[Open map services](../open-map-services.md).

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
| Source | Geofabrik country extracts (`.osm.pbf`), downloaded once into `backend/data/osm/` |
| Region choice | The smallest Geofabrik region that contains the area; never a continent. An area crossing a border uses the country containing its centre and is flagged *partial* |
| Reading | GDAL's OSM driver, cut per area into a GeoPackage under `data/cache/osm/<region>/<snapshot>/` |
| Themes | 16 layers (schools, health, buildings, roads, water points, power, …) defined in `backend/seeds/data/osm_taxonomy.yaml` |
| Reproducibility | The extract's snapshot date is read from its header and stored with every run |
| Fallback | The live Overpass API, if no extract can be used (`OSM_SOURCE=overpass` forces it) |
| Licence | ODbL: credit "© OpenStreetMap contributors" on every map and table |

To refresh a country, delete its `.osm.pbf`; the next run downloads the current extract.

## Administrative boundaries

GADM 4.1, levels 0–3, loaded into the `AdminUnit` table by `seed --boundaries` from
GeoPackages in `backend/data/boundaries/` (not in git, about 4.5 GB). GADM is free for
non-commercial use; its use at IsDB is an open licensing question.

## Reference data in the repository

| File | Content |
|---|---|
| `backend/seeds/data/isdb_cri_2025_seed.csv` | The 77 IsDB Core Result Indicators (2025 list) |
| `backend/seeds/data/isdb_member_countries.geojson` | Outlines of the 57 IsDB member countries |
| `backend/seeds/data/osm_taxonomy.yaml` | OSM tag rules for the 16 themed layers |
| `backend/modules/categories.yaml` | Analysis categories |

## Local overrides

A file in `backend/data/datasets/<dataset id>/<ISO3>.tif` (or `.geojson`) replaces the
downloaded data for that country, for example an official facility list. Datasets are
registered in `backend/apps/analysis/datasets/registry.py`.
