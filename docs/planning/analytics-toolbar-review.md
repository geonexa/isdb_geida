# Analytics page: toolbar review

**Status:** first round applied on 17 Nov 2026 (`frontend/gis/apps/web/public/deployment.json`, locked):
US and France data portals, database connections (Add Data and the Browser panel), other map engines, visual
effects and demos, field and desktop-only items, items needing outside accounts or keys (Share, Comments, Earth
Engine, AI Providers, Geocoding and Cloud Storage settings), Help's Website, GitHub, Feedback, Diagnostics and
Check for Updates, and the Browser panel's built-in services (only OpenStreetMap, Sentinel-2 cloudless and GEBCO
kept).

Second round, same day: everything that asks for an API key, token or outside account, or sends users to another
site, is gone too. The AI Assistant and GeoAgent (`ai.enabled: false`), Share and the GeoLibre project Gallery
(`sharing.shareUrl: "off"`), Street View, Mapillary, ArcGIS Portal, NASA Earthaccess, Hugging Face, Cesium Ion and
CZML, Geocode Addresses, Directions, Turn-by-Turn Navigation and Reverse Geocode (with the right-click directions,
drive and walk time), View in Google Maps / Google Earth (menu and right-click), the right-click "What's here"
(Wikipedia), the Environment Variables and Manage Plugins settings, review comments, the Diagnostics badge (its
dialog reports to GeoLibre's GitHub), the Command Palette's Help links (the palette now follows the hidden lists),
and the Basemaps panel's keyed and single-country providers and its API keys page. The About dialog describes
GEIDA Analytics and credits GeoLibre without links; the status bar credit is plain text.

The other rows below are still open.

The Analytics page (`/analytics`) is GeoLibre, the open-source web GIS, with GEIDA's project layers added. It
ships with every GeoLibre feature: desktop-only items, US data portals, 3D and LiDAR tools, collaboration and
four map engines. This page lists every item as it appears in the running app and says whether GEIDA needs it.

**Who uses Analytics:** IsDB staff and partners, in a browser, working on a project's layers (analysis and
Toolbox results, area of influence) or their own files. Analyses and the Toolbox already run on the server, so
Analytics is for looking further: overlaying, extra processing, styling, comparing dates, making maps.

**Verdicts:** **Keep** · **Remove** · **Your call** (useful to some users, adds clutter for most).

## How to remove items (no code changes)

GeoLibre hides items through its UI profile, set by a `deployment.json` file at the app root
(`frontend/gis/apps/web/public/deployment.json`, now `null`). Its `interface` section takes:

- `hiddenMenus`: whole top menus (`project`, `edit`, `view`, `addData`, `processing`, `controls`, `plugins`, `help`)
- `hiddenMenuItems`: single items (ids in `frontend/gis/apps/web/src/lib/ui-profile.ts`, `MENU_ITEM_CATALOG`)
- `hiddenDataSources`: Add Data entries
- `hiddenPlugins`: Plugins menu entries
- `level` (`beginner`, `intermediate`, `advanced`) as a starting point, and `lock: true` so users can't turn
  hidden items back on in Settings

This keeps the GeoLibre code as it is, so later GeoLibre updates stay easy to take. Some items aren't in the
catalogue (the Settings menu, the status bar, the layer panel buttons) and need small code changes.

## Project

| Item | Verdict | Why |
|---|---|---|
| New… | Keep | Start a clean map |
| Open From › File… | Keep | Reopen a saved map file |
| Open From › URL… | Remove | Rarely used; files and project layers cover it |
| Open From › Gallery… | Remove | GeoLibre's sample projects (US and global demos) |
| Open Recent | Keep | |
| History… | Your call | Snapshots of the map; useful but rarely found |
| Import › QGIS Project… | Keep | Many staff and consultants use QGIS |
| Import › ArcGIS Pro Project… | Keep | Same for ArcGIS users |
| Import › Layer Styles… | Your call | Advanced |
| Save / Save As… | Keep | |
| Duplicate project | Remove | Save As covers it |
| Save as template… | Remove | Niche |
| Share… | Remove | Needs GeoLibre's sharing server; GEIDA shares through projects and reports |
| Export › Export as HTML… | Keep | A stand-alone web map to send |
| Export › Export Layer Styles… | Your call | Advanced |
| Export › Export Layers… | Keep | Download results |
| Print Layout… | Keep | Maps for reports and missions |
| Offline Basemap… | Remove | Desktop and field use |
| Story Map… | Your call | Nice for communication; not core |

