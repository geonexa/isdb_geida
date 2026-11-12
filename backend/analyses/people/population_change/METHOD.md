# Population change

**Question:** How fast has the population grown since 2000?

## Method

1. Both years come from the same source: WorldPop for 2015–2030 (any year; the API's `/trend` adds
   every year between), else GHS-POP R2023A epochs. They are read on the same 100 m UTM grid (sum resampling).
2. Population at both dates, change (people and %) and the compound yearly growth rate
   ((P₁ / P₀)^(1 / years) − 1) for the area and per admin unit.
3. Map: people added or lost per cell.

## Data

| Input | Dataset | Resolution | Period | Licence |
|---|---|---|---|---|
| Population, age and sex | WorldPop Global2 R2025A v1 (University of Southampton), WorldPop API v3; DOI 10.5258/SOTON/WP00839, WP00841 | 100 m | 2015–2030, yearly | CC BY 4.0 |
| Population | GHS-POP R2023A (European Commission JRC) | 100 m | 1975–2030, every 5 years | CC BY 4.0 |

## Limitations

- Epochs are modelled from censuses of other years and interpolated or extrapolated; change at
  cell level reflects built-up growth more than counted people. Use admin-unit totals.
- 2025 and 2030 are projections.
