# Road network

**Question:** How many kilometres of road are mapped in the project area, of what class and surface?

## Method

1. Roads (OSM `highway`) are read for the area plus 100 m and cut to the administrative units
   inside the area of influence.
2. Each road is classed (motorway/trunk, primary, secondary, tertiary, local/residential, service,
   track) and its surface grouped as paved, unpaved or unknown; bridges are flagged.
3. Lengths are measured in km in an equal-area frame, per class, surface and unit; road density is
   km per km² of each unit.
4. The total is proposed as evidence for CRI 2.2 (role: verify).

## Data

| Input | Dataset | Resolution | Period | Licence |
|---|---|---|---|---|
| OSM features | OpenStreetMap, from a Geofabrik country extract or the Overpass API (GEIDA tag taxonomy) | Vector | Snapshot date shown in the summary | ODbL (© OpenStreetMap contributors) |

## Outputs

| Output | Meaning |
|---|---|
| `km` | Km of road in the area |
| `by_class` | Km per class, paved and unpaved, bridges |
| `per_zone` | Km, major roads and density per unit |
| `roads` | Map layer by class |
| `csv` | The tables as CSV |

## Limitations

Surface is missing for many roads ("unknown"); tracks and small roads are under-mapped in rural
areas. It measures mapped roads, not roads built by the project.
