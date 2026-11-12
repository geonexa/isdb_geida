"""Population and density (WorldPop yearly or GHSL epochs): totals, density classes, per admin unit, age and sex (WorldPop)."""
import numpy as np

from apps.analysis.core.errors import AnalysisError
from apps.analysis.data.base import DatasetUnavailable
from apps.analysis.data import people as WP
from apps.analysis.ops import people as P

# Density classes, people per km² of the 1 km block (GHSL thresholds: 300 = cluster, 1,500 = high density)
EDGES = [0, 0.5, 25, 100, 300, 1500]
LABELS = ["Uninhabited", "Very sparse (under 25 per km²)", "Sparse (25–100)", "Moderate (100–300)",
          "Clustered (300–1,500)", "High density (1,500 and more)"]
RAMP = ["#FFFFCC", "#FFEDA0", "#FED976", "#FEB24C", "#FD8D3C", "#FC4E2A", "#E31A1C", "#B10026"]
GROUPS = [("under_5", "Children under 5"), ("age_5_14", "School age (5–14)"), ("age_15_24", "Youth (15–24)"),
          ("age_15_64", "Working age (15–64)"), ("women_15_49", "Women of reproductive age (15–49)"), ("age_65_plus", "65 and over")]


def age_sex(ctx, year, zones):
    """WorldPop groups and pyramid for the area, groups per admin unit: (group rows, pyramid rows, {zone index: groups})."""
    area = WP.simple_geojson(ctx.area_geojson)
    g = WP.worldpop_post("/groups", {"geojson": area, "year": year, "groups": [k for k, _ in GROUPS]})
    total = g["total_population"]
    by_name = {x["name"]: x for x in g["groups"]}
    group_rows = [{"label": lab, "people": round(by_name[k]["population"]), "share": round(100 * (by_name[k]["share"] or 0), 1)}
                  for k, lab in GROUPS if k in by_name]
    a = WP.worldpop_post("/agesex", {"geojson": area, "year": year})
    pyramid = [{"age": row["age"], "male": round(row["male"] or 0), "female": round(row["female"] or 0),
                "male_pct": round(100 * (row["male"] or 0) / total, 2) if total else 0,
                "female_pct": round(100 * (row["female"] or 0) / total, 2) if total else 0}
               for row in reversed(a["agesex_pyramid"])]
    per_zone = {}
    if len(zones) > 1 or zones[0][1] != "area":
        feats = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "id": str(i), "properties": {"name": name}, "geometry": WP.simple_geojson(gj, 0.0005, 20000)}
            for i, _, name, gj in zones]}
        b = WP.worldpop_post("/batch", {"features": feats, "year": year, "include": "groups"})
        for f in b["features"]:
            per_zone[int(f["id"])] = {x["name"]: x["population"] for x in (f.get("groups") or [])}
    return group_rows, pyramid, per_zone, g


