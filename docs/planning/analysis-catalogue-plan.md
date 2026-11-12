# GEIDA analysis catalogue: categories and plan

Status: draft v2 for discussion · 11 November 2026 · not on the docs site (`docs/planning/` is excluded)

This plan defines the **broad categories** that every analysis in a project's **Analyses** tab
will sit in, the analyses planned in each, and **which project phase each analysis appears
in**. It is the basis for choosing tools and building modules. Nothing here is built yet
beyond the modules marked *existing*.

Related: data inventory `docs/planning/GEIDA_data_inventory.xlsx` (IDs such as `T-01`),
Earth Map review `docs/planning/earthmap-analysis.md`, open services `docs/open-map-services.md`.

---

## 1. Principles

- **Few, broad categories.** A category is a domain a project team recognises ("Water",
  "People"), not a dataset or a technique. Land cover, NDVI or slope are analyses *inside*
  a category, never categories of their own. 8 categories hold everything planned.
- **Phase decides what is shown.** Each analysis is tagged with the phases it serves; the
  Analyses tab lists only the current phase's analyses (the module framework already has a
  `phases` field). The same analysis can serve several phases, with a different purpose.
- **Server-side, open source.** Analyses run as GEIDA modules on the worker (Celery) with
  GDAL / rasterio, GRASS GIS, WhiteboxTools and PostGIS. The browser Toolbox stays for
  ad-hoc work.
- **Open data, trusted publishers first:** (1) UN, World Bank, ESA / Copernicus, NASA, JRC,
  FAO, WRI; (2) OpenStreetMap; (3) Overture Maps; (4) other open services. A project's own
  national data always wins. Data marked ⚠ needs licence clearance first.
- **Every output answers a project question:** metrics, tables (CSV), map layers and, where
  it fits, a proposed value for a Results Framework indicator (CRI).

## 2. What each phase needs from analysis

| Phase | Report | What analysis is for | Typical outputs |
|---|---|---|---|
| **Preparation** | PPRR | Baseline of the area, feasibility, site selection, design inputs, environmental and social screening | Baseline values, suitability maps, risk and exposure, design parameters (catchment area, slope, demand) |
| **Implementation** | PIASR | Monitoring progress and conditions against the baseline: is construction happening, is land changing as expected, are risks materialising | Change since baseline, construction footprint, seasonal conditions (rain, vegetation), new hazards |
| **Completion** | PCR | Verifying outcomes and results: what changed between baseline and completion, who benefits, evidence for CRIs | Before / after comparison, beneficiaries reached, indicator values with sources |

## 3. The 8 categories

| # | Category | What it covers | Phases mostly used |
|---|---|---|---|
| 1 | **Terrain and site conditions** | The physical setting of the site: elevation, slope, aspect, contours, landforms, soils | Preparation |
| 2 | **Water resources** | Catchments and rivers, surface water, water balance and water accounting (precipitation, ETa, biomass, water productivity) | All three |
| 3 | **Land, vegetation and agriculture** | Land use and land cover, vegetation condition (NDVI, EVI…), crops and fields, forests, soils for farming | All three |
| 4 | **Climate and natural hazards** | Climate trends and anomalies, floods, drought, heat, landslides, and what is exposed to them | Preparation, implementation |
| 5 | **People and socio-economics** | Population, settlements, poverty and wealth, electrification, access to towns and services | Preparation, completion |
| 6 | **Infrastructure and services** | Buildings, transport (roads, rail, airports, seaports), social services (schools, health), public facilities, utilities and power / energy | All three |
| 7 | **Site selection and planning** | Multi-criteria suitability, candidate sites, service gaps, alternatives comparison | Preparation |
| 8 | **Monitoring and impact** | Change since baseline, construction progress, before / after outcomes, beneficiaries, CRI evidence | Implementation, completion |

How the earlier draft and the mandatory list fit:

| Topic you listed | Category |
|---|---|
| Building analysis | 6 Infrastructure and services (buildings), with settlement patterns in 5 |
| Infrastructure: roads, rivers, railways, buildings, hospitals, schools, airports, seaports, public infrastructure | 6 (rivers in 2) |
| Power infrastructure: electricity, power plants, power lines, solar | 6 (energy sub-group); solar / wind resource in 7 for siting |
| Topography: contours, DEM, slope, aspect | 1 Terrain and site conditions |
| Catchment delineation and analysis | 2 Water resources |
| Agricultural analysis: NDVI, EVI, field boundaries | 3 Land, vegetation and agriculture |
| Socio-economic parameters, population | 5 People and socio-economics |
| Site suitability | 7 Site selection and planning |
| Water accounting: ETa, precipitation, biomass | 2 Water resources |
| Land use and land cover | 3 Land, vegetation and agriculture |

Today's categories (`backend/modules/categories.yaml`) fold in: *Built environment*, *Social
services* and *Infrastructure networks* → 6; *Neighbourhood and access* → 5 and 7. The
existing **Area profile** module becomes a pinned summary above the categories.

---

## 4. Analyses by category and phase

Columns **P / I / C** = Preparation (PPRR) / Implementation (PIASR) / Completion (PCR).
● = shown in that phase. **Wave** = delivery order (1 first; see §6). *Existing* = runs today.

### 4.1 Terrain and site conditions

| Analysis | Answers | P | I | C | Main data | Engine | Wave |
|---|---|---|---|---|---|---|---|
| Elevation profile of the area | Min / max / mean elevation, hypsometry | ● | | | T-01 Copernicus DEM GLO-30 | GDAL, numpy | 1 |
| Slope and slope classes | How steep, how much land in each class | ● | | | T-01 | `gdaldem`, GRASS `r.slope.aspect` | 1 |
| Aspect | Which way slopes face | ● | | | T-01 | `gdaldem` | 1 |
| Hillshade and relief | Relief for maps and reports | ● | | | T-01 | `gdaldem` | 1 |
| Contours | Contour lines at a chosen interval (download) | ● | | | T-01 | `gdal_contour` | 1 |
| Landforms and ruggedness (TPI, TRI, geomorphons) | Ridges, valleys, plains | ● | | | T-01, Geomorpho90m | GRASS `r.geomorphon` | 2 |
| Soil properties | Texture, organic carbon, pH, depth for design | ● | | | SO-01 SoilGrids 2.0 | zonal statistics | 2 |
| Elevation profile along a line, viewshed | Alignment design, visibility | ● | | | T-01 | GRASS `r.profile`, `r.viewshed` | 3 |

### 4.2 Water resources

| Analysis | Answers | P | I | C | Main data | Engine | Wave |
|---|---|---|---|---|---|---|---|
| Catchment delineation from a point | Which area drains to the site, how big | ● | | | T-01, HydroSHEDS | GRASS `r.watershed`, `r.water.outlet` | 2 |
| Stream network and stream order | Rivers and streams, km by order | ● | | | T-01, W-01 HydroRIVERS | GRASS `r.stream.*` | 2 |
| Sub-basins in the area | Basin units for planning and reporting | ● | | | HydroBASINS | PostGIS | 1 |
| Rivers, lakes and reservoirs | What water bodies exist in / near the area | ● | | | W-01, W-04 HydroLAKES, GRanD | PostGIS | 1 |
| Surface water occurrence and change | Permanent / seasonal water, trend | ● | ● | ● | W-02 JRC GSW | zonal statistics | 1 |
| Water points | Wells, boreholes, taps; functionality | ● | ● | ● | W-03 WPdx+, OSM | PostGIS | 1 |
| Precipitation (annual, seasonal, anomaly, trend) | How much rain, is this year normal | ● | ● | ● | C-01 CHIRPS | zonal statistics, xarray | 1 |
| Evapotranspiration (ETa, T, E, I) | Water consumed by land and crops | ● | ● | ● | C-03 WaPOR v3 | zonal statistics | 1 |
| Water balance (P − ETa) | Surplus or deficit per year | ● | ● | ● | C-01, C-03 | numpy | 1 |
| ET deficit / relative ET (ETa / ETref) | Water stress | ● | ● | | C-03 | numpy | 2 |
| Water productivity and its gap | Biomass per m³ of water; potential gains | ● | | ● | V-02 WaPOR | numpy | 2 |
| Water accounting summary (WA+ style) | Resource base: inflows, consumption, outflows | ● | | ● | C-01, C-03, W-01 | numpy | 3 |
| Runoff estimate (curve number) | Runoff volume for design | ● | | | Land cover, SoilGrids, CHIRPS | numpy | 3 |

