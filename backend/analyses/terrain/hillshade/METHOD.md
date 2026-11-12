# Hillshade and relief

**Question:** What does the relief look like, for maps and reports?

## Method

1. The Copernicus DEM GLO-30 is clipped to the area of influence plus a 250 m margin and
   reprojected to the area's UTM zone.
2. Each pixel is shaded by how directly it faces a sun placed at the chosen direction
   (default 315°, north-west, the cartographic convention) and height (default 45°), with
   Horn's 3×3 slope and aspect (as `gdaldem hillshade`). An optional vertical exaggeration
   brings out gentle relief.
3. The local relief (highest minus lowest elevation) is reported for the area and per
   administrative unit.

## Data

| Input | Dataset | Resolution | Period | Licence |
|---|---|---|---|---|
| Elevation | Copernicus DEM GLO-30 (ESA) | 30 m | Static | Copernicus DEM licence, free with attribution |

## Outputs

| Output | Meaning |
|---|---|
| `relief` | Highest minus lowest elevation in the area (m) |
| `per_zone` | Lowest, highest and relief per administrative unit |
| `hillshade` | Shaded relief, 0 (shadow) to 255 (lit) |

## Limitations

A picture for reading the landscape, not a measurement. With the sun from the south-east,
valleys can look like ridges (relief inversion); keep the north-west default for maps.
