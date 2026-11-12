"""Hillshade: shaded relief for maps and reports, with local relief per admin unit."""
from apps.analysis.ops import terrain


def run(ctx):
    dem = ctx.raster("dem", buffer_m=terrain.DEM_BUFFER_M)
    ctx.progress(35)
    az, alt, z = float(ctx.params["azimuth"]), float(ctx.params["altitude"]), float(ctx.params["z_factor"])
    shade = terrain.hillshade(dem, az, alt, z)
    inside = ctx.area_mask(dem) & dem.valid
    vals = dem.data[inside]
    relief = float(vals.max() - vals.min()) if vals.size else 0.0
    ctx.progress(60)

    zone_rows = []
    for _, gid, name, mask in ctx.zone_masks(dem, int(ctx.params.get("zone_level") or 2)):
        v = dem.data[mask & inside]
        if v.size:
            zone_rows.append({"unit": name, "lowest": round(float(v.min())), "highest": round(float(v.max())),
                              "relief": round(float(v.max() - v.min()))})
    ctx.progress(75)

    ctx.add_metric("relief", "Local relief (highest minus lowest)", round(relief), "m")
    ctx.add_table("per_zone", "Relief per administrative unit", [
        {"key": "unit", "label": "Unit"}, {"key": "lowest", "label": "Lowest", "unit": "m"},
        {"key": "highest", "label": "Highest", "unit": "m"}, {"key": "relief", "label": "Relief", "unit": "m"}], zone_rows)
    title = "Hillshade" + (f" (×{z:g} vertical)" if z != 1 else "")
    ctx.add_raster("hillshade", title, shade, legend="legend.yaml")
    ctx.summary(f"Shaded relief with the sun at {az:g}° from north, {alt:g}° above the horizon"
                f"{f', vertical exaggeration ×{z:g}' if z != 1 else ''}. The terrain rises {relief:,.0f} m "
                f"from its lowest to its highest point.")
