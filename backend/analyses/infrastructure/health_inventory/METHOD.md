# Health facilities in the area

**Question:** Which hospitals, clinics and health posts are mapped in the project area?

## Method

1. Health facilities (OSM `amenity` and `healthcare` tags: hospitals, clinics, health centres,
   health posts, doctors, birthing centres) are read for the area plus 100 m and kept when inside
   the area of influence.
2. Each facility gets a type from `healthcare`, else `amenity`; level, operator and beds are
   listed when mapped.
3. Facilities are counted by type and per administrative unit (default level 3) and shown on the map.
4. The count is proposed as evidence for CRI 8.1 (role: verify), for a reviewer to accept or reject.

## Data

| Input | Dataset | Resolution | Period | Licence |
|---|---|---|---|---|
| OSM features | OpenStreetMap, from a Geofabrik country extract or the Overpass API (GEIDA tag taxonomy) | Vector | Snapshot date shown in the summary | ODbL (© OpenStreetMap contributors) |

## Outputs

| Output | Meaning |
|---|---|
| `count` | Facilities in the area |
| `by_kind` | Count per type |
| `per_zone` | Count per unit |
| `list` | Every facility with its attributes |
| `points` | Map layer |
| `csv` | The list as CSV |

## Limitations

It counts mapped facilities, not those built or equipped by the project. Check against the
Ministry of Health facility list and imagery by date.