### 4.3 Land, vegetation and agriculture

| Analysis | Answers | P | I | C | Main data | Engine | Wave |
|---|---|---|---|---|---|---|---|
| Land cover composition | Area and share of each class, per admin unit | ● | ● | ● | L-01 ESA WorldCover, L-02 Esri / IO annual | numpy class counts | 1 |
| Land cover change between two years | What became what (transition matrix) | ● | ● | ● | L-02 annual 2017 onwards | GRASS `r.stats` | 1 |
| Vegetation indices (NDVI, EVI, SAVI, NDMI) for a period | Vegetation condition now | ● | ● | ● | Sentinel-2 L2A (STAC), V-01 MODIS | rasterio band maths | 1 |
| Seasonal profile and anomaly (2000 onwards) | Is this season better or worse than normal | ● | ● | ● | V-01 MODIS MOD13Q1 | xarray | 1 |
| Field boundaries | Number, size distribution and area of fields | ● | ● | ● | V-04 Fields of The World (GeoParquet) | GeoPandas, DuckDB | 1 |
| Per-field statistics | NDVI, biomass per field | ● | ● | ● | V-04, Sentinel-2, V-02 | zonal statistics | 2 |
| Cropland and irrigated area | Where crops and irrigation are | ● | | ● | V-03 ESA WorldCereal | zonal statistics | 1 |
| Biomass production | Agricultural output proxy | ● | ● | ● | V-02 WaPOR | zonal statistics | 1 |
| Forest cover and loss | Deforestation per year | ● | ● | ● | Hansen GFC (CC BY 4.0), JRC TMF | zonal statistics | 2 |
| Cropland / urban expansion | How farmland and towns grew | ● | | ● | L-02, GHSL | numpy | 2 |

### 4.4 Climate and natural hazards

| Analysis | Answers | P | I | C | Main data | Engine | Wave |
|---|---|---|---|---|---|---|---|
| Climate profile (rain and temperature normals, trends) | Long-term climate of the area | ● | | | C-01 CHIRPS, C-02 ERA5-Land | xarray | 1 |
| Drought indicators (rainfall anomaly, VCI) | Is the area in drought | ● | ● | | C-01, V-01 | xarray | 2 |
| Flood hazard | Flood-prone areas (return periods) | ● | ● | | W-05 JRC flood hazard, GloFAS | zonal statistics | 2 |
| Observed flooding / surface water extent | Where water went this season | | ● | ● | W-02, Sentinel-1 (later) | numpy | 3 |
| Landslide susceptibility | Slope + soils + rainfall proxy | ● | | | T-01, SoilGrids, CHIRPS | GRASS `r.mapcalc` | 3 |
| Heat (hot days, land surface temperature) | Heat stress | ● | | | ERA5-Land, MODIS LST | xarray | 3 |
| Exposure to hazards | People, buildings, roads, farmland in hazard zones | ● | ● | | Hazard layers + 5, 6, 3 | overlay | 2 |

### 4.5 People and socio-economics

| Analysis | Answers | P | I | C | Main data | Engine | Wave |
|---|---|---|---|---|---|---|---|
| Population and density | How many people, where, per admin unit | ● | | ● | P-01 GHSL, P-02 WorldPop | zonal statistics | 1 |
| Population change | Growth 2000 → 2020 / 2025 | ● | | ● | P-01, P-02 | numpy | 1 |
| Settlements | Villages and towns, size classes, degree of urbanisation | ● | | ● | S-03 GHS-SMOD, S-04 OSM places, building clusters | GeoPandas | 1 |
| Access to services | People within 2 / 5 km or 30 / 60 min of schools, clinics, markets, roads | ● | | ● | P-01 + layers from 6, MAP friction | GRASS `r.cost` | 2 |
| Travel time to towns and cities | Remoteness | ● | | ● | MAP accessibility | zonal statistics | 2 |
| Electrification proxy | Lit / unlit settlements, night-light trend | ● | ● | ● | U-02 NASA Black Marble | xarray | 2 |
| Relative wealth / poverty | Poorest areas | ● | | ● | P-04 Meta RWI ⚠ | zonal statistics | 2 |
| Subnational development indicators | HDI, education, health per region | ● | | ● | Global Data Lab (check terms) | table join | 3 |
| Census indicators (project upload) | Out-of-school, WASH, electricity per unit | ● | | ● | P-03 national census | table join | 3 |

