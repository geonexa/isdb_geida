"""Terrain: elevation bands and slope classes for the project area (DEM only)."""
import numpy as np

from apps.analysis.ops import raster
from apps.analysis.render import preview as render
from apps.analysis.core.errors import ModuleError

SLOPE_CLASSES = [  # (from, to, label, colour)
    (0, 2, "Flat", (237, 248, 233)), (2, 5, "Gentle", (186, 228, 179)), (5, 15, "Moderate", (116, 196, 118)),
    (15, 30, "Steep", (238, 150, 75)), (30, 90, "Very steep", (189, 0, 38)),
]
HYPSO = [(26, 150, 65), (166, 217, 106), (255, 255, 191), (253, 174, 97), (215, 25, 28), (140, 81, 10)]


def nice_bands(lo, hi, n=6):
    """n equal elevation bands with round edges covering [lo, hi]."""
    span = max(hi - lo, 1)
    step = next(s for s in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000) if s * n >= span)
    start = np.floor(lo / step) * step
    edges = [start + k * step for k in range(n + 1)]
    while edges[-1] < hi:
        edges.append(edges[-1] + step)
    return edges


def preview(ctx, name, title, classes, inside, transform, palette, legend):
    small, step = render.downsample_for_preview(classes)
    ins, _ = render.downsample_for_preview(inside)
    bounds = render.write_png(ctx.path(f"{name}.png"), render.colorize(small, palette, ins), transform * transform.scale(step, step))
    ctx.add_image(name, title, f"{name}.png", bounds, legend)


