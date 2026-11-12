# Biomass production

**Question:** How much biomass does the land produce each year?

## Method

1. FAO WaPOR v3 level 1 (global) annual Total Biomass Production (kg dry matter per hectare per
   year, 300 m) is read for the year, reprojected to the area's UTM zone, with WaPOR's scale factor
   applied.
2. Total production = Σ (kg/ha × pixel area in ha) / 1,000 (tonnes); the mean is over pixels with
   a value inside the area.
3. ESA WorldCover 2021 is resampled to the 300 m grid (nearest neighbour) to give the mean on
   cropland and the totals per land cover class.
4. With a comparison year, the same is computed for it; the change is reported in percent for
   the area, per admin unit (on pixels valid in both years) and per pixel (map, pixels with at
   least 100 kg/ha in the comparison year).

## Data

| Input | Dataset | Resolution | Period | Licence |
|---|---|---|---|---|
| Biomass | FAO WaPOR v3, L1 Total Biomass Production (annual, global), FAO public cloud bucket | 300 m | 2018–2025 | Open (FAO WaPOR terms) |
| Land cover | ESA WorldCover 2021 v200 | 10 m | 2021 | CC BY 4.0 |

## Limitations

- GEIDA uses WaPOR level 1 (global, 300 m) everywhere, so results are comparable between
  countries; level 2 (100 m, Africa and the Near East only) is not used.
- WaPOR's Total Biomass Production is net primary production converted to dry matter: it
  counts all growth, above and below ground, so values (often 10–25 t/ha) are well above
  harvestable biomass. Use it to compare places and years, not as a yield.
- Biomass is modelled from net primary production (light use efficiency), not measured yield;
  converting to crop yield needs a harvest index and moisture content per crop.
- A 300 m pixel mixes several land cover classes in fragmented landscapes; per-class figures
  use the class at the pixel centre.
