"""Access to services: people by straight-line distance to the nearest OSM school, clinic, market, water point or road."""
import numpy as np
import shapely

from apps.analysis.core.errors import AnalysisError
from apps.analysis.ops import people as P

BUFFER_M = 10_000
EDGES = [0, 1, 2, 5, 10]
LABELS = ["Under 1 km", "1–2 km", "2–5 km", "5–10 km", "10 km and more"]
SERVICE = {"osm_schools": "a school", "osm_health": "a health facility", "osm_markets": "a market",
           "osm_water_points": "a water point", "osm_roads": "a road"}
RAMP = ["#1A9850", "#91CF60", "#D9EF8B", "#FEE08B", "#FC8D59", "#D73027"]


def run(ctx):
    ds = ctx.params.get("facilities_dataset") or "osm_schools"
    what = SERVICE.get(ds, "a service")
    thr = float(ctx.params["threshold_km"])
    year = int(ctx.params.get("year") or 2025)
    pop, src = P.read_population(ctx, year, P.population_source(ctx, [year]), buffer_m=BUFFER_M)
    who = src["people"]
    ctx.progress(30)
    box = ctx.bbox(buffer_m=BUFFER_M)
    layer = ctx.features("facilities", box)
    if len(layer):  # keep what touches the search box (extracts and local files can be larger)
        layer = layer.subset(shapely.intersects(ctx.frame.to_deg(layer.geoms), shapely.box(*box)))
    ctx.progress(50)
    inside = ctx.area_mask(pop)
    cells = np.nan_to_num(pop.data, nan=0.0)
    px_km2 = pop.grid.pixel_area_m2 / 1e6
    total = P.people(cells, inside)
    if not len(layer):
        raise AnalysisError(f"OpenStreetMap has no {what.split(' ', 1)[1]} within 10 km of the area, so distances can't be measured.")
    geoms = P.to_grid_coords(ctx.frame.to_deg(layer.geoms), pop.crs)
    dist_m = P.distance_to(geoms, pop.grid)
    km = (dist_m / 1000).astype("float32")
    zones = ctx.vzones(int(ctx.params.get("zone_level") or 2))
    n_inside = int((zones.assign(layer.geoms) > 0).sum())
    ctx.progress(70)

    within = P.people(cells, inside & (km <= thr))
    mean_km = P.weighted_mean(km, cells, inside)
    bands = P.band_rows(km, cells, inside, EDGES, LABELS, px_km2)
    zone_rows = []
    for _, _, name, m in ctx.zone_masks(pop, int(ctx.params.get("zone_level") or 2)):
        z = m & inside
        p = P.people(cells, z)
        if not z.any() or not p:
            continue
        zone_rows.append({"unit": name, "people": round(p), "within": round(100 * P.people(cells, z & (km <= thr)) / p, 1),
                          "beyond": round(P.people(cells, z & (km > thr))), "mean_km": round(P.weighted_mean(km, cells, z) or 0, 2)})
    zone_rows.sort(key=lambda r: r["within"])
    ctx.progress(85)

    share = 100 * within / total if total else 0
    ctx.add_metric("within_share", f"{who.capitalize()} within {thr:g} km of {what}", round(share, 1), f"% of {who}", note=f"{src['name']} {src['year']}")
    ctx.add_metric("people_beyond", f"{who.capitalize()} farther than {thr:g} km", round(total - within), who)
    ctx.add_metric("mean_distance", "Mean distance (population-weighted)", round(mean_km, 2) if mean_km is not None else None, "km")
    ctx.add_metric("facilities", "Locations mapped in the area" if ds != "osm_roads" else "Road segments in the area", n_inside, "")
    ctx.add_table("bands", f"{who.capitalize()} by distance to {what}", [
        {"key": "label", "label": "Distance"}, {"key": "people", "label": "People"}, {"key": "share", "label": "Of people", "unit": "%"},
        {"key": "cumulative", "label": "Cumulative", "unit": "%"}, {"key": "area_km2", "label": "Area", "unit": "km²"}], bands,
        note="Straight-line distance to the nearest location in OpenStreetMap (locations up to 10 km outside the area count).")
    ctx.add_table("per_zone", f"Access to {what} per administrative unit", [
        {"key": "unit", "label": "Unit"}, {"key": "people", "label": "People"},
        {"key": "within", "label": f"Within {thr:g} km", "unit": "%"}, {"key": "beyond", "label": f"Beyond {thr:g} km", "unit": "people"},
        {"key": "mean_km", "label": "Mean distance", "unit": "km"}], zone_rows)
    ctx.add_raster("distance", f"Distance to {what}", pop.like(km),
                   legend={"type": "ramp", "palette": RAMP, "min": 0, "max": 10, "unit": "km", "open_max": True})
    ctx.summary(f"{share:.0f}% of the area's {total:,.0f} {who} live within {thr:g} km of {what}; "
                f"{total - within:,.0f} live farther. Population-weighted mean distance {mean_km:.1f} km "
                f"({n_inside} mapped in the area, OpenStreetMap{(' ' + ctx.snapshot()) if ctx.snapshot() else ''}; {src['name']} {src['year']}).")
