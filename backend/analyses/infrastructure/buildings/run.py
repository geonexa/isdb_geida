"""Buildings and settlement density: OSM footprints by type, density grid and per admin unit (vector)."""
import numpy as np
import shapely

from apps.analysis.ops import inventory, vector

GROUPS = {
    "Residential": {"house", "residential", "apartments", "detached", "semidetached_house", "terrace", "hut",
                    "bungalow", "dormitory", "cabin", "static_caravan", "houseboat"},
    "Commercial": {"commercial", "retail", "shop", "office", "kiosk", "supermarket", "hotel", "warehouse_shop"},
    "Industrial": {"industrial", "warehouse", "factory", "manufacture", "storage_tank", "hangar"},
    "Public and community": {"school", "hospital", "clinic", "public", "civic", "government", "university", "college",
                             "kindergarten", "mosque", "church", "chapel", "temple", "cathedral", "religious",
                             "train_station", "transportation", "fire_station", "sports_hall", "stadium"},
    "Agricultural": {"farm", "barn", "farm_auxiliary", "greenhouse", "stable", "cowshed", "sty", "silo", "granary"},
    "Ancillary": {"shed", "garage", "garages", "roof", "carport", "toilets", "service", "construction", "ruins"},
}
LOOKUP = {v: g for g, vs in GROUPS.items() for v in vs}
DENSITY = [(1, "#FFEDA0", "1–4"), (5, "#FEB24C", "5–19"), (20, "#F03B20", "20–49"), (50, "#BD0026", "50–149"),
           (150, "#5A001E", "150+")]
MAX_FOOTPRINTS = 20_000
MAX_POINTS = 60_000


def kind(p):
    b = (p.get("building") or "").strip().lower()
    if b in ("", "yes"):
        return "Not specified"
    return LOOKUP.get(b, "Other")


