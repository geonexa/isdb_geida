"""Aspect: the direction slopes face, by area, overall and per admin unit."""
from apps.analysis.ops import terrain

LABELS = {0: "Flat", **{k: label for k, (label, _, _) in enumerate(terrain.ASPECT_CLASSES, start=1)}}


def run(ctx):
    dem = ctx.raster("dem", buffer_m=terrain.DEM_BUFFER_M)
    ctx.progress(35)
    flat = float(ctx.params["flat_threshold"])
    classes = terrain.aspect_classes(terrain.aspect(dem, flat), terrain.slope(dem), flat)
    inside = ctx.area_mask(classes) & classes.valid
    rows = terrain.class_areas(classes, LABELS, inside)
    sloped = [r for r in rows if r["class"] != 0]
    main = max(sloped, key=lambda r: r["area_km2"]) if any(r["area_km2"] for r in sloped) else rows[0]
    flat_share = next(r["share"] for r in rows if r["class"] == 0)
    south = sum(r["share"] for r in rows if r["label"] in ("South", "South-east", "South-west"))
    ctx.progress(60)

    zone_rows = []
    for _, gid, name, mask in ctx.zone_masks(classes, int(ctx.params.get("zone_level") or 2)):
        zr = terrain.class_areas(classes, LABELS, mask & inside)
        total = sum(r["area_km2"] for r in zr)
        if total:
            top = max((r for r in zr if r["class"] != 0), key=lambda r: r["area_km2"])
            zone_rows.append({"unit": name, "main": top["label"] if top["area_km2"] else "Flat",
                              "flat_share": next(r["share"] for r in zr if r["class"] == 0), "area_km2": round(total, 1)})
    ctx.progress(80)

    ctx.add_metric("main_direction", "Slopes mostly face", main["label"], "")
    ctx.add_metric("flat_share", f"Flat (slope under {flat:g}°)", flat_share, "% of area")
    ctx.add_metric("south_facing_share", "Facing south, south-east or south-west", round(south, 1), "% of area")
    ctx.add_table("directions", "Area by direction faced", [
        {"key": "label", "label": "Faces"}, {"key": "area_km2", "label": "Area", "unit": "km²"},
        {"key": "share", "label": "Share", "unit": "%"}], rows)
    ctx.add_table("per_zone", "Aspect per administrative unit", [
        {"key": "unit", "label": "Unit"}, {"key": "main", "label": "Mostly faces"},
        {"key": "flat_share", "label": "Flat", "unit": "%"}, {"key": "area_km2", "label": "Area", "unit": "km²"}], zone_rows)
    ctx.add_raster("aspect", "Aspect", classes, legend="legend.yaml")
    ctx.summary(f"Slopes mostly face {main['label'].lower()} ({main['share']:.0f}% of the area); "
                f"{flat_share:.0f}% is flat and {south:.0f}% faces south, south-east or south-west.")
