# Spec: replace Google Earth Engine with an open raster stack (COG + STAC + TiTiler)

Status: **in progress** · 5 Nov 2026 · Aman (with Claude Code)

**Done 6 Nov (first cut, "use hosted data first"):** Earth Engine removed from code,
settings and requirements. Catalogue layers are read as COGs where they are hosted
and drawn by the hosted TiTiler (`TITILER_URL`, default `https://titiler.waterinag.org`),
without pgSTAC or a data lake yet:

| Layer | Source read in place | How |
|---|---|---|
| Precipitation | FAO WaPOR v3 L1-PCP-A (CHIRPS), 2017–2025 | one global COG per year |
| Actual ET, Reference ET | WaPOR v3 L1-AETI-A, L1-RET-A, 2018–2025 | one global COG per year |
| Biomass | WaPOR v3 L2-TBP-A, 2018–2025 (Africa, Near East) | one COG per year |
| Land cover | ESA WorldCover 2020/2021, AWS | 3° tiles from ESA's grid file → in-line VRT, zoom ≥ 7 |
| Elevation, slope, hillshade | Copernicus DEM GLO-30, AWS, found with Earth Search STAC | 1° tiles → in-line VRT; TiTiler `slope` / `hillshade` algorithms, zoom ≥ 8 |
| Surface water | JRC GSW 2021 | Google's public tiles for display; 10° COG tiles for clips |

Project tiles: GEIDA's route (`/api/projects/<code>/satellite/<id>/xyz/…`) redirects
tiles inside the area to TiTiler, masks boundary tiles itself and returns empty
tiles outside. Downloads: TiTiler `/cog/bbox` in the local UTM zone at native
resolution (up to 9 MP), nodata and area mask set by GEIDA.