## Edit

| Item | Verdict | Why |
|---|---|---|
| Undo, Redo | Keep | |
| Select by Expression…, Select by Location… | Keep | Basic GIS selection |
| Zoom to, Invert, Clear Selection | Keep | |
| Export Selected Features as Layer | Keep | |

The whole menu stays.

## View

| Item | Verdict | Why |
|---|---|---|
| Zoom In / Out | Remove | Duplicates the map's + and − buttons |
| Previous / Next View | Keep | |
| Reset Orientation | Keep | |
| Set View… | Keep | Go to coordinates |
| Split View (1 to 3 × 3 maps, Sync views) | Keep | Compare dates or layers side by side |
| Color vision preview | Remove | Accessibility check for map makers; niche |
| Rendering engine › MapLibre | Keep | The only engine GEIDA styles and tests |
| Rendering engine › Mapbox, ArcGIS, Cesium | Remove | Need outside accounts or keys; untested with GEIDA layers |
| View in Google Maps / Google Earth | Your call | Quick check of a place; sends the location to Google |

## Add Data

| Item | Verdict | Why |
|---|---|---|
| Vector Layer, Raster Layer | Keep | Shapefile, GeoPackage, GeoJSON, GeoTIFF |
| Delimited Text Layer | Keep | CSV with coordinates (survey points, sites) |
| KML / KMZ | Keep | Common from Google Earth and partners |
| GPX Layer | Keep | Field tracks |
| Geotagged Photos | Keep | Site visit photos |
| CAD (DXF/DWG) Layer | Keep | Engineering drawings of project works |
| File Geodatabase (GDB) | Keep | Partners on ArcGIS |
| LandXML Layer | Your call | Survey and road design files; niche |
| Encoded Polyline | Remove | Developer format |
| MBTiles Layer | Your call | Offline tile packages |
| OSM PBF Layer | Remove | Large OSM extracts; GEIDA analyses already use OSM |
| ICESat-2 / GEDI | Remove | Specialist satellite LiDAR |
| XYZ, WMS, WMTS, WFS Layer | Keep | National and partner map services |
| WCS Layer | Your call | Raster services; less common |
| CSW Catalog | Remove | Rare |
| OGC API - Features | Keep | Newer standard for partner services |
| OGC Vector Tiles | Your call | |
| ArcGIS Layer | Keep | Many governments publish on ArcGIS |
| GeoRSS Layer | Remove | Rare |
| Administrative Boundaries | Keep | |
| STAC Layer | Keep | Satellite imagery catalogues |
| Video Layer | Remove | |
| Deck.gl Layer | Remove | Developer feature |
| GeoParquet, FlatGeobuf, PMTiles Layer | Keep | Modern formats; GEIDA uses PMTiles |
| Zarr Layer, NetCDF / HDF | Your call | Climate data cubes; advanced users only |
| LiDAR Layer, Gaussian Splatting, 3D Tiles, Cesium Ion, CZML, 3D Model (glTF) | Remove | 3D and point clouds; outside GEIDA's scope |
| DuckDB Layer | Your call | SQL on files in the browser; advanced |
| PostgreSQL, SQL Server, Apache Iceberg Layer | Remove | Need database servers and passwords |

## Processing

