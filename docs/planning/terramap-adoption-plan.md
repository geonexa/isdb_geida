# What GEIDA can take from TerraMap (earthmap-dashboard)

Status: plan, 12 Nov 2026. Source reviewed: `Terra_ECD/earthmap-dashboard` ("TerraMap"), a
browser-only copy of FAO Earth Map's workflow with no Google Earth Engine: 67 layers in 15 themes
(46 NASA GIBS layers plus 21 others), special tools (ERA5 climate, CMIP6, terrain, land-cover change,
NDVI trend, power plants, World Bank indicators), a pixel inspector with trend tests, a suitability
builder, AI explanations, URL sharing and five languages including Arabic. Its `docs/` folder holds
FAO Earth Map's full list of 166 layers.

Companion document: [earthmap-analysis.md](earthmap-analysis.md) (what FAO Earth Map does and the
ideas to borrow). This plan is narrower: **which data and code from TerraMap fit GEIDA, how to get
them without GEE, and in what order**.

## 1. Summary

TerraMap's value for GEIDA is less its data (most of it is NASA GIBS map tiles) than:

1. **Open, keyless services that GEIDA doesn't use yet:** World Bank indicators, Open-Meteo
   (ERA5 and CMIP6 time series), ISRIC SoilGrids, WRI power plants, JRC surface water change
   layers, UNEP-WCMC protected areas.
2. **Methods ready to port:** Mann-Kendall / Sen's slope trend test, yearly / monthly / anomaly
   maps against a baseline, point time series, swipe comparison, suitability scoring, AI
   explanation of statistics.
3. **Product features:** country context panel, Arabic and French, shareable map state.

How TerraMap reads values matters: it **decodes the colours of map tiles back to values**
(`src/lib/raster.ts`), so its numbers are binned to the colour table and computed at coarse
zoom levels. That is fine for a quick look but **not good enough for evidence**. GEIDA keeps
reading the source data (COGs, APIs), and uses GIBS for display only.

## 2. Data sources

Verdict: **Analysis** = becomes an analysis input (values read from the source); **Display** =
Data Catalog layer for viewing only; **Context** = shown alongside a project, not mapped;
**Skip** = not worth it now.

