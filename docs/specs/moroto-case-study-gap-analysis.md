# Gap analysis: the Moroto / Kaolack training case studies in GEIDA

Status: analysis · 2 Nov 2026 · Aman (with Claude Code)

Source: `geo-training-stack-sajid/docs/` — `CASE_STUDIES_UGANDA.md` (Moroto, parts 0–4),
`CASE_STUDIES.md` (server workflows 1–5), `ANALYSIS.md`, `CASE_STUDY_BRIEF.md`, and the
course data in `Moroto_course_data/`.

**Question:** can GEIDA run these analyses itself, with data downloaded and processed
automatically instead of supplied in a course folder? What exists, what is missing?

## Summary

| Part | Analysis | GEIDA today | Verdict |
|---|---|---|---|
| 0 | Census targeting: subcounties with >70 % out of school → Moroto | Not possible: no census data, and GADM does not hold UBOS subcounties | **Missing data + feature** |
| 1 | People > 5 km from a school, per subcounty | `school_access` module does this exact raster chain, auto-downloading OSM + WorldPop; but zones are GADM, population is WorldPop 2020 unconstrained, and the module is about to be parked | **Mostly there**, wrong zones and population year |
| 2 | Same for health, all vs HC III+ | No `health_access` module; OSM has no facility level (only in names); duplicates | **Missing module + data cleaning** |
| 3 | Road corridor screening (1 km buffer: slope, land cover, people, facilities) | DEM, WorldCover, WorldPop fetch automatically and `area_baseline` / `terrain` summarise them, but only over a project polygon; no line input, no buffer, no facilities-in-corridor | **Missing module + line input** |
| 4 | Report map with IsDB logo | No print/report output in modules; GeoLibre print layout exists in `/analytics` (manual) | **Missing feature** (plan 2e) |
| W1 | Accessibility (Kaolack, HRSL population) | As Part 1; HRSL not registered | Partly |
| W2 | Suitability / MCDA (school siting) | Nothing | **Missing** (not in any plan yet) |
| W3 | Buffer screening (JRC water, Overture buildings) | As Part 3; JRC and Overture not registered | Missing |
| W4 | Hydrology, check dams (Whitebox) | Whitebox runs in the browser in `/analytics`, not as a module; no server-side Whitebox | Missing as a module |
| W5 | District profile (zonal stats per ADM2, CSV) | `ctx.zones()` + zonal sums inside modules, GADM zones only; no country-wide run | Partly |

**Bottom line:** the *download-and-process* engine is in place: for Moroto, GEIDA pulled every
OSM layer automatically in 11.5 s from the Uganda extract, and the raster fetchers (DEM,
WorldCover, WorldPop) already clip to any area. The gaps are (1) **reference data the course
hand-prepared**: current admin boundaries with census attributes and facility levels; (2) **four
modules**: health access, corridor screening, census targeting, print map; (3) **inputs a project
polygon can't express**: a road line, a facility filter.

## What GEIDA fetched for Moroto, automatically (2 Nov 2026)

Run against the course's Moroto boundary (9 subcounties) plus 10 km, OSM snapshot 2026-11-01:

| Layer | GEIDA (auto) district + 10 km | in district | Course folder | Note |
|---|---|---|---|---|
| Schools | 54 | 33 | 106 (amenity=school) | 37 more mapped as `building=school` without `amenity`; course clip was a 10 km box from an older HOT export |
| Health facilities | 30 | 19 | 31 (cleaned) | All tagged `amenity=hospital`; level only in names; 3 duplicate pairs |
| Roads (motor) | 818 | 613 | 3,131 incl. 1,656 paths | GEIDA keeps paths in a separate `paths` layer |
| Buildings | 53,421 | **38,732** | — | Not used by the course; a usable population proxy |
| Water points | 14 | 1 | — | Sparse in OSM |
| Named places | 249 | 168 | — | Villages for labels and checks |

Rasters, also automatic (existing fetchers): Copernicus DEM 30 m, ESA WorldCover 2021,
WorldPop **2020** (course: WorldPop **2024 constrained**).

## Data gaps