**Next step (needs processing into GEIDA's S3 bucket):** MODIS NDVI annual means,
ERA5-Land temperature, CHIRPS 1981–2016, population; then pgSTAC for our own
collections. WorldCereal dropped (only distributed through Earth Engine).

The original proposal follows.
Replaces plan item C2.4 ("Rasters return via STAC / COG") and closes the open
decision "Earth Engine: replace with STAC/COG once hosted at IsDB" in `decisions.md`.

## Why

- **IsDB hosting.** IMDT will host GEIDA; a Google service account key, Google
  quotas and Google terms in the request path are hard to justify there.
- **No hidden limits.** Earth Engine caps downloads (we coarsen to 4 MP),
  expires map ids after hours, and can throttle without notice.
- **Same data, open formats.** Almost every layer we show already exists as
  Cloud-Optimised GeoTIFFs (COGs) on public buckets; GEE is only rendering them.
- **One raster path.** Analysis modules already read COGs directly
  (`apps/analysis/datasets/registry.py`); the portal should use the same files.

## 1. Where GEE is used today

| # | Where | What it does | Code |
|---|---|---|---|
| 1 | Data Catalog (Geo-Portal) map | XYZ tiles for 10 catalogue layers, coloured server-side (`getMapId`), cached 3 h | `geoportal/gee.py` `tile_url`, `views.layer_tiles` |
| 2 | Data Catalog toolbox | Raw float32 GeoTIFF of a layer over the user's area, in UTM, ≤ 4 MP (`getDownloadURL`) for the browser processing engine | `gee.clip_geotiff`, `views.layer_clip`, `engine/toolbox.js` |
| 3 | Project workspace → Data catalog tab | Same tiles **clipped to the project area**; GeoTIFF download masked to the area | `geoportal/project_rs.py`, `workspace/satellite.tsx` |
| 4 | Two tile-service layers (JRC water, hillshade) | Served from Google / Esri tiles, but use a GEE recipe (`aoi_gee`) for clipping and download | `catalog.py` |
| 5 | Helpers | `utm_epsg()` lives in `gee.py` (not GEE-specific) and is imported by `projects/geometry.py` and `geoportal/areas.py` | move to `apps/core` |
| 6 | Dependencies and config | `earthengine-api` in `requirements.txt`; `EE_KEY` / `EE_KEY_FILE` / `EE_PROJECT` in `.env`; key in `cred/` | — |
| 7 | UI copy | "from Earth Engine", "(Earth Engine)" in the satellite panel and toolbox | `satellite.tsx`, `toolbox.js` |

**Not using GEE:** the analysis modules (DEM, WorldCover, WorldPop read as COGs
over HTTP with GDAL `/vsicurl/`), the OSM layer, boundaries, basemaps.

## 2. Is replacement possible? Layer by layer

| Layer | GEE recipe today | Open source of the same data | Work | Verdict |
|---|---|---|---|---|
| Elevation (Copernicus GLO-30) | collection mosaic | COGs on AWS Open Data (`copernicus-dem-30m`), STAC on Planetary Computer (`cop-dem-glo-30`); already used by modules | Mosaic (STAC search or VRT) | **Direct** |
| Slope | `ee.Terrain.slope` on the fly | Same DEM | Slope as a TiTiler algorithm, or a precomputed slope COG for member countries | **Direct** |
| Hillshade | `ee.Terrain.hillshade` | Same DEM | TiTiler's built-in `hillshade` algorithm | **Direct** |
| Land cover (ESA WorldCover 2020/21) | `remap` classes | COGs on AWS (`esa-worldcover`); already used by modules | Colormap only | **Direct** |
| Cropland (WorldCereal 2021) | filter + `eq(100)` | GeoTIFFs on Zenodo (record 7875105), COG mirror on Source Cooperative | Ingest once, convert to COG, add to STAC | **Ingest once** |
| Surface water occurrence (JRC GSW) | single image | COG tiles on the public `global-surface-water` bucket; STAC on Planetary Computer (`jrc-gsw`) | Mosaic | **Direct** |
| Actual ET, biomass (FAO WaPOR v3) | `loadGeoTIFF` of FAO's COGs | The same COGs on FAO's public GCS bucket | Read in place (no GEE at all) | **Direct** |
| Precipitation (CHIRPS annual) | sum of pentads | CHIRPS v2 global annual/monthly GeoTIFFs from UCSB CHC; CHIRPS COGs on AWS (Digital Earth Africa) | Yearly job: download annual file → COG | **Precompute** |
| NDVI (MODIS MOD13Q1, annual mean) | mean of 23 composites | MOD13Q1 v061 COGs on Planetary Computer (`modis-13Q1-061`) and NASA LP DAAC | Yearly job: mean of the year's 23 composites → one COG (member countries) | **Precompute** |
| Air temperature (ERA5-Land annual mean) | mean of monthly aggregates | ERA5-Land monthly means from Copernicus CDS (NetCDF), ARCO Zarr copies | Yearly job: CDS API → annual mean → COG (tiny, 9 km) | **Precompute** |

**All 12 layers can be replaced.** 6 are read in place, 1 is ingested once,
3 need a small yearly job, 2 are computed on the fly from the DEM.

## 3. Where replacement is not possible (or not worth it)

| What GEE gives | Why it is hard without GEE | What we do instead |
|---|---|---|
| **Any computation, anywhere, on the fly** (e.g. "mean NDVI for any date range", "cloud-free Sentinel-2 composite for March 2019") | Needs a compute cluster near the data; GEE gives Google's for free | **Precompute** the products the curated modules need (annual/seasonal COGs per member country); run ad-hoc work per project area only (small AOI, dask/xarray in the Celery worker). No global on-demand compositing. |
| **Long time series over large areas** (e.g. 20-year NDVI trend for a whole country) | Reading thousands of COGs per request | Precomputed annual layers make it 20 reads; heavier studies run as background jobs, not as tile requests |
| **GEE-only datasets**: Dynamic World (near-real-time 10 m land cover) is distributed through Earth Engine | No open bucket of the full archive | Use ESA WorldCover (2020/21) and Esri/Impact Observatory 10 m annual land cover (`io-lulc-annual-v02` on Planetary Computer); drop Dynamic World from the plan |
| **Interactive Earth Engine scripting for analysts** | Some analysts may expect the Code Editor | Out of GEIDA's scope; Analytics (GeoLibre + Whitebox) is the advanced toolbox. Analysts can still use GEE personally. |

None of these block the current catalogue or the planned curated modules.

## 4. Recommended stack

```
                    ┌──────────────── GEIDA data lake (object storage) ───────────────┐
 public COG buckets │  COGs: mirrored member-country tiles + precomputed annual layers  │
 (AWS, GCS, PC) ───►│  s3://geida-lake/<collection>/<year>/<tile>.tif                   │
        ▲           └───────────────▲──────────────────────────────▲──────────────────┘
        │ read in place (dev)       │ write (ETL jobs)             │ read
        │                           │                              │
 ┌──────┴─────────┐   ┌─────────────┴────────────┐   ┌─────────────┴─────────────┐
 │ pgSTAC         │◄──│ ETL (Celery beat):       │   │ TiTiler (titiler-pgstac)  │──► XYZ tiles, colormaps,
 │ (in PostGIS)   │   │ rio-cogeo, rioxarray,    │   │ + GEIDA extension:         │    hillshade/slope,
 │ + stac-fastapi │   │ odc-stac, cdsapi         │   │ clip-to-project, download  │    clipped GeoTIFF
 └──────▲─────────┘   └──────────────────────────┘   └─────────────▲─────────────┘
        │ search / items                                           │ /tiles, /part, /feature
 ┌──────┴─────────────────────── Django (catalog.py, project_rs, modules) ─────────┴────┐
 │ catalogue = STAC collection id + render params; analysis modules read COGs via STAC   │
 └────────────────────────────────────────────────────────────────────────────────────────┘
```

| Need | Choice | Why | Alternatives considered |
|---|---|---|---|
| Raster format | **COG** (deflate/zstd, internal overviews, 512 px tiles) | Range-read over HTTP, no server-side tiling cache needed | Zarr (better for climate cubes; keep for ERA5 if we add daily data later) |
| Storage | **S3-compatible object storage**: MinIO on IsDB servers, or any cloud S3 | Same API in dev, staging and IsDB; GDAL/rasterio read it natively | Plain disk + Apache (works, but no range-read scaling) |
| Catalogue | **STAC** in **pgSTAC** (inside the existing PostGIS) + **stac-fastapi-pgstac** | Standard, searchable by date/bbox; mosaics for tiled datasets; IMDT can browse it with any STAC client | Static STAC JSON (fine for < 10 collections, no mosaic search) |
| Tiles | **TiTiler** (`titiler-pgstac`), FastAPI + uvicorn | Dynamic tiles from COG/STAC mosaics, colormaps and rescale per request, algorithms (hillshade, NDVI), `/part` and `/feature` for clipped downloads | GeoServer (heavier, XML styling), MapServer, pre-rendered tile pyramids (static, huge) |
| Packaging | **eoAPI** pattern (pgSTAC + stac-fastapi + titiler-pgstac + tipg) in Docker Compose | One known, maintained bundle (Development Seed); same layout on staging and at IsDB | Hand-rolled services |
| Processing / ETL | **rasterio, rio-cogeo, rioxarray/xarray + dask, odc-stac**, `cdsapi` for ERA5 | Already in our conda env (rasterio), pure open source | openEO (good, but another service to run) |
| Zonal statistics in modules | **exactextract** (or rasterstats) | Fast, exact partial-pixel weights on COG windows | Our current numpy masks (keep for small areas) |
| Vector tiles (later) | **tipg** or **Martin** for PostGIS; **PMTiles** for static layers | Already planned in C2.8 | GeoServer WMS |
| Sentinel-2 by date (C2.8) | Element 84 Earth Search STAC (Sentinel-2 L2A COGs on AWS) or Copernicus Data Space; TiTiler mosaic per date, cloud filter via STAC `eo:cloud_cover` | Scenes as they are, no compositing needed for Verify roles | EOX s2cloudless yearly mosaics for a cloud-free backdrop |

### How the current features map

| Today (GEE) | Tomorrow (open) |
|---|---|
| `gee.tile_url(layer, year)` → Google tile URL | `stac.tile_url(layer, year)` → `TITILER/searches/{id}/tiles/{z}/{x}/{y}?colormap=…&rescale=…` (register one search per collection + year) |
| `image.clip(project_area)` | GEIDA TiTiler extension: `/project/{code}/tiles/…` masks each tile with the project polygon (rio-tiler `ImageData` + `rasterio.features.geometry_mask`); or MapLibre inverse mask as a stop-gap |
| `vis` params (`min`, `max`, `palette`) | TiTiler `rescale` + `colormap` (catalogue palettes → TiTiler colormaps; classed layers → discrete colormap) |
| `getDownloadURL` (≤ 4 MP, UTM) | rio-tiler `part()` / `feature()` at native resolution, reprojected to UTM, written as COG; size limit is ours to set |
| Map-id cache, 3 h expiry | Stable URLs; HTTP cache headers; optional CDN |
| Service-account key | Object-storage credentials only (read-only for TiTiler) |

## 5. Data volumes (member countries only)

Rough figures to size the IsDB storage request (decision 5 in `plan.md`):

| Collection | Mirror? | Approx. size |
|---|---|---|
| Copernicus DEM GLO-30 | yes (member countries) | ~120 GB |
| Slope (precomputed, optional) | yes | ~60 GB |
| ESA WorldCover 2020 + 2021 | yes | ~60 GB |
| JRC GSW occurrence | yes | ~10 GB |
| WorldCereal 2021 cropland | yes | ~15 GB |
| WaPOR v3 L1 (300 m) + L2 (100 m), 2018–2025 | yes | ~40 GB |
| CHIRPS annual 1981–2025 | yes (global, small) | ~2 GB |
| ERA5-Land annual mean 1950–2025 | yes (global, small) | < 1 GB |
| MODIS NDVI annual mean 2000–2025 | yes | ~40 GB |
| **Total** | | **≈ 350 GB**, plus room for Sentinel-2 caching if added |

Development and staging read the public buckets in place (zero storage);
production at IsDB mirrors into its own object storage. Only STAC asset
`href`s change, not code.

## 6. Build order

| Step | Deliverable | Done when |
|---|---|---|
| G1 | **Infrastructure:** `deploy/raster/` Docker Compose with MinIO (dev), pgSTAC (in the PostGIS container), stac-fastapi, titiler-pgstac; Django setting `RASTER_API` | `docker compose up` serves the STAC API and a TiTiler `/healthz` |
| G2 | **Collections read in place:** STAC collections + items for DEM, WorldCover, JRC GSW, WaPOR (L1 AETI, L2 TBP), loaded by `manage.py load_stac` | Their tiles render in the Data Catalog from TiTiler, side by side with GEE |
| G3 | **Ingest + yearly jobs:** WorldCereal (once), CHIRPS annual, ERA5-Land annual, MODIS NDVI annual → COGs in the lake + STAC items; Celery beat yearly; `manage.py raster_ingest <collection> --year` | All 12 catalogue layers render without GEE |
| G4 | **Project clipping and downloads:** TiTiler extension for clip-to-project tiles; `/part` downloads in UTM replacing `clip_geotiff` (Data Catalog toolbox + project tab) | Toolbox and project tab work with GEE switched off; downloads at native resolution |
| G5 | **Remove GEE:** delete `gee.py`, `earthengine-api`, `EE_*` settings and the key; move `utm_epsg` to `apps/core/geo.py`; catalogue `kind: stac`; update UI copy and `decisions.md` | `grep -ri "earth engine\|earthengine\|import ee"` finds nothing; tests pass |
| G6 | **Analysis modules on STAC:** `RasterTiles` datasets resolve files through STAC instead of hard-coded URLs; un-park `terrain`, `area_baseline`, `school_access` | Parked module tests pass against the lake |
| G7 | **Sentinel-2 by date (C2.8):** Earth Search STAC, cloud filter, date slider in the project tab | A project shows any cloud-free-enough scene by date |

G1–G5 is about **2 weeks** of work; G6 about 3 days; G7 about 1 week. G1–G4 can
run alongside GEE (a `RASTER_BACKEND = "gee" | "stac"` setting), so nothing
breaks for the demo; switch over after the demo.

## Acceptance tests

- Every catalogue layer renders from TiTiler with the same legend and palette as today.
- Pixel values in a downloaded GeoTIFF match the source COG at the same location (spot checks per layer); CHIRPS/NDVI/ERA5 annual values match GEE's for 3 test points within 1%.
- Project-clipped tiles are transparent outside the area of influence.
- Downloads for UGA1072 come at native resolution (no 4 MP coarsening) within 30 s.
- With `EE_*` unset and `earthengine-api` uninstalled, all backend tests pass and all pages work.
- STAC API lists every collection with licence, citation and temporal extent.

## Risks

| Risk | Mitigation |
|---|---|
| One more service to run (TiTiler, STAC API) | eoAPI images, health checks, same Compose file for staging and IsDB |
| Planetary Computer needs SAS-token signing and may change terms | Use it only to discover/mirror; production reads our own lake |
| Yearly jobs fail silently | Celery beat + run log in admin; STAC item missing → layer shows "data for {year} not available" |
| Storage size at IsDB | Member countries only; ≈ 350 GB; decision with IMDT (plan decision 5) |
| Licences | All listed datasets are open (CC-BY 4.0 for WorldCover/WorldCereal/JRC, Copernicus licence for DEM and ERA5, public domain for MODIS/CHIRPS, CC-BY for WaPOR); record citations in STAC collections |

## Open decisions

1. Approve the eoAPI-style stack (pgSTAC + TiTiler) over GeoServer. **Recommended.**
2. Production: mirror into IsDB object storage (recommended) or keep reading public buckets.
3. Drop Dynamic World from the roadmap in favour of WorldCover + Esri 10 m annual land cover.
4. Timing: start G1–G4 in parallel now behind `RASTER_BACKEND`, switch after the demo.