### 4.6 Infrastructure and services

Sub-groups in the list: *Buildings*, *Transport*, *Social services*, *Public facilities*,
*Energy and utilities*.

| Analysis | Answers | P | I | C | Main data | Engine | Wave |
|---|---|---|---|---|---|---|---|
| Buildings and settlement density (*existing*: `buildings`) | How many buildings, what kind, how dense | ● | ● | ● | S-02 Open Buildings, Overture, OSM | PostGIS | Existing |
| Built-up area and growth | Built-up surface 1975–2030 | ● | | ● | S-01 GHSL | zonal statistics | 2 |
| Road network (*existing*: `road_network`, CRI 2.2) | Road km by class and surface | ● | ● | ● | R-01 OSM, Overture | PostGIS | Existing |
| Railways, airports, seaports | What transport hubs serve the area, how far | ● | | | OSM, OurAirports, World Port Index | PostGIS | 1 |
| Bridges and river crossings | Where roads cross rivers | ● | | | R-01 × W-01 | PostGIS | 2 |
| Schools (*existing*: `schools_inventory`, CRI 9.3) | Which schools, where | ● | ● | ● | E-01 Giga / EMIS, OSM | PostGIS | Existing |
| Health facilities (*existing*: `health_inventory`, CRI 8.1) | Which facilities, where | ● | ● | ● | H-01 healthsites.io, WHO / MoH | PostGIS | Existing |
| Public facilities | Markets, banks, offices, police, post, places of worship | ● | | ● | M-01 OSM, Overture places | PostGIS | 1 |
| Power grid | Lines (km), substations, distance to grid | ● | ● | ● | U-01 gridfinder, OSM power | PostGIS, GDAL proximity | 1 |
| Power plants | Plants by fuel and capacity (MW) | ● | | ● | WRI Global Power Plant Database | PostGIS | 1 |
| Telecoms, water and pipeline networks | Other utility networks | ● | | | U-03 Open Infrastructure Map | PostGIS | 2 |

### 4.7 Site selection and planning

Weighted multi-criteria analysis that combines layers from categories 1–6. Users pick a
preset or build their own criteria set.

| Analysis | Answers | P | I | C | Main data | Engine | Wave |
|---|---|---|---|---|---|---|---|
| Solar and wind resource | Where generation potential is best | ● | | | Global Solar Atlas, Global Wind Atlas (CC BY 4.0) | zonal statistics | 1 |
| Suitability map (presets: solar plant, school / clinic, irrigation scheme, water point, road alignment) | Where an intervention fits best | ● | | | Layers from 1–6; WDPA ⚠ for exclusions | numpy, GRASS `r.mapcalc` | 3 |
| Candidate sites | Ranked sites with their criteria values | ● | | | Suitability map | GRASS `r.clump` | 3 |
| Service gaps | Areas and people beyond reach of a service | ● | | | Access results (4.5) | numpy | 2 |
| Off-grid / mini-grid candidates | Unlit, far from grid, enough people | ● | | | 4.5, 4.6 | numpy | 3 |
| Alternatives comparison | Compare two or more candidate sites or alignments | ● | | | Any of the above | tables | 3 |

### 4.8 Monitoring and impact

Analyses that compare the area at two dates (baseline vs. now), mostly reusing the
measurements above with a before / after design.

| Analysis | Answers | P | I | C | Main data | Engine | Wave |
|---|---|---|---|---|---|---|---|
| Baseline snapshot | Freezes key indicators at appraisal for later comparison | ● | | | Results of 1–6 | stored run | 1 |
| Change since baseline (any indicator) | What changed: land cover, vegetation, water, buildings, roads | | ● | ● | Same sources at two dates | B6 change | 2 |
| Construction footprint and progress | New built-up / cleared land at the site | | ● | ● | Sentinel-2 by date, L-02, Open Buildings | numpy | 2 |
| Before / after imagery | Visual evidence for reports | | ● | ● | I-02 Sentinel-2, Esri Wayback | image export | 1 |
| Beneficiaries reached | People within reach of what was built | | | ● | 4.5 access, 4.6 assets | GRASS `r.cost` | 2 |
| Outcome indicators for CRIs | Indicator values with sources, as evidence | | ● | ● | Module results | evidence workflow | Existing (framework) |

