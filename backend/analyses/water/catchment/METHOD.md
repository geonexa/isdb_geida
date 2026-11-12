# Catchment from a point

**Question:** Which land drains to a chosen point (a dam, intake, bridge or road crossing), and how
large and steep is it?

## Method

1. **Outlet.** The user picks a point on the map (or types longitude, latitude) inside the area of
   influence or within 10 km of it. It is moved within the snapping distance (default 300 m), in one of two ways:
   - **Nearest stream** (default; Jenson 1991): the nearest cell draining at least 1 km², then the largest
     stream within two cells (D8 can run a small channel right beside the main one). With no such stream in
     reach it goes to the cell of highest flow accumulation in reach.
   - **Largest stream** (as ArcGIS Snap Pour Point): the cell of highest flow accumulation within the distance,
     e.g. the main river near a click. Use it with a larger distance (1–2 km) to catch a river clicked roughly.

   The profile gives both points, the distance moved and the area drained at the outlet. If the outlet drains
   less than 1 km², it isn't on a stream: the summary and the profile say so, and name the nearest stream
   draining 1 km² or more and where the biggest stream within 3 km passes (distance, direction, drained area).
2. **Elevation clip.** The Copernicus DEM GLO-30 is read for the area of influence plus 5 km (the
   same clip as Stream network and Sub-catchments, so their cached flow is reused), widened to
   include the outlet. Depressions are breached (least cost, Lindsay 2016), and D8 flow direction and
   accumulation are computed with WhiteboxTools.
3. **Catchment.** WhiteboxTools `Watershed` from the outlet. If the catchment reaches the edge of the
   clip, the clip is doubled on each side it reaches and the steps repeat, up to the largest catchment
   chosen (default 25,000 km²) and a clip of 80,000 km² (growth stops once the clip can't grow by a quarter). Clips over 45,000 km² are read at 90 m
   instead of 30 m (in flat land 90 m moves divides noticeably, so 30 m is kept as long as practical). The
   outlet is snapped once, on the first clip; on larger clips the outlet is the cell nearest it that drains at least
   what the smaller clip found, so a coarser grid can't move it onto another channel. If the catchment still reaches the edge, the run says it is cut off and the area
   is a minimum.
4. **Profile:**
   - area, and the part inside the area of influence;
   - elevation (outlet, lowest, mean, highest) and mean slope;
   - longest flow path (WhiteboxTools `MaxUpslopeFlowpathLength` at the outlet);
   - time of concentration, for catchments up to 1,000 km² (Kirpich 1940: *t* = 0.0195 *L*^0.77 *S*^−0.385 minutes, with *L* the
     longest flow path in metres and *S* the drop from the highest point to the outlet over *L*);
   - streams by Strahler order, from 1 km² upstream, or from area / 2,500 for catchments over
     2,500 km² so the map stays readable.

## Data

| Input | Dataset | Resolution | Period | Licence |
|---|---|---|---|---|
| Elevation | Copernicus DEM GLO-30 (ESA), via Earth Search STAC / AWS Open Data | 30 m (90 m for clips over 45,000 km²) | Static | Copernicus DEM licence |

Engine: WhiteboxTools 2.4 (University of Guelph, MIT licence). The analysis uses the elevation
model only.

## Limitations

- The catchment comes from the DEM alone. In flat land, deltas, karst and irrigated plains (canals),
  divides are uncertain or the catchment differs from where water actually goes.
- Snapping can pick the wrong stream where two run close together (a confluence just upstream or
  downstream). Check the outlet on the map and move it, or lower the snapping distance.
- Only the catchment itself is reported. Rainfall, evapotranspiration, land cover and people inside
  it are left to the analyses for those (e.g. the planned water balance).
- Kirpich was derived for small, steep agricultural catchments, so it is left out above 1,000 km²;
  even below, design floods need a hydrological study.
- Very large catchments (25,000 km² or more) are cut off at the limit. HydroBASINS, once uploaded,
  will give the full basin.
