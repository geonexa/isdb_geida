# Contours

**Question:** Contour lines at a chosen interval, ready to download.

## Method

1. The Copernicus DEM GLO-30 is clipped to the area of influence plus a 250 m margin and
   reprojected to the area's UTM zone; pixels outside the area are set to no data so lines
   stop at its border.
2. Optional smoothing (mean of 3 × 3 or 5 × 5 pixels) removes pixel noise that would make
   lines jagged.
3. Contours are traced with GDAL (`ContourGenerate`) at the chosen interval, or at a round
   interval giving about 15 levels between the lowest and highest point. Every fifth level is
   an index contour.
4. Lines are saved in a GeoPackage in the UTM zone (full detail, for CAD and GIS) and as a
   simplified GeoJSON (tolerance one pixel) for the map.

## Data

| Input | Dataset | Resolution | Period | Licence |
|---|---|---|---|---|
| Elevation | Copernicus DEM GLO-30 (ESA) | 30 m | Static | Copernicus DEM licence, free with attribution |

## Outputs

| Output | Meaning |
|---|---|
| `interval` | Contour interval used (m) |
| `lines`, `length_km` | Number of lines and their total length |
| `contours` | Contour lines on the map (`elev`, `index` per line) |
| `gpkg` | GeoPackage download (UTM, full detail) |

## Limitations

Contours from a 30 m surface model are fit for planning and orientation, not for detailed
design: their vertical accuracy is a few metres and intervals below 5 m show DEM noise more
than terrain. Use survey data for engineering design.
