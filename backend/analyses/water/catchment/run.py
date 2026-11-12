"""Catchment upstream of a point picked on the map (Copernicus DEM, WhiteboxTools), with its profile."""
import json
import math

import numpy as np
import shapely
from rasterio.warp import transform as warp

from apps.analysis.core.errors import AnalysisError
from apps.analysis.engines import whitebox
from apps.analysis.ops import grid as G
from apps.analysis.ops import hydro, terrain

FINE_MAX_KM2 = 45_000        # DEM clips larger than this (about 50 M cells at 30 m) are read at 90 m
COARSE_RES_M = 90
MAX_CLIP_KM2 = 80_000
MAX_TRIES = 6
SNAP_STREAM_KM2 = 1          # snap onto streams draining at least this much
NEARBY_M = 3000              # how far to look for streams to suggest when the outlet isn't on one
KIRPICH_MAX_KM2 = 1000     # Kirpich is for small catchments; not reported above this
ORDER_STYLE = {1: ("#9ECAE1", 0.8), 2: ("#6BAED6", 1.2), 3: ("#4292C6", 1.8), 4: ("#2171B5", 2.4), 5: ("#08519C", 3.0),
               6: ("#08306B", 3.6)}


def bbox_km2(b):
    w, s, e, n = b
    return (e - w) * 111.32 * math.cos(math.radians((s + n) / 2)) * (n - s) * 111.32


def first_bbox(ctx, lon, lat):
    """The area plus the usual 5 km margin (so the flow cache of the other hydrology analyses is reused), widened to
    include the outlet with 2 km around it."""
    w, s, e, n = ctx.bbox(hydro.MARGIN_M)
    dlat = 2000 / 111_320
    dlon = dlat / max(0.2, math.cos(math.radians(lat)))
    return (min(w, lon - dlon), min(s, lat - dlat), max(e, lon + dlon), max(n, lat + dlat))


def grow(b, sides, cap_km2):
    """Extend the clip on the sides the catchment reaches, doubling its size along that axis (within cap_km2).
    None when it can't grow by at least a quarter any more (at the cap)."""
    w, s, e, n = b
    dx, dy = e - w, n - s
    for _ in range(8):
        nb = (w - dx * ("w" in sides), s - dy * ("s" in sides), e + dx * ("e" in sides), n + dy * ("n" in sides))
        if bbox_km2(nb) <= cap_km2:
            return nb if bbox_km2(nb) >= 1.25 * bbox_km2(b) else None
        dx, dy = dx / 2, dy / 2
    return None


def touched_sides(rows, cols, dem, b):
    """Which sides of the lon/lat clip the catchment's edge cells lie on ('n', 's', 'e', 'w')."""
    if not len(rows):
        return set()
    xs, ys = dem.transform * (cols + 0.5, rows + 0.5)
    lon, lat = (np.asarray(v) for v in warp(dem.crs, "EPSG:4326", list(xs), list(ys)))
    w, s, e, n = b
    d = np.stack([lon - w, e - lon, lat - s, n - lat])
    tol = 5 * dem.grid.res / 111_000          # a few cells: edge cells far from every side are no-data holes, not the clip edge
    near = d.min(axis=0) <= tol
    return {"wesn"[i] for i in np.argmin(d[:, near], axis=0)} if near.any() else set()


def to_cell(dem, lon, lat):
    xs, ys = warp("EPSG:4326", dem.crs, [lon], [lat])
    c, r = ~dem.transform * (xs[0], ys[0])
    return int(math.floor(r)), int(math.floor(c))


def cell_lonlat(dem, r, c):
    x, y = dem.transform * (c + 0.5, r + 0.5)
    lon, lat = warp(dem.crs, "EPSG:4326", [x], [y])
    return lon[0], lat[0]


