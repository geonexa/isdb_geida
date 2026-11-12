# Features

This page describes what each part of GEIDA does today. The [Changelog](../changelog.md)
records when each feature arrived.

## Projects

### Onboarding

A project can enter GEIDA three ways:

| Route | How | Use when |
|---|---|---|
| **Wizard** | `/projects/new`, step by step | One project at a time |
| **Bulk import** | `/projects/import`: download the Excel template, fill it, upload, preview row errors, commit | Many projects from a portfolio list |
| **Submission form** | Upload IsDB's Project Data Submission Form | The project team already filled the form |

The wizard collects:

1. **Identity**: project code, title, country, sector, cycle stage, dates, regional hub.
2. **Area of influence**, by one of four methods: upload a file (GeoJSON, KML/KMZ,
   GeoPackage, GML or a zipped Shapefile), draw a polygon, pick administrative units, or place a
   point with a buffer. Geometries are validated, repaired where possible, reprojected to
   WGS 84 and their area computed. Problems are reported, never silently fixed.
3. **Themes and components**.
4. **Results Framework**: indicators at impact, outcome and output level, each with an
   optional CRI code, baseline, target and geospatial role.
5. **Documents**: links to the project's documents (for example on SharePoint).

A duplicate project code updates the existing record instead of creating a second one.

### Review

```mermaid
stateDiagram-v2
    [*] --> Draft
    Draft --> Review: owner submits
    Review --> Published: reviewer publishes
    Review --> Draft: reviewer returns with a comment
    Published --> [*]
```

- **Draft**: visible to the owner and reviewers only.
- **Under review**: waiting in the review queue (`/projects/review`).
- **Published**: visible to everyone, including visitors who are not signed in.

Every action is recorded in the project's Activity log.

## Project workspace

`/projects/<code>` combines one persistent map with a side panel chosen from a rail. The top
of the side panel always shows the project's code, status, title and the workflow actions
(edit, submit, return, publish, delete) the user is allowed:

| Tab | What it shows |
|---|---|
| **Overview** | Key facts, area of influence, project details |
| **Results** | The Results Framework and the evidence attached to each indicator |
| **Analyses** | First the project phase (preparation, implementation, completion), then two views. **Analysis modules**: the catalogue for the current phase in collapsible category sections (recommended modules open first; a search opens every section with matches), with past runs and their outputs. **Data layers**: the Data Catalog's rasters in their sections (Climate and water, Vegetation and land, Crop water productivity, Terrain, Population and imagery), cut to the area of influence, each with its period and a GeoTIFF download. Each phase lists its own modules and data layers; a layer can belong to several phases |
| **Toolbox** | 186 vector and raster processing tools (buffer, clip, intersect, dissolve, zonal statistics, reclassify, raster to polygons, distances, interpolation…; GeoLibre engine plus GEIDA's own) run on the server on the project's layers: area and admin units, Data Catalog rasters, OpenStreetMap layers, analysis results, earlier Toolbox results and uploaded files. Every run is saved; results can be shown on the map, downloaded (GeoPackage, GeoJSON, GeoTIFF, CSV), used as inputs, renamed and deleted. See [Toolbox](toolbox.md) |
| **Evidence** | Values proposed by analyses, to accept or reject |
| **Documents** | Links to the project's documents |
| **Activity** | The history of the project record |

The map has a Layers panel listing every layer on it (run outputs, data layers, area of
influence, basemap). Each has a legend and display settings: opacity for all; palette
(optionally reversed) and value range for continuous data layers, redrawn by the tile
server; colour or palette, size and outline for analysis outputs; outline and fill for the
area; basemap on or off and the map background colour. Settings are kept per project in
the browser, and the map export's legend and colour bar follow them. The map also has a
basemap picker shared with the rest of the platform, a **place search** button below fullscreen (admin units
suggested while typing; Enter also searches towns and other places with OpenStreetMap's Nominatim, through
GEIDA's server; choosing a result zooms to it) and a **map export** button. Every project map (project
list, the new-project steps, the project page) has the search button.

### Map export

The map export opens a layout editor: a page on which maps, legends, scale bars, north
arrows, colour bars, text (with fields such as the project title), pictures (the IsDB
logo) and shapes are placed and styled freely. Overview maps come in two styles: a
globe locator with the country highlighted (the default), or a 2D map of the project's
country or its province/region (from the administrative boundaries) with the boundary drawn
and the main map's extent marked. Templates give a starting layout; your own
layouts can be saved as templates (up to 20). Signed-in users' layouts, templates and export
resolution are kept in their account, so they are the same on any computer or browser; without
signing in they stay in the browser. Output is SVG, PNG or PDF at up to 600 dpi.

## Analyses

An analysis is a **module**: a folder with a manifest and a Python script (see
[Analysis modules](../architecture/analysis-modules.md)). Analyses are grouped in eight
broad categories. Each analysis is tagged with the project phases it serves (preparation /
PPRR, implementation / PIASR, completion / PCR), and the Analyses tab lists only the current
phase's analyses. Analyses not built yet are listed as **Planned** (`backend/analyses/planned.yaml`).

| Category | Question | Modules today |
|---|---|---|
| Terrain and site conditions | What is the physical setting of the site? | `elevation_profile`, `slope`, `aspect`, `hillshade`, `contours` |
| Water resources | Catchments, rivers, rainfall, ET, water accounting | `stream_network`, `sub_basins`, `catchment` |
| Land, vegetation and agriculture | Land cover, vegetation, fields, crops, forests | `land_cover`, `land_cover_change`, `vegetation_indices`, `biomass`, `forest_loss`, `field_boundaries` |
| Climate and natural hazards | Climate, drought, floods, landslides, exposure | planned |
| People and socio-economics | Population, settlements, access, wealth | `population`, `population_change`, `settlements`, `service_access`, `travel_time` |
| Infrastructure and services | Buildings, transport, schools, health, power | `area_profile`, `buildings`, `road_network`, `schools_inventory`, `health_inventory` |
| Site selection and planning | Suitability, candidate sites, service gaps | `suitability` |
| Monitoring and impact | Change since baseline, progress, before / after | planned |

Each module is marked **ready**, **needs data** or **not available** for a project, so
staff see before running it whether the data exist. Runs are queued and executed by a
background worker; the page updates while a run is in progress. Outputs are map layers,
tables (downloadable as CSV), metrics and a summary paragraph; the data sources and the run log
open on request under the results. Some analyses take a **point picked on the map** (e.g. the
outlet of Catchment from a point): the run form turns the map into a picker, and the point can
also be typed.

The person who started a run, or a reviewer, can **delete** it once it has finished (one at a
time, or several with **Select**). Its files and any proposed or rejected evidence go with it;
runs with accepted evidence are kept, since that evidence is the project's record. Deletions
are recorded in the Activity log.

Every analysis is described in [Analyses](../analyses/index.md): question, input data,
settings, workflow, method, outputs and limitations.

## Data Catalog (Geo-Portal)

`/geoportal` is a full-screen map for browsing, inspecting and visualising data without a
project (analysis happens in a project's [Analyses](../analyses/index.md) and [Toolbox](toolbox.md) tabs):

- **Layers**: climate and water (precipitation, evapotranspiration, surface water),
  vegetation and land (biomass, land cover), terrain (elevation, slope, hillshade),
  boundaries, and view-only layers from open map services.
- **Areas**: draw or upload an area, save it, and download a layer clipped to it as a
  GeoTIFF.

## Analytics

`/analytics` is the full GIS workspace (GeoLibre): add data from files and services,
style layers, run processing tools and models, and print maps. It is intended for
analysts and trainers, and can be limited to them (see [Users and roles](roles.md)).

## Accounts

- Registration with an emailed verification code.
- Sign-in with email or username; password reset by email.
- Roles are assigned by administrators in `/admin` (see [Users and roles](roles.md)).
