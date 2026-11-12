"""Vegetation indices from a cloud-free Sentinel-2 composite: mean, classes, per admin unit and land cover class."""
import calendar
import datetime as dt

import numpy as np

from apps.analysis.core.errors import AnalysisError
from apps.analysis.data import sentinel2 as S2
from apps.analysis.data.base import DatasetUnavailable
from apps.analysis.ops import landcover as L

SEASONS = {"year": (1, 12), "jan_mar": (1, 3), "apr_jun": (4, 6), "jul_sep": (7, 9), "oct_dec": (10, 12),
           "jan_jun": (1, 6), "jul_dec": (7, 12)}
# Class breaks (upper bounds) and labels per index; the last class has no upper bound.
GREEN = ["Water, built-up or bare", "Sparse vegetation", "Low vegetation", "Moderate vegetation", "Dense vegetation"]
CLASSES = {
    "ndvi": ([0.1, 0.2, 0.4, 0.6], GREEN),
    "evi": ([0.1, 0.2, 0.3, 0.45], GREEN),
    "savi": ([0.1, 0.2, 0.3, 0.45], GREEN),
    "ndmi": ([-0.2, 0.0, 0.2, 0.4], ["Very dry", "Dry", "Moderate moisture", "Moist", "Very moist"]),
}
COLORS = ["#A50026", "#F46D43", "#FEE08B", "#A6D96A", "#1A9850"]
NDMI_COLORS = ["#8C510A", "#D8B365", "#F6E8C3", "#5AB4AC", "#01665E"]
RAMP = {"ndvi": (0, 0.9), "evi": (0, 0.7), "savi": (0, 0.7), "ndmi": (-0.4, 0.6)}
RDYLGN = ["#A50026", "#E95739", "#FDBE6E", "#FEFEBD", "#B7E075", "#4EB15D", "#006837"]
BRBG = ["#8C510A", "#D8B365", "#F6E8C3", "#F5F5F5", "#C7EAE5", "#5AB4AC", "#01665E"]


def period(year, season):
    m0, m1 = SEASONS[season]
    start = dt.date(year, m0, 1)
    end = min(dt.date(year, m1, calendar.monthrange(year, m1)[1]), dt.date.today())
    if start > end:
        raise AnalysisError(f"The period starts in the future ({start:%B %Y}). Choose an earlier year or season.")
    return start, end