def refind(acc, row, col, res_m, min_cells, reach_m=300):
    """The cell nearest (row, col) within reach_m draining at least min_cells; else the highest accumulation in reach."""
    h, w = acc.shape
    k = max(2, int(reach_m // res_m) + 1)
    r0, r1, c0, c1 = max(0, row - k), min(h, row + k + 1), max(0, col - k), min(w, col + k + 1)
    win = np.where(np.isfinite(acc[r0:r1, c0:c1]), acc[r0:r1, c0:c1], -1)
    rr, cc = np.mgrid[r0:r1, c0:c1]
    d = np.hypot(rr - row, cc - col)
    ok = win >= min_cells
    i = np.unravel_index(int(np.argmin(np.where(ok, d, np.inf))) if ok.any() else int(np.argmax(win)), win.shape)
    return int(rr[i]), int(cc[i])


def trace(ctx, lon, lat, snap_m, max_km2, snap_to="nearest"):
    """DEM, flow, snapped outlet and catchment mask, enlarging the clip until the catchment fits."""
    b = first_bbox(ctx, lon, lat)
    prev = snapped = None
    for attempt in range(MAX_TRIES):
        km2 = bbox_km2(b)
        res = None if km2 <= FINE_MAX_KM2 else COARSE_RES_M
        ctx.set_grid(None)                       # each clip sets its own grid
        dem = ctx.raster("dem", bbox=b, res=res)
        ctx.log(f"Elevation clip {km2:,.0f} km² at {dem.grid.res:.0f} m")
        f = hydro.flow(ctx, dem)
        acc = f.accumulation().data
        px_km2 = dem.grid.pixel_area_m2 / 1e6
        r, c = to_cell(dem, lon, lat)
        h, w = acc.shape
        if not (0 <= r < h and 0 <= c < w) or not np.isfinite(dem.data[r, c]):
            raise AnalysisError("The outlet has no elevation data (sea or outside the elevation model). Move it onto land.")
        if prev is None:
            sr, sc, moved = hydro.snap_outlet(acc, r, c, dem.grid.res, snap_m, SNAP_STREAM_KM2 / px_km2, mode=snap_to)
            nearby = hydro.nearby_streams(acc, r, c, dem.grid.res, px_km2, SNAP_STREAM_KM2 / px_km2, NEARBY_M)
            snapped = cell_lonlat(dem, sr, sc)
        else:
            # Larger clips (maybe at 90 m): don't snap again, which could jump to another channel; take the cell
            # nearest the outlet found first that drains at least what the smaller clip found.
            sr, sc = refind(acc, *to_cell(dem, *snapped), dem.grid.res, 0.9 * prev / px_km2)
        mask = hydro.watershed(ctx, f, sr, sc, folder=ctx.scratch(f"hydro{attempt}"))
        ws_km2 = float(mask.sum()) * px_km2
        prev = ws_km2
        sides = touched_sides(*hydro.edge_cells(mask, dem.valid), dem, b)
        if not sides:
            return dem, f, (sr, sc, moved), mask, False, nearby
        ctx.log(f"Catchment reaches the clip edge ({', '.join(sorted(sides))}) at {ws_km2:,.0f} km²")
        if ws_km2 >= max_km2 or km2 >= MAX_CLIP_KM2 * 0.99:
            return dem, f, (sr, sc, moved), mask, True, nearby
        nb = grow(b, sides, MAX_CLIP_KM2)
        if nb is None:
            return dem, f, (sr, sc, moved), mask, True, nearby
        b = nb
        ctx.progress(10 + 8 * (attempt + 1))
    return dem, f, (sr, sc, moved), mask, True, nearby


def write_geojson(path, geoms_ll, props):
    feats = [{"type": "Feature", "geometry": json.loads(shapely.to_geojson(shapely.set_precision(g, 1e-6))), "properties": p}
             for g, p in zip(geoms_ll, props)]
    path.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))


