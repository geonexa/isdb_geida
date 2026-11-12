# Travel time to cities and health care

**Question:** How remote is the area from towns, cities and health care?

## Method

1. The chosen Malaria Atlas Project travel-time map (minutes, ~1 km) is read for the area from MAP's
   public WCS and resampled onto the 100 m population grid of the area (WorldPop, everyone or an age / sex group; GHSL as fallback).
2. Each cell's travel time is weighted by its people: population-weighted mean and median, the share
   within the chosen time, and people per band (15, 30, 60 min, 2, 3, 6 h); the same per admin unit.

## Data

| Input | Dataset | Resolution | Period | Licence |
|---|---|---|---|---|
| Population, age and sex | WorldPop Global2 R2025A v1 (University of Southampton), WorldPop API v3; DOI 10.5258/SOTON/WP00839, WP00841 | 100 m | 2015–2030, yearly | CC BY 4.0 |
| Travel time to cities (50,000+) | Weiss et al. 2018, Nature 553 (Malaria Atlas Project) | ~1 km | 2015 | CC BY 4.0 |
| Travel time to health care, motorised / walking | Weiss et al. 2020, Nature Medicine 26 (Malaria Atlas Project) | ~1 km | 2019 | CC BY 4.0 |
| Population | GHS-POP R2023A (European Commission JRC) | 100 m | 2015, 2020 | CC BY 4.0 |

## Limitations

- Travel times are modelled from road and land friction surfaces (OSM and Google roads of 2015 /
  2019, land cover, slope), not observed; new roads since then are not reflected.
- Health facilities in the 2019 map come from a global compilation and may differ from the
  national list.