| Source (in TerraMap) | What | Access without GEE | Licence | GEIDA today | Verdict |
|---|---|---|---|---|---|
| World Bank WDI API | Country indicators: population, urban share, electricity access, GDP per capita, forest, agricultural land, emissions | `api.worldbank.org/v2`, JSON, no key | CC BY 4.0 | None | **Context**: country panel on the project Overview (IsDB member countries), yearly series |
| Open-Meteo archive (ERA5) | Daily rainfall and temperature since 1940 at a point | REST, no key | Data CC BY 4.0; **API free for non-commercial use only** | ERA5-Land temperature listed as "planned" | **Analysis**: climate profile (normals 1991–2020, trends). Self-host Open-Meteo (open source) or subscribe if IsDB use counts as commercial. For area means, ERA5-Land COGs later |
| Open-Meteo climate (CMIP6) | Daily projections to 2050, 7 high-resolution models | REST, no key | As above; models are HighResMIP (one high-emission pathway) | None | **Analysis**, later: projected change at the project centre. For SSP2-4.5 / SSP5-8.5 choices use NASA NEX-GDDP-CMIP6 (on AWS, no key) |
| ISRIC SoilGrids | Clay, sand, silt, organic carbon, pH, bulk density, depths 0–200 cm, 250 m | COG / VRT files at `files.isric.org` (range reads); WMS for display | CC BY 4.0 | Planned `soil_properties` | **Analysis**: soil properties of the area; also feeds runoff curve numbers later |
| JRC Global Surface Water | Occurrence, **change intensity, seasonality, transitions** (1984–2021) | COG tiles on Google Cloud Storage (no GEE needed) | CC BY 4.0 (Copernicus) | Occurrence only | **Analysis**: add change and transitions to the planned `surface_water` (water gained, lost, seasonal) |
| WRI Global Power Plant Database | 35,000 plants: fuel, capacity, year | One CSV on GitHub | CC BY 4.0; last update 2021 | Planned `power_plants` | **Analysis**: plants in and near the area by fuel and capacity, alongside OSM. Note the 2021 cut-off |
| UNEP-WCMC WDPA | Protected areas (polygons) | ArcGIS REST query per country | **Non-commercial use only** without a licence (IBAT for commercial) | None | **Analysis** once the licence is cleared: overlap of the area with protected areas (safeguards screening); protected areas as analysis units |
| Hansen / UMD forest change | Tree cover 2000, loss by year | COG tiles | CC BY 4.0 | **Built** (`forest_loss`) | Done |
| Malaria Atlas Project | Travel time to health care | WCS | CC BY 4.0 | **Built** (`travel_time`) | Done |
| geoBoundaries | Admin levels 1–2 (CC BY 4.0) | API + GeoJSON | CC BY 4.0 | GADM 4.1 (**non-commercial licence**) | **Decision**: consider geoBoundaries as the open default for admin units (see §5) |
| Natural Earth | Countries, regions | GeoJSON | Public domain | Member-country outlines | Skip (GEIDA has its own) |
| EOX Sentinel-2 cloudless | Yearly cloud-free mosaic, display | WMTS | **2018+ CC BY-NC-SA 4.0**; 2016 CC BY 4.0 | **GEIDA's "Sentinel-2" basemap uses the 2020 mosaic** | **Decision**: switch to 2016 or GEIDA's own Sentinel-2 composites, or confirm non-commercial use (see §5) |
| NASA GIBS: MODIS NDVI/EVI, LST, snow, IGBP land cover, MERRA-2, GLDAS | Monthly maps | WMTS tiles, no key | NASA open data | NDVI and LST already displayed | **Display**: add snow cover, root-zone soil moisture (SMAP L4), GRACE groundwater anomaly. Values for analysis come from source products later |
| NASA GIBS: GEDI canopy height, biomass density | 1 km grids | Tiles (display); values need Earthdata login | Open | None | **Display** now; values later with an Earthdata token |
| NASA GIBS: VIIRS Black Marble | Night lights | Tiles | Open | Planned (electrification needs a token) | **Display** now; values for `electrification` from Black Marble files with a free Earthdata token |
| NASA GIBS: OPERA surface water (DSWx-HLS), MODIS 3-day flood | Recent water and floods | Tiles | Open | None | **Display**: quick "observed flooding" look; analysis later from Sentinel-1 |
| SEDAC hazard layers (NDH 1980–2003), human footprint, anthromes, GPW | Old global maps | Tiles | Open | GPW density displayed | **Skip** (dated; GHSL, WorldPop and modern hazard data replace them). Remove the GPW layer as proposed earlier |
| Esri imagery, OSM, Nominatim | Basemap, search | Tiles, API | Esri terms / ODbL | Already used | Done |

From **FAO Earth Map's 166 layers** (not in TerraMap), worth adding without GEE: FAO GAEZ v4
agro-ecological zones and suitability (FAO data portal), GCN250 curve numbers and HYSOGs250m soil
groups (runoff estimates), ESA CCI land cover 1992–2022, ESA CCI forest biomass, Land Productivity
Dynamics (land degradation), FAO ASIS drought indices (FAO GIEWS), GLAD cropland extent, Global
Drivers of Forest Loss, GRIP road density, and HydroLAKES/HydroRIVERS. **The HydroATLAS shapefiles
(BasinATLAS, RiverATLAS, LakeATLAS) are already in `geida_static_data/`**, so basins and rivers can be
used now.

## 3. Methods and code to port