---

## 5. Phase view (what the Analyses tab shows)

| Category | Preparation (PPRR) | Implementation (PIASR) | Completion (PCR) |
|---|---|---|---|
| 1 Terrain and site conditions | All | — | — |
| 2 Water resources | All | Surface water, water points, rain, ETa, balance, ET deficit | Surface water, water points, rain, ETa, balance, water productivity, WA+ |
| 3 Land, vegetation and agriculture | All | Land cover, change, indices, seasonal anomaly, fields, biomass, forest | Most (not per-season monitoring only) |
| 4 Climate and natural hazards | All | Drought, flood hazard, observed flooding, exposure | Observed flooding |
| 5 People and socio-economics | All | Electrification | Population, settlements, access, electrification, wealth, indicators |
| 6 Infrastructure and services | All | Buildings, roads, schools, health, grid | Buildings, built-up growth, roads, schools, health, facilities, grid, plants |
| 7 Site selection and planning | All | — | — |
| 8 Monitoring and impact | Baseline snapshot | Change, construction progress, imagery, CRI outcomes | Change, construction, imagery, beneficiaries, CRI outcomes |

Preparation shows the most (baseline and design); implementation narrows to what moves
during a project; completion focuses on before / after and evidence.

## 6. Shared building blocks and delivery

| Block | What it does | Used by |
|---|---|---|
| B1 Area data access | Clip COGs and STAC items to the area in UTM; read GeoParquet (Overture, Open Buildings, FTW) and OSM for the area | All |
| B2 Zonal statistics | Exact area-weighted statistics per area and admin unit (exactextract) | 2, 3, 4, 5, 6 |
| B3 Terrain and hydrology | DEM conditioning, slope, flow, watersheds, streams (GRASS + GDAL) | 1, 2, 4, 7 |
| B4 Distance and travel time | Proximity and cost distance on a friction surface | 5, 6, 7, 8 |
| B5 Time series | Seasonal and multi-year stacks, trends, anomalies (xarray) | 2, 3, 4, 5 |
| B6 Change detection | Two-date comparison and transition matrices | 3, 6, 8 |
| B7 Multi-criteria engine | Rescale, weight, constrain, combine, rank | 7 |
| B8 Results and evidence | Metrics, tables, layers, CRI evidence (exists) | All |

| Wave | Content | Needs |
|---|---|---|
| **1** | Terrain (basic), water: rain / ETa / balance / surface water / water points / sub-basins, land cover composition and change, vegetation indices and anomaly, fields, cropland, biomass, climate profile, population, settlements, transport hubs, public facilities, power grid and plants, solar / wind resource, baseline snapshot, before / after imagery | B1, B2, B5; data mostly in the catalogue |
| **2** | Catchments and streams, landforms, soils, ET deficit and water productivity, per-field statistics, forest loss, drought, flood hazard and exposure, access and travel time, electrification, wealth, built-up growth, bridges, change since baseline, construction progress, beneficiaries | GRASS on the server (B3, B4), B6 |
| **3** | Site suitability presets and candidate sites, WA+ summary, runoff, landslide and heat, observed flooding, profiles and viewshed, subnational and census indicators, alternatives comparison | B7; licence clearance; national uploads |

Python packages to add to `geida` (and the server, once agreed): GeoPandas, pyproj,
exactextract, pystac-client, DuckDB (spatial), xarray / rioxarray, GRASS scripting (needs
GRASS on the server).

## 7. Decisions needed

1. The 8 categories and their names.
2. The phase tags per analysis (§4), especially what implementation (PIASR) should show.
3. Primary hydrology engine: GRASS GIS (recommended) or WhiteboxTools.
4. Licence clearance for ⚠ data: Meta Relative Wealth Index, WDPA, FABDEM, MERIT Hydro.
5. Sentinel-2 source: Earth Search (AWS) or Microsoft Planetary Computer.
6. First site suitability presets.
7. When to add GRASS and the new packages on `ecd_server` (agreed before any change).