def run(ctx):
    cell_m = float(ctx.params["cell_m"])
    layer = ctx.features("buildings", ctx.bbox(buffer_m=100))
    ctx.progress(35)
    zones = ctx.vzones(int(ctx.params.get("zone_level") or 2))
    z = zones.assign(layer.geoms)
    inside = layer.subset(z > 0)
    z = z[z > 0]
    n = len(inside)
    ctx.log(f"{len(layer):,} buildings in the search box, {n:,} inside the area")
    ctx.progress(55)

    dims = shapely.get_dimensions(inside.geoms) if n else np.empty(0)
    foot_m2 = np.where(dims == 2, shapely.area(inside.geoms), 0.0) if n else np.empty(0)
    kinds = np.array([kind(p) for p in inside.props], dtype=object)
    total_km2 = float(foot_m2.sum()) / 1e6

    # By type --------------------------------------------------------------------------
    by_kind = []
    for k in sorted(set(kinds.tolist()), key=lambda k: -(kinds == k).sum()):
        sel = kinds == k
        by_kind.append({"kind": k, "count": int(sel.sum()), "share": round(sel.sum() / n * 100, 1),
                        "footprint_km2": round(float(foot_m2[sel].sum()) / 1e6, 3),
                        "mean_m2": round(float(foot_m2[sel].mean()), 0) if sel.any() else 0})

    # Per unit -------------------------------------------------------------------------
    counts = zones.count(z)
    foot_by_zone = zones.count(z, weights=foot_m2) / 1e6 if n else np.zeros(zones.size)
    per_zone = []
    for i, gid, name, area in zones.rows():
        c = int(counts[i])
        per_zone.append({"zone": name, "gid": gid, "area_km2": round(area, 1), "buildings": c,
                         "per_km2": round(c / area, 1) if area else 0,
                         "footprint_km2": round(float(foot_by_zone[i]), 3),
                         "built_pct": round(float(foot_by_zone[i]) / area * 100, 2) if area else 0})
    per_zone.sort(key=lambda r: (-r["buildings"], r["zone"]))
    ctx.progress(70)

    # Density grid ---------------------------------------------------------------------
    anchors = vector.anchor(inside.geoms)
    cells, cell_counts = vector.grid_counts(anchors, cell_m, clip=zones.union)
    vector.write_geojson(ctx.path("density.geojson"), ctx.frame, cells,
                         [{"buildings": int(c), "per_km2": round(c / (cell_m * cell_m / 1e6), 1)} for c in cell_counts])
    grid_rows = []
    if len(cells):
        cx, cy = vector.lonlat(ctx.frame, shapely.centroid(cells))
        grid_rows = [{"lon": round(float(x), 5), "lat": round(float(y), 5), "buildings": int(c)}
                     for x, y, c in zip(cx, cy, cell_counts)]
    peak = int(cell_counts.max()) if len(cell_counts) else 0
    ctx.progress(85)

    # Outputs --------------------------------------------------------------------------
    area = ctx.area_km2 or 0
    ctx.add_metric("count", "Buildings mapped", n, "")
    ctx.add_metric("per_km2", "Buildings per km²", round(n / area, 1) if area else 0, "")
    ctx.add_metric("footprint", "Total footprint", round(total_km2, 3), "km²")
    ctx.add_metric("mean_m2", "Mean footprint", round(float(foot_m2.mean()), 0) if n else 0, "m²")
    ctx.add_table("by_kind", "Buildings by type", [
        {"key": "kind", "label": "Type"}, {"key": "count", "label": "Buildings"}, {"key": "share", "label": "Share", "unit": "%"},
        {"key": "footprint_km2", "label": "Footprint", "unit": "km²"}, {"key": "mean_m2", "label": "Mean size", "unit": "m²"}],
        by_kind, note="Type from the OSM building tag; 'Not specified' = building=yes.")
    ctx.add_table("per_zone", "Buildings by administrative unit", [
        {"key": "zone", "label": "Unit"}, {"key": "area_km2", "label": "Area", "unit": "km²"},
        {"key": "buildings", "label": "Buildings"}, {"key": "per_km2", "label": "Per km²"},
        {"key": "footprint_km2", "label": "Footprint", "unit": "km²"}, {"key": "built_pct", "label": "Built", "unit": "%"}],
        per_zone, note=inventory.OSM_CAVEAT)
    ctx.add_vector("density", f"Building density (per {cell_m:g} m cell)", "density.geojson", {
        "property": "buildings", "opacity": 0.7,
        "steps": [{"from": lo, "color": c, "label": lab} for lo, c, lab in DENSITY]})
    classes = [{"value": k, "color": c, "label": k} for k, c in zip(
        [g for g in GROUPS] + ["Other", "Not specified"],
        ["#C2410C", "#7C3AED", "#475569", "#0E7490", "#4D7C0F", "#A8A29E", "#78716C", "#9F1239"])]
    names = dict(zip(zones.ids.tolist(), zones.names))
    feats = [vector.osm_props(p, kind=k, zone=names[int(zz)], footprint_m2=round(float(a), 1))
             for k, p, zz, a in zip(kinds.tolist(), inside.props, z, foot_m2)]
    if 0 < n <= MAX_FOOTPRINTS:
        vector.write_geojson(ctx.path("footprints.geojson"), ctx.frame, inside.geoms, feats)
        ctx.add_vector("footprints", "Building footprints", "footprints.geojson",
                       {"property": "kind", "classes": classes, "color": "#9F1239", "radius": 2.5, "opacity": 0.8})
    elif 0 < n <= MAX_POINTS:
        vector.write_geojson(ctx.path("footprints.geojson"), ctx.frame, anchors, feats)
        ctx.add_vector("footprints", "Buildings (points)", "footprints.geojson",
                       {"property": "kind", "classes": classes, "color": "#9F1239", "radius": 2})
        ctx.log(f"{n:,} buildings: drawn as points instead of footprints.")
    elif n:
        ctx.log(f"{n:,} buildings: too many to draw one by one; see the density layer.")
    vector.write_csv(ctx.path("density.csv"), grid_rows, ["lon", "lat", "buildings"])
    ctx.add_file("grid_csv", "Density grid (CSV, cell centres)", ctx.path("density.csv"))

    snap = ctx.snapshot()
    top = ", ".join(f"{r['zone']} ({r['buildings']:,})" for r in per_zone[:3] if r["buildings"])
    main = next((r for r in by_kind if r["kind"] not in ("Not specified", "Other")), None)
    ctx.summary(
        f"{n:,} buildings are mapped in OpenStreetMap inside the {area:,.0f} km² area "
        f"({n / area if area else 0:.1f} per km²){f', most in {top}' if top else ''}. "
        f"Together they cover {total_km2:,.2f} km² ({total_km2 / area * 100 if area else 0:.2f}% of the area). "
        + (f"Where the type is mapped, the most common is {main['kind'].lower()} ({main['count']:,}). " if main else "")
        + f"{len(cells):,} of the {cell_m:g} m grid cells contain at least one building (busiest: {peak:,}). "
        + (f"OSM snapshot {snap}. " if snap else "")
        + "Building mapping in OpenStreetMap is often incomplete in rural areas; check against recent imagery.")
    ctx.progress(100)