| Item | Verdict | Why |
|---|---|---|
| AI Assistant | Remove for now | Needs an AI provider key; decide with an IsDB AI policy |
| Whitebox Toolbox | Keep | The searchable dialog for all engine tools, run in the browser |
| Category submenus (Conversion, Hydrology, LiDAR, Network, Projection, Raster, Remote Sensing, Terrain, Vector) | Remove | The same ~1,000 tools as the Whitebox Toolbox dialog, as very long nested menus |
| GeoLibre Toolbox › Conversion, Vector, Raster, Spatial Statistics | Keep | Everyday tools (convert, buffer, clip, statistics) |
| GeoLibre Toolbox › Network | Your call | Routing and service areas; useful for access studies |
| GeoLibre Toolbox › DGGS | Remove | Hexagon grids (H3, S2); niche |
| GeoLibre Toolbox › Geocode Addresses | Your call | Sends addresses to an outside geocoder |
| GeoLibre Toolbox › Batch tools | Keep | |
| AI Segmentation, Object Detection, Segment Everything | Your call | Heavy AI models in the browser; slow on office laptops |
| Model Builder | Keep | Chain tools into a workflow |
| Object-Based Analysis | Remove | Specialist remote sensing |
| SQL Workspace | Your call | Advanced users |
| Python Console, Jupyter Notebook | Your call | Analysts like them; heavy to load |
| Dashboard | Your call | Charts on a layer |
| History | Keep | Past processing runs |
| Planetary Computer | Keep | Free global imagery and data (Sentinel, Landsat, DEMs) |
| Earth Engine | Remove | Needs each user's Google Earth Engine account |

## Controls

| Item | Verdict | Why |
|---|---|---|
| Layer Control, Navigation, Fullscreen, Scale, Attribution | Keep | On by default |
| Compass | Keep | |
| Geolocate | Remove | Shows the user's own location; little use for project areas |
| Globe | Keep | |
| Terrain, Terrain exaggeration, Elevation | Keep | 3D relief helps read sites |
| Logos | Remove | MapLibre and Maptoolkit logos |
| Atmospheric Effects, Weather (clouds, precipitation), Sun | Remove | Visual effects |
| Route Animation, Flight Simulator, Spinning Globe | Remove | Demos |
| Gridlines | Keep | Coordinate grid for printed maps |
| Directions, Turn-by-Turn Navigation…, Reverse Geocode | Remove | Consumer navigation; outside services |
| Search | Keep | Find places |
| Colorbar, Legend | Keep | |
| HTML, Image | Remove | Custom HTML or picture boxes on the map; Print Layout covers maps for reports |
| Measure | Keep | Distances and areas |
| Bookmark | Keep | Saved views |
| Minimap | Keep | |
| View State | Remove | Developer readout (the status bar shows the same) |
| Field Collection…, GPS Tracking… | Remove | Mobile field work; GEIDA has no field app |
| Record Map Tour…, Record Video… | Your call | Short videos for presentations |

## Plugins

| Item | Verdict | Why |
|---|---|---|
| GeoEditor | Keep | Draw and edit features (e.g. a proposed site) |
| Annotations, Dimensions | Your call | Labels and measurements for maps |
| Web Services › ArcGIS Hub, ArcGIS Portal, CKAN, Hugging Face, Natural Earth, OpenAerialMap, OSM Downloader, Planet Open Data, Satellite Embeddings, Sentinel-2 Explorer, Source Cooperative, STAC Catalogs, Fields of the World, NASA Earthdata, NASA Earthaccess, Earthdata GIS, Dynamical, Ocean Data Platform, GeoLens, Portolan, Socrata, Vantor Open Data | Your call | Global open data portals; keep a short list (suggested: Sentinel-2 Explorer, STAC Catalogs, Natural Earth, OpenAerialMap, OSM Downloader, Fields of the World, NASA Earthdata) |
| Web Services › FEMA NFHL, Tennessee GIS, US EPA EnviroAtlas, US Federal, Local and State GIS, USGS 3DEP, USGS LiDAR, USGS National Map, USGS NLDI, IGN LiDAR HD, S3 Browser | Remove | US or France only, or developer tools |
| Street View, Mapillary | Your call | Street photos; coverage in member countries is patchy |
| DGGS (H3, S2, A5, DGGRID, DGGAL, OLC, Geohash, Tilecode) | Remove | Niche grid systems |
| Basemaps | Keep | |
| Historical Imagery | Keep | Wayback imagery, matches the project page's time series |
| Time Slider, Timelapse | Keep | Change over time |
| Overture Maps | Keep | Global buildings, roads and places |
| GeoAgent | Remove for now | AI agent; same decision as the AI Assistant |
| Elevation Profile | Keep | |
| Layer Swipe | Keep | Before and after comparison |
| Flight Simulator, God's Eye View | Remove | Demos |
| SamGeo | Your call | AI segmentation of imagery; heavy |
| Point Cloud Annotation | Remove | LiDAR |

