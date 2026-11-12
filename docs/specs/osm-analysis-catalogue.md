# Spec: OSM analysis catalogue (phase 2 rework)

Status: **approved** with the recommended defaults · 2 Nov 2026 · Aman (with Claude Code)
Progress: steps 1–4 done (data layer; vector helpers; categories and parking; schools, buildings, area profile, health, roads); steps 5–7 to do. Decision 1 (Sajid's sign-off) still open.

## Purpose

Replace the current mix of raster and vector modules with a catalogue of
**OpenStreetMap-only** analyses, grouped into categories staff recognise
(Area profile, Social services, Neighbourhood and access, ...). Raster analyses
(elevation, land cover, population) are parked, not deleted, and come back in a
later phase.

Why now:

- The raster chain (Copernicus DEM, WorldCover, WorldPop) is the slowest and most
  fragile part of a run, and the demo needs reliable, explainable results.
- OSM answers the questions staff ask first at PCN/PPRR: what is in the area,
  where are the schools and clinics, how far are people from them, what roads exist.
- Every OSM result can be traced to a named feature with a link, which suits
  Verify-type CRIs (9.3, 8.1, 2.2, 3.7).

## What changes

| Module | Today | Plan |
|---|---|---|
| `area_baseline` | DEM + WorldCover + WorldPop | **Park** (move to `modules/_parked/`) |
| `terrain` | DEM | **Park** |
| `school_access` | OSM schools × WorldPop raster | **Park**; replaced by `facility_proximity` (vector) |
| `buildings` | OSM + WorldCover built-up raster | **Rework**: OSM only (footprints, types, density grid) |
| `schools_inventory` | OSM, zones via rasterised labels | **Rework**: vector point-in-polygon, richer breakdown |

The registry skips folders starting with `_`, so parked modules disappear from the
catalogue but their code, manifests and past runs stay intact.

## Categories

Categories are data, in `backend/modules/categories.yaml` (id, title, one-line
description, icon, order). Each manifest gets one `category:` field; themes stay as
tags for search and recommendation.

| # | Category | Question it answers | Modules |
|---|---|---|---|
| 1 | **Area profile** | What is mapped in the project area? | `area_profile` |
| 2 | **Social services** | Which schools, clinics and community facilities exist, and where? | `schools_inventory`, `health_inventory`, `community_facilities` |
| 3 | **Neighbourhood and access** | Who lives near or far from services and roads? What is around a site? | `facility_proximity`, `neighbourhood_profile`, `road_access` |
| 4 | **Built environment** | How many buildings, how dense, what kind? | `buildings` |
| 5 | **Infrastructure networks** | What roads, water and power assets exist? | `road_network`, `utilities_inventory` |

## Modules (v1)

All use OSM only, summarise per admin unit (level 1–3, user's choice), and produce a
headline, a per-unit table, a feature list (CSV), a map layer (GeoJSON) and a
summary paragraph. Distances are straight-line in v1 (see open decisions).

| Module | Category | Inputs (OSM tags) | Key outputs | CRI (role) |
|---|---|---|---|---|
| `area_profile` | 1 | all layers below | counts by category, road km by class, named places list, OSM snapshot date | context for all |
| `schools_inventory` | 2 | `amenity=school/kindergarten/college/university` | count by level (ISCED), operator, per unit, per 100 km² | 9.3 verify |
| `health_inventory` | 2 | `amenity=hospital/clinic/doctors`, `healthcare=*` | count by facility type/level, per unit | 8.1 verify |
| `community_facilities` | 2 | markets, places of worship, government, police, community centres, banks | count by type, per unit | 3.7 verify (markets) |
| `facility_proximity` | 3 | facility type (choice) + buildings | buildings within distance bands (default 1 / 2 / 5 km) and beyond, per unit; map of buildings by band; facility service areas | 9.1, 8.3, 7.1 estimate (proxy, see decision 2) |
| `neighbourhood_profile` | 3 | a site picked on the map + radius | nearest school, clinic, water point, market, major road (name, distance); counts by category within the radius | context (site selection at PCN) |
| `road_access` | 3 | roads by class + buildings | buildings within 2 km of a primary–tertiary road (Rural Access Index proxy); distance to nearest major road | 2.1 estimate (proxy) |
| `buildings` | 4 | `building=*` footprints | count, footprint area, type breakdown, density grid (vector cells), per unit | 6.2 context |
| `road_network` | 5 | `highway=*` | km by class and surface (paved/unpaved), bridges, road density per unit | 2.2 verify |
| `utilities_inventory` | 5 | water points, wells, boreholes, water towers; power lines, substations, plants | counts and km by type, per unit | 7.1 context, 1.3 verify |

Every result carries the OSM caveat: completeness varies by country; counts are of
**mapped** features and should be checked against project lists and imagery.

## Data layer

### Source: Geofabrik extracts read with GDAL (recommended)

```
Geofabrik index ──► smallest region covering the project bbox ──► <region>.osm.pbf
   (once per country, refreshed on demand)              backend/data/osm/
                                                              │ GDAL OSM driver (ogr), clipped to bbox
                                                              ▼
                       backend/data/cache/osm/<project>_<snapshot>.gpkg  (layers: points, lines, polygons)
                                                              │ tag taxonomy
                                                              ▼
                                     themed layers: schools, health, buildings, roads, water, ...
```

- **Reliable at district scale.** Overpass times out or rate-limits on large areas
  with many buildings; a local extract does not.
- **Reproducible evidence.** Each run records the extract's snapshot date, so a PCR
  value can be traced to the exact OSM state years later.
- **IsDB-hostable.** No live third-party API at analysis time; IMDT can mirror the
  extracts.
- **No new parser.** The conda env's GDAL already reads `.osm.pbf` (OSM driver).
- **Fallback:** the existing Overpass fetcher stays for countries or areas with no
  extract yet, and for small quick checks.

### Tag taxonomy as data

`geida_static_data/OSM_Taxonomy/osm_taxonomy.yaml` defines each layer: id, label, geometry
(point / line / polygon), tag filters, tags to keep, and how ways become points
(centroid). Modules ask for layers by id (`ctx.osm("schools")`), never by raw tag.
Changing what counts as a "health facility" is a data edit, not a code change.

### Vector helpers (replacing raster label tricks)

Add **shapely 2** (conda-forge, same GEOS build) to `environment.yml` for
vectorised point-in-polygon, buffers, nearest-neighbour (STRtree) and lengths in a
local metric projection. New helpers in `apps/analysis/vector.py`: `assign_zones`,
`count_by_zone`, `length_by_zone`, `nearest`, `within_distance`, `grid_counts`.

## What we take from Aleph

Aleph (`~/Desktop/crazy_gis/Aleph`, MIT, © 2026 Belluxx). Only its open-data
parts; everything that touches Google services is excluded.

| Aleph part | Use? | How |
|---|---|---|
| `osm.py` Geofabrik region lookup (`region()`, `covers()`) | **Adapt** | Pick the smallest Geofabrik region whose polygon covers the project bbox; cache the index |
| `pbf.py` header timestamp (`PBF.timestamp`) | **Adapt (small)** | Read the extract's snapshot date for evidence records; ~30 lines |
| `layers.py` tag rules (`AREA_TAGS`, `AREA_VALUES`, `is_area`, `MAJOR_ROADS`, `PATHS`) and `osm.py` `POI_KEYS` | **Adapt** | Seed the first version of `osm_taxonomy.yaml` |
| `places.py` `nearby()` | **Pattern** | Model for `neighbourhood_profile` (nearest-by-category with distance and OSM link) |
| `pbf.py` full PBF parser (825 lines) | No | GDAL's OSM driver does this, in C++, maintained upstream |
| `routes.py`, `geo.py` | No | Street-photo routing and helpers; shapely/GEOS covers our needs |
| `terrain.py` (AWS Terrain Tiles) | Later | Candidate open DEM source when raster analyses return |
| `places.py` geocoder (photon.komoot.io) | Later | Only if self-hosted; the public server is fair-use |
| `streetview.py`, `satellite.py`, `mesh.py`, related `quick.py`/`capture.py` paths | **Excluded** | Google data; against Google's terms |

Adapted code keeps Aleph's MIT notice in the file header and is listed in
`docs/decisions.md` under licences.

## Frontend

- **Catalogue by category**: category cards with module counts; inside, "recommended
  for this project" first (CRI or theme match), then the rest. Search keeps working
  across categories.
- **Run form**: new parameter types `point` (pick a site on the project map) and
  `distance_bands` (list of metres), built from the manifest like the others.
- **Results**: MapLibre vector layers styled per OSM category, feature popups (name,
  key tags, link to openstreetmap.org), table row ↔ map feature highlight, CSV and
  GeoJSON downloads, and an "OSM snapshot: <date>" badge.
- **Large layers**: buildings over ~50k are shown as the density grid and centroids,
  not footprints, until vector tiles land (plan phase 3f).

## Build order

| Step | Deliverable | Done when |
|---|---|---|
| 1 | Data layer: Geofabrik lookup + download, GDAL extraction to cached GeoPackage, taxonomy file, snapshot date; Overpass fallback | Uganda extract downloads; UGA1072 area extracts all taxonomy layers in < 1 min after first download |
| 2 | Vector helpers (`vector.py`, shapely) and tests | Unit tests for zone assignment, nearest, bands, lengths |
| 3 | Categories in registry + API + catalogue UI; park raster modules | Catalogue shows 5 categories; parked modules gone, old runs still open |
| 4 | Port `schools_inventory`, `buildings`; add `area_profile`, `health_inventory`, `road_network` | Each passes its fixture test and runs on UGA1072 |
| 5 | Neighbourhood: `facility_proximity`, `neighbourhood_profile` (point input), `road_access` | Point picker works; band counts sum to total buildings |
| 6 | `community_facilities`, `utilities_inventory`; result viewer polish | All 10 modules run on UGA1072 and AZE1028 |
| 7 | Docs: module README, plan.md, decisions.md; demo walkthrough | Sajid reviews on staging |

Each module ships with `tests/` using a small fixture extract (a few km² clipped
from Uganda), so tests need no network.

## Acceptance tests

- Re-running a module on the same project and snapshot gives identical numbers.
- Counts per admin unit add up to the area total; distance-band counts add up to all
  buildings in the area.
- Every listed feature links to its OSM object; every run shows its snapshot date.
- A project in a country with no extract yet falls back to Overpass and says so in the run log.
- Parked modules: not listed, past runs and evidence still viewable.

## Open decisions

1. **Sajid's sign-off.** The working plan's Cycle 1 lists `health_access` and
   `road_corridor` with population rasters and Moroto acceptance values. This spec
   replaces them with OSM-only versions for now. Agree before step 4.
2. **Buildings as a proxy for people.** For 9.1, 8.3, 7.1 and 2.1, propose evidence
   as "buildings within X km" (role *estimate*, caveat stated), or only report it as
   context until census or population data returns?
3. **Straight-line vs network distance.** v1 uses straight-line; road-network
   distance (OSRM or pgRouting on the same extract) is a later step.
4. **Data source.** Geofabrik snapshot first, Overpass fallback (recommended), or
   stay on live Overpass?
5. **Dependency.** Add shapely 2 to `environment.yml` (recommended) or keep to
   Django GEOS only (slower on 100k+ buildings)?