def run(ctx):
    year = int(ctx.params.get("year") or 2025)
    ds = P.population_source(ctx, [year])
    pop, src = P.read_population(ctx, year, ds)
    year = src["year"]
    ctx.progress(45)
    inside = ctx.area_mask(pop)
    if not inside.any():
        raise AnalysisError("The area of influence is smaller than one population cell.")
    cells = np.nan_to_num(pop.data, nan=0.0)
    px_km2 = pop.grid.pixel_area_m2 / 1e6
    total = P.people(cells, inside)
    area_km2 = float(inside.sum()) * px_km2
    density = P.block_density(cells, pop.grid.res)   # density of the 1 km block each cell is in
    classes = P.band_rows(density, cells, inside, EDGES, LABELS, px_km2, cumulative=False)
    dense = sum(r["share"] for r in classes[-2:])

    level = int(ctx.params.get("zone_level") or 2)
    zones = ctx.zones(level)
    groups = pyramid = per_zone_groups = None
    if src["dataset"] == "worldpop":
        try:
            groups, pyramid, per_zone_groups, _ = age_sex(ctx, year, zones)
        except DatasetUnavailable as exc:
            ctx.log(f"Age and sex not available: {exc}")
    ctx.progress(70)

    zone_rows = []
    for i, _, name, m in ctx.zone_masks(pop, level):
        z = m & inside
        if not z.any():
            continue
        p, a = P.people(cells, z), float(z.sum()) * px_km2
        row = {"unit": name, "people": round(p), "area_km2": round(a, 1), "density": round(p / a, 1) if a else 0,
               "share": round(100 * p / total, 1) if total else 0}
        if per_zone_groups:
            zg = per_zone_groups.get(i, {})
            row.update(under5=round(zg.get("under_5", 0)), school=round(zg.get("age_5_14", 0)),
                       women=round(zg.get("women_15_49", 0)), old=round(zg.get("age_65_plus", 0)))
        zone_rows.append(row)
    zone_rows.sort(key=lambda r: -r["people"])
    ctx.progress(85)

    label = f"{year}{' (projection)' if year > 2025 or (src['dataset'] == 'ghsl_pop' and year > 2020) else ''}"
    source = src["name"]
    ctx.add_metric("total_population", f"Population {label}", round(total), "people", note=source)
    ctx.add_metric("density", "Density", round(total / area_km2, 1) if area_km2 else 0, "people per km²")
    ctx.add_metric("dense_share", "Living in clusters (300+ per km² at 1 km)", round(dense, 1), "% of people")
    cols = [{"key": "unit", "label": "Unit"}, {"key": "people", "label": "People"}, {"key": "area_km2", "label": "Area", "unit": "km²"},
            {"key": "density", "label": "Density", "unit": "per km²"}, {"key": "share", "label": "Of the area's people", "unit": "%"}]
    if per_zone_groups:
        cols += [{"key": "under5", "label": "Under 5"}, {"key": "school", "label": "Age 5–14"},
                 {"key": "women", "label": "Women 15–49"}, {"key": "old", "label": "65 and over"}]
    ctx.add_table("density_classes", f"People by density, {label}", [
        {"key": "label", "label": "Density class"}, {"key": "people", "label": "People"},
        {"key": "share", "label": "Of people", "unit": "%"}, {"key": "area_km2", "label": "Area", "unit": "km²"}], classes,
        note=f"Density of the 1 km block around each cell. {source}: modelled from census counts and settlement data.")
    ctx.add_table("per_zone", f"Population per administrative unit, {label}", cols, zone_rows,
                  note="Age groups: WorldPop's count for each unit's boundary (may differ slightly from the grid count)." if per_zone_groups else "")
    if groups:
        under5 = next((r for r in groups if r["label"].startswith("Children under 5")), None)
        if under5:
            ctx.add_metric("under5", "Children under 5", under5["people"], "people", note=f"{under5['share']:g}% of people")
        ctx.add_table("age_groups", f"Age and sex groups, {label}", [
            {"key": "label", "label": "Group"}, {"key": "people", "label": "People"}, {"key": "share", "label": "Of people", "unit": "%"}],
            groups, note="WorldPop R2025A age-sex structure for the area of influence (groups overlap).")
        ctx.add_table("age_pyramid", f"Age pyramid, {label}", [
            {"key": "age", "label": "Age"}, {"key": "male", "label": "Male"}, {"key": "female", "label": "Female"},
            {"key": "male_pct", "label": "Male", "unit": "%"}, {"key": "female_pct", "label": "Female", "unit": "%"}], pyramid)
    shown = pop.like(np.where(cells > 0, cells, np.nan).astype("float32"))
    ctx.add_raster("population", f"People per {pop.grid.res:.0f} m cell, {label}", shown,
                   legend={"type": "ramp", "palette": RAMP, "min": 0, "max": 50, "unit": "people per cell", "open_max": True})
    top = zone_rows[0] if zone_rows else None
    kids = next((r for r in groups or [] if r["label"].startswith("Children under 5")), None)
    ctx.summary(f"About {total:,.0f} people lived in the area in {label} ({total / area_km2:,.1f} per km²)"
                + (f", {kids['share']:g}% of them under 5" if kids else "")
                + f"; {dense:.0f}% live in settled clusters (1 km blocks of 300 or more people per km²)"
                + (f". Most populous unit: {top['unit']} ({top['people']:,} people)" if top and len(zone_rows) > 1 else "")
                + f". {source}, 100 m.")
