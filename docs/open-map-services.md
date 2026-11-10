# Open map services for GEIDA (WMS, WMTS, WCS, WFS, XYZ, ArcGIS)

Compiled 6 Nov 2026 for the Data Catalog and project data layers; §9 (infrastructure) added 9 Nov 2026.
"Tested" means GEIDA's team fetched the capabilities document or a tile from a
browser on 6 Nov 2026 and got a valid answer. "Documented" means the endpoint
comes from the provider's own documentation but was not tested.

## How these fit GEIDA

| What a service gives | Use in GEIDA | Catalogue `kind` |
|---|---|---|
| WMS / WMTS / XYZ / ArcGIS export: **coloured pictures** | Display: Data Catalog, project map, printed maps | `wms`, `xyz`, `arcgis_image` (all already supported by the Geo-Portal engine) |
| WCS / COG / ArcGIS ImageServer raw pixels: **values** | Analysis, statistics and GeoTIFF downloads | `cog` (TiTiler) or a future `wcs` kind |
| WFS / ArcGIS FeatureServer: **vector features** | Boundaries, facilities, overlays | future `wfs` kind |

WMS and WMTS layers can't feed analyses: they deliver coloured pixels, not
values. GEIDA keeps its COG path (TiTiler) for analysis and downloads, and can
use WMS/WMTS for fast display at every zoom level.

**Quick wins for DEM and land cover**
- Terrascope WMTS and WMS draw WorldCover and the Copernicus 90 m DEM at every zoom. GEIDA's COG layers only appear from zoom 7 or 8.
- Esri / Impact Observatory 10 m land cover adds yearly maps for 2017–2025.
- The terrestris SRTM layers and GEBCO give relief at every zoom.

---

## 1. Elevation and terrain

| Service | Protocol | Endpoint | Layers | Coverage, resolution | Terms | Status |
|---|---|---|---|---|---|---|
| **Terrascope MapProxy (VITO)** | WMS 1.3.0, WMTS | `https://mapproxy.terrascope.be/mapproxy/service?service=WMS&request=GetCapabilities` · WMTS `https://mapproxy.terrascope.be/mapproxy/wmts/1.0.0/WMTSCapabilities.xml` | `cop-dem-glo-90m-cog_dem` | Global, Copernicus DEM 90 m | No login for public layers; Copernicus DEM licence | **Tested** (GetMap 200, ~0.3 s) |
| **Terrascope WMTS** | WMTS (TIME dimension) | `https://wmts.terrascope.be/?service=WMTS&request=GetCapabilities` | `cop-dem-glo-90m-cog_dem` (DEM colour map) | Global, 90 m | No login | **Tested** (capabilities) |
| **terrestris / mundialis OWS** | WMS | `https://ows.mundialis.de/osm/service?service=WMS&request=GetCapabilities` (also `https://ows.terrestris.de/osm/service`) | `SRTM30-Hillshade`, `SRTM30-Colored`, `SRTM30-Colored-Hillshade`, `SRTM30-Contour`, `TOPO-WMS`, `TOPO-OSM-WMS` | Global, SRTM 30 m / 450 m | Free, no fees; attribution required (listed in the capabilities); free use to about 1:25,000, watermark beyond | **Tested** (capabilities) |
| **GEBCO** | WMS 1.3.0 | `https://wms.gebco.net/mapserv?request=getcapabilities&service=wms&version=1.3.0` | `GEBCO_LATEST` (shaded relief), `GEBCO_LATEST_2` (colour), `GEBCO_LATEST_SUB_ICE_TOPO`, `GEBCO_LATEST_TID` | Global land + sea floor, ~450 m | Free; credit GEBCO Compilation Group | **Tested** (capabilities) |
| **NASA GIBS** | WMTS, WMS | WMTS `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/1.0.0/WMTSCapabilities.xml` · WMS `https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi` | `SRTM_Color_Index`, `ASTER_GDEM_Color_Index`, `ASTER_GDEM_Color_Shaded_Relief`, `ASTER_GDEM_Greyscale_Shaded_Relief`, `GEDI_ISS_L3_Elevation_Mean_Lowest_Mode_*` | Global, to zoom 12 | No login; NASA open data | **Tested** (capabilities) |
| **Esri World Hillshade** | ArcGIS tiles (XYZ) | `https://server.arcgisonline.com/ArcGIS/rest/services/Elevation/World_Hillshade/MapServer/tile/{z}/{y}/{x}` | Hillshade (also `World_Hillshade_Dark`) | Global, multi-scale | Esri terms; attribution "© Esri" | Was in GEIDA's catalogue before 6 Nov |
| **AWS Terrain Tiles** | XYZ (Terrarium PNG) | `https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png` | Encoded elevation (decode in the client: MapLibre `raster-dem`) | Global, to zoom 15 | Open data, attribution per source | Documented |
| **OpenTopoMap** | XYZ | `https://{a-c}.tile.opentopomap.org/{z}/{x}/{y}.png` | Topographic map | Global | CC-BY-SA; light use only | Used as a GEIDA basemap |
| **Digital Earth Africa OWS** | WMS, WMTS, WCS | `https://ows.digitalearth.africa/wms?request=GetCapabilities&service=WMS&version=1.3.0` (also `/wmts`, `/wcs`; `ows-latest.` mirror) | Copernicus DEM 30 m (`dem_cop_30`), SRTM | Africa only | Open (CC BY 4.0) | **403 in our test**, retry from the server |
| Copernicus Data Space (Sentinel Hub) | WMS, WMTS, WCS | `https://sh.dataspace.copernicus.eu/ogc/wms/<INSTANCE_ID>` | Copernicus DEM 30/90 m, all Sentinel data | Global | **Free account and instance ID required**; quotas | Documented |

