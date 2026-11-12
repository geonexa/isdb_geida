# Aspect

**Question:** Which way do the slopes face?

## Method

1. The Copernicus DEM GLO-30 is clipped to the area of influence plus a 250 m margin and
   reprojected to the area's UTM zone.
2. Aspect, the compass direction a slope faces (down-slope), is computed with Horn's 3×3
   method (as `gdaldem aspect`), in degrees clockwise from north.
3. Land flatter than the threshold (default 2° of slope) is classed *flat*: its direction has
   no meaning. The rest is grouped into eight directions of 45° each (north = 337.5°–22.5°).
4. The area facing each direction is counted for the area of influence and per
   administrative unit. In the northern hemisphere, south-facing slopes get the most sun.

## Data

| Input | Dataset | Resolution | Period | Licence |
|---|---|---|---|---|
| Elevation | Copernicus DEM GLO-30 (ESA) | 30 m | Static | Copernicus DEM licence, free with attribution |

## Outputs

| Output | Meaning |
|---|---|
| `main_direction` | Direction faced by the largest area of sloping land |
| `flat_share` | Share of the area flatter than the threshold |
| `south_facing_share` | Share facing south, south-east or south-west |
| `directions` | Area and share facing each direction, and flat |
| `per_zone` | Main direction and flat share per administrative unit |
| `aspect` | Aspect map in nine classes |

## Limitations

On gentle slopes aspect is sensitive to small errors in the elevation model; the flat
threshold hides the least reliable pixels. South-facing means more sun only north of the
equator (south of it, north-facing slopes get more sun).