def run(ctx):
    index = ctx.params.get("index") or "ndvi"
    meta = S2.INDICES[index]
    start, end = period(int(ctx.params["year"]), ctx.params.get("season") or "year")
    grid = S2.area_grid(ctx.area_in(), f"EPSG:{ctx.epsg}")
    ctx.set_grid(grid)
    if grid.res > 10:
        ctx.log(f"The area is large: composite at {grid.res:.0f} m instead of 10 m")
    items = S2.search(ctx.bbox(), start.isoformat(), end.isoformat(), float(ctx.params["max_cloud"]),
                      int(ctx.params["scenes_per_tile"]))
    ctx.log(f"Sentinel-2: {len(items)} scene(s) from {start} to {end} below {ctx.params['max_cloud']:g}% cloud")
    ctx.progress(15)

    parts = [index, start.isoformat(), end.isoformat(), sorted(i["id"] for i in items), "s2-1"]
    held = {}

    def compute():
        med, cnt = S2.composite(items, grid, index, log=ctx.log)
        held["count"] = cnt
        return med

    try:
        idx = ctx.cached(f"s2_{index}", parts, compute)
        cnt = ctx.cached("s2_count", parts, lambda: held.get("count") or S2.composite(items, grid, index, log=ctx.log)[1])
    except DatasetUnavailable as exc:
        raise AnalysisError(str(exc)) from None
    ctx.record_dataset("sentinel2_l2a", {"id": "sentinel2_l2a", "title": "Sentinel-2 L2A (ESA Copernicus)", "kind": "raster",
                                         "resolution": f"{grid.res:.0f} m", "version": "collection 1",
                                         "reference_date": f"{start} to {end}", "citation": S2.CITATION,
                                         "licence": "Copernicus open data", "source": "Earth Search (AWS)",
                                         "scenes": len(items)})
    ctx.progress(70)

    inside = ctx.area_mask(grid)
    ok = inside & idx.valid
    if not ok.any():
        raise AnalysisError("No clear Sentinel-2 observation inside the area for this period. "
                            "Choose a longer period or a higher cloud limit.")
    vals = idx.data[ok]
    px_km2 = grid.pixel_area_m2 / 1e6
    breaks, labels = CLASSES[index]
    k = np.digitize(idx.data, breaks) + 1          # classes 1..5
    class_rows = []
    for c, label in enumerate(labels, start=1):
        n = int((ok & (k == c)).sum())
        lo = breaks[c - 2] if c > 1 else None
        hi = breaks[c - 1] if c <= len(breaks) else None
        rng = f"under {hi:g}" if lo is None else (f"{lo:g} and above" if hi is None else f"{lo:g}–{hi:g}")
        class_rows.append({"label": f"{label} ({rng})", "area_km2": round(n * px_km2, 2), "share": round(100 * n / vals.size, 1)})
    high = sum(r["share"] for r in class_rows[-2:])

    zone_rows = []
    for _, _, name, m in ctx.zone_masks(grid, int(ctx.params.get("zone_level") or 2)):
        z = idx.data[ok & m]
        if z.size:
            zone_rows.append({"unit": name, "mean": round(float(z.mean()), 3), "median": round(float(np.median(z)), 3),
                              "high": round(100 * float((z >= breaks[-2]).mean()), 1), "area_km2": round(z.size * px_km2, 1)})

    lc_rows = None
    try:
        lc = ctx.raster("landcover")
        codes = L.codes_of(lc, L.WORLDCOVER)
        lc_rows = []
        for code, (label, _) in L.WORLDCOVER.items():
            z = idx.data[ok & (codes == code)]
            if z.size * px_km2 >= 0.01:
                lc_rows.append({"label": label, "mean": round(float(z.mean()), 3), "area_km2": round(z.size * px_km2, 2)})
        lc_rows.sort(key=lambda r: -r["area_km2"])
    except (AnalysisError, DatasetUnavailable) as exc:
        ctx.log(f"Land cover not available, no per-class table: {exc}")
    ctx.progress(85)

    lab = meta["label"]
    ctx.add_metric("mean_index", f"Mean {lab}", round(float(vals.mean()), 3), "")
    ctx.add_metric("high_share", f"{labels[-2]} or {labels[-1].lower()}", round(high, 1), "% of area")
    ctx.add_metric("scenes", "Sentinel-2 scenes used", len(items), "")
    ctx.add_table("classes", f"{lab} classes, {start:%b %Y}–{end:%b %Y}", [
        {"key": "label", "label": "Class"}, {"key": "area_km2", "label": "Area", "unit": "km²"},
        {"key": "share", "label": "Share", "unit": "%"}], class_rows)
    ctx.add_table("per_zone", f"{lab} per administrative unit", [
        {"key": "unit", "label": "Unit"}, {"key": "mean", "label": "Mean"}, {"key": "median", "label": "Median"},
        {"key": "high", "label": f"{labels[-2]} or more", "unit": "%"}, {"key": "area_km2", "label": "Area", "unit": "km²"}],
        zone_rows)
    if lc_rows is not None:
        ctx.add_table("by_landcover", f"{lab} by land cover class (ESA WorldCover 2021)", [
            {"key": "label", "label": "Land cover"}, {"key": "mean", "label": f"Mean {lab}"},
            {"key": "area_km2", "label": "Area", "unit": "km²"}], lc_rows)
    ctx.add_table("scene_list", "Sentinel-2 scenes", [
        {"key": "date", "label": "Date"}, {"key": "tile", "label": "Tile"}, {"key": "cloud", "label": "Cloud", "unit": "%"}],
        [{"date": i["date"], "tile": i["tile"].replace("MGRS-", ""), "cloud": round(float(i["cloud"]), 1)} for i in items])
    lo, hi = RAMP[index]
    ctx.add_raster("index", f"{lab}, {start:%b %Y}–{end:%b %Y}", idx,
                   legend={"type": "ramp", "palette": BRBG if index == "ndmi" else RDYLGN, "min": lo, "max": hi, "unit": lab,
                           "open_max": True})
    ctx.add_raster("observations", "Clear observations per pixel", cnt,
                   legend={"type": "ramp", "palette": ["#F7FBFF", "#C6DBEF", "#6BAED6", "#2171B5", "#08306B"],
                           "min": 0, "max": max(int(np.nanmax(cnt.data)) if np.isfinite(cnt.data).any() else 1, 1),
                           "unit": "scenes"})
    ctx.summary(f"Mean {lab} {vals.mean():.2f} from {len(items)} Sentinel-2 scene(s), {start:%d %b %Y} to {end:%d %b %Y}; "
                f"{high:.0f}% of the area is {labels[-2].lower()} or {labels[-1].lower()}. Pixels of {grid.res:.0f} m.")
