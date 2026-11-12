# People and socio-economics: analysis plan

Status: wave 1 built (2026-11-11); WorldPop added as the main population source. Category `people` in `backend/analyses/people/`.
Catalogue plan: [analysis-catalogue-plan.md](analysis-catalogue-plan.md) §4.5.

## 1. What is built now

| # | Analysis (id) | Answers | P / I / C | Data |
|---|---|---|---|---|
| 1 | Population and density (`population`) | How many people live in the area, where, per admin unit; how many in dense / sparse areas | ● ○ ● | GHS-POP R2023A, 100 m, epochs 1975–2030 |
| 2 | Population change (`population_change`) | How the population grew between two epochs, yearly growth rate, where it grew most | ● ○ ● | GHS-POP R2023A, two epochs |
| 3 | Settlements and urbanisation (`settlements`) | How much of the population is urban, peri-urban or rural (degree of urbanisation); which towns and villages are named | ● ○ ● | GHS-SMOD R2023A (1 km, 8 classes) + GHS-POP; OSM places |
| 4 | Access to services (`service_access`) | How many people live within 1 / 2 / 5 / 10 km of a school, health facility, market or water point | ● ○ ● | GHS-POP 100 m + OSM facility layers (straight-line distance) |
| 5 | Travel time to cities and health care (`travel_time`) | How remote people are: travel time to the nearest city, or to health care by car / on foot | ● ○ ● | Malaria Atlas Project accessibility maps (Weiss et al. 2018, 2020), ~1 km |

(○ = not in that phase.)

## 2. Data access

- **GHSL (JRC)**: published as zipped GeoTIFF tiles (1,000 km, Mollweide) on JRC's open data
  server, with no partial (range) reads. The tiles covering the area are downloaded once into
  `DATA_DIR/ghsl/` (about 50 MB per tile and epoch at 100 m, 2 MB at 1 km), then read by GDAL
  from the zip and warped to the area's UTM grid. Population is resampled with **sum**, so
  counts are kept. Epochs: 1975–2030 every 5 years (2025 and 2030 are projections).
  Licence CC BY 4.0.
- **Malaria Atlas Project**: travel-time maps read for the area from MAP's public WCS
  (GeoTIFF subset, ~1 km), cached per area. Licence CC BY 4.0.
- **OSM**: the existing taxonomy layers (`schools`, `health`, `markets`, `water_points`, `places`).
- **WorldPop API v3** (Global2 R2025A, 100 m, yearly 2015–2030, CC BY 4.0) is the main population
  source: `POST /raster` cuts the grid to the area (everyone or an age / sex group), and `/groups`,
  `/agesex`, `/batch`, `/trend` give age-sex tables and yearly series. Free without a key
  (1,000 requests a day, 100,000 km²); a free key (`WORLDPOP_API_KEY`) raises the limits.
  GHSL is used for years before 2015, for settlement types, and when WorldPop is unavailable.

## 3. Framework additions

| Addition | For |
|---|---|
| `data/people.py`: GHSL tile datasets (`ghsl_pop`, `ghsl_smod`, `ghsl_built`, any epoch) and MAP accessibility datasets | 1–5 |
| Per-dataset resampling in `CatalogRaster` (`sum` for counts) | 1–4 |
| `ops/people.py`: population-weighted statistics, distance bands, people per class | 1–5 |

## 4. Later

| Analysis | Waiting for |
|---|---|
| Travel time to schools / clinics / markets (cost distance on MAP friction) | a cost-distance helper (GRASS `r.cost` or a Dijkstra on the friction grid) |
| Electrification proxy (night lights) | NASA Black Marble needs an Earthdata token (free account) |
| Relative wealth (Meta RWI) | Licence is CC BY-NC (non-commercial): to clear first |
| Subnational development indicators (Global Data Lab), census uploads | table-join framework |
| Built-up area and growth (GHS-BUILT-S, infrastructure category) | same GHSL access; small step after this wave |
