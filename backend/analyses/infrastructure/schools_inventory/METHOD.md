# Schools in the area

**Question:** Which schools are mapped inside the project area, and where?

## Method

1. Schools, kindergartens, colleges and universities (OSM `amenity`) are read for the area plus
   100 m and kept when inside the area of influence.
2. Each gets an education level from `isced:level` (pre-primary to tertiary), else from its
   amenity; operator type and name are listed when mapped.
3. Schools are counted by level and per administrative unit (default level 3) and shown on the map.
4. The count is proposed as evidence for CRI 9.3 (role: verify).

## Data

| Input | Dataset | Resolution | Period | Licence |
|---|---|---|---|---|
| OSM features | OpenStreetMap, from a Geofabrik country extract or the Overpass API (GEIDA tag taxonomy) | Vector | Snapshot date shown in the summary | ODbL (© OpenStreetMap contributors) |

## Outputs

| Output | Meaning |
|---|---|
| `count` | Schools in the area |
| `by_kind` | Count per level |
| `per_zone` | Count per unit |
| `list` | Every school with level and operator |
| `points` | Map layer |
| `csv` | The list as CSV |

## Limitations

It counts mapped schools, not schools built by the project, and the level is often not mapped.
Check against the project's school list and imagery by date.
