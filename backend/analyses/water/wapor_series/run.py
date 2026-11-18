"""WaPOR time series: a WaPOR v3 level 1 layer over time, at a point or as the mean of each polygon."""
import csv
import json
import math
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from apps.analysis.core.errors import AnalysisError
from apps.analysis.data import wapor
from apps.analysis.ops.timeseries import sens_slope

MAX_STEPS = 220             # about six years of dekads
MAX_POLYGONS = 200
MAX_WINDOW_PX = 6000 * 6000
MAX_SERIES_ON_CHART = 12
WIDE_TABLE_ZONES = 8

NAMES = {
    "PCP": "Precipitation", "RET": "Reference evapotranspiration", "AETI": "Actual evapotranspiration and interception",
    "T": "Transpiration", "E": "Evaporation", "I": "Interception", "NPP": "Net primary production",
    "TBP": "Total biomass production", "GBWP": "Gross biomass water productivity",
    "NBWP": "Net biomass water productivity", "RSM": "Relative soil moisture",
}
# Units as FAO publishes them (dekadal values are daily means over the dekad).
UNITS = {
    "PCP-D": "mm/day", "PCP-M": "mm/month", "PCP-A": "mm/year",
    "RET-D": "mm/day", "RET-M": "mm/month", "RET-A": "mm/year",
    "AETI-D": "mm/day", "AETI-M": "mm/month", "AETI-A": "mm/year",
    "T-D": "mm/day", "T-A": "mm/year", "E-D": "mm/day", "E-A": "mm/year", "I-D": "mm/day", "I-A": "mm/year",
    "NPP-D": "gC/m²/day", "NPP-M": "gC/m²/month", "TBP-A": "kg/ha", "GBWP-A": "kg/m³", "NBWP-A": "kg/m³",
    "RSM-D": "%",
}
STEP_NAMES = {"D": "dekadal", "M": "monthly", "A": "annual"}
RESOLUTION = {"PCP": "about 5 km", "RET": "about 30 km"}


# Geometry --------------------------------------------------------------------------------------------------
def _feature_name(props, i):
    for k in ("name", "NAME", "Name", "label", "title", "id", "ID", "fid", "field_id"):
        v = props.get(k)
        if v not in (None, ""):
            return str(v)
    for v in props.values():
        if isinstance(v, str) and v.strip():
            return v.strip()[:60]
    return f"Polygon {i}"


def targets(ctx):
    """[(key, name, geojson geometry)] for polygons, or a (lon, lat) point; and a description of the place."""
    aoi = ctx.params.get("aoi") or "area"
    if aoi == "point":
        lon, lat = ctx.point("point")
        return "point", (lon, lat), f"the point {lon:.4f}, {lat:.4f}"
    if aoi == "zones":
        level = int(ctx.params.get("zone_level") or 2)
        zones = ctx.zones(level)
        return "polygons", [(gid, name, gj) for _, gid, name, gj in zones], f"{len(zones)} administrative unit(s)"
    if aoi == "layer":
        fc = ctx.layer("layer")
        polys = []
        for i, f in enumerate(fc.get("features") or [], start=1):
            g = f.get("geometry") or {}
            if g.get("type") in ("Polygon", "MultiPolygon"):
                polys.append((str(i), _feature_name(f.get("properties") or {}, i), g))
        if not polys:
            raise AnalysisError("The chosen layer has no polygons. Choose a polygon layer (fields, sub-basins, a catchment…).")
        if len(polys) > MAX_POLYGONS:
            raise AnalysisError(f"The layer has {len(polys):,} polygons; this analysis takes up to {MAX_POLYGONS}. "
                                "Choose a smaller layer, or use administrative units.")
        # Names repeat (e.g. crop types): number the repeats so table columns and chart lines stay distinct.
        total, seen, named = {}, {}, []
        for _, n, _ in polys:
            total[n] = total.get(n, 0) + 1
        for k, n, g in polys:
            seen[n] = seen.get(n, 0) + 1
            named.append((k, f"{n} ({seen[n]})" if total[n] > 1 else n, g))
        polys = named
        return "polygons", polys, f"{len(polys)} polygon(s) of the chosen layer"
    return "polygons", [("area", "Area of influence", ctx.area_geojson)], "the area of influence"


