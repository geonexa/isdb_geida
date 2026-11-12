"""Stream network and Strahler order from the Copernicus DEM (WhiteboxTools), km per order and drainage density per admin unit."""
import numpy as np
import shapely

from apps.analysis.core.errors import AnalysisError
from apps.analysis.data.base import DatasetUnavailable
from apps.analysis.ops import hydro, vector

# Strahler order -> (colour, line width); higher orders are thicker and darker
ORDER_STYLE = {1: ("#9ECAE1", 0.8), 2: ("#6BAED6", 1.2), 3: ("#4292C6", 1.8), 4: ("#2171B5", 2.4), 5: ("#08519C", 3.0),
               6: ("#08306B", 3.6)}


def style(order):
    return ORDER_STYLE.get(order, ORDER_STYLE[6])


def run(ctx):
    thr_km2 = float(ctx.params["threshold_km2"])
    dem = ctx.raster("dem", buffer_m=hydro.MARGIN_M)
    ctx.progress(20)
    flow = hydro.flow(ctx, dem)
    ctx.progress(45)
    cells = thr_km2 * 1e6 / dem.grid.pixel_area_m2
    net = hydro.streams(ctx, flow, cells)
    ctx.progress(60)
    values, lines_ll = hydro.read_lines(net.lines, dem.crs)
    if not len(lines_ll):
        raise AnalysisError(f"No stream drains {thr_km2:g} km² or more inside the area. Lower the threshold.")
    orders = np.array([int(v or 1) for v in values])
    ctx.progress(70)

    # Clip to the area (metric frame) and measure ----------------------------------------
    zones = ctx.vzones(int(ctx.params.get("zone_level") or 2))
    geoms_m = ctx.frame.to_m(lines_ll)
    idx, cut = vector.clip(geoms_m, zones.union)
    if not len(idx):
        raise AnalysisError("The derived streams don't cross the area of influence. Lower the threshold.")
    o_in = orders[idx]
    km = shapely.length(cut) / 1000
    area_km2 = float(zones.area_km2.sum())
    total = float(km.sum())
    by_order = []
    for o in sorted(set(o_in.tolist())):
        sel = o_in == o
        by_order.append({"order": int(o), "km": round(float(km[sel].sum()), 1), "share": round(100 * float(km[sel].sum()) / total, 1),
                         "segments": int(sel.sum())})
    measured = zones.measure(cut, classes=o_in.tolist())
    per_zone = []
    for i, gid, name, a in zones.rows():
        d = measured.get(int(i), {})
        z_km = sum(d.values())
        per_zone.append({"unit": name, "area_km2": round(a, 1), "km": round(z_km, 1), "density": round(z_km / a, 3) if a else 0,
                         "max_order": max(d) if d else None})
    per_zone.sort(key=lambda r: -r["km"])

    # OSM rivers and streams in the area, for comparison --------------------------------
    osm_km = None
    try:
        ww = ctx.try_features("waterways", ctx.bbox())
    except DatasetUnavailable as exc:
        ww = None
        ctx.log(f"OSM waterways not available: {exc}")
    if ww is not None:
        _, ww_cut = vector.clip(ww.geoms, zones.union)
        osm_km = float(shapely.length(ww_cut).sum() / 1000) if len(ww_cut) else 0.0
    ctx.progress(85)

    # Map ------------------------------------------------------------------------------
    props = [{"order": int(o), "length_km": round(float(k), 2)} for o, k in zip(o_in, km)]
    hydro.write_lines_geojson(ctx.path("streams.geojson"), ctx.frame.to_deg(cut), props)
    present = sorted(set(o_in.tolist()))
    ctx.add_metric("stream_km", f"Streams (from {thr_km2:g} km² upstream)", round(total, 1), "km")
    ctx.add_metric("drainage_density", "Drainage density", round(total / area_km2, 3) if area_km2 else 0, "km per km²")
    ctx.add_metric("max_order", "Highest Strahler order", int(max(present)), "")
    if osm_km is not None:
        ctx.add_metric("osm_km", "Rivers and streams in OpenStreetMap", round(osm_km, 1), "km")
    ctx.add_table("by_order", "Streams by Strahler order", [
        {"key": "order", "label": "Order"}, {"key": "km", "label": "Length", "unit": "km"}, {"key": "share", "label": "Share", "unit": "%"},
        {"key": "segments", "label": "Segments"}], by_order,
        note="Order 1: headwater streams; two streams of the same order join into the next order (Strahler).")
    ctx.add_table("per_zone", "Streams per administrative unit", [
        {"key": "unit", "label": "Unit"}, {"key": "area_km2", "label": "Area", "unit": "km²"}, {"key": "km", "label": "Streams", "unit": "km"},
        {"key": "density", "label": "Drainage density", "unit": "km/km²"}, {"key": "max_order", "label": "Highest order"}], per_zone)
    ctx.add_vector("streams", "Streams by Strahler order", "streams.geojson", {
        "property": "order", "color": ORDER_STYLE[1][0],
        "classes": [{"value": o, "color": style(o)[0], "label": f"Order {o}", "width": style(o)[1]} for o in present]})
    ctx.summary(f"{total:,.0f} km of streams drain {thr_km2:g} km² or more inside the area (drainage density "
                f"{total / area_km2:.2f} km/km²), up to Strahler order {max(present)}"
                + (f"; OpenStreetMap maps {osm_km:,.0f} km of rivers and streams" if osm_km is not None else "")
                + ". Derived from the Copernicus 30 m DEM with WhiteboxTools.")
