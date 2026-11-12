"""Slope and slope classes from the elevation model, with the steep share per admin unit."""
import numpy as np

from apps.analysis.ops import terrain

# (upper bound in degrees, label); the last class has no upper bound
CLASSES = [(2, "Flat (0–2°)"), (5, "Gentle (2–5°)"), (10, "Moderate (5–10°)"), (15, "Strong (10–15°)"),
           (30, "Steep (15–30°)"), (None, "Very steep (30° and more)")]


def run(ctx):
    dem = ctx.raster("dem", buffer_m=terrain.DEM_BUFFER_M)
    ctx.progress(35)
    deg = terrain.slope(dem, "degrees")
    inside = ctx.area_mask(deg) & deg.valid
    vals = deg.data[inside]
    px_km2 = deg.grid.pixel_area_m2 / 1e6
    thr = float(ctx.params["steep_threshold"])
    steep_share = 100 * float((vals >= thr).mean()) if vals.size else 0.0
    ctx.progress(55)

    classes = terrain.classify(deg, [b for b, _ in CLASSES if b is not None])
    class_rows = terrain.class_areas(classes, {k: label for k, (_, label) in enumerate(CLASSES, start=1)}, inside)

    zone_rows = []
    for _, gid, name, mask in ctx.zone_masks(deg, int(ctx.params.get("zone_level") or 2)):
        z = deg.data[mask & inside]
        if z.size:
            zone_rows.append({"unit": name, "mean": round(float(z.mean()), 1), "max": round(float(z.max()), 1),
                              "steep_share": round(100 * float((z >= thr).mean()), 1),
                              "area_km2": round(z.size * px_km2, 1)})
    ctx.progress(75)

    pct = ctx.params["units"] == "percent"
    unit = "%" if pct else "°"
    shown = terrain.slope(dem, "percent") if pct else deg
    mean = float(shown.data[inside].mean())
    ctx.add_metric("mean_slope", "Mean slope", round(mean, 1), unit)
    ctx.add_metric("steep_share", f"Steeper than {thr:g}°", round(steep_share, 1), "% of area")
    ctx.add_table("classes", "Area by slope class", [
        {"key": "label", "label": "Slope class"}, {"key": "area_km2", "label": "Area", "unit": "km²"},
        {"key": "share", "label": "Share", "unit": "%"}], class_rows)
    ctx.add_table("per_zone", "Slope per administrative unit", [
        {"key": "unit", "label": "Unit"}, {"key": "mean", "label": "Mean", "unit": "°"},
        {"key": "max", "label": "Highest", "unit": "°"}, {"key": "steep_share", "label": f"Steeper than {thr:g}°", "unit": "%"},
        {"key": "area_km2", "label": "Area", "unit": "km²"}], zone_rows)
    if pct:
        legend = {"type": "ramp", "palette": ["#FFFFCC", "#FEE692", "#FEBF5A", "#FD8D3C", "#F33C25", "#CA0922", "#800026"],
                  "min": 0, "max": 60, "unit": "%", "open_max": True}
        ctx.add_raster("slope", "Slope (%)", shown, legend=legend)
    else:
        ctx.add_raster("slope", "Slope", deg, legend="legend.yaml")
    main = max(class_rows, key=lambda r: r["share"])
    ctx.summary(f"Mean slope {mean:.1f}{unit}; {steep_share:.0f}% of the area is steeper than {thr:g}°. "
                f"Most of the land is {main['label'].split(' (')[0].lower()} ({main['share']:.0f}%). "
                f"Pixels of {deg.grid.res:.0f} m.")
