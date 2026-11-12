# Buildings and settlement density

**Question:** How many buildings are in the project area, what kind, and where are settlements
concentrated?

## Method

1. Building footprints are read from OpenStreetMap for the area plus 100 m and kept when they fall
   inside the area of influence.
2. Each footprint's area is measured in an equal-area frame; the `building` tag is grouped into
   residential, commercial, industrial, public and community, agricultural, ancillary, other and
   not specified.
3. Buildings are counted on a square grid (default 500 m cells) to map density (1–4, 5–19,
   20–49, 50–149, 150 and more per cell).
4. Count, footprint and type are summarised per administrative unit.

## Data

| Input | Dataset | Resolution | Period | Licence |
|---|---|---|---|---|
| OSM features | OpenStreetMap, from a Geofabrik country extract or the Overpass API (GEIDA tag taxonomy) | Vector | Snapshot date shown in the summary | ODbL (© OpenStreetMap contributors) |

## Outputs

| Output | Meaning |
|---|---|
| `count` | Buildings in the area |
| `by_kind` | Count and footprint per building type |
| `per_zone` | Count, footprint and density per unit |
| `density` | Density grid (map) |
| `footprints` | Footprints (map, up to 20,000; points beyond) |
| `grid_csv` | The density grid as CSV |

## Limitations

Rural buildings are often unmapped in OpenStreetMap, and most footprints carry only
`building=yes` ("not specified"). Use as context (CRI 6.2), not as a census.
