# Earth Map (FAO): detailed analysis for GEIDA

Prepared 9 Nov 2026 by Aman (with Claude Code) from a signed-in session on
<https://earthmap.org>, FAO's help centre and published descriptions. Area used for
testing: Uganda. Purpose: learn what Earth Map does well before building GEIDA further.

---

## 1. Summary

**Earth Map** is FAO's free web platform for "Google Earth Engine without coding": pick an
area, switch on any of **166 global layers in 19 themes**, and get maps, statistics, time
series, anomaly maps and suitability maps in a few clicks. It runs on Google Earth Engine
(GEE), was launched with Google in September 2020, and is part of FAO's Open Foris family.

What it does very well, and GEIDA should learn from:

1. **Area first.** The user chooses an area of interest before anything else; layers and
   boundaries follow from it.
2. **One consistent layer card.** Every layer has the same controls: period stepper,
   value filter, opacity, download, "about", compare two dates, remove.
3. **Statistics for every layer** ("Insights"), on any polygon or several polygons, as a
   chart and CSV.
4. **Time dimension built in.** Yearly, monthly, yearly-anomaly, monthly-anomaly and
   period-anomaly maps with a user-set baseline (default 2001–2020).
5. **Pixel Inspector.** Click a point to get a full time series (e.g. monthly NDVI
   2000–2025) with a linear trend and a significance verdict.
6. **Suitability / Risk / Probability builder.** Score layers 1–3, weight them to 100%,
   preview the result; an AI assistant proposes layers and weights.
7. **"Explain with AI".** Writes a structured report (introduction, metrics, trends,
   implications, recommendations) from the statistics, with a disclaimer.
8. **Analysis units beyond admin areas.** Districts, municipalities, protected areas and
   HydroSHEDS river basins (levels 6–12), plus your own drawn or uploaded polygons.
9. **Everything in the URL.** Area, boundary, layers, opacity, configuration and open panels
   are encoded in the address, so every view can be shared (short links, social, e-mail).
10. **Transparent sources.** Each layer's "about" card gives the description, citation, the
    GEE asset, the script, and links to more information and the data source.

What GEIDA should **not** copy: the dependency on Google Earth Engine (accounts, quotas,
terms, hosting outside IsDB), Google basemaps, and layers that are not cut to the area.
GEIDA's own strengths stay: the IsDB project cycle, Results Framework and CRIs, evidence
review, project areas, and open hosting.

---

## 2. What Earth Map is

| Aspect | Finding |
|---|---|
| Owner | Food and Agriculture Organization of the UN (FAO); developed with Google |
| Launch | 16 Sep 2020 (FAO–Google partnership since 2015) |
| Family | FAO Open Foris (with Collect Earth, SEPAL); linked from FAO's Hand-in-Hand Geospatial Platform |
| Engine | Google Earth Engine: layers and statistics are computed on demand in the cloud |
| Basemap | Google Maps (Map / satellite / terrain, labels toggle) |
| Access | Sign in with Google, sign in with e-mail, or access anonymously; free |
| Languages | English, Spanish, French, Portuguese (no Arabic) |
| Help | Help centre (how-to guides, datasets, customised datasets, guided use cases, FAQ, publications), Open Foris support forum, contact form |
| Spin-offs | Customised versions for projects: Whisp (EU deforestation regulation due diligence), AIM4Forests, UNEP-FAO Strata, North Macedonia Agroecological Atlas, Dryland Sustainable Landscapes, PILAFOLUR, ROOTS |
| Reference | Morales C. et al. 2023, *Earth Map: A Novel Tool for Fast Performance of Advanced Land Monitoring and Climate Assessment*, Journal of Remote Sensing 3:0003 |
| Recognition | Google Geo for Good Impact Award |

---

## 3. Interface, section by section

```
┌ Header: logo · Find location / coordinates · user · help · language · share ─────────────┐
│ Left panel                   │ Map                                   │ Right panel        │
│  1 Area of interest          │  Legend card (one row per layer)      │  Analytics         │
│  2 Boundary (+ add, … list)  │  Basemap: Map ▾  · Labels             │  or                │
│  3 My custom maps            │  Coordinates readout                  │  Pixel Inspector   │
│  4 Filter layers             │                                       │                    │
│  5 Layer catalogue (19)      │                                       │                    │
└──────────────────────────────┴───────────────────────────────────────┴────────────────────┘
```

