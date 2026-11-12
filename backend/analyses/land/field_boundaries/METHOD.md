# Field boundaries

**Question:** How many fields are there, how large, and how much land do they cover?

## Method

1. Fields of The World (2nd edition) field polygons for the chosen year are read from the
   GeoParquet file of each UTM zone the area touches, by bounding box (HTTP range requests;
   GDAL's Parquet driver).
2. Polygons with a model score below the minimum are dropped (default: keep all).
3. A field is counted in the admin unit that holds its representative point (so each field is
   counted once); its area is the product's `metrics:area` (m²).
4. Reported: number of fields, land in fields and its share of the area, the median size, the
   distribution by size class, the same per admin unit, and a density grid (share of each cell's
   land in fields). Field outlines are drawn when there are at most 30,000.

## Data

| Input | Dataset | Resolution | Period | Licence |
|---|---|---|---|---|
| Field boundaries | Fields of The World, Global Data 2nd Edition (Taylor Geospatial Engine), Source Cooperative | Polygons from 10 m Sentinel-2 quarterly mosaics | 2023, 2024, 2025 | CC BY 4.0 |

## Limitations

- Polygons are **model predictions**, not surveyed, cadastral or legal parcels; one parcel may
  be several polygons or none.
- Detection is weaker in smallholder systems and outside the training regions; small fields
  are under-counted. The score is a ranking, not a probability.
- Coverage differs by region and year: no polygons does not mean no fields.
- Fields crossing the area's edge are counted whole in the unit holding their representative point.
