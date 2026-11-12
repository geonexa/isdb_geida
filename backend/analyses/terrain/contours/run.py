"""Contours from the elevation model inside the area, as a map layer and a GeoPackage."""
import numpy as np

from apps.analysis.core.errors import AnalysisError
from apps.analysis.ops import terrain

STYLE = {"shape": "line", "property": "index", "color": "#8C6D46", "width": 0.8,
         "classes": [{"value": 0, "color": "#A8865B", "label": "Contour", "width": 0.7},
                     {"value": 1, "color": "#5C3D1E", "label": "Index contour (every fifth)", "width": 1.6}]}


def run(ctx):
    dem = ctx.raster("dem", buffer_m=terrain.DEM_BUFFER_M)
    ctx.progress(30)
    size = {"none": 0, "light": 3, "strong": 5}[ctx.params["smoothing"]]
    if size:
        dem = terrain.smooth(dem, size)
    inside = ctx.area_mask(dem) & dem.valid
    vals = dem.data[inside]
    if not vals.size:
        raise AnalysisError("The elevation model has no values inside the area of influence.")
    lo, hi = float(vals.min()), float(vals.max())
    interval = float(ctx.params["interval"]) or terrain.nice_interval(lo, hi)
    if (hi - lo) / interval > 400:
        raise AnalysisError(f"An interval of {interval:g} m would draw more than 400 contour levels here. "
                            f"Choose at least {terrain.nice_interval(lo, hi, 400):g} m.")
    ctx.progress(45)

    clipped = dem.like(np.where(inside, dem.data, np.nan))  # lines stop at the area's border
    gpkg, geojson = ctx.path("contours.gpkg"), ctx.path("contours.geojson")
    lines, km = terrain.contours(clipped, interval, gpkg, geojson, simplify_m=dem.grid.res)
    if not lines:
        raise AnalysisError(f"No contour falls inside the area at {interval:g} m intervals "
                            f"(elevation {lo:,.0f}–{hi:,.0f} m). Choose a smaller interval.")
    ctx.progress(85)

    ctx.add_metric("interval", "Contour interval", interval, "m")
    ctx.add_metric("lines", "Contour lines", lines, "")
    ctx.add_metric("length_km", "Total length", round(km, 1), "km")
    ctx.add_vector("contours", f"Contours every {interval:g} m", geojson, STYLE)
    ctx.add_file("gpkg", "Contours (GeoPackage)", gpkg)
    ctx.summary(f"{lines:,} contour lines every {interval:g} m (index contours every {interval * 5:g} m) "
                f"between {lo:,.0f} m and {hi:,.0f} m, {km:,.0f} km in total.")