## 2. Land cover and land use

| Service | Protocol | Endpoint | Layers | Coverage, years | Terms | Status |
|---|---|---|---|---|---|---|
| **ESA WorldCover via Terrascope MapProxy** | WMS 1.3.0, WMTS | `https://mapproxy.terrascope.be/mapproxy/service?service=WMS&request=GetCapabilities` | `esa-worldcover-map-10m-2020-v1_map`, `esa-worldcover-map-10m-2021-v2_map`; also WorldCover NDVI, S2 true/false colour, SWIR, S1 VV/VH composites (2020, 2021); `LCM_2020` | Global, 10 m | No login; WorldCover CC BY 4.0 | **Tested** (GetMap 200, ~0.2 s) |
| **Terrascope WMTS** (TiTiler-backed) | WMTS + TIME | `https://wmts.terrascope.be/?service=WMTS&request=GetCapabilities` · GetTile e.g. `…?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=esa-worldcover-map-10m-2021-v2_map&STYLE=default&TILEMATRIXSET=EPSG:3857&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&FORMAT=image/png&TIME=2021-01-01` | WorldCover 2020/2021, **WorldCereal 2021** (`esa-worldcereal-temporarycrops-…`, `-activecropland-`, `-irrigation-`, `-maize-`, `-wintercereals-`, `-springcereals-`), `lcfm-lcm-10_map` (Land Cover and Forest Monitoring 2020) | Global, 10 m | No login | **Tested** (WorldCereal tile 200 in 0.9 s; WorldCover tile 200 but 17 s on first request) |
| Terrascope TiTiler WMS | WMS | `https://titiler.terrascope.be/wms?service=WMS&request=GetCapabilities` | Same collections as the WMTS | Global | No login | Documented |
| **Esri / Impact Observatory 10 m Land Use Land Cover** | ArcGIS ImageServer (`exportImage`; no WMS) | `https://ic.imagery1.arcgis.com/arcgis/rest/services/Sentinel2_10m_LandCover/ImageServer` | 9 classes; raster functions "Cartographic Renderer", "Isolate Crops/Built/Trees/Water/…" | Global, 10 m, **yearly 2017–2025** (use `time=`) | Copyright Impact Observatory, Microsoft, Esri (CC BY 4.0 per the producer) | **Tested** (exportImage PNG, anonymous) |
| **NASA GIBS** | WMTS | `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/1.0.0/WMTSCapabilities.xml` | `MODIS_Combined_L3_IGBP_Land_Cover_Type_Annual` (500 m, to 2024), `Agricultural_Lands_Croplands_2000`, `Landsat_Human_Built-up_And_Settlement_Extent`, `GRUMP_Urban_Extents_Grid_1995`, `Probabilities_of_Urban_Expansion_2000-2030` | Global | No login | **Tested** |
| Digital Earth Africa OWS | WMS, WMTS, WCS | see §1 | ESA WorldCover, ESA CCI Land Cover, Copernicus Global Land Cover, Esri LULC, Cropland extent (`crop_mask`), World Settlement Footprint (`wsf_evolution`), Global Mangrove Watch (`gmw`), Africapolis | Africa | Open | 403 in our test |

