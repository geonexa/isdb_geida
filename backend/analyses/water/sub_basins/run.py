"""Sub-catchments of the area from the Copernicus DEM (WhiteboxTools Subbasins), with the points where water leaves the area."""
import json

import numpy as np
import shapely
from scipy import ndimage

from apps.analysis.core.errors import AnalysisError
from apps.analysis.ops import grid as G
from apps.analysis.ops import hydro, terrain

PALETTE = ["#8DD3C7", "#FFFFB3", "#BEBADA", "#FB8072", "#80B1D3", "#FDB462", "#B3DE69", "#FCCDE5"]
MAX_EXITS = 15


def write_geojson(path, geoms_ll, props):
    feats = [{"type": "Feature", "geometry": json.loads(shapely.to_geojson(shapely.set_precision(g, 1e-6))), "properties": p}
             for g, p in zip(geoms_ll, props)]
    path.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))


def run(ctx):
    min_km2 = float(ctx.params["min_area_km2"])
    dem = ctx.raster("dem", buffer_m=hydro.MARGIN_M)
    ctx.progress(20)
    f = hydro.flow(ctx, dem)
    px_km2 = dem.grid.pixel_area_m2 / 1e6
    labels, streams = hydro.subbasins(ctx, f, min_km2 / px_km2)
    acc = f.accumulation().data
    dirs = G.read(f.dir).data
    lab = hydro.merge_small(labels.data, acc, dirs, min_km2 / 5 / px_km2)
    ctx.progress(55)

    inside = ctx.area_mask(dem)
    in_area = np.unique(lab[inside & (lab > 0)])
    if not in_area.size:
        raise AnalysisError("No sub-catchment reaches the chosen size inside the area. Lower the minimum area.")
    n = int(lab.max()) + 1
    cnt_in = np.bincount(lab[inside], minlength=n)
    cnt_all = np.bincount(lab.ravel(), minlength=n)
    slope = terrain.slope(dem, "degrees").data
    ok = inside & np.isfinite(slope)
    slope_sum = np.bincount(lab[ok], weights=slope[ok], minlength=n)
    z = np.where(np.isfinite(dem.data), dem.data, np.nan)
    zmin = ndimage.minimum(np.nan_to_num(z, nan=1e9), labels=np.where(inside, lab, 0), index=in_area)
    zmax = ndimage.maximum(np.nan_to_num(z, nan=-1e9), labels=np.where(inside, lab, 0), index=in_area)
    outs = hydro.outlets(lab, acc)
    ctx.progress(70)

    # Polygons: whole units in the clip, cut to the area for the map ------------------------------
    area_utm = shapely.geometry.shape(ctx.area_in(int(str(dem.crs).split(":")[-1])))
    polys = hydro.polygons(lab, dem.transform, set(in_area.tolist()))
    order = sorted(in_area.tolist(), key=lambda k: -cnt_in[k])
    rows, geoms, props, outlet_pts = [], [], [], []
    for i, k in enumerate(order, start=1):
        r, c = outs[k]
        x, y = dem.transform * (c + 0.5, r + 0.5)
        outlet_in = bool(inside[r, c])
        drains = float(acc[r, c]) * px_km2
        row = {"unit": f"SC-{i:02d}", "area_km2": round(cnt_in[k] * px_km2, 1), "share": round(100 * cnt_in[k] / inside.sum(), 1),
               "whole_km2": round(cnt_all[k] * px_km2, 1), "slope": round(slope_sum[k] / max(cnt_in[k], 1), 1),
               "elev_min": round(float(zmin[np.searchsorted(in_area, k)])), "elev_max": round(float(zmax[np.searchsorted(in_area, k)])),
               "drains_km2": round(drains, 1), "outlet": "in the area" if outlet_in else "outside"}
        rows.append(row)
        g = shapely.intersection(polys[k], area_utm)
        if not g.is_empty:
            geoms.append(g)
            props.append({"unit": row["unit"], "area_km2": row["area_km2"], "drains_km2": row["drains_km2"], "color": i % len(PALETTE)})
        if outlet_in:
            outlet_pts.append((row["unit"], x, y, drains))
    write_geojson(ctx.path("sub_basins.geojson"), hydro.to_lonlat(geoms, dem.crs), props)

    # Where streams leave the area ------------------------------------------------------------
    ex = hydro.exits(inside, streams.data, dirs, acc)
    seen, exit_rows, exit_geoms = set(), [], []
    for r, c, a in ex:
        k = int(lab[r, c])
        if k in seen:          # one exit per unit: its largest
            continue
        seen.add(k)
        x, y = dem.transform * (c + 0.5, r + 0.5)
        unit = next((rw["unit"] for rw, kk in zip(rows, order) if kk == k), "")
        exit_geoms.append(shapely.Point(x, y))
        exit_rows.append({"exit": f"E{len(exit_rows) + 1}", "unit": unit, "drains_km2": round(a * px_km2, 1)})
        if len(exit_rows) >= MAX_EXITS:
            break
    if exit_geoms:
        ll = hydro.to_lonlat(exit_geoms, dem.crs)
        for row, p in zip(exit_rows, ll):
            row["lon"], row["lat"] = round(p.x, 5), round(p.y, 5)
        write_geojson(ctx.path("exits.geojson"), ll, [{"exit": r["exit"], "drains_km2": r["drains_km2"]} for r in exit_rows])
    else:
        write_geojson(ctx.path("exits.geojson"), [], [])
    ctx.progress(85)

    sizes = [r["area_km2"] for r in rows]
    main = exit_rows[0]["drains_km2"] if exit_rows else 0
    ctx.add_metric("unit_count", f"Sub-catchments (from {min_km2:g} km²)", len(rows), "")
    ctx.add_metric("median_km2", "Median size inside the area", round(float(np.median(sizes)), 1), "km²")
    ctx.add_metric("main_exit_km2", "Largest stream leaving the area drains", round(main, 1), "km²")
    ctx.add_table("units", "Sub-catchments", [
        {"key": "unit", "label": "Unit"}, {"key": "area_km2", "label": "In the area", "unit": "km²"},
        {"key": "share", "label": "Of the area", "unit": "%"}, {"key": "whole_km2", "label": "Whole unit", "unit": "km²"},
        {"key": "slope", "label": "Mean slope", "unit": "°"}, {"key": "elev_min", "label": "Lowest", "unit": "m"},
        {"key": "elev_max", "label": "Highest", "unit": "m"}, {"key": "drains_km2", "label": "Drains at outlet", "unit": "km²"},
        {"key": "outlet", "label": "Outlet"}], rows,
        note="Each unit drains to one outlet; 'drains at outlet' includes all land upstream (other units and land outside "
             "the area, within 5 km of it). Units are cut at confluences of streams draining the chosen area.")
    ctx.add_table("exits", "Where streams leave the area", [
        {"key": "exit", "label": "Exit"}, {"key": "unit", "label": "Unit"}, {"key": "drains_km2", "label": "Drains", "unit": "km²"},
        {"key": "lon", "label": "Longitude"}, {"key": "lat", "label": "Latitude"}], exit_rows,
        note="Largest stream crossing the area's boundary in each unit; drained area counts land upstream within the DEM clip.")
    ctx.add_vector("sub_basins", "Sub-catchments", "sub_basins.geojson", {
        "property": "color", "opacity": 0.45, "outline": "#1F4E79", "color": PALETTE[0],
        "classes": [{"value": i, "color": col, "label": "Sub-catchment (colours tell neighbours apart)" if i == 0 else ""}
                    for i, col in enumerate(PALETTE)]})
    ctx.add_vector("exit_points", "Where streams leave the area", "exits.geojson", {"color": "#08519C", "radius": 6})
    ctx.summary(f"The area splits into {len(rows)} sub-catchments (median {np.median(sizes):,.0f} km² inside the area); "
                f"{len(exit_rows)} streams leave it, the largest draining {main:,.0f} km². Copernicus 30 m DEM, WhiteboxTools.")
