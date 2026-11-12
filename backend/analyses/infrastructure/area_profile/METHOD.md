# Area profile

**Question:** What is mapped in the project area?

## Method

1. Each OpenStreetMap layer listed in the manifest (named places, buildings, schools, health
   facilities, markets, places of worship, public services, banks, roads, paths, railways, rivers,
   lakes, water points, power lines and power assets) is read for the area of influence plus 100 m.
2. Features are assigned to the administrative units (level 1, 2 or 3) they fall in; points are
   counted, lines measured in km and polygons in km², in an equal-area frame centred on the area.
3. One row per layer gives the total in the area and per km²; a second table gives each unit's
   values; named places are listed by type (city, town, village…).
4. Layers with a colour are drawn on the map (up to 60,000 features each), polygons under lines
   under points. Layers that couldn't be read are named in the summary.

## Data

| Input | Dataset | Resolution | Period | Licence |
|---|---|---|---|---|
| OSM features | OpenStreetMap, from a Geofabrik country extract or the Overpass API (GEIDA tag taxonomy) | Vector | Snapshot date shown in the summary | ODbL (© OpenStreetMap contributors) |
| Admin units | GADM 4.1, cut to the area | Vector | 2022 | GADM licence |

## Outputs

| Output | Meaning |
|---|---|
| `inventory` | Count, km or km² per layer, and per km² of area |
| `per_zone` | The same per administrative unit |
| `place_list` | Named places with their type |
| `layer_*`, `places_map` | Map layers |
| `csv` | The inventory as CSV |

## Limitations

OpenStreetMap is complete in some places and sparse in others; a low count can mean little is
mapped rather than little exists. Compare with official lists and imagery.
