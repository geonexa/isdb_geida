# Elevation profile

**Question:** What are the lowest, highest and mean elevations, and how is the land distributed by height?

## Method

1. The Copernicus DEM GLO-30 is clipped to the area of influence and reprojected to the area's
   UTM zone (30 m pixels; larger areas are read at a coarser resolution, reported in the log).
2. Pixels whose centre lies inside the area are kept.
3. Lowest, mean and highest elevation are computed over those pixels.
4. Hypsometry: the elevation range is split into equal bands (rounded to a readable step,
   about the number of bands chosen) and the area of each band is counted.
5. The same statistics are computed per administrative unit.

## Data

| Input | Dataset | Resolution | Period | Licence |
|---|---|---|---|---|
| Elevation | Copernicus DEM GLO-30 (ESA), via Earth Search STAC / AWS Open Data | 30 m | Static (2011–2015 acquisitions) | Copernicus DEM licence, free with attribution |

## Outputs

| Output | Meaning |
|---|---|
| `min_elevation`, `mean_elevation`, `max_elevation` | Over the area of influence, metres above sea level |
| `bands` | Area (km²) and share (%) per elevation band |
| `per_zone` | Lowest, mean and highest elevation and area per administrative unit |
| `elevation` | Elevation map (GeoTIFF values and map preview) |

## Limitations

The DEM is a surface model: in forests and towns it shows the top of trees and buildings,
not the ground. Vertical accuracy is a few metres; in steep terrain and over water it is worse.
