# WaPOR time series

**Question:** How do rainfall, water use and biomass change over time at a point or in each zone?

## Data

FAO WaPOR v3, **level 1** (global), read from FAO's cloud-optimised GeoTIFFs. Values are as FAO publishes them:
dekadal layers give the mean per day over the dekad (e.g. mm/day), monthly and annual layers the total.

| Data | Dekadal | Monthly | Annual | Resolution |
|---|---|---|---|---|
| Precipitation (CHIRPS) | ✓ | ✓ | ✓ | about 5 km |
| Reference evapotranspiration | ✓ | ✓ | ✓ | about 30 km |
| Actual evapotranspiration and interception (AETI) | ✓ | ✓ | ✓ | 300 m |
| Transpiration, evaporation, interception | ✓ | | ✓ | 300 m |
| Net primary production | ✓ | ✓ | | 300 m |
| Total biomass production | | | ✓ | 300 m |
| Gross and net biomass water productivity | | | ✓ | 300 m |
| Relative soil moisture | ✓ | | | 300 m |

## Method

1. **Periods.** The WaPOR mapset for the data and time step (e.g. `L1-AETI-M`) and the periods FAO has published
   in the chosen years (WaPOR v3 starts in 2018; up to 220 periods per run, about six years of dekads).
2. **Place.** A point picked on the map; the area of influence; its administrative units (GADM, clipped to the
   area); or the polygons of one of the project's layers (an analysis or Toolbox result such as fields or
   sub-basins, up to 200 polygons).
3. **Reading.** For each period, only the window around the point or polygons is read (scale factor applied,
   no-data removed), several files at a time. Windows are cached, so a second run on the same place is fast.
4. **Values.** A point takes the pixel it falls in. A polygon takes the mean of the pixels whose centre lies in
   it; a polygon smaller than a pixel takes every pixel it touches. Pixels are not weighted by area (at 300 m the
   difference is negligible).
5. **Trend.** Sen's slope per year with the Mann-Kendall test (significant when p < 0.05), on yearly means for
   dekadal and monthly steps (only years with nearly all periods) and on the yearly values for an annual step.
6. **Mean map.** The mean of all periods per pixel, inside the polygons.

## Outputs

- Mean, highest and lowest value over the period and the trend per year (for several polygons: the mean of the
  polygon means).
- A chart of the series (one line per polygon, the first 12) and a table of all values; a CSV of every value.
- A summary per polygon: mean, lowest, highest, trend and whether it is significant.
- The mean map of the period, and the point or polygons as a layer with their mean.

## Limits

- WaPOR level 1 is a global product at 300 m (rainfall about 5 km, reference evapotranspiration about 30 km):
  small fields mix with their surroundings. Use it for patterns and trends, not field-level accounting.
- Periods FAO hasn't published, or files that can't be read, are skipped and listed in the run log.

## Reference

FAO (2024). WaPOR v3 database and methodology. FAO, Rome. Data under CC BY 4.0.