## 3. Water and hydrology

| Service | Protocol | Endpoint | Layers | Coverage | Terms | Status |
|---|---|---|---|---|---|---|
| **JRC Global Surface Water** | XYZ | `https://storage.googleapis.com/global-surface-water/tiles2021/{occurrence\|change\|seasonality\|recurrence\|transitions\|extent}/{z}/{x}/{y}.png` | One per path | Global, 30 m, 1984–2021 | EC JRC / Google, open | In GEIDA (`occurrence`) |
| **NASA GIBS** | WMTS | see §2 | `OPERA_L3_Dynamic_Surface_Water_Extent-HLS`, `-Sentinel-1`, `MODIS_Combined_Flood_1-Day/2-Day/3-Day`, `VIIRS_Combined_Flood_*`, `GRanD_Reservoirs`, `GRanD_Dams`, `MODIS_Terra_L3_Land_Water_Mask` | Global | No login | **Tested** |
| **GloFAS (Copernicus EMS)** | WMS-T | `https://ows.globalfloods.eu/glofas-ows/ows.py` | Flood forecasts, accumulated rainfall (`AccRain`, `AccRainEGE`), return periods | Global | Open, no credentials | Documented |
| Terrascope WMTS | WMTS | see §2 | Sentinel-2 water quality: `terrascope-s2-chl-v1_chl`, `-spm-`, `-tur-`, `-rhow-` | Global, 10–20 m, 2015– | No login | Listed in capabilities |
| Digital Earth Africa OWS | WMS, WCS | see §1 | Water Observations from Space (WOfS), Waterbodies, Water Quality | Africa | Open | 403 in our test |

## 4. Climate, vegetation and water productivity