def _bbox_of(geoms):
    from shapely.geometry import shape
    w, s, e, n = math.inf, math.inf, -math.inf, -math.inf
    for g in geoms:
        a, b, c, d = shape(g).bounds
        w, s, e, n = min(w, a), min(s, b), max(e, c), max(n, d)
    return w, s, e, n


# Periods ---------------------------------------------------------------------------------------------------
def period_label(code, step):
    """'2024-06-D1' -> '2024-06 D1'; months and years unchanged."""
    return code.replace("-D", " D") if step == "D" else code


def period_time(code, step):
    """Decimal year of the middle of a period."""
    y = int(code[:4])
    if step == "A":
        return y + 0.5
    m = int(code[5:7])
    if step == "M":
        return y + (m - 0.5) / 12
    d = int(code[-1])
    return y + (m - 1) / 12 + (d - 0.5) / 36


def _fmt(v):
    if v is None or not math.isfinite(v):
        return None
    return round(v, 3) if abs(v) < 10 else round(v, 1)


# Run -------------------------------------------------------------------------------------------------------
def run(ctx):
    from rasterio.features import geometry_mask

    var = ctx.params.get("variable") or "AETI"
    step = ctx.params.get("step") or "M"
    code = f"{var}-{step}"
    if code not in UNITS:
        allowed = ", ".join(STEP_NAMES[s] for s in "DMA" if f"{var}-{s}" in UNITS)
        raise AnalysisError(f"WaPOR has no {STEP_NAMES.get(step, step)} {NAMES.get(var, var).lower()}; choose {allowed}.")
    y0, y1 = int(ctx.params.get("start_year") or 2020), int(ctx.params.get("end_year") or 2024)
    if y1 < y0:
        y0, y1 = y1, y0
    mapset, unit, title = f"L1-{code}", UNITS[code], NAMES[var]

    periods = [p for p in wapor.periods(mapset) if y0 <= int(p[:4]) <= y1]
    if not periods:
        raise AnalysisError(f"FAO publishes no {STEP_NAMES[step]} {title.lower()} for {y0}–{y1} "
                            "(WaPOR v3 starts in 2018), or its catalogue couldn't be reached.")
    if len(periods) > MAX_STEPS:
        raise AnalysisError(f"{len(periods)} {STEP_NAMES[step]} values in {y0}–{y1} is more than {MAX_STEPS}. "
                            "Choose fewer years, or a monthly or annual step.")

    kind, place, where = targets(ctx)
    if kind == "point":
        lon, lat = place
        d = 0.0001
        bbox = (lon - d, lat - d, lon + d, lat + d)
    else:
        bbox = _bbox_of([g for _, _, g in place])
        pad = 0.01
        bbox = (bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad)
    ctx.log(f"{mapset}: {len(periods)} period(s) {periods[0]} to {periods[-1]} for {where}")
    ctx.progress(5)

    # Read every period (in parallel; cached windows return at once).
    results = [None] * len(periods)
    done = [0]

    def job(i):
        results[i] = wapor.read_window(mapset, periods[i], bbox)
        done[0] += 1
        if done[0] % 6 == 0:
            ctx.progress(5 + 75 * done[0] / len(periods))

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(job, range(len(periods))))
    ok = [i for i, r in enumerate(results) if r is not None]
    if not ok:
        raise AnalysisError(f"None of the {len(periods)} WaPOR files could be read. Try again later.")
    missing = [periods[i] for i, r in enumerate(results) if r is None]
    if missing:
        ctx.log(f"Skipped {len(missing)} period(s) that couldn't be read: {', '.join(missing[:10])}")
    ref = results[ok[0]]
    shape, transform, crs = ref[0].shape, ref[1], ref[2]
    if shape[0] * shape[1] > MAX_WINDOW_PX:
        raise AnalysisError("The polygons cover too large an area for this analysis; choose a smaller area or layer.")
    ctx.record_dataset(f"wapor:{mapset}", {
        "id": f"wapor_{mapset}", "title": f"FAO WaPOR v3 {title} ({STEP_NAMES[step]}, L1)",
        "citation": "FAO WaPOR v3, level 1, FAO 2024, CC BY 4.0",
        "resolution": RESOLUTION.get(var, "300 m"), "reference_date": f"{periods[0]} to {periods[-1]}",
        "licence": "CC BY 4.0"})

    # Zones as pixel masks on the window (all touched pixels for polygons smaller than a pixel).
    if kind == "point":
        col, row = ~transform * (lon, lat)
        r, c = min(max(int(row), 0), shape[0] - 1), min(max(int(col), 0), shape[1] - 1)
        masks = [("point", "Point", None, (r, c))]
    else:
        masks = []
        for key, name, g in place:
            m = ~geometry_mask([g], out_shape=shape, transform=transform)
            if not m.any():
                m = ~geometry_mask([g], out_shape=shape, transform=transform, all_touched=True)
            masks.append((key, name, g, m))

    def value(arr, m):
        if isinstance(m, tuple):
            v = arr[m]
            return float(v) if np.isfinite(v) else None
        vals = arr[m]
        vals = vals[np.isfinite(vals)]
        return float(vals.mean()) if vals.size else None

    series = {key: [] for key, *_ in masks}
    stack_sum, stack_n = np.zeros(shape, "float64"), np.zeros(shape, "int32")
    for i, p in enumerate(periods):
        r = results[i]
        if r is None or r[0].shape != shape:
            for key, *_ in masks:
                series[key].append(None)
            continue
        arr = r[0]
        for key, _, _, m in masks:
            series[key].append(value(arr, m))
        fin = np.isfinite(arr)
        stack_sum[fin] += arr[fin]
        stack_n[fin] += 1
    ctx.progress(85)

    labels = [period_label(p, step) for p in periods]
    times = [period_time(p, step) for p in periods]

    # Trend on yearly means (the yearly values for an annual step).
    def trend(vals):
        years = sorted({int(p[:4]) for p in periods})
        if step == "A":
            return sens_slope(times, [v if v is not None else np.nan for v in vals])
        per_year = []
        for y in years:
            yv = [v for p, v in zip(periods, vals) if int(p[:4]) == y and v is not None]
            full = len(yv) >= (30 if step == "D" else 10)          # only (nearly) complete years
            per_year.append(float(np.mean(yv)) if full else np.nan)
        return sens_slope(years, per_year)

    rows_zone = []
    for key, name, *_ in masks:
        vals = [v for v in series[key] if v is not None]
        slope, p = trend(series[key])
        rows_zone.append({
            "zone": name, "mean": _fmt(float(np.mean(vals))) if vals else None,
            "min": _fmt(min(vals)) if vals else None, "max": _fmt(max(vals)) if vals else None,
            "trend": _fmt(slope) if slope is not None else None,
            "significant": ("Yes" if p < 0.05 else "No") if p is not None else "",
            "values": len(vals)})

    # Metrics: the point, the single polygon, or all polygons together (mean of polygon means).
    first = series[masks[0][0]]
    if len(masks) == 1:
        overall = first
    else:
        overall = [float(np.mean([series[k][i] for k, *_ in masks if series[k][i] is not None]))
                   if any(series[k][i] is not None for k, *_ in masks) else None for i in range(len(periods))]
    vals = [v for v in overall if v is not None]
    if not vals:
        raise AnalysisError("WaPOR has no values here for these periods (water, outside its coverage, or no data).")
    hi = max(range(len(overall)), key=lambda i: overall[i] if overall[i] is not None else -math.inf)
    lo = min(range(len(overall)), key=lambda i: overall[i] if overall[i] is not None else math.inf)
    slope, p = trend(overall)
    scope = "" if len(masks) == 1 else " (mean of the polygons)"
    ctx.add_metric("mean", f"Mean {STEP_NAMES[step]} value{scope}", _fmt(float(np.mean(vals))), unit,
                   note=f"{labels[0]} to {labels[-1]}")
    ctx.add_metric("highest", "Highest", _fmt(overall[hi]), unit, note=labels[hi])
    ctx.add_metric("lowest", "Lowest", _fmt(overall[lo]), unit, note=labels[lo])
    trend_unit = f"{unit} per year"
    ctx.add_metric("trend", "Trend", _fmt(slope) if slope is not None else None, trend_unit,
                   note=("significant (Mann-Kendall p < 0.05)" if p is not None and p < 0.05 else
                         "not significant" if p is not None else "needs three years or more"))

    # Chart: one line per zone (the first few when there are many).
    shown = masks[:MAX_SERIES_ON_CHART]
    ctx.add_chart("series", f"{title}, {STEP_NAMES[step]}", [
        {"name": name, "points": [[lab, _fmt(v) if v is not None else None] for lab, v in zip(labels, series[key])]}
        for key, name, *_ in shown], x_label=STEP_NAMES[step].capitalize(), y_label=title, unit=unit,
        kind="bar" if step == "A" and len(shown) == 1 else "line",
        note=f"{len(masks) - len(shown)} more polygon(s) in the table." if len(masks) > len(shown) else "")

    ctx.add_table("by_zone", "Summary per polygon" if kind != "point" else "Summary", [
        {"key": "zone", "label": "Place"}, {"key": "mean", "label": "Mean", "unit": unit},
        {"key": "min", "label": "Lowest", "unit": unit}, {"key": "max", "label": "Highest", "unit": unit},
        {"key": "trend", "label": "Trend", "unit": trend_unit}, {"key": "significant", "label": "Significant trend"},
        {"key": "values", "label": "Periods with data"}], rows_zone)

    # Values: periods as rows, one column per zone (long format when there are many zones).
    if len(masks) <= WIDE_TABLE_ZONES:
        cols = [{"key": "period", "label": STEP_NAMES[step].capitalize()}] + [
            {"key": f"z{i}", "label": name, "unit": unit} for i, (_, name, *_) in enumerate(masks)]
        rows = [{"period": lab, **{f"z{j}": _fmt(series[key][i]) if series[key][i] is not None else None
                                   for j, (key, *_) in enumerate(masks)}} for i, lab in enumerate(labels)]
    else:
        cols = [{"key": "period", "label": STEP_NAMES[step].capitalize()}, {"key": "zone", "label": "Place"},
                {"key": "value", "label": title, "unit": unit}]
        rows = [{"period": lab, "zone": name, "value": _fmt(series[key][i]) if series[key][i] is not None else None}
                for key, name, *_ in masks for i, lab in enumerate(labels)]
    ctx.add_table("values", f"{title}, {STEP_NAMES[step]} values", cols, rows)

    csv_path = ctx.path("wapor_series.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["place", "period", "start_decimal_year", f"{var.lower()}_{unit}"])
        for key, name, *_ in masks:
            for lab, t, v in zip(labels, times, series[key]):
                w.writerow([name, lab, round(t, 4), "" if v is None else round(v, 4)])
    ctx.add_file("csv", "All values (CSV)", csv_path)

    # Mean map of the period (inside the polygons; around the point).
    if kind != "point" and stack_n.any():
        from apps.analysis.ops import grid as G
        mean = np.where(stack_n > 0, stack_sum / np.maximum(stack_n, 1), np.nan).astype("float32")
        inside = np.zeros(shape, bool)
        for *_, m in masks:
            inside |= m
        mean[~inside] = np.nan
        r = G.Raster(mean, transform, crs, {"dataset": f"wapor_{mapset}"})
        utm = G.reproject(r, G.utm_grid(r, ctx.epsg, None), "nearest")
        ctx.add_raster("mean_map", f"Mean {title.lower()}, {labels[0]} to {labels[-1]}", utm, unit=unit,
                       mask_to_area=False)

    # The places, as a layer (with their mean).
    feats = []
    if kind == "point":
        feats.append({"type": "Feature", "properties": {"name": "Point", "mean": rows_zone[0]["mean"], "unit": unit},
                      "geometry": {"type": "Point", "coordinates": [lon, lat]}})
    else:
        for (key, name, g, _), rz in zip(masks, rows_zone):
            feats.append({"type": "Feature", "properties": {"name": name, "mean": rz["mean"], "unit": unit,
                                                             "trend_per_year": rz["trend"]}, "geometry": g})
    gj = ctx.path("places.geojson")
    gj.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    ctx.add_vector("zones", "Point" if kind == "point" else f"Places: mean {title.lower()}", gj,
                   style={"color": "#0B3B47", "width": 2, "opacity": 0.05, "outline": "#0B3B47"})
    ctx.progress(100)

    trend_txt = (f"{'rising' if slope > 0 else 'falling'} by {abs(_fmt(slope))} {unit} per year"
                 f"{' (significant)' if p is not None and p < 0.05 else ' (not significant)'}"
                 if slope not in (None, 0) else "no clear trend")
    ctx.summary(f"{title} ({STEP_NAMES[step]}, WaPOR v3 L1) for {where}, {labels[0]} to {labels[-1]}: "
                f"mean {_fmt(float(np.mean(vals)))} {unit}, highest {_fmt(overall[hi])} in {labels[hi]}, "
                f"lowest {_fmt(overall[lo])} in {labels[lo]}; {trend_txt}.")
