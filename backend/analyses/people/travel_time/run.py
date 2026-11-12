"""Travel time to cities or health care (Malaria Atlas Project) weighted by GHSL population, per admin unit."""
import numpy as np

from apps.analysis.core.errors import AnalysisError
from apps.analysis.ops import people as P

EDGES = [0, 15, 30, 60, 120, 180, 360]
LABELS = ["Under 15 min", "15–30 min", "30 min – 1 h", "1–2 h", "2–3 h", "3–6 h", "6 h and more"]
TARGET = {"map_tt_cities": "the nearest city (50,000+ people)", "map_tt_health_motor": "health care by motorised transport",
          "map_tt_health_walk": "health care on foot"}
RAMP = ["#FFFFCC", "#C7E9B4", "#7FCDBB", "#41B6C4", "#1D91C0", "#225EA8", "#0C2C84"]


def fmt(minutes):
    return f"{minutes:.0f} min" if minutes < 90 else f"{minutes / 60:.1f} h"


def run(ctx):
    ds = ctx.params.get("travel_dataset") or "map_tt_cities"
    target = TARGET.get(ds, "the destination")
    thr = float(ctx.params["threshold_min"])
    year = int(ctx.params.get("year") or 2025)
    pop, src = P.read_population(ctx, year, P.population_source(ctx, [year]))
    who = src["people"]
    ctx.progress(35)
    tt = ctx.raster("travel")
    ctx.progress(60)
    inside = ctx.area_mask(pop)
    cells = np.nan_to_num(pop.data, nan=0.0)
    minutes = np.where(tt.data >= 0, tt.data, np.nan)
    px_km2 = pop.grid.pixel_area_m2 / 1e6
    total = P.people(cells, inside & np.isfinite(minutes))
    if not total:
        raise AnalysisError("No people with a travel time in the area (travel-time map or population missing).")
    mean = P.weighted_mean(minutes, cells, inside)
    median = P.weighted_median(minutes, cells, inside)
    within = P.people(cells, inside & (minutes <= thr))
    bands = P.band_rows(minutes, cells, inside, EDGES, LABELS, px_km2)

    zone_rows = []
    for _, _, name, m in ctx.zone_masks(pop, int(ctx.params.get("zone_level") or 2)):
        z = m & inside & np.isfinite(minutes)
        p = P.people(cells, z)
        if not p:
            continue
        zone_rows.append({"unit": name, "people": round(p), "mean": round(P.weighted_mean(minutes, cells, z)),
                          "within": round(100 * P.people(cells, z & (minutes <= thr)) / p, 1)})
    zone_rows.sort(key=lambda r: -r["mean"])
    ctx.progress(85)

    share = 100 * within / total
    ctx.add_metric("mean_minutes", f"Mean travel time to {target}", round(mean), "minutes")
    ctx.add_metric("median_minutes", "Median (half the people are closer)", round(median), "minutes")
    ctx.add_metric("within_share", f"{who.capitalize()} within {fmt(thr)}", round(share, 1), f"% of {who}", note=f"{src['name']} {src['year']}")
    ctx.add_table("bands", f"{who.capitalize()} by travel time to {target}", [
        {"key": "label", "label": "Travel time"}, {"key": "people", "label": "People"}, {"key": "share", "label": "Of people", "unit": "%"},
        {"key": "cumulative", "label": "Cumulative", "unit": "%"}, {"key": "area_km2", "label": "Area", "unit": "km²"}], bands,
        note="Modelled fastest travel time over roads, paths and land (Malaria Atlas Project), weighted by population.")
    ctx.add_table("per_zone", f"Travel time to {target} per administrative unit", [
        {"key": "unit", "label": "Unit"}, {"key": "people", "label": "People"}, {"key": "mean", "label": "Mean", "unit": "min"},
        {"key": "within", "label": f"Within {fmt(thr)}", "unit": "%"}], zone_rows)
    ctx.add_raster("travel_time", f"Travel time to {target}", tt.like(minutes.astype("float32")),
                   legend={"type": "ramp", "palette": RAMP, "min": 0, "max": 240, "unit": "minutes", "open_max": True})
    ctx.summary(f"{who.capitalize()} in the area are on average {fmt(mean)} from {target} (median {fmt(median)}); "
                f"{share:.0f}% are within {fmt(thr)}. Malaria Atlas Project travel-time model, {src['name']} {src['year']}.")