| From TerraMap | What it does | In GEIDA | Effort |
|---|---|---|---|
| `src/lib/trend.ts` | Least squares, Sen's slope, Mann-Kendall test with p-value and a verdict ("significant increase") | Python in `ops/trend.py` (numpy/scipy, about 60 lines); used by every time-series analysis and the point inspector | S |
| `src/lib/computed.ts` | Yearly, monthly, yearly anomaly, monthly anomaly and period anomaly maps against a chosen baseline | Analysis option for WaPOR, rainfall, NDVI: "anomaly vs baseline 2018–2022", computed from the COGs on the run grid | M |
| Pixel inspector | Click → time series, trend, deviation from the monthly mean | Backend endpoint that samples a COG stack at a point (WaPOR 2018–2025, CHIRPS); chart in a map popup | M |
| Special tool "ERA5 climate" | Yearly rainfall and temperature 1981–last year, 1991–2020 normals, trends | New analysis `climate_profile` (planned): Open-Meteo at the area centre plus a few points, with the trend test | M |
| Special tool "CMIP6" | Projections to 2050 | `climate_profile` option, or later analysis `climate_projections` from NEX-GDDP-CMIP6 | M |
| Special tool "Power plants" | Count and capacity by fuel | Planned `power_plants`: GPPD CSV plus OSM `power=plant`, cut to the area plus a buffer | S |
| Special tool "World Bank" | Country indicators over time | Overview tab: "Country context" card (indicators chosen per theme, e.g. electricity access for energy projects); cached daily | S |
| `CompareOverlay.tsx` | Swipe between two dates or layers | Project map: compare two analysis layers or two years (MapLibre compare) | S |
| `Builder.tsx` + `computeCustomMap` | Suitability / risk map: score layers 1–3, weights to 100 % | Planned planning analyses (`suitability`, `candidate_sites`) on the run grid with source values, not tile colours | L |
| `src/lib/ai.ts` | "Explain with AI" from statistics (user's own key), template fallback | Run summary helper on the server with an IsDB-held key, clearly labelled, never written into the Results Framework | M |
| `src/i18n.ts` | Five languages, Arabic right-to-left | Frontend i18n starting with **Arabic and French** (most IsDB member countries) | L |
| `src/state.ts` URL state | The whole view in the URL | Encode project map layers, styles and years in the URL for reviewers | S–M |

## 4. What not to take

- **Colour-decoded values** from map tiles for any number that goes into evidence.
- **Browser-side computing** of statistics: GEIDA computes on the server, on the run grid, cut to
  the area, with a run record.
- **Dated global maps** (SEDAC hazards 1980–2003, human footprint, anthromes, GPW 2020).
- **User-held API keys** for AI: GEIDA would hold one key on the server.

## 5. Licence decisions

1. **Open-Meteo**: the API is free for non-commercial use. Decide whether IsDB's use counts as
   commercial. If it does, either subscribe or self-host Open-Meteo (open source).
2. **WDPA**: protected areas need a licence for commercial use (IBAT). Ask UNEP-WCMC, or leave
   protected areas out.
3. **EOX Sentinel-2 cloudless**: GEIDA's Sentinel-2 basemap uses the 2020 mosaic (CC BY-NC-SA).
   Switch to 2016 (CC BY), use GEIDA's own Sentinel-2 composites, or confirm the use is
   non-commercial.
4. **GADM**: free for non-commercial use only, with no redistribution. geoBoundaries (CC BY 4.0)
   is the open alternative for admin units shown and downloaded in GEIDA.

## 6. Build order

| Wave | Content | Size |
|---|---|---|
| A (quick wins) | `ops/trend.py`; World Bank country context on the Overview; `power_plants` (GPPD + OSM); JRC surface water change and transitions into `surface_water`; HydroBASINS (local) as analysis units; swipe compare; remove GPW | S each |
| B (climate and soil) | `climate_profile` (ERA5 via Open-Meteo: normals, trends, extremes such as days above 35 °C or 50 mm); `soil_properties` (SoilGrids COGs); anomaly maps for WaPOR yearly layers; point time-series inspector | M each |
| C (planning and reach) | Suitability builder; `climate_projections` (NEX-GDDP-CMIP6); AI explanation of runs; Arabic and French; display layers (SMAP, GRACE, GEDI, Black Marble, OPERA) | M–L |

Each analysis follows the usual pattern: manifest, `run.py`, METHOD.md, tests on synthetic or
fixture data, live runs on the test projects, docs and changelog.

## 7. Decisions needed

1. Licences in §5 (Open-Meteo, WDPA, EOX, GADM).
2. Start with wave A, and which items first.
3. Whether AI explanation is wanted, and who holds the key.
4. Languages: Arabic and French first?