### 3.1 Area of interest
A dropdown of every country plus regions and programmes (e.g. "Africa", "Africa's Great
Green Wall", "Antarctica"). Until an area is chosen the panel says *"Select an area of
interest — available layers and boundaries will be shown."* Choosing one zooms the map and
loads that area's boundaries.

### 3.2 Boundaries (analysis units)
- **Boundary list:** International boundaries, Districts, Municipalities, National Parks
  (WDPA, UNEP-WCMC), Basins level 6–12 (WWF HydroSHEDS).
- **"+" Add boundary:** draw a polygon, or upload a zipped shapefile, GeoJSON, KML or KMZ.
- **"…" My boundaries/polygons:** list, delete and download boundary sets; includes
  **UN 2023** versions of international boundaries, regions and districts. Selected units use
  FAO **GAUL** ids (e.g. `feature=gaul_165` for Uganda).

### 3.3 My custom maps
Saved suitability, risk and probability maps (see 3.8). Empty state with a "Click here to
create one" link.

### 3.4 Layer catalogue
19 collapsible themes with a text filter. Each layer row has an **info** button and an
**on/off** switch. Dynamic layers open a **Configure** dialog when switched on:
year, map type (*Yearly, Monthly, Yearly anomaly, Monthly anomaly, Period anomaly*) and,
for anomalies, an **advanced baseline period** (default 2001–2020).

**About this layer** card: description, citation (e.g. *GHS-POP R2023A, European Commission
JRC*), and buttons **GEE Asset**, **Script**, **More info**, **Data source**.

### 3.5 Legend card (one row per layer)
Drag handle to reorder · previous / next period · date picker · **"Show values where"**
threshold filter (e.g. ≥ 0) · opacity · **download layer** · about · **compare two dates**
(side-by-side) · remove. Colour ramp with min, max and unit.

### 3.6 Analytics panel ("Insights")
1. Click a region on the map (or "Select multiple polygons").
2. Pick an **Insight**: the layers currently on the map come first, then every layer by
   theme, then special tools:
   **B-INTACT** (biodiversity assessment), **Climate projections – NASA NEX CMIP6**,
   **Climatic water deficit**, **Biomass-fire emissions**, **Global Forest Change
   2000–2024**, **Tree restoration potential**, **LPD by land use**, **ERA5-Land
   precipitation**, **WaPOR (Africa)** components, **Whisp – supply-chain due diligence**.
3. **Process** → a result card (chart; e.g. Uganda population 1975–2030 from GHSL:
   11.7 M → 44.4 M in 2020 → 58.4 M projected for 2030) with **info**, **Explain**,
   **download**, **enlarge**, **close**. Several cards stack.

Analyses can take minutes for large areas (FAQ). Exports: chart image and CSV.

### 3.7 Explain with AI
Generates a structured report from the statistics: *Introduction, Breakdown of key metrics,
Trends and patterns, Implications, Recommendations*, with exact values, a copy button and
an FAO disclaimer (*informational only, not official FAO policy; verify with FAO sources*).

### 3.8 Custom map builder (`/suitability`)
- **Types:** Suitability, Risk, Probability; choice of legend colours.
- **Steps:** add layers (or "Create map using AI assistant"), **score** each layer's values
  1–3 (by value range for continuous data, by class for categorical), assign **weights**
  totalling 100%, **preview**.
- Suggested uses: agriculture siting, renewable energy, urban development, conservation.

### 3.9 Pixel Inspector
"+ New point", click the map: coordinates plus the value of every visible layer at that
point; for time-series layers a **chart over the full record** (NDVI: Feb 2000 – Dec 2025)
showing monthly mean, linear trend and monthly deviation, a date-range slider, and a
verdict such as *"Strong evidence of a significant trend."*

### 3.10 Sharing, help, account
- **Share:** generates a short URL; Facebook, X, WhatsApp, LinkedIn, e-mail, copy link.
- **URL state:** `aoi`, `boundary`, `map` (centre, zoom, basemap), `layers` (with opacity),
  `feature` (selected unit), `scripts` (analysis settings such as date range), per-layer
  `…_config` (map type, year, baseline), `mainmenu`, `statisticsOpen`.
- **Help menu:** Help centre / tutorials, support forum, about, disclaimer, contact us.
- **User menu:** options, **Get token for API**, sign out.

---

## 4. Data catalogue (Uganda selected: 166 layers, 19 themes)

| Theme | Layers | Main sources |
|---|---|---|
| Agricultural Stress Index System (ASIS) | 13: ASI annual and dekadal, drought intensity, historic drought frequency, crop/pasture phenology, VCI, VHI, weighted mean VHI | FAO ASIS |
| Agriculture | 7: cropland (GFSAD1000, GFSAD30, UMD GLAD), GAEZ agro-ecological zones and suitability (rain-fed high / low inputs), oil palm plantation year | NASA/USGS, FAO/IIASA GAEZ, UMD |
| Biodiversity | 9: Ecosystem Integrity Index, endemicity, extinction risk, vulnerability (WWF), tree species richness, IUCN Global Ecosystem Typology (biomes, functional groups), RESOLVE biomes and ecoregions | WWF, IUCN, RESOLVE |
| Climate | 15: aridity index and change, extreme-rain / frost / heat-stress / heatwave days (thresholds editable), FAO ecological zones, IPCC climatic zones, min / mean / max temperature (ERA5-Land), PET (MODIS), precipitation (CHIRPS, ERA5-Land) | ECMWF, UCSB CHC, NASA, FAO, IPCC |
| Climate projections | 11: flooding RCP 4.5 / 8.5; precipitation, Tmax, Tmin for baseline, SSP4.5, SSP8.5 | NASA NEX-GDDP-CMIP6 and flood models |
| Emissions | 4: biomass fires (CCI, MODIS), drained organic soils, fires in organic soils | ESA CCI, MODIS, FAO |
| Energy | 9: mining footprints, offshore wind turbines, Global Power Plant Database, oil and gas infrastructure, solar and wind farms, TransitionZero Solar Asset Mapper, dams, reservoirs | WRI, research datasets |
| Fire | 4: burned-area frequency, last fire year, fires by land use (MODIS MCD64A1), forest loss due to fire | NASA MODIS, UMD GLAD |
| Forestry | 23: ESA CCI biomass, forest integrity, forest typology, natural vegetation (Bastin), drivers of forest loss, canopy height (UMD, Meta/WRI), Global Forest Change, intact forest landscapes, JRC forest cover 2020 (EUDR), tropical moist forest, forest types, natural forests (Google DeepMind), RADD and GLAD-S2 alerts, restoration potential | ESA, UMD GLAD, JRC, WRI/GFW, Meta, Google DeepMind, WUR |
| Geophysical | 6: elevation, slope, aspect, contours (SRTM), Kapos mountains, landforms | NASA SRTM, UNEP-WCMC |
| Hydrology | 11: curve number (several), hydrologic soil groups (HSG, HYSOGs250m), HydroLAKES, major rivers, HydroSHEDS river network, runoff, total available water | WWF HydroSHEDS, ORNL, SoilGrids |
| Imagery | 14: JRC Sentinel-2 false-colour mosaics 2015–2020 and change, Landsat annual and 8/9, PALSAR yearly, Sentinel-1 SAR, Sentinel-2 annual and false-colour mosaics | ESA, USGS, JAXA, JRC |
| Land cover / land use | 14: CGLS-LC100, Dynamic World, Esri 2017–2025, GLC_FCS30D, GLAD land cover change, Global Pasture Watch, GlobCover, IPCC land-use classes (CCI, CGLS), ESA CCI 1992–2022, Africa 20 m 2016, MODIS (combined, IGBP), ESA WorldCover | ESA, Copernicus, Google/WRI, Esri, UMD, CAS |
| Land degradation neutrality | 1: land productivity dynamics trend (MODIS) | UNCCD method |
| Protected areas | 2: WDPA, nature-based carbon offset projects | UNEP-WCMC |
| Social | 8: accessibility to healthcare (Malaria Atlas Project), GHSL built-up, global road density (GRIP), night lights (VIIRS yearly and anomalies), population (GHSL, WorldPop), settlement grid (GHSL SMOD) | MAP, JRC, PBL GRIP, NASA/NOAA, WorldPop |
| Soil | 4: soil organic carbon (GSOC), histosols, IPCC soil classes (HWSD 2.0), soil texture at six depths (OpenLandMap) | FAO, IIASA, OpenLandMap |
| Vegetation | 2: NDVI (MODIS), WaPOR net primary production | NASA, FAO WaPOR |
| Water | 9: JRC surface water occurrence, change, transitions; WaPOR AETI, E, RET, T, water productivity; water deficit (MODIS) | JRC, FAO WaPOR, NASA |

Dynamic layers (climate, NDVI, WaPOR, water deficit) support yearly and monthly maps and
anomaly detection. Layer availability depends on the chosen area (some products are
regional, e.g. WaPOR L2 Africa).

---

## 5. Where the data come from

- **All layers are Google Earth Engine assets** (public GEE catalogue or FAO-hosted
  assets), shown by the "GEE Asset" and "Script" buttons on every layer card.
- Each layer is rendered and summarised **on demand by an Earth Engine script**; the
  `scripts` URL parameter carries the analysis settings. Nothing is pre-processed per area.
- **Publishers:** FAO (ASIS, WaPOR, GAEZ, GSOC, ecological zones), EC JRC (GHSL, surface
  water, forest), ESA (WorldCover, CCI, Sentinel), NASA (MODIS, SRTM, NEX-GDDP-CMIP6,
  VIIRS), ECMWF (ERA5-Land), UCSB (CHIRPS), UMD GLAD, WWF (HydroSHEDS), UNEP-WCMC (WDPA),
  WRI/GFW, Meta, Google DeepMind, Malaria Atlas Project, PBL (GRIP), WorldPop, OpenLandMap.
- **Boundaries:** FAO GAUL; UN 2023 boundaries; WDPA; HydroSHEDS basins.
- **Basemap:** Google Maps.
- **Account model:** the FAQ says access needs a Google account with Earth Engine enabled;
  in practice e-mail and anonymous access also work (computation probably runs under FAO's
  own Earth Engine project).

---

## 6. Technology (observed)

| Layer | Observation |
|---|---|
| Front end | React single-page app with Material UI components; Google Maps JavaScript API |
| Sign-in | Firebase Authentication (`production-earthmap.firebaseapp.com`): Google, e-mail, anonymous |
| Compute | Google Earth Engine for tiles, statistics, time series, anomalies, suitability |
| State | Entire view encoded in the URL; short-link service for sharing |
| Extensibility | "Plugin" layers (e.g. `PluginNDVI`) with their own configuration; customised deployments on subdomains |
| API | Per-user API token from the user menu |
| AI | LLM-generated explanations of statistics and AI-suggested suitability layers and weights |

---

## 7. Strengths and limitations

**Strengths**
- Very large, well-curated catalogue of trusted global datasets, each with citation.
- Consistent controls, so learning one layer teaches every layer.
- Time-aware analysis (anomalies, baselines, trends with significance) without coding.
- Analysis on many kinds of units (admin, protected areas, basins, own polygons).
- Shareable state, exports, multilingual, free.

**Limitations**
- **Locked to Google Earth Engine:** availability, quotas and terms are Google's; not
  self-hostable; a poor fit for IsDB hosting, which is why GEIDA moved off GEE.
- **Layers are not clipped to the area** on the map (they show across borders).
- **Generic, not project-aware:** no projects, no results framework, no indicators, no
  evidence or review workflow, no project-cycle stages.
- **Little vector infrastructure:** no schools, health facilities or road network as
  features (only road density, power plants, dams, etc.); no OpenStreetMap themes.
- Analyses can take minutes; boundaries are GAUL (outdated in places); no Arabic.
- The FAQ says "no forecasts", yet a *Climate projections* theme exists: documentation lags
  the product.

---

## 8. Earth Map compared with GEIDA today

| Capability | Earth Map | GEIDA (9 Nov 2026) |
|---|---|---|
| Purpose | Land and climate monitoring for everyone | EO evidence for the IsDB project cycle |
| Starting point | Area of interest | Project and its area of influence |
| Raster catalogue | 166 layers, 19 themes (GEE) | About 30 catalogue entries (COGs via TiTiler, view-only services; some planned) |
| Vector features | Few (energy, dams, protected areas) | OSM schools, health, roads, buildings, water, power… |
| Clipped to area | No | Yes (project data layers) |
| Statistics per layer | Yes, any polygon(s) | Through analysis modules only; per-layer zonal statistics planned |
| Time series and anomalies | Yes, with baselines and trend test | Year picker only |
| Point time series | Yes (Pixel Inspector) | No |
| Suitability / MCDA | Yes, with AI suggestions | Not built (gap analysis P6) |
| AI explanation | Yes | No |
| Project / RF / CRI / evidence | No | Yes |
| Map export | Chart / layer download | Full layout editor (PDF, SVG, PNG up to 600 dpi) |
| Layer styling | Opacity, value filter | Opacity, palette, range, colours, size |
| Sharing | URL state, short links, social | Tabs and run in the URL only |
| Hosting | Google / Firebase | Own servers, open stack, movable to IsDB |
| Languages | EN, ES, FR, PT | EN |

---

## 9. What GEIDA should borrow (prioritised)

| # | Idea | Why for IsDB | Fits in GEIDA | Effort |
|---|---|---|---|---|
| 1 | **Per-layer statistics ("Insights")** for every data layer over the project area, its admin units, or basins: mean / sum / class areas per year, chart + CSV | Turns the data catalogue into evidence; planned "zonal stats" | Analyses → Data layers: "Statistics" button per layer; backend zonal stats on COGs (rasterio) | M |
| 2 | **Uniform layer card** in the Layers panel: period stepper, value filter ("show values where"), opacity, download, about, compare dates, remove | Consistency; less learning | Extend the existing Layers panel | S–M |
| 3 | **Yearly / monthly / anomaly maps with a baseline** for time-series layers (WaPOR, CHIRPS, NDVI once processed) | Change since baseline is what PIASR and PCR need | Map type + baseline in the layer configuration; anomaly computed in TiTiler expressions or pre-processed COGs | M |
| 4 | **Point time series with trend test** (Mann-Kendall / Sen's slope) | Quick "has it changed?" checks for Verify roles | Click map → backend samples the COG stack → chart | M |
| 5 | **Suitability / risk builder** (score 1–3, weights to 100%, preview), later AI-suggested weights | Site selection (course W2), resilience screening | New module family "Site selection" using data layers as criteria | L |
| 6 | **More analysis units:** HydroSHEDS basins (levels 6–12), protected areas (WDPA), user polygons, multi-polygon comparison | Water and agriculture projects work by basin | `ctx.zones(source=…)`; basins and WDPA as boundary sources | M |
| 7 | **"About this layer" card** with citation, licence, resolution, period, source link, and how it was computed | Trust and auditability for IMDT and reviewers | Catalogue already holds most fields; add a card | S |
| 8 | **Explain with AI** for run results and statistics, clearly labelled, never written into the Results Framework | Faster write-ups for PCN / PCR drafts | Summary panel on a run; disclaimer; stays evidence | M |
| 9 | **Shareable map state** (area, layers, styles, periods in the URL) and short links | Reviewers open exactly what the author saw | Encode workspace state in query parameters | S–M |
| 10 | **Compare two dates** side by side or with a swipe | Before / after for project outputs | MapLibre compare plugin on the project map | S |
| 11 | **Languages:** French and Arabic first (IsDB member countries) | Reach beyond English-speaking staff | i18n on the frontend; layer names as data | L |
| 12 | **API token** for programmatic access to statistics | Integration with IsDB systems | Token auth on read endpoints | M |

**New datasets seen in Earth Map worth adding** (all published by trusted sources; check
non-GEE access): FAO ASIS drought indicators, GAEZ zones and suitability, WDPA, HydroSHEDS
basins and rivers, Global Power Plant Database (WRI), Malaria Atlas Project accessibility
to healthcare, GRIP road density, VIIRS night lights, NEX-GDDP-CMIP6 projections, Hansen
Global Forest Change, ESA CCI land cover and biomass. These go into the data inventory
(`GEIDA_data_inventory.xlsx`).

**Not to copy:** dependence on Google Earth Engine and Google basemaps; unclipped display;
analysis that ignores the project context.

---

## Sources

- Earth Map, signed-in session, 9 Nov 2026: <https://earthmap.org>
- Earth Map help centre and FAQ: <https://help.earthmap.org/home>, <https://help.earthmap.org/faq>, <https://help.earthmap.org/cooperation>
- FAO newsroom, *Google and FAO launch new Big Data tool for all* (16 Sep 2020): <https://www.fao.org/newsroom/detail/Google-and-FAO-launch-new-Big-Data-tool-for-all/en>
- UN-SPIDER, *Google and FAO develop web-based tool to facilitate big data access*: <https://un-spider.org/news-and-events/news/google-and-fao-develop-web-based-tool-facilitate-big-data-access>
- Morales C. et al. (2023), Journal of Remote Sensing 3:0003, DOI 10.34133/remotesensing.0003: <https://www.fao.org/3/cc4088en/cc4088en.pdf>
- Whisp help: <https://whisp-help.earthmap.org/>
