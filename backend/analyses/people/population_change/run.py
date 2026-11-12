"""Population change between two years (WorldPop 2015–2030, or GHSL epochs): totals, yearly growth, per admin unit, change map."""
import numpy as np

from apps.analysis.core.errors import AnalysisError
from apps.analysis.data import people as WP
from apps.analysis.data.base import DatasetUnavailable
from apps.analysis.ops import people as P

DIVERGING = ["#2166AC", "#67A9CF", "#D1E5F0", "#F7F7F7", "#FDDBC7", "#EF8A62", "#B2182B"]


def rate(a, b, years):
    """Compound yearly growth rate in % (None when the start is zero)."""
    return round(100 * ((b / a) ** (1 / years) - 1), 2) if a > 0 and b > 0 and years else None


def label(y):
    return f"{y}{' (projection)' if y > 2025 else ''}"


def run(ctx):
    y0, y1 = int(ctx.params["year_from"]), int(ctx.params["year_to"])
    if y0 >= y1:
        raise AnalysisError("The 'to' year must be later than the 'from' year.")
    ds = P.population_source(ctx, [y0, y1])
    a, src0 = P.read_population(ctx, y0, ds)
    ctx.progress(35)
    b, src1 = P.read_population(ctx, y1, src0["dataset"])   # same source for both years
    if src1["dataset"] != src0["dataset"]:                    # WorldPop failed on the second year: redo the first from GHSL
        a, src0 = P.read_population(ctx, y0, "ghsl_pop")
    y0, y1 = src0["year"], src1["year"]
    if y0 >= y1:
        raise AnalysisError(f"Both years fall on the same GHSL epoch ({y0}). Choose years at least five years apart.")
    ctx.progress(60)
    inside = ctx.area_mask(a)
    pa, pb = np.nan_to_num(a.data, nan=0.0), np.nan_to_num(b.data, nan=0.0)
    t0, t1 = P.people(pa, inside), P.people(pb, inside)
    years = y1 - y0
    pct = 100 * (t1 - t0) / t0 if t0 else None
    r = rate(t0, t1, years)

    zone_rows = []
    for _, _, name, m in ctx.zone_masks(a, int(ctx.params.get("zone_level") or 2)):
        z = m & inside
        if not z.any():
            continue
        z0, z1 = P.people(pa, z), P.people(pb, z)
        zone_rows.append({"unit": name, "from": round(z0), "to": round(z1), "change": round(z1 - z0),
                          "change_pct": round(100 * (z1 - z0) / z0, 1) if z0 else None, "rate": rate(z0, z1, years)})
    zone_rows.sort(key=lambda row: -row["change"])

    by_year = None
    if src0["dataset"] == "worldpop":
        try:
            tr = WP.worldpop_post("/trend", {"geojson": WP.simple_geojson(ctx.area_geojson), "from_year": y0, "to_year": y1})
            by_year = [{"year": y["data_year"], "people": round(y["total_population"]),
                        "density": round(y["population_density"], 1)} for y in tr["years"]]
        except DatasetUnavailable as exc:
            ctx.log(f"Yearly series not available: {exc}")
    ctx.progress(80)

    source = src0["name"]
    ctx.add_metric("population_from", f"Population {label(y0)}", round(t0), "people", note=source)
    ctx.add_metric("population_to", f"Population {label(y1)}", round(t1), "people", note=source)
    ctx.add_metric("change_pct", f"Change {y0}–{y1}", round(pct, 1) if pct is not None else None, "%")
    ctx.add_metric("growth_rate", "Average yearly growth", r, "% per year")
    ctx.add_table("per_zone", f"Population change {y0}–{y1} per administrative unit", [
        {"key": "unit", "label": "Unit"}, {"key": "from", "label": str(y0)}, {"key": "to", "label": str(y1)},
        {"key": "change", "label": "Change", "unit": "people"}, {"key": "change_pct", "label": "Change", "unit": "%"},
        {"key": "rate", "label": "Yearly growth", "unit": "%"}], zone_rows,
        note=f"{source}. Modelled estimates: change at small scales (a few cells) is uncertain.")
    if by_year:
        ctx.add_table("by_year", f"Population every year, {y0}–{y1}", [
            {"key": "year", "label": "Year"}, {"key": "people", "label": "People"}, {"key": "density", "label": "Density", "unit": "per km²"}],
            by_year, note="WorldPop's count for the area's boundary (may differ slightly from the grid count).")
    diff = pb - pa
    ctx.add_raster("change", f"People added or lost per {a.grid.res:.0f} m cell, {y0}–{y1}",
                   a.like(np.where((pa > 0) | (pb > 0), diff, np.nan).astype("float32")),
                   legend={"type": "ramp", "palette": DIVERGING, "min": -20, "max": 20, "unit": "people per cell",
                           "open_min": True, "open_max": True})
    ctx.summary(f"The population went from about {t0:,.0f} ({label(y0)}) to {t1:,.0f} ({label(y1)})"
                + (f", {pct:+.0f}% or {r:+.1f}% a year" if pct is not None and r is not None else "") + f". {source}, 100 m.")