def run(ctx):
    thr = float(ctx.params["slope_threshold_deg"])
    ctx.progress(5)
    dem, t, nd = raster.read_tif(ctx.dataset("dem", ctx.bbox(buffer_m=200)))
    slope = raster.slope_degrees(dem, t, nd)
    valid = np.isfinite(slope) & ((dem != nd) if nd is not None else True)
    inside = raster.area_mask(ctx.area_geojson, t, dem.shape) & valid
    if not inside.any():
        raise ModuleError("The elevation data doesn't cover the project area.")
    pa = raster.pixel_area_km2(t, dem.shape)
    elev = dem.astype("float64")
    a_in, s_in, e_in = pa[inside], slope[inside], elev[inside]
    total = float(a_in.sum())
    ctx.log(f"{inside.sum():,} DEM cells inside the area ({abs(t.a) * 111_320:.0f} m)")
    ctx.progress(35)

    mean_slope = float(np.average(s_in, weights=a_in))
    steep = float(a_in[s_in > thr].sum() / total)
    flat = float(a_in[s_in < 5].sum() / total)
    e_mean = float(np.average(e_in, weights=a_in))
    e_lo, e_hi = float(np.percentile(e_in, 1)), float(np.percentile(e_in, 99))

    slope_rows, slope_cls = [], np.zeros(dem.shape, dtype=np.int16)
    for k, (lo, hi, name, _) in enumerate(SLOPE_CLASSES, 1):
        m = (slope >= lo) & (slope < hi)
        slope_cls[m] = k
        km2 = float(pa[m & inside].sum())
        slope_rows.append({"class": name, "range": f"{lo}–{hi}°" if hi < 90 else f"> {lo}°",
                           "km2": round(km2, 1), "share": round(km2 / total * 100, 1)})

    edges = nice_bands(e_lo, e_hi, n=len(HYPSO))
    nb = len(edges) - 1
    colours = [HYPSO[min(k * len(HYPSO) // nb, len(HYPSO) - 1)] for k in range(nb)]
    elev_cls = (np.clip(np.digitize(elev, edges[1:-1]), 0, nb - 1) + 1).astype(np.int16)
    band_rows = []
    for k in range(nb):
        km2 = float(pa[(elev_cls == k + 1) & inside].sum())
        band_rows.append({"band": f"{edges[k]:,.0f}–{edges[k + 1]:,.0f} m", "km2": round(km2, 1), "share": round(km2 / total * 100, 1)})
    ctx.progress(60)

    zones = ctx.zones(int(ctx.params.get("zone_level") or 2))
    zr = raster.zone_raster([(g, i) for i, _, _, g in zones], t, dem.shape)
    rows = []
    for i, gid, name, _ in zones:
        m = (zr == i) & inside
        if not m.any():
            continue
        w = pa[m]
        rows.append({"zone": name, "gid": gid, "area_km2": round(float(w.sum()), 1),
                     "elev_min": round(float(elev[m].min())), "elev_mean": round(float(np.average(elev[m], weights=w))),
                     "elev_max": round(float(elev[m].max())),
                     "mean_slope": round(float(np.average(slope[m], weights=w)), 1),
                     "steep_pct": round(float(w[slope[m] > thr].sum() / w.sum() * 100), 1)})
    rows.sort(key=lambda r: -r["steep_pct"])
    ctx.progress(80)

    ctx.add_metric("elev_range", "Elevation (min – max)", f"{e_in.min():,.0f} – {e_in.max():,.0f}", "m")
    ctx.add_metric("elev_mean", "Mean elevation", round(e_mean), "m")
    ctx.add_metric("mean_slope", "Mean slope", round(mean_slope, 1), "°")
    ctx.add_metric("steep_share", f"Steeper than {thr:g}°", round(steep * 100, 1), "%")
    ctx.add_table("per_zone", "By administrative unit", [
        {"key": "zone", "label": "Unit"}, {"key": "area_km2", "label": "Area", "unit": "km²"},
        {"key": "elev_min", "label": "Min elev.", "unit": "m"}, {"key": "elev_mean", "label": "Mean elev.", "unit": "m"},
        {"key": "elev_max", "label": "Max elev.", "unit": "m"}, {"key": "mean_slope", "label": "Mean slope", "unit": "°"},
        {"key": "steep_pct", "label": f"> {thr:g}°", "unit": "%"}], rows)
    ctx.add_table("slope_classes", "Slope classes", [
        {"key": "class", "label": "Class"}, {"key": "range", "label": "Slope"},
        {"key": "km2", "label": "Area", "unit": "km²"}, {"key": "share", "label": "Share", "unit": "%"}], slope_rows)
    ctx.add_table("elevation_bands", "Elevation bands", [
        {"key": "band", "label": "Elevation"}, {"key": "km2", "label": "Area", "unit": "km²"},
        {"key": "share", "label": "Share", "unit": "%"}], band_rows)

    preview(ctx, "elevation", "Elevation", elev_cls, inside, t, {k + 1: c for k, c in enumerate(colours)},
            [{"label": r["band"], "color": render.hex_color(c)} for r, c in zip(band_rows, colours)])
    preview(ctx, "slope", "Slope classes", slope_cls, inside, t, {k: c for k, (_, _, _, c) in enumerate(SLOPE_CLASSES, 1)},
            [{"label": f"{n} ({r})", "color": render.hex_color(c)} for (_, _, n, c), r in zip(SLOPE_CLASSES, (x["range"] for x in slope_rows))])
    preview(ctx, "steep", f"Steeper than {thr:g}°", np.where(slope > thr, 1, 0).astype(np.int16), inside, t,
            {1: (189, 0, 38)}, [{"label": f"> {thr:g}°", "color": "#bd0026"}])
    out_tif = raster.write_tif(ctx.path("slope_deg.tif"), np.where(valid, slope, -9999).astype("float32"), t, -9999)
    ctx.add_file("slope_tif", "Slope (GeoTIFF, degrees)", out_tif)

    worst = ", ".join(f"{r['zone']} ({r['steep_pct']:.0f}%)" for r in rows[:3] if r["steep_pct"] > 0)
    ctx.summary(
        f"Elevation in the {ctx.area_km2:,.0f} km² area ranges from {e_in.min():,.0f} to {e_in.max():,.0f} m "
        f"(mean {e_mean:,.0f} m). The mean slope is {mean_slope:.1f}°; {flat * 100:.0f}% of the land is flat or gently "
        f"sloping (< 5°) and {steep * 100:.0f}% is steeper than {thr:g}°"
        f"{f', mostly in {worst}' if worst else ''}. Source: Copernicus DEM GLO-30.")
    ctx.progress(100)
