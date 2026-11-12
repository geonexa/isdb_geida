# Site suitability

**Question:** Where does an intervention fit best, given your own conditions on terrain, land, water,
people and access?

## Method

A weighted overlay of yes/no conditions (a simple multi-criteria evaluation), on a 30 m grid over the area
of influence.

1. **Conditions.** You list conditions in the run form. Each one has:
   - a layer (slope, elevation, land cover, rainfall, ETa, biomass, surface water, tree cover, population
     density, travel time to a city, or distance to roads, rivers, places, power lines, schools or health
     facilities);
   - a limit: a minimum, a maximum or both for values (e.g. slope 0–10°, ETa ≥ 200 mm), or one or more
     classes for land cover (e.g. cropland);
   - a weight (any numbers; they are scaled to 100%);
   - optionally **must-have**: land failing it is excluded whatever else it meets.
2. **Grid.** The Copernicus DEM GLO-30 sets the grid (30 m, the area's UTM zone, the area plus 250 m so slope
   is valid at the border). Every other layer is read for the area and resampled onto it: land cover by
   nearest neighbour (classes are kept), population with totals kept, other values by averaging or bilinear
   interpolation. Rainfall, ETa and biomass are read for the chosen year.
3. **Derived layers.**
   - Slope: Horn's 3×3 method on the DEM, in degrees.
   - Population density: WorldPop 2025 people per km² over 1 km blocks (so a single house doesn't make a
     cell "dense").
   - Distances: straight-line distance in km from each cell to the nearest OpenStreetMap feature, counting
     features up to 10 km outside the area. Where there is none within 10 km, the distance counts as over
     10 km.
4. **Test.** Each condition gives met / not met for every cell. A cell with no data for a layer counts as not
   meeting that condition.
5. **Score.** Score = the sum of the weights of the conditions a cell meets, as a share of all weights (0–100%).
   If every condition is a must-have with no weight, the score is 100% where all are met.
6. **Classes.** Not suitable (fails a must-have), low (under 50%), moderate (50–74%), high (75–99%), all
   conditions met (100%).
7. **Suitable land and sites.** Cells not excluded and scoring at least the chosen score (default 75%) are
   suitable. Touching suitable cells (8 neighbours) form sites; sites at least the smallest size (default
   0.5 km²) are listed, largest first, with their area, mean score and centre, and drawn on the map.
8. **Summary.** Area and share per class; for each condition the area that meets it (to see which condition
   limits the result); suitable and excluded land per administrative unit.

## Data

| Layer | Dataset | Resolution | Period | Licence |
|---|---|---|---|---|
| Elevation, slope | Copernicus DEM GLO-30 (ESA) | 30 m | Static | Copernicus DEM licence |
| Land cover | ESA WorldCover | 10 m | 2021 | CC BY 4.0 |
| Rainfall, ETa, biomass | FAO WaPOR v3 L1 (rainfall from CHIRPS) | 5 km / 300 m / 300 m | 2018–2025 | CC BY 4.0 |
| Surface water occurrence | JRC Global Surface Water | 30 m | 1984–2021 | Copernicus / CC BY 4.0 |
| Tree cover | Hansen / UMD Global Forest Change v1.12 | 30 m | 2000 | CC BY 4.0 |
| Population | WorldPop Global2 R2025A | 100 m | 2025 | CC BY 4.0 |
| Travel time to cities | Malaria Atlas Project (Weiss et al. 2018) | ~1 km | 2015 | CC BY 4.0 |
| Roads, rivers, places, power lines, schools, health | OpenStreetMap | Vector | Current snapshot | ODbL |

Only the layers used by your conditions are read.

## Outputs

| Output | Meaning |
|---|---|
| `suitable_km2`, `suitable_share` | Suitable land (score at least the chosen score, no must-have failed) |
| `excluded_share` | Share of the area failing a must-have |
| `site_count` | Sites at least the smallest size |
| `criteria` | Each condition with its weight and the area meeting it |
| `classes` | Area per suitability class |
| `per_zone` | Suitable and excluded land per administrative unit |
| `sites` | The largest sites: area, mean score, centre |
| `suitability`, `score` | Class map and score map (GeoTIFF + map) |
| `site_polygons` | Site outlines (map, GeoJSON) |

## Limitations

- Conditions are yes/no: a slope of 10.1° fails "≤ 10°" as much as 30° does. Use several conditions with
  different limits and weights to grade a layer (e.g. ≤ 5° weight 20 and ≤ 10° weight 10).
- Rainfall is at about 5 km and travel time at about 1 km; on a 30 m grid their limits fall along coarse
  blocks.
- Distances are straight lines, not along roads or paths, and depend on how complete OpenStreetMap is.
- The result ranks land by your conditions; it isn't a feasibility study. Check sites on imagery and on the
  ground (land tenure, soils, flood risk, protected areas).
