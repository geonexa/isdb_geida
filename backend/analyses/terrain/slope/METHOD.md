# Slope and slope classes

**Question:** How steep is the land, and how much of it falls in each slope class?

## Method

1. The Copernicus DEM GLO-30 is clipped to the area of influence plus a 250 m margin (so pixels
   at the border have neighbours) and reprojected to the area's UTM zone.
2. Slope is computed with Horn's 3×3 method (the method of `gdaldem slope`), in degrees or
   percent rise.
3. Pixels whose centre lies inside the area are classed: flat (0–2°), gentle (2–5°), moderate
   (5–10°), strong (10–15°), steep (15–30°) and very steep (30° and more), and the area of each
   class is counted.
4. The mean slope and the share of land steeper than the chosen threshold (default 15°) are
   reported for the area and per administrative unit.

## Data

| Input | Dataset | Resolution | Period | Licence |
|---|---|---|---|---|
| Elevation | Copernicus DEM GLO-30 (ESA), via Earth Search STAC / AWS Open Data | 30 m | Static | Copernicus DEM licence, free with attribution |

## Outputs

| Output | Meaning |
|---|---|
| `mean_slope` | Mean slope over the area (degrees or percent) |
| `steep_share` | Share of the area steeper than the threshold |
| `classes` | Area and share per slope class |
| `per_zone` | Mean and highest slope, steep share and area per administrative unit |
| `slope` | Slope map (GeoTIFF values and map preview) |

## Limitations

Slope depends on pixel size: at 30 m (or coarser for large areas, see the log) short steep
banks and terraces are smoothed out. The DEM is a surface model, so tree and building edges
can appear as steep slopes.
