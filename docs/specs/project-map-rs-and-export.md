# Spec: project map, remote-sensing layers and map export (phase 2r.2)

> **Update 6 Nov 2026:** Earth Engine has been removed. The same endpoints now serve cloud-optimised GeoTIFFs through TiTiler (`apps/geoportal/raster.py`); see `specs/gee-replacement.md`.

Status: **in progress** · 2 Nov 2026 · Aman (with Claude Code)
Progress: Part A (A1–A5) and Part B (B1–B5) built; B6 later.

## Purpose

Two things staff ask for as soon as a project has an area of influence:

1. **See the Geo-Portal's satellite layers over their project**, cut to the area of
   influence (AOI), and download them for their own GIS. No analysis on them yet.
2. **Make a proper map of it**: a print-ready page with title, legend, scale, north
   arrow, sources and the IsDB logo, as PDF, PNG or SVG. This is plan item 2e and
   the course's Part 4 (`moroto-case-study-gap-analysis.md`, P5).

Both run alongside the OSM rework (`osm-analysis-catalogue.md`, steps 2–7); neither
changes the module framework.

## Part A: remote-sensing layers clipped to the AOI

### What exists

The Geo-Portal catalogue (`apps/geoportal/catalog.py`) already serves 11 raster
layers: CHIRPS precipitation, WaPOR ETa and biomass, ERA5 temperature, JRC surface
water, MODIS NDVI, ESA WorldCover and WorldCereal, Copernicus DEM elevation and
slope, Esri hillshade. Earth Engine layers are rendered on demand
(`gee.tile_url`) and can be downloaded as a GeoTIFF over a geometry
(`gee.clip_geotiff`, `POST /api/geoportal/layers/<id>/clip/`), today used by the
Geo-Portal Toolbox.

### What changes

| # | Piece | Detail |
|---|---|---|
| A1 | **Project-scoped tiles** | `GET /api/projects/<code>/satellite/<layer>/tiles/?year=` builds the same Earth Engine image **clipped to the project's AOI** (`image.clip(aoi)`), so pixels stop at the boundary. Map ids cached per project + layer + year (as now, 1 h). Permission = can view the project. |
| A2 | **Project-scoped GeoTIFF** | `GET /api/projects/<code>/satellite/<layer>/download/?year=`: raw values, local UTM, **masked to the AOI polygon** (nodata outside; the Toolbox endpoint keeps the full bounding box for neighbourhood tools). File name `<code>_<layer>_<year>.tif`, with a sidecar of source, year, resolution, licence. |
| A3 | **Satellite catalog + Layers panel** | "Satellite" button in the project side nav opens the Geo-Portal's catalog window (same CSS, `shared/styles/catalog.css`): search, groups, switches, info. Layers switched on appear under "Satellite data" in the Layers panel with year, opacity, legend (ramp or classes) and GeoTIFF download. JRC water and hillshade, tile services in the Geo-Portal, get an Earth Engine recipe (`aoi_gee` in the catalogue) so they clip the same way. |
| A4 | **Print integration** | Visible satellite layers feed the export's legend (classes) or colour bar (ramps) and its sources line. |
| A5 | **Tests** | Endpoint permissions, year validation, clip geometry passed to Earth Engine (mocked), GeoTIFF mask. |

Not in this part: zonal statistics over the AOI (mean NDVI, rainfall), time series,
or evidence. Those come with the raster modules when they return.

### Constraints

- **Earth Engine stays a dependency** for now (open decision: STAC/COG via TiTiler at
  IsDB, plan 3a). The project endpoints take the layer id and year only, so the
  backend can switch source without a front-end change.
- Large AOIs: downloads coarsen to stay under ~4 Mpx, as now; the panel says the
  resolution actually delivered.
- No Google basemaps, Street View or imagery (terms of service).

## Part B: map export and print

### Approach

GeoLibre (vendored in `frontend/gis`, MIT) already has a mature print composer.
Its drawing engine, `gis/apps/web/src/lib/print-layout.ts`, is framework-free: it
takes a captured map image plus options and draws the page (title, legend, scale
bar, north arrow, info block, colour bar, footer) onto any 2D canvas; the same
commands drive the preview, PNG/PDF and editable SVG (`print-layout-svg.ts`).

GEIDA **reuses that engine unchanged** through a typed bridge (`virtual:gis-print`,
like `virtual:gis-mount`) and **owns everything around it**:

| GEIDA piece | Why it is GEIDA's |
|---|---|
| Map capture | An off-screen MapLibre map at the page's map-frame size and export DPI, so the print is sharp and its extent exact (not a screenshot of the screen) |
| Legend | Built from what the project workspace shows: AOI, run outputs, satellite layers |
| IsDB logo and partner logo | GeoLibre has no logo element; drawn beside the title, or on a plate in the map corner |
| Sources and disclaimer | GeoLibre's footer is one line and squeezes long text; GEIDA draws a wrapped notes panel |
| Defaults | Project title, code, country, author, date, sources from the visible layers |
| Presets | Saved per project in the browser |

The dialog's state is a plain object, so the same layout can later be rendered on
the server for module reports (B6).

### Customisation (v1)

| Group | Options |
|---|---|
| Page | A4, A3, Letter, Legal, Tabloid, Full HD, 4K, square, custom (mm or px); portrait or landscape; margins (normal, narrow, none); page border |
| Extent | Current view, project area, or a fixed scale (1:N); map background; frame colour and width |
| Title | Title, subtitle, alignment, above or over the map |
| Legend | On/off, title, rename or hide entries, group by layer |
| Colour bar | For ramp layers: min, max, label, position, orientation (with the satellite layers, B5) |
| Navigation | Scale bar (metric, imperial, nautical), north arrow, grouped or apart |
| Info block | Author, project code, CRS, revision, scale |
| Logos | IsDB logo on/off and corner; optional partner logo upload |
| Sources and footer | Sources (pre-filled from the visible layers) and disclaimer as a wrapped notes panel on the map, position; date; "Created with GEIDA" credit |
| Output | PNG (96–300 dpi), PDF, SVG (editable), copy to clipboard, print |

### Steps

| # | Step | Status |
|---|---|---|
| B1 | Bridge to GeoLibre's engine (`virtual:gis-print`, typed) | Done |
| B2 | Off-screen capture at page size and DPI; extent modes | Done |
| B3 | Composer dialog with live preview, all v1 options, presets | Done |
| B4 | Exports: PNG, PDF, SVG, clipboard, print | Done |
| B5 | Satellite layers in legend and colour bar (with A4) | Done |
| B6 | Server-side render of the same layout for module reports (PDF per run) | Later (needs a headless renderer; decide with IMDT) |

## Suggested order for the rest of the phase

1. OSM spec step 2 (shapely helpers), then the OSM modules (steps 3–7).
2. Boundaries and census registry (gap analysis D1, D2).

## Open decisions

1. Default page for IsDB maps: A4 landscape (proposed) or A3?
2. Should the export carry a disclaimer line ("Boundaries do not imply …")? Proposed: yes,
   editable, on by default; IsDB wording to confirm.
3. Earth Engine vs STAC/COG for Part A once hosted at IsDB (existing open item).
