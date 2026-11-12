"""Land cover composition: area and share of each class, per admin unit, from WorldCover or the Esri yearly map."""
from apps.analysis.core.errors import AnalysisError
from apps.analysis.ops import landcover as L

WORLDCOVER_YEARS = (2020, 2021)


def run(ctx):
    ds = ctx.params.get("landcover_dataset") or "landcover"
    year = int(ctx.params.get("year") or 2021)
    if ds == "landcover" and year not in WORLDCOVER_YEARS:
        raise AnalysisError(f"ESA WorldCover exists for 2020 and 2021 only. Choose one of them, "
                            f"or the Esri / Impact Observatory map for {year}.")
    classes = L.PRODUCTS[ds]
    r = ctx.raster("landcover", year=year)
    ctx.progress(50)
    codes = L.codes_of(r, classes)
    inside = ctx.area_mask(r)
    px_km2 = r.grid.pixel_area_m2 / 1e6
    rows = L.class_rows(codes, classes, inside, px_km2)
    if not rows:
        raise AnalysisError("The land cover map has no classified pixels inside the area of influence.")
    share = {row["code"]: row["share"] for row in rows}
    crop, trees, built = (share.get(k[ds], 0.0) for k in (L.CROPLAND, L.TREES, L.BUILT))

    show = {"cropland": L.CROPLAND[ds], "trees": L.TREES[ds], "built": L.BUILT[ds]}
    zones = L.zone_rows(codes, classes, ctx.zone_masks(r, int(ctx.params.get("zone_level") or 2)), inside, px_km2, show)
    ctx.progress(75)

    name = "ESA WorldCover" if ds == "landcover" else "Esri / Impact Observatory"
    ctx.add_metric("cropland_share", "Cropland", crop, "% of area")
    ctx.add_metric("tree_share", "Trees", trees, "% of area")
    ctx.add_metric("built_share", "Built-up", built, "% of area")
    ctx.add_table("classes", f"Land cover {year} ({name})", [
        {"key": "label", "label": "Class"}, {"key": "area_km2", "label": "Area", "unit": "km²"},
        {"key": "share", "label": "Share", "unit": "%"}], [{k: v for k, v in row.items() if k != "code"} for row in rows])
    ctx.add_table("per_zone", "Land cover per administrative unit", [
        {"key": "unit", "label": "Unit"}, {"key": "area_km2", "label": "Area", "unit": "km²"},
        {"key": "main", "label": "Main class"}, {"key": "cropland", "label": "Cropland", "unit": "%"},
        {"key": "trees", "label": "Trees", "unit": "%"}, {"key": "built", "label": "Built-up", "unit": "%"}], zones)
    present = {row["code"] for row in rows}
    ctx.add_raster("land_cover", f"Land cover {year}", L.as_raster(r, codes), legend=L.legend(classes, present))
    top = rows[0]
    ctx.summary(f"{top['label']} covers most of the area ({top['share']:.0f}%). Cropland {crop:.0f}%, trees {trees:.0f}%, "
                f"built-up {built:.1f}% ({name} {year}, {r.grid.res:.0f} m pixels).")
