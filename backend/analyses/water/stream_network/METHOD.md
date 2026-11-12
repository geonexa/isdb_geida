# Stream network and order

**Question:** Where do streams run, how long are they by order, and how dense is the drainage?

## Method

1. The Copernicus DEM GLO-30 is read for the area of influence plus 5 km (water reaching the area
   comes from beyond it) in the area's UTM zone at 30 m.
2. WhiteboxTools conditions the DEM: depressions are breached along least-cost channels (Lindsay
   2016) and any remaining pits filled, so every cell drains to the edge. D8 flow direction and
   flow accumulation (number of upstream cells) follow. This step is cached and shared with the
   other hydrology analyses.
3. Streams are the cells whose upstream area is at least the threshold (default 1 km²). Their
   Strahler order is computed (headwaters are 1; two streams of order n join into n + 1), and the
   streams are vectorised, one line per link.
4. Inside the area: km per order, drainage density (km of stream per km²), the same per admin
   unit, and the length of rivers and streams mapped in OpenStreetMap for comparison.

## Data

| Input | Dataset | Resolution | Period | Licence |
|---|---|---|---|---|
| Elevation | Copernicus DEM GLO-30 (ESA), via Earth Search STAC / AWS Open Data | 30 m | Static | Copernicus DEM licence |
| Waterways (comparison) | OpenStreetMap | lines | snapshot | ODbL |

Engine: WhiteboxTools 2.4 (University of Guelph, MIT licence).

## Limitations

- Streams are modelled where water would concentrate; whether they carry water, and for how long,
  depends on climate and soils. The threshold sets how far upstream channels begin: lower it in
  humid areas, raise it in drylands.
- The DEM is a surface model: in flat areas, cities and dense forest, channels can be displaced, and
  in very flat floodplains D8 can draw short parallel channels.
- Areas draining from far upstream (big rivers entering the area) have their full order only if the
  5 km margin includes enough of the basin; order of large rivers may be underestimated.
