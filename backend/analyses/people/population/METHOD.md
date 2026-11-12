# Population and density

**Question:** How many people live in the area, where, and per admin unit?

## Method

1. Population per 100 m cell for the chosen year comes from **WorldPop** (Global2 R2025A, every year
   2015–2030, cut to the area by the WorldPop API) or, for earlier years, if chosen, or when the API is
   unavailable, from the GHSL grid (below). With WorldPop, the age and sex structure of the area and of
   each admin unit comes from the API (`/groups`, `/agesex`, `/batch`).
   GHSL: the GHSL population grid (GHS-POP R2023A, residents per 100 m cell, World Mollweide) for the
   chosen epoch is read from the JRC tile(s) covering the area (downloaded once and cached) and
   warped to the area's UTM grid at 100 m with **sum** resampling, so the total is kept.
2. People are counted in cells whose centre lies inside the area; density = people / area.
3. Density is measured on 1 km blocks (the scale of the GHSL urban thresholds; a 100 m cell with
   3 people would otherwise count as 300 per km²) and each cell takes its block's class (300 or more
   is a settled cluster, which can be a town or a dense village; Settlements separates urban from rural): uninhabited, under 25, 25–100, 100–300,
   300–1,500 and 1,500 or more (300 and 1,500 are the GHSL thresholds for urban clusters and
   centres); people and land per class are reported, and the same per admin unit.

## Data

| Input | Dataset | Resolution | Period | Licence |
|---|---|---|---|---|
| Population, age and sex | WorldPop Global2 R2025A v1 (University of Southampton), WorldPop API v3; DOI 10.5258/SOTON/WP00839, WP00841 | 100 m | 2015–2030, yearly | CC BY 4.0 |
| Population | GHS-POP R2023A, GHSL Data Package 2023 (European Commission JRC) | 100 m | 1975–2030, every 5 years (2025, 2030 projected) | CC BY 4.0 |

## Limitations

- GHS-POP disaggregates census counts (GPW v4.11, census years vary by country) to 100 m with
  built-up volume: totals per admin unit follow the census, the placement within units is
  modelled. Very small areas (a few cells) are uncertain.
- 2025 and 2030 are projections. Recent displacement or refugee settlements may be missing.
- Official national figures win when available; use this for consistent, comparable estimates.