## Settings

| Item | Verdict | Why |
|---|---|---|
| Language | Keep, trimmed | Keep English, العربية and Français (IsDB's languages); remove the others and "Manage language packs" |
| Map Preferences | Keep | |
| Layout | Your call | Panel toggles; GEIDA set the layout already |
| Appearance (colour themes) | Remove | GEIDA has its own look |
| Interface (Beginner / Intermediate / Advanced) | Remove once locked | GEIDA's profile decides; otherwise users can undo the clean-up |
| Geocoding, AI Providers, Environment Variables, Cloud Storage | Remove | Ask for keys and accounts |
| Startup Settings | Remove | |
| Manage Plugins | Remove | Lets users install outside plugins |
| Style Manager | Your call | Saved layer styles |

## Help

| Item | Verdict | Why |
|---|---|---|
| Command Palette, Keyboard Shortcuts | Keep | |
| Simplify Interface… | Remove | Replaced by GEIDA's profile |
| Website, GitHub repository | Remove | GeoLibre's own links; the status bar credit already links to GeoLibre |
| Diagnostics | Remove for users | Developer tool |
| Give Feedback | Replace | Point to GEIDA's feedback instead of GeoLibre's GitHub |
| Check for Updates | Remove | Desktop app only |
| About | Keep | Credits GeoLibre (MIT licence) |

## Rest of the screen

| Item | Verdict | Why |
|---|---|---|
| Left rail: Layers, Browser | Keep | Project layers and files |
| Right rail: Comments | Remove | Needs GeoLibre's collaboration server |
| Right rail: Style | Keep | Layer styling |
| Layers panel buttons: GeoEditor, New group, Compact view, Hide all, Identify, Collapse | Keep | |
| Map buttons: zoom, compass, geolocate, fullscreen, globe, layer control | Keep (geolocate: remove with the control) | |
| Status bar: coordinates, zoom, scale | Keep | |
| Status bar: Eye alt, Bearing, Pitch, BBox | Your call | Technical readouts |
| Status bar: Diagnostics badge | Remove for users | Shows a warning count meant for developers |
| Status bar: "Built on GeoLibre · MIT licence" | Keep | Required credit |
| Search box under the layers ("layers, places, lat, lon, or H3 cell") | Keep | |

## Summary

| | Keep | Your call | Remove |
|---|---|---|---|
| Top menus | Project (most), Edit, View (most), Add Data (common formats and services), Processing (toolboxes, Model Builder), Controls (core), Plugins (time and comparison tools), Help (basic) | Python and notebooks, AI imagery tools, open data portals, videos | 3D and LiDAR, US portals, databases, other map engines, visual effects, demos, field and GPS tools, desktop-only items, keys and accounts settings |

Roughly a third of the items go, a third stay, and a third are your call. The next step is to agree the
"Your call" rows, then write `deployment.json` with `lock: true` and make the small code changes for the
items the profile can't reach (Settings items, Comments rail, Diagnostics badge, Give Feedback link).