| # | Data | Course | GEIDA | Fix | Auto-downloadable? |
|---|---|---|---|---|---|
| D1 | **Current admin boundaries** | UBOS 2024: 146 districts, 2,205 subcounties | GADM 4.1: 58 Uganda "districts" (2008 layout), 965 level-3 units; GADM "Moroto" = 8,517 km² (includes today's Napak, Nabilatuk) | Boundary source per country: geoBoundaries (ADM1–3, API) or OCHA COD; official upload where those are old. Same `AdminUnit` table with a `source` field | geoBoundaries / COD: **yes**. UBOS: manual (portal) |
| D2 | **Census attributes** (pop, out-of-school, WASH, electricity...) | NPHC 2024, 80 fields, joined on `SCCode` | None | Country dataset registry (plan 2d / 3b): table + join key + admin level + data dictionary + `data_note`; upload wizard maps columns | No: national statistics offices; upload once per country |
| D3 | **Facility service level** | `level` = HC II / HC III / Hospital, derived from names | Not in OSM tags | Name parser per country (rules in a data file, e.g. Uganda `HC II|HEALTH CENT(RE|ER) II`), stored as a derived field; ministry facility list as optional upload | Derivable automatically from OSM names |
| D4 | **Facility duplicates** | Removed by hand | 3 duplicate pairs in Moroto | Dedupe rule: same normalised name within 300 m | Automatic |
| D5 | **Schools mapped as buildings only** | Not handled | 37 missed | Add `building=school` to the taxonomy **with** a rule that drops a building inside an `amenity=school` campus | Automatic |
| D6 | **Population raster year** | WorldPop 2024 constrained (100 m) | WorldPop 2020 unconstrained | Add WorldPop 2024 constrained (and HRSL / Meta 30 m for W1–W3) to the registry; or OSM buildings × census household size as the OSM-only proxy | Yes |
| D7 | **The road to screen** | `moroto_tapac_road.geojson` (27 km line) | Project area is a polygon | Line input on a run (draw, upload, or pick an OSM road by name) | Partly (OSM road by name) |
| D8 | **Extra layers for W1–W5** | HRSL, JRC surface water, Overture buildings, CHIRPS, CGLS cover fractions | None registered | STAC/COG fetcher (plan 3a) | Yes |
| D9 | **Cross-border areas** | Not an issue (course data clipped to Uganda) | Moroto + 10 km crosses into Kenya; now uses Uganda only, flagged partial | Merge two country extracts when a box crosses a border | Yes |

## Process gaps

| # | Capability | Needed for | Status | Where it fits |
|---|---|---|---|---|
| P1 | **Census targeting**: filter admin units by indicator thresholds, shortlist, save as project area | Part 0 | Not built | New "Country explorer" (Geo-Portal or project creation): choose country → indicator → threshold → select units → create project |
| P2 | **Facility access with filter**: distance bands from a facility layer, optionally filtered by an attribute (level ≥ HC III), people or buildings beyond the limit per zone | Parts 1–2, W1 | `school_access` (raster, schools only); `facility_proximity` planned (OSM, buildings) | One module, facility type + filter as parameters; population source = raster or buildings |
| P3 | **Corridor screening**: buffer a line, then slope stats, land-cover class areas, population, facilities inside | Part 3, W3 | Not built (`road_corridor` in plan 2b) | Module with a `line` input and a `distance_m` parameter |
| P4 | **Zones = census units**: summarise any module by the official units and add census columns (e.g. `pct_oos612` beside "share > 5 km") | Parts 1–3, W5 | `ctx.zones()` uses GADM only | `ctx.zones(source=…)` + join census fields into per-zone tables |
| P5 | **Print map** with title, legend, scale, north arrow, sources, IsDB logo; PDF/PNG | Part 4 | Not built (plan 2e); manual print layout in `/analytics` | Server-rendered A4 template per run |
| P6 | **Suitability / MCDA**: scored criteria, weights (AHP), exclusions, ranked sites | W2 | Not planned | New module family "Site selection" |
| P7 | **Hydrology** (breach, flow accumulation, streams) | W4 | Browser-only Whitebox in `/analytics` | Server-side Whitebox in the worker (as the working plan proposes) |
| P8 | **Country-wide zonal profile** | W5 | Modules run per project area only | "Country profile" run outside a project, or a project whose area is the country |
| P9 | **Vector performance**: point-in-polygon over 50k+ buildings | All OSM modules | Slow with Django GEOS one-by-one (this analysis had to switch to prepared geometries) | Shapely 2 vectorised helpers — step 2 of `osm-analysis-catalogue.md` |

## Conflict with the OSM-only decision

The course's core method in Parts 1–3 is **population-weighted** (raster distance × WorldPop,
slope, land cover). The approved rework parks raster modules and uses OSM buildings as a proxy.

- With the proxy, GEIDA can answer the same *questions* ("how many buildings beyond 5 km of an
  HC III, per subcounty") but **cannot reproduce the course's numbers** (14,800 people beyond 5 km;
  11 % steeper than 15° in the corridor).
- Moroto has 38,732 OSM buildings, so the proxy is workable there; it will be weak where
  buildings are not mapped.
- The course's expected results were planned as GEIDA's acceptance tests (working plan, step 2c).

Options: (a) keep OSM-only now and treat Moroto numbers as a later acceptance test; (b) keep
`school_access`, `terrain` and `area_baseline` live (not parked) as an "EO layers" category while
the OSM modules are built; (c) build the population-weighted versions on top of the OSM modules
(same module, population source = raster or buildings).

## Suggested order (fits the existing plan)

1. **Step 2 of the OSM spec** (shapely helpers): unblocks everything above (P9).
2. **Boundaries + census registry** (D1, D2, P4): geoBoundaries auto-download per country,
   UBOS 2024 subcounties + census as the first uploaded country dataset (plan 2d). Without it,
   no part of the Uganda storyline matches the course.
3. **Facility access module** (P2) with level filter, name-derived levels and dedupe (D3, D4, D5):
   covers Parts 1–2 and W1.
4. **Corridor screening** with a line input (P3, D7): Part 3 and W3.
5. **Print map** (P5): Part 4, and every module's output.
6. **Census targeting / country explorer** (P1): Part 0.
7. Later: STAC fetcher (D8), MCDA (P6), server Whitebox (P7), country-wide profile (P8).

## Decisions needed

1. Raster vs OSM-only for Parts 1–3: option (a), (b) or (c) above.
2. Boundary source: geoBoundaries as the default instead of GADM (licence is also friendlier:
   CC BY 4.0 vs GADM non-commercial), with official uploads overriding per country?
3. Is Part 0 (national targeting) in scope for the platform, or training-only?
4. MCDA and hydrology (W2, W4): in the 2026 build or later?
