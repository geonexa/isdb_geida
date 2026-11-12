# Sub-catchments in the area

**Question:** Which drainage units does the area split into, how large and steep are they, and where
does water leave the area?

## Method

1. The Copernicus DEM GLO-30 (area plus 5 km, UTM, 30 m) is conditioned and D8 flow direction and
   accumulation computed with WhiteboxTools (shared with Stream network, cached).
2. Streams are the cells draining at least the chosen area (default 25 km²). WhiteboxTools
   `Subbasins` gives one unit per stream link, so units are cut where streams meet; each drains to
   a single outlet.
3. Units smaller than a fifth of the chosen area (short links between close confluences) are merged
   into the unit their outlet drains into.
4. For each unit touching the area: area inside the area, whole unit area (within the DEM clip),
   mean slope, elevation range and the land draining through its outlet (all upstream units).
5. Exits: stream cells inside the area that drain out of it and whose water doesn't come back in
   (a river along the boundary counts once, at its last crossing); one per unit, largest first.

## Data

| Input | Dataset | Resolution | Period | Licence |
|---|---|---|---|---|
| Elevation | Copernicus DEM GLO-30 (ESA), via Earth Search STAC / AWS Open Data | 30 m | Static | Copernicus DEM licence |

Engine: WhiteboxTools 2.4 (University of Guelph, MIT licence).

## Limitations

- Units come from the DEM alone; HydroBASINS (when uploaded) gives the official nested basins for
  reporting and naming.
- Drained areas only count land inside the DEM clip (the area plus 5 km): a large river entering
  the area drains much more than reported. Catchment from a point reads as much upstream land as
  needed.
- In very flat terrain, divides between units are uncertain.
