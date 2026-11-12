# Access to services

**Question:** How many people live within reach of schools, clinics, markets, water points and roads?

## Method

1. People per 100 m cell (WorldPop, everyone or an age / sex group such as school-age children 5–14;
   GHSL as fallback for everyone) are read over the area plus 10 km, and the chosen OpenStreetMap layer
   (schools, health facilities, markets, water points or roads) over the same box, so services just
   outside the area count.
2. The locations are burnt into the 100 m grid and the straight-line (Euclidean) distance from every
   cell centre to the nearest one is computed.
3. People are counted per distance band (under 1, 1–2, 2–5, 5–10, 10 km and more), within and beyond
   the chosen distance, with the population-weighted mean distance; the same per admin unit.

## Data

| Input | Dataset | Resolution | Period | Licence |
|---|---|---|---|---|
| Population, age and sex | WorldPop Global2 R2025A v1 (University of Southampton), WorldPop API v3; DOI 10.5258/SOTON/WP00839, WP00841 | 100 m | 2015–2030, yearly | CC BY 4.0 |
| Population | GHS-POP R2023A (European Commission JRC) | 100 m | 2015–2025 | CC BY 4.0 |
| Services | OpenStreetMap layers of the GEIDA taxonomy | points / lines | snapshot | ODbL |

## Limitations

- Straight-line distance ignores terrain, rivers and the road network; real travel is longer
  (see Travel time). Common SDG-style thresholds (e.g. 2 km to a school, 5 km to a clinic) assume
  walking distance.
- OSM completeness varies by country: missing facilities make people look farther than they are;
  an official facility list can replace OSM as a local override.
