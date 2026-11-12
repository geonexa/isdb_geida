# Settlements and urbanisation

**Question:** Which villages and towns are there, how large, how urban?

## Method

1. GHS-POP (100 m, sum) and the GHSL settlement model GHS-SMOD (1 km, degree of urbanisation level 2,
   nearest neighbour) are read on the same UTM grid for the chosen epoch.
2. People and land are counted per class: urban centre, dense urban cluster, semi-dense urban cluster
   (together **urban**), suburban / peri-urban (**peri-urban**), rural cluster, low and very low
   density rural (**rural**), water. The same shares per admin unit.
3. OpenStreetMap named places (`place=city/town/village/hamlet/...`) inside the area are listed
   with their settlement class and the people within about 1 km of the point (GHSL).

## Data

| Input | Dataset | Resolution | Period | Licence |
|---|---|---|---|---|
| Settlement classes | GHS-SMOD R2023A (European Commission JRC), Degree of Urbanisation method | 1 km | 1975–2030 | CC BY 4.0 |
| Population | GHS-POP R2023A | 100 m | 1975–2030 | CC BY 4.0 |
| Named places | OpenStreetMap (Geofabrik extract) | points | snapshot | ODbL |

## Limitations

- The Degree of Urbanisation is a harmonised international definition (UN Statistical Commission
  2020); national urban / rural definitions differ.
- Classes are 1 km cells: a small town can appear as a rural cluster.
- OSM place points are named locations, not boundaries; people within 1 km overlap between
  nearby places and are not a settlement's population.