| Service | Protocol | Endpoint | Layers | Coverage | Terms | Status |
|---|---|---|---|---|---|---|
| **NASA GIBS** | WMTS, WMS | see §2 | NDVI: `MODIS_Terra_L3_NDVI_Monthly`, `MODIS_Terra_L3_NDVI_16Day`, `MODIS_Terra_NDVI_8Day`, `VIIRS_SNPP_L3_NDVI_Monthly`, `Landsat_WELD_NDVI_Global_Annual`; EVI: `MODIS_Terra_L3_EVI_Monthly`; rain: `IMERG_Precipitation_Rate` (daily), `IMERG_Precipitation_Rate_30min`; land surface temperature: `MODIS_Terra_L3_Land_Surface_Temp_Monthly_Day/Night`, `VIIRS_SNPP_L3_Land_Surface_Temp_Monthly_Day`; soil moisture: `SMAP_L4_Analyzed_Root_Zone_Soil_Moisture`, `SMAP_L3_Passive_Day_Soil_Moisture`, `GLDAS_Underground_Soil_Moisture_Monthly`; `SMAP_L4_Mean_Gross_Primary_Productivity`; `MERRA2_Evaporation_Land_Monthly`; `GEDI_ISS_L4B_Aboveground_Biomass_Density_Mean_201904-202303`; drought/flood hazard (`NDH_*`) | Global; daily to annual (`{Time}` in the URL) | No login; NASA open data | **Tested** (capabilities) |
| **Terrascope WMTS** | WMTS + TIME | see §2 | `terrascope-s2-ndvi-v2_ndvi`, `-fapar-`, `-fcover-`, `-lai-` (Sentinel-2, 2015–); Sentinel-3 NDVI; PROBA-V NDVI (2013–2021) | Global | No login | Listed in capabilities |
| **FAO WaPOR v3** | COG (read by GEIDA's TiTiler) | `https://storage.googleapis.com/fao-gismgr-wapor-3-data/DATA/WAPOR-3/MAPSET/<code>/WAPOR-3.<code>.<period>.tif` | L1 (300 m): AETI, T, E, I, NPP, RET, PCP, RSM…; L2 (100 m): AETI, TBP, NPP…; annual `-A`, monthly `-M`, dekadal `-D` | Global (L1), Africa + Near East (L2), 2018– | Open, cite FAO | In GEIDA |
| GloFAS | WMS-T | see §3 | Rainfall accumulations | Global | Open | Documented |
| Digital Earth Africa OWS | WMS, WCS | see §1 | CHIRPS rainfall, ERA5, NDVI anomaly and climatology, fractional cover, WaPOR, DIWASA evapotranspiration, Sentinel-3 LST | Africa | Open | 403 in our test |

## 5. Population and settlements

| Service | Protocol | Endpoint | Layers | Coverage | Terms | Status |
|---|---|---|---|---|---|---|
| **NASA GIBS (SEDAC)** | WMTS | see §2 | `GPW_Population_Density_2000/2005/2010/2015/2020`, `GRUMP_Settlements`, `Human_Footprint_1995-2004`, `Estimated_Net_Migration_*`, `VIIRS_Black_Marble` (night lights 2016), `VIIRS_SNPP_DayNightBand_At_Sensor_Radiance` (daily) | Global, ~1 km | No login | **Tested** |
| WorldPop GeoServer | WMS, WFS, WCS | `https://ogc.worldpop.org/geoserver/ows?service=WMS&request=GetCapabilities` | Only `VaxPop:*` (vaccination coverage for some countries); **no population grids** | Selected countries | Open | **Tested** |
| **GHSL (JRC)**, WorldPop | COG on AWS Open Data | `https://jrc-ghsl.s3.amazonaws.com/ghs-pop/r2023a/4326/3asec/2020/GHS_POP_E2020_GLOBE_R2023A_4326_3ss_V1_0.tif` (also 2025, 1975–2030 epochs, 30″); built-up `…/ghs-built-s/r2023a/4326/3asec/2020/GHS_BUILT_S_E2020_GLOBE_R2023A_4326_3ss_V1_0.tif`; also `ghs-smod`, `ghs-built-v`, `ghs-built-h-*`; WorldPop GeoTIFFs at `data.worldpop.org` | Population (people per ~100 m cell), built-up surface (m² per cell), degree of urbanisation, building height and volume | Global, 3″ (~100 m) and 30″ | CC BY 4.0 | **Tested 9 Nov**: valid COGs (DEFLATE, 11 overview levels); GEIDA's TiTiler draws them (tile 200). Ready for the COG path: display, clip, download and analysis |

## 6. Soils and agriculture

| Service | Protocol | Endpoint | Layers | Coverage | Terms | Status |
|---|---|---|---|---|---|---|
| **ISRIC SoilGrids 2.0** | WMS, **WCS**, WFS (MapServer) | `https://maps.isric.org/mapserv/<property>` | Properties: `bdod`, `cec`, `cfvo`, `clay`, `nitrogen`, `ocd`, `ocs`, `phh2o`, `sand`, `silt`, `soc`, `wrb`, `wv0010`, `wv0033`, `wv1500`; layer names like `soc_0-5cm_mean`, `clay_15-30cm_Q0.5` (6 depths × mean/Q0.05/Q0.5/Q0.95/uncertainty) | Global, 250 m | CC BY 4.0 (ISRIC data policy) | **Tested** (service pages) |
| ISRIC Africa | WMS, WCS | `https://maps.isric.org/` → Rasters: `af250m_nutrient`, `gyga` | Africa soil nutrients, Global Yield Gap Atlas | Africa / selected countries | ISRIC policy | Listed |
| **FAO GAEZ v4** | ArcGIS ImageServer | `https://gaez-services.fao.org/server/rest/services/` (e.g. `res01`…`res07`, `LR`) | Agro-climatic resources, suitability, attainable yield, land resources | Global, 5′–30″ | FAO open (CC BY 4.0) | Documented |
| Terrascope WMTS | WMTS | see §2 | WorldCereal 2021 crop types and irrigation (see §2); CropSAR fAPAR/NDVI (Belgium only) | Global (WorldCereal) | No login | **Tested** |
| Digital Earth Africa | WMS, WCS | see §1 | iSDA soil (30 m), cropland extent | Africa | Open | 403 in our test |

## 7. Imagery (true colour, by date)

| Service | Protocol | Endpoint | Notes | Terms | Status |
|---|---|---|---|---|---|
| **Esri World Imagery Wayback** | WMTS | `https://wayback.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/WMTS/1.0.0/WMTSCapabilities.xml` | All archived World Imagery releases since 2014: the "imagery by date" for Verify roles (plan C2.8) | Esri terms (display) | Documented |
| **EOX Sentinel-2 cloudless** | WMS, WMTS/TMS | WMS `https://tiles.maps.eox.at/?SERVICE=WMS&REQUEST=GetMap&LAYERS=s2cloudless-2024_3857…`; TMS `https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2024_3857/default/g/{z}/{y}/{x}.jpg` | Yearly cloud-free 10 m mosaics 2016 and 2018–2024 (replace the year) | 2016: CC BY 4.0; 2018+: CC BY-NC-SA 4.0 (non-commercial; check s2maps.eu) | GEIDA basemap (2020) |
| **NASA GIBS** | WMTS | see §2 | `MODIS_Terra_CorrectedReflectance_TrueColor`, `VIIRS_SNPP_CorrectedReflectance_TrueColor` (daily, 250–375 m) | No login | **Tested** |
| Terrascope WMTS | WMTS + TIME | see §2 | `terrascope-s2-toc-v2_tci` (Sentinel-2 true colour by date, 2015–), `sentinel-2-ltmm-2017-2024_ltmm` | No login | Listed |
| Esri Landsat | ArcGIS ImageServer | `https://landsat2.arcgis.com/arcgis/rest/services/` → `Landsat8_Views`, `Landsat8_PanSharpened`; folders `Landsat`, `LandsatGLS` | Landsat by date, band combinations | Esri terms; some services may ask for a sign-in | Documented |
| Copernicus Data Space (Sentinel Hub) | WMS/WMTS/WCS | see §1 | Every Sentinel scene by date, custom band scripts | Free account and instance ID; quotas | Documented |

## 8. Boundaries, infrastructure and reference

| Service | Protocol | Endpoint | Layers | Terms | Status |
|---|---|---|---|---|---|
| **terrestris OSM WMS** | WMS | `https://ows.mundialis.de/osm/service` · `https://ows.terrestris.de/osm/service` | `OSM-WMS`, `OSM-WMS-no-labels`, `OSM-Overlay-WMS` (labels only), `Dark` | Free to ~1:25,000; attribution "© OpenStreetMap contributors, © terrestris…" | **Tested** |
| **UN ClearMap** | ArcGIS MapServer | `https://geoservices.un.org/arcgis/rest/services/ClearMap_WebTopo/MapServer` | UN-cleared basemap with UN boundary depictions | For the UN community; follow UN map guidelines and disclaimers | Documented |
| NASA GIBS | WMTS | see §2 | `Reference_Features`, `Reference_Labels`, `Coastlines` | No login | **Tested** |
| Global Forest Watch (UMD) | Data API | `https://data-api.globalforestwatch.org/dataset/umd_tree_cover_loss` (v1.13, loss to 2025) | Tree cover loss; tiles via the GFW API | CC BY 4.0 | Documented |
| FAO Hand-in-Hand platform | Catalogue (WMS links per dataset) | `https://www.fao.org/hih-geospatial-platform` | GAUL 2024 boundaries, many FAO layers | FAO terms | Documented |

## 9. Roads, rivers, buildings, health facilities and power

Tested 9 Nov 2026 from the development machine (tile or capabilities request, and the
`Access-Control-Allow-Origin` header the browser needs). These are **vector tiles** or
**PMTiles** archives read in place over HTTP range requests: nothing is downloaded or
stored by GEIDA. MapLibre draws them directly (project map, map export); the OpenLayers
Data Catalog needs `ol-mapbox-style` or the move to MapLibre.

| Service | Protocol | Endpoint | What it contains | Coverage | Terms | Status |
|---|---|---|---|---|---|---|
| **OpenFreeMap** (OpenStreetMap, OpenMapTiles schema) | Vector tiles (MVT), TileJSON | `https://tiles.openfreemap.org/planet` (TileJSON; tiles under a dated path it lists) · styles `https://tiles.openfreemap.org/styles/liberty` | `transportation` (roads, rail, by class), `waterway` (rivers, streams, canals), `water`, `building`, `poi` (class `hospital`, `school`, …), `aeroway`, `landuse`, `place`, `boundary` | Global, to z14 (overzoomed beyond); weekly OSM | Free, **no key, no request limits, commercial use allowed**; attribution required (OpenFreeMap, OpenMapTiles, OSM); no SLA; self-hostable (MIT) | **Tested** (TileJSON and tile 200, CORS `*`) |
| **OSM Foundation vector tiles** (Shortbread schema) | Vector tiles (MVT), TileJSON | `https://vector.openstreetmap.org/shortbread_v1/tilejson.json` · tiles `https://vector.openstreetmap.org/shortbread_v1/{z}/{x}/{y}.mvt` | `streets`, `water_lines` (rivers), `water_polygons`, `buildings`, `pois` (amenity, incl. hospitals), `public_transport`, `bridges`, `boundaries` | Global, to z14 | Donation-funded, best effort; **app-specific User-Agent and Referer required**, no bulk download, heavy or commercial use may be blocked | **Tested** (TileJSON and tile 200, CORS `*`). Fallback only |
| **Overture Maps** (OSM + Microsoft + Google + Esri and others, conflated) | PMTiles (one file per theme, HTTP range) | `https://overturemaps-extras-us-west-2.s3.us-west-2.amazonaws.com/tiles/2026-10-21.0/{theme}.pmtiles`, themes `transportation` (134 GB), `buildings` (181 GB), `places` (20 GB), `base` (water, land use, 192 GB), `divisions` (boundaries), `addresses`. New release monthly: list `…/?list-type=2&prefix=tiles/` | Roads with class and surface; **2.5+ billion buildings** (with height where known); places with categories (hospital, clinic, school, market, …); rivers and water bodies | Global | CDLA-Permissive 2.0 / ODbL by theme; attribution "© Overture Maps Foundation" and sources | **Tested** (range read returns the PMTiles header; CORS `*`) |
| **Google–Microsoft Open Buildings**, combined by VIDA | PMTiles | `https://data.source.coop/vida/google-microsoft-open-buildings/pmtiles/go_ms_building_footprints.pmtiles` (208 GB) | ~2.5 billion building footprints from Google (Africa, South and Southeast Asia, Latin America) and Microsoft (global), with source and confidence | Global | ODbL (Microsoft), CC BY 4.0 (Google) | **Tested** (range read, CORS `*`) |
| **Open Infrastructure Map** | Vector tiles (MVT) | `https://openinframap.org/map/power/{z}/{x}/{y}.pbf`, also `/map/telecoms/`, `/map/water/`, `/map/petroleum/`, `/map/other_pipeline/`, `/map/solar_heatmap/` (older `/tiles/…` endpoint is marked deprecated) | Power lines, substations, plants (with voltage and output), telecoms, water and oil/gas infrastructure | Global | Data ODbL; style CC BY 4.0; **no published tile-use policy**: ask the maintainers before production use | **Found** in the site's map code; terms to confirm |
| **Esri World Transportation** (reference overlay) | ArcGIS tiles (XYZ, transparent PNG) | `https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}` | Roads and railways with labels, to put over imagery or a data layer | Global | Esri terms; "© Esri" attribution | **Tested** (tile 200) |
| **Esri Hydro Reference Overlay** | ArcGIS tiles (hosted, transparent) | `https://tiles.arcgis.com/tiles/P3ePLMYs2RVChkJx/arcgis/rest/services/Esri_Hydro_Reference_Overlay/MapServer/tile/{z}/{y}/{x}` | Rivers, streams and water bodies with labels, cartographic | Global (most detail in the US) | Esri terms | **Tested** (service JSON 200) |
| **terrestris / mundialis OSM WMS** | WMS | see §8 | `OSM-WMS`, `OSM-Overlay-WMS` (roads and labels as a picture) | Global | Free to ~1:25,000 | **Tested** |
| healthsites.io | API (key), downloads on HDX | `https://healthsites.io` | Health facilities (from OSM), with attributes | Global | ODbL | No open tile or WMS service found; use OpenFreeMap / Overture `places` for display |
| HydroRIVERS (WWF HydroSHEDS) | Download only | `https://www.hydrosheds.org/products/hydrorivers` | River network with flow and order | Global | Free incl. commercial | No public map service found; would need hosting as PMTiles |

---

## Recommendations for GEIDA

1. **WorldCover display at every zoom.** Add Terrascope WMTS (`esa-worldcover-map-10m-2021-v2_map`, `…2020-v1_map`) as the display source for Land cover. Keep the WorldCover COGs for clips and downloads.
2. **DEM display at low zoom.** Use Terrascope `cop-dem-glo-90m-cog_dem` (WMTS) or GIBS `SRTM_Color_Index` below zoom 8, and switch to the 30 m COG layer from zoom 8.
3. **Hillshade.** Use terrestris `SRTM30-Colored-Hillshade` / `SRTM30-Hillshade` (WMS) or the Esri World Hillshade tiles. GEIDA's TiTiler hillshade stays for clipped downloads.
4. **New land cover layer.** Add Esri / Impact Observatory 10 m Land Use Land Cover, yearly 2017–2025, as a catalogue layer of kind `arcgis_image`, with a year selector mapped to `time=`.
5. **WorldCereal is back.** Terrascope serves WorldCereal 2021 (temporary crops, maize, cereals, irrigation) as WMTS. It is display only.
6. **NDVI, rainfall and land surface temperature until the processing step.** Add GIBS WMTS layers (`MODIS_Terra_L3_NDVI_Monthly`, `IMERG_Precipitation_Rate`, `MODIS_Terra_L3_Land_Surface_Temp_Monthly_Day`) with a date picker. They are display only; values come later from processed COGs.
7. **Population.** Add GIBS `GPW_Population_Density_2020` for display. GHSL/WorldPop COGs (AWS) are for analysis.
8. **Soils.** Add SoilGrids WMS for display; its WCS gives values for future modules (for example soil organic carbon, texture).
9. **Imagery by date (plan C2.8).** Esri Wayback WMTS (archived releases since 2014) and Terrascope Sentinel-2 TCI by date need no account.
10. **Infrastructure layers, global, without downloads (§9).**
    - *Roads, rivers, buildings, hospitals* in one source: **OpenFreeMap** vector tiles,
      styled per layer (`transportation`, `waterway`, `building`, `poi` where
      `class=hospital`). Free, no key, commercial use allowed.
    - *Buildings* in full: **Overture `buildings`** PMTiles (or the VIDA Google–Microsoft
      archive) from about zoom 13.
    - *Health facilities and services*: **Overture `places`** PMTiles filtered by
      category, or OpenFreeMap `poi`.
    - *Power and utilities*: **Open Infrastructure Map** tiles once its maintainers confirm
      use; otherwise OpenFreeMap has no power layer.
    - *Built-up and population values*: **GHSL** COGs on AWS through the existing TiTiler
      path. This also fills the population gap of the parked modules.
11. **Check before relying on these:**
    - Digital Earth Africa answered 403 to our browser; retry from the server or ask DE Africa.
    - Copernicus Data Space needs an account.
    - EOX 2018+ mosaics are non-commercial.

## Sources

- Terrascope OGC docs: <https://docs.terrascope.be/Developers/WebServices/OGC/WMTSv2.html>, <https://docs.terrascope.be/Developers/WebServices/OGC/MapProxy.html>
- NASA GIBS: <https://wiki.earthdata.nasa.gov/x/cBbVB>, <https://nasa-gibs.github.io/gibs-api-docs/access-advanced-topics/>
- ISRIC: <https://maps.isric.org/>, <https://docs.isric.org/globaldata/soilgrids/wcs.html>
- mundialis / terrestris: <https://www.mundialis.de/en/integrate-topographic-data-for-free/>, <https://terrestris.de/en/products/free-osm-wms/>
- GEBCO: <https://www.gebco.net/news/changes-gebco-wms-0>
- Digital Earth Africa: <https://ows-latest.digitalearth.africa/>, <https://docs.digitalearthafrica.org/en/latest/data_specs/>
- Copernicus Data Space: <https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/OGC/WMS.html>
- GloFAS / EFAS WMS: <https://confluence.ecmwf.int/spaces/CEMS/pages/247897113/CEMS-Flood+Web+Map+Service+WMS+-+General+Information>
- Esri: <https://ic.imagery1.arcgis.com/arcgis/rest/services/Sentinel2_10m_LandCover/ImageServer>, <https://www.esri.com/arcgis-blog/products/arcgis-living-atlas/imagery/wayback-server-connection-in-pro>, <https://landsat2.arcgis.com/arcgis/rest/services>
- EOX Sentinel-2 cloudless: <https://wiki.openstreetmap.org/wiki/Sentinel-2>
- WorldPop OGC: <https://sdi.worldpop.org/services/gis>
- GHSL on AWS: <https://registry.opendata.aws/ghs-pop/>
- FAO GAEZ: <https://gaez-services.fao.org/server/rest/services/res02/ImageServer/info/iteminfo>
- UN ClearMap: <https://geoservices.un.org/arcgis/rest/services/ClearMap_WebTopo/MapServer/info/iteminfo>
- GFW: <https://data-api.globalforestwatch.org/dataset/umd_tree_cover_loss>
- OpenFreeMap: <https://openfreemap.org>
- OSMF vector tile policy: <https://operations.osmfoundation.org/policies/vector/>
- Overture tiles: <https://docs.overturemaps.org/examples/overture-tiles/>, <https://docs.overturemaps.org/getting-data/cloud-sources/>
- Google–Microsoft Open Buildings by VIDA: <https://source.coop/vida/google-microsoft-open-buildings>
- Open Infrastructure Map copyright: <https://openinframap.org/copyright>
- Esri Hydro Reference Overlay: <https://www.esri.com/arcgis-blog/products/analytics/analytics/the-esri-hydro-reference-overlay-is-a-hosted-tile-layer-on-arcgis-online>
- HydroRIVERS: <https://www.hydrosheds.org/products/hydrorivers>
- GHSL on AWS: <https://registry.opendata.aws/ghs-built-s/>
