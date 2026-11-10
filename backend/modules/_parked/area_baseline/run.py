"""Area baseline: terrain, land cover and population summary for the project area."""
import numpy as np

from apps.analysis import raster
from apps.analysis.datasets.registry import WorldCover

SLOPE_CLASSES = [(0, 5, (229, 245, 224)), (5, 15, (161, 217, 155)), (15, 30, (49, 163, 84)), (30, 90, (0, 90, 50))]


def run(ctx):
    thr = float(ctx.params["slope_threshold_deg"])
    bbox = ctx.bbox(buffer_m=200)

    # Terrain ---------------------------------------------------------------------------
    ctx.progress(5)
    dem, t_dem, nd_dem = raster.read_tif(ctx.dataset("dem", bbox))
    slope = raster.slope_degrees(dem, t_dem, nd_dem)
    inside = raster.area_mask(ctx.area_geojson, t_dem, dem.shape) & np.isfinite(slope)
    if not inside.any():
        from apps.analysis.runner import ModuleError
        raise ModuleError("The elevation data doesn't cover the project area.")
    pa = raster.pixel_area_km2(t_dem, dem.shape)
    s_in, a_in = slope[inside], pa[inside]
    mean_slope = float(np.average(s_in, weights=a_in))
    steep_share = float(a_in[s_in > thr].sum() / a_in.sum())
    elev = dem[inside].astype(float)
    ctx.log(f"Mean slope {mean_slope:.1f}°, {steep_share * 100:.0f}% steeper than {thr:g}°")
    ctx.progress(30)

    # Land cover ------------------------------------------------------------------------
    lc, t_lc, _ = raster.read_tif(ctx.dataset("landcover", bbox))
    lc_in = raster.area_mask(ctx.area_geojson, t_lc, lc.shape)
    lc_pa = raster.pixel_area_km2(t_lc, lc.shape)
    total = lc_pa[lc_in].sum() or 1.0
    lc_rows = []
    for code, name in WorldCover.CLASSES.items():
        km2 = float(lc_pa[lc_in & (lc == code)].sum())
        if km2 > 0:
            lc_rows.append({"class": name, "km2": round(km2 * ctx.area_km2 / total, 2), "share": round(km2 / total * 100, 1)})
    lc_rows.sort(key=lambda r: -r["km2"])
    ctx.progress(55)

    # Population ------------------------------------------------------------------------
    pop, t_pop, nd_pop = raster.read_tif(ctx.dataset("population", bbox))
    pop = np.where((pop == nd_pop) | ~np.isfinite(pop) | (pop < 0), 0, pop) if nd_pop is not None else np.nan_to_num(pop)
    pop_in = raster.area_mask(ctx.area_geojson, t_pop, pop.shape)
    pop_total = float(pop[pop_in].sum())
    ctx.progress(70)

    # Per zone ----------------------------------------------------------------------------
    zones = ctx.zones(int(ctx.params.get("zone_level") or 2))
    z_dem = raster.zone_raster([(g, i) for i, _, _, g in zones], t_dem, dem.shape)
    z_pop = raster.zone_raster([(g, i) for i, _, _, g in zones], t_pop, pop.shape)
    z_lc = raster.zone_raster([(g, i) for i, _, _, g in zones], t_lc, lc.shape)
    rows = []
    for i, gid, name, _ in zones:
        m = (z_dem == i) & np.isfinite(slope)
        if not m.any():
            continue
        w = pa[m]
        lc_z = lc[(z_lc == i)]
        dominant = WorldCover.CLASSES.get(int(np.bincount(lc_z[lc_z > 0]).argmax()), "") if (lc_z > 0).any() else ""
        rows.append({
            "zone": name, "gid": gid, "area_km2": round(float(w.sum()), 1),
            "mean_slope": round(float(np.average(slope[m], weights=w)), 1),
            "steep_pct": round(float(w[slope[m] > thr].sum() / w.sum() * 100), 1),
            "elev_mean": round(float(dem[m].mean()), 0),
            "population": round(float(pop[z_pop == i].sum())),
            "landcover": dominant,
        })
    ctx.progress(85)

    # Outputs ------------------------------------------------------------------------------
    ctx.add_metric("mean_slope", "Mean slope", round(mean_slope, 1), "°")
    ctx.add_metric("steep_share", f"Steeper than {thr:g}°", round(steep_share * 100, 1), "%")
    ctx.add_metric("elevation", "Elevation (min – max)", f"{elev.min():.0f} – {elev.max():.0f}", "m")
    ctx.add_metric("population", "Population (2020)", round(pop_total), "people")
    ctx.add_table("per_zone", "By administrative unit", [
        {"key": "zone", "label": "Unit"}, {"key": "area_km2", "label": "Area", "unit": "km²"},
        {"key": "mean_slope", "label": "Mean slope", "unit": "°"},
        {"key": "steep_pct", "label": f"> {thr:g}°", "unit": "%"},
        {"key": "elev_mean", "label": "Mean elevation", "unit": "m"},
        {"key": "population", "label": "Population"}, {"key": "landcover", "label": "Main land cover"},
    ], rows)
    ctx.add_table("landcover", "Land cover (ESA WorldCover 2021)", [
        {"key": "class", "label": "Class"}, {"key": "km2", "label": "Area", "unit": "km²"},
        {"key": "share", "label": "Share", "unit": "%"}], lc_rows)

    classes = np.zeros(slope.shape, dtype=np.int16)
    for k, (lo, hi, _) in enumerate(SLOPE_CLASSES, start=1):
        classes[(slope >= lo) & (slope < hi)] = k
    small, step = raster.downsample_for_preview(classes)
    ins, _ = raster.downsample_for_preview(inside)
    t_small = t_dem * t_dem.scale(step, step)
    bounds = raster.write_png(ctx.path("slope.png"), raster.colorize(small, {k: c for k, (_, _, c) in enumerate(SLOPE_CLASSES, 1)}, ins), t_small)
    ctx.add_image("slope", "Slope", "slope.png", bounds,
                  [{"label": f"{lo}–{hi}°" if hi < 90 else f"> {lo}°", "color": "#%02x%02x%02x" % c} for lo, hi, c in SLOPE_CLASSES])
    lc_small, step = raster.downsample_for_preview(lc)
    lc_ins, _ = raster.downsample_for_preview(lc_in)
    bounds = raster.write_png(ctx.path("landcover.png"), raster.colorize(lc_small, WorldCover.COLORS, lc_ins), t_lc * t_lc.scale(step, step))
    ctx.add_image("landcover_map", "Land cover", "landcover.png", bounds,
                  [{"label": r["class"], "color": "#%02x%02x%02x" % WorldCover.COLORS[c]}
                   for c, n in WorldCover.CLASSES.items() for r in lc_rows if r["class"] == n])

    top = ", ".join(f"{r['class'].lower()} {r['share']:.0f}%" for r in lc_rows[:3])
    ctx.summary(
        f"The {ctx.area_km2:,.0f} km² area of influence has a mean slope of {mean_slope:.1f}°, with "
        f"{steep_share * 100:.0f}% of the land steeper than {thr:g}°; elevation ranges from "
        f"{elev.min():.0f} to {elev.max():.0f} m. Land cover is mainly {top}. About {pop_total:,.0f} people "
        f"lived in the area in 2020 (WorldPop). Sources: Copernicus DEM GLO-30, ESA WorldCover 2021, WorldPop 2020.")
    ctx.progress(100)
