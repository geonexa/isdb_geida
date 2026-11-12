"""Elevation profile: lowest, highest and mean elevation, area by elevation band, per admin unit."""
import numpy as np

from apps.analysis.core.errors import AnalysisError
from apps.analysis.ops import terrain

TERRAIN = ["#00A35C", "#7BD37A", "#F5FD97", "#C2B078", "#825F55", "#BFADA9", "#FFFFFF"]


def _nice_step(span, n):
    """The readable step (1, 2, 2.5 or 5 × a power of ten) nearest to span / n."""
    raw = span / n
    mag = 10 ** np.floor(np.log10(raw)) if raw > 0 else 1
    return float(min((s * mag for s in (1, 2, 2.5, 5, 10)), key=lambda v: abs(v - raw)))


def run(ctx):
    dem = ctx.raster("dem", buffer_m=terrain.DEM_BUFFER_M)  # same clip as the other terrain analyses (cached)
    ctx.progress(40)
    inside = ctx.area_mask(dem) & dem.valid
    vals = dem.data[inside]
    if not vals.size:
        raise AnalysisError("The elevation model has no values inside the area of influence.")
    px_km2 = dem.grid.pixel_area_m2 / 1e6
    lo, hi, mean = float(vals.min()), float(vals.max()), float(vals.mean())

    # Hypsometry: area in equal elevation bands (rounded to a readable step)
    step = _nice_step(max(hi - lo, 1.0), int(ctx.params["bands"]))
    start = np.floor(lo / step) * step
    edges = start + step * np.arange(int(np.floor((hi - start) / step)) + 2)  # always covers hi, even on flat land
    counts, _ = np.histogram(vals, bins=edges)
    total = counts.sum()
    band_rows = [{"band": f"{a:,.0f}–{b:,.0f} m", "area_km2": round(c * px_km2, 1), "share": round(100 * c / total, 1)}
                 for a, b, c in zip(edges[:-1], edges[1:], counts) if c]
    ctx.progress(65)

    zone_rows = []
    for _, gid, name, mask in ctx.zone_masks(dem, int(ctx.params.get("zone_level") or 2)):
        z = dem.data[mask & inside]
        if z.size:
            zone_rows.append({"unit": name, "min": round(float(z.min())), "mean": round(float(z.mean())),
                              "max": round(float(z.max())), "area_km2": round(z.size * px_km2, 1)})
    ctx.progress(80)

    ctx.add_metric("min_elevation", "Lowest elevation", round(lo), "m")
    ctx.add_metric("mean_elevation", "Mean elevation", round(mean), "m")
    ctx.add_metric("max_elevation", "Highest elevation", round(hi), "m")
    ctx.add_table("bands", "Area by elevation band", [
        {"key": "band", "label": "Elevation"}, {"key": "area_km2", "label": "Area", "unit": "km²"},
        {"key": "share", "label": "Share", "unit": "%"}], band_rows)
    ctx.add_table("per_zone", "Elevation per administrative unit", [
        {"key": "unit", "label": "Unit"}, {"key": "min", "label": "Lowest", "unit": "m"},
        {"key": "mean", "label": "Mean", "unit": "m"}, {"key": "max", "label": "Highest", "unit": "m"},
        {"key": "area_km2", "label": "Area", "unit": "km²"}], zone_rows)
    legend = {"type": "ramp", "palette": TERRAIN, "min": round(lo), "max": round(hi), "unit": "m"}
    ctx.add_raster("elevation", "Elevation", dem, legend=legend)
    main = max(band_rows, key=lambda r: r["share"])
    ctx.summary(f"Elevation ranges from {lo:,.0f} m to {hi:,.0f} m (mean {mean:,.0f} m); the largest share of the "
                f"area ({main['share']:.0f}%) lies at {main['band']}. Pixels of {dem.grid.res:.0f} m.")