def run(ctx):
    lon, lat = ctx.point("outlet")
    snap_m = float(ctx.params.get("snap_m") or 0)
    max_km2 = float(ctx.params.get("max_area_km2") or 25000)
    ctx.progress(5)

    snap_to = str(ctx.params.get("snap_to") or "nearest")
    dem, f, (sr, sc, moved), mask, cut_off, nearby = trace(ctx, lon, lat, snap_m, max_km2, snap_to)
    px_km2 = dem.grid.pixel_area_m2 / 1e6
    area_km2 = float(mask.sum()) * px_km2
    if mask.sum() < 4:
        raise AnalysisError("Almost no land drains to this point. Place it on a stream or valley floor, or increase the snapping distance.")
    acc = f.accumulation().data
    slon, slat = cell_lonlat(dem, sr, sc)
    ctx.progress(55)

    # Terrain -----------------------------------------------------------------------------------------
    z = dem.data
    zin = z[mask & np.isfinite(z)]
    slope = terrain.slope(dem, "degrees").data
    mean_slope = float(np.nanmean(slope[mask]))
    z_out = float(z[sr, sc])
    folder = ctx.scratch("hydro_profile")
    folder.mkdir(parents=True, exist_ok=True)
    wbt = whitebox.tools(folder, log=ctx.log)
    whitebox.call(wbt, "max_upslope_flowpath_length", str(f.filled), "flowpath.tif")
    fp = G.read(folder / "flowpath.tif").data
    length_m = float(fp[sr, sc]) if np.isfinite(fp[sr, sc]) else None
    tc_h = None
    if length_m and length_m > 0 and area_km2 <= KIRPICH_MAX_KM2:
        s = max((float(zin.max()) - z_out) / length_m, 1e-4)
        tc_h = 0.0195 * length_m ** 0.77 * s ** -0.385 / 60     # Kirpich (1940), minutes -> hours

    # Area of influence share ------------------------------------------------------------------------------
    inside = ctx.area_mask(dem)
    in_km2 = float((mask & inside).sum()) * px_km2

    # Streams in the catchment ----------------------------------------------------------------------------
    thr_km2 = 1.0 if area_km2 <= 2500 else float(f"{area_km2 / 2500:.0g}")
    net = hydro.streams(ctx, f, thr_km2 / px_km2, folder=ctx.scratch("hydro_streams"))
    values, lines_ll = hydro.read_lines(net.lines, dem.crs)
    polys = hydro.polygons(mask.astype(np.int32), dem.transform, {1})
    poly_utm = polys.get(1, shapely.Polygon())
    stream_geoms, stream_props, stream_km, max_order = [], [], 0.0, 0
    if len(lines_ll):
        from apps.analysis.ops.people import to_grid_coords
        lines_utm = to_grid_coords(lines_ll, dem.crs)
        hit = shapely.intersects(lines_utm, poly_utm)
        for g, v in zip(lines_utm[hit], np.array(values, dtype=object)[hit]):
            cut = shapely.intersection(g, poly_utm)
            km = cut.length / 1000
            if km <= 0:
                continue
            o = int(v or 1)
            stream_geoms.append(cut)
            stream_props.append({"order": o, "length_km": round(km, 2)})
            stream_km += km
            max_order = max(max_order, o)
    ctx.progress(65)

    # Not on a stream? Say so, and where the real streams are ---------------------------------------------
    drains_km2 = float(acc[sr, sc]) * px_km2
    warning = ""
    if drains_km2 < SNAP_STREAM_KM2:
        where = []
        if nearby.get("nearest"):
            d, km2, way = nearby["nearest"]
            where.append(f"the nearest stream draining {SNAP_STREAM_KM2:g} km² or more is {d:,.0f} m {way} (it drains {km2:,.1f} km²)")
        if nearby.get("largest") and nearby["largest"][1] >= SNAP_STREAM_KM2:
            d, km2, way = nearby["largest"]
            where.append(f"the biggest stream within {NEARBY_M / 1000:g} km passes {d:,.0f} m {way} (it drains about {km2:,.0f} km² there)")
        warning = (f"The outlet isn't on a stream: nothing within {snap_m:,.0f} m drains {SNAP_STREAM_KM2:g} km² or more, "
                   "so the catchment is only the slope around the point. "
                   + ("; ".join(where).capitalize() + ". " if where else "")
                   + "Place the outlet on the stream, or set Snap to: largest stream with a larger distance.")
        ctx.log(warning)

    # Outputs -------------------------------------------------------------------------------------------
    at_least = "at least " if cut_off else ""
    rows = ([{"measure": "Warning", "value": "Outlet not on a stream", "unit": "", "note": warning}] if warning else []) + [
        {"measure": "Catchment area", "value": round(area_km2, 2), "unit": "km²",
         "note": "cut off at the edge of the elevation clip: the real catchment is larger" if cut_off else ""},
        {"measure": "Inside the area of influence", "value": round(in_km2, 2), "unit": "km²",
         "note": f"{100 * in_km2 / area_km2:.0f}% of the catchment"},
        {"measure": "Outlet as picked", "value": f"{lon:.5f}, {lat:.5f}", "unit": "lon, lat", "note": ""},
        {"measure": "Outlet on the stream", "value": f"{slon:.5f}, {slat:.5f}", "unit": "lon, lat",
         "note": (f"moved {moved:,.0f} m ({'largest' if snap_to == 'largest' else 'nearest'} stream); "
                  if moved else "not moved; ") + f"drains {drains_km2:,.1f} km²"},
        {"measure": "Elevation at the outlet", "value": round(z_out), "unit": "m", "note": ""},
        {"measure": "Elevation (lowest / mean / highest)", "value": f"{zin.min():,.0f} / {zin.mean():,.0f} / {zin.max():,.0f}", "unit": "m", "note": ""},
        {"measure": "Mean slope", "value": round(mean_slope, 1), "unit": "°", "note": ""},
    ]
    if length_m:
        rows.append({"measure": "Longest flow path", "value": round(length_m / 1000, 1), "unit": "km", "note": "from the farthest point to the outlet"})
    if tc_h:
        rows.append({"measure": "Time of concentration (Kirpich)", "value": round(tc_h, 1), "unit": "hours",
                     "note": "Kirpich (1940), for small catchments: a rough first estimate for design-flood work"})
    rows.append({"measure": f"Streams (from {thr_km2:g} km² upstream)", "value": round(stream_km, 1), "unit": "km",
                 "note": f"drainage density {stream_km / area_km2:.2f} km/km²; highest Strahler order {max_order}" if max_order else ""})

    ll_poly = hydro.to_lonlat([poly_utm], dem.crs)
    write_geojson(ctx.path("catchment.geojson"), ll_poly, [{"area_km2": round(area_km2, 2)}])
    if stream_geoms:
        hydro.write_lines_geojson(ctx.path("streams.geojson"), hydro.to_lonlat(stream_geoms, dem.crs), stream_props)
    else:
        write_geojson(ctx.path("streams.geojson"), [], [])
    write_geojson(ctx.path("outlet.geojson"), [shapely.Point(lon, lat), shapely.Point(slon, slat)],
                  [{"point": "picked"}, {"point": "on the stream", "drains_km2": round(float(acc[sr, sc]) * px_km2, 1)}])

    ctx.add_metric("area_km2", "Catchment area", round(area_km2, 1 if area_km2 < 100 else 0), "km²")
    ctx.add_metric("in_area_share", "Inside the area of influence", round(100 * in_km2 / area_km2, 1), "%")
    ctx.add_metric("mean_slope", "Mean slope", round(mean_slope, 1), "°")
    ctx.add_table("profile", "Catchment profile", [
        {"key": "measure", "label": "Measure"}, {"key": "value", "label": "Value"}, {"key": "unit", "label": "Unit"},
        {"key": "note", "label": "Note"}], rows)
    ctx.add_vector("catchment", "Catchment", "catchment.geojson", {"color": "#4292C6", "opacity": 0.3, "outline": "#08306B", "shape": "polygon"})
    present = sorted({p["order"] for p in stream_props})
    ctx.add_vector("streams", "Streams in the catchment", "streams.geojson", {
        "property": "order", "color": ORDER_STYLE[1][0], "shape": "line",
        "classes": [{"value": o, "color": ORDER_STYLE.get(o, ORDER_STYLE[6])[0], "label": f"Order {o}",
                     "width": ORDER_STYLE.get(o, ORDER_STYLE[6])[1]} for o in present]})
    ctx.add_vector("outlet_point", "Outlet", "outlet.geojson", {
        "property": "point", "classes": [{"value": "picked", "color": "#C9A25B", "label": "As picked", "radius": 5},
                                         {"value": "on the stream", "color": "#08306B", "label": "On the stream", "radius": 7}]})

    parts = [f"{at_least}{area_km2:,.1f} km² drain to the outlet" if area_km2 < 100 else f"{at_least}{area_km2:,.0f} km² drain to the outlet",
             f"{100 * in_km2 / area_km2:.0f}% of it inside the area of influence", f"mean slope {mean_slope:.0f}°"]
    text = "; ".join(parts) + f". Copernicus DEM at {dem.grid.res:.0f} m, WhiteboxTools."
    if cut_off:
        text += f" The catchment reaches the largest clip traced ({max_km2:,.0f} km² limit): the real catchment is larger."
    text = text[0].upper() + text[1:]
    ctx.summary(f"{warning} {text}" if warning else text)
