"""Field boundaries (Fields of The World): count, size classes, land in fields, per admin unit, density grid."""
import numpy as np
import shapely

from apps.analysis.core.errors import AnalysisError
from apps.analysis.ops import vector

SIZES = [(0.5, "Under 0.5 ha"), (1, "0.5–1 ha"), (2, "1–2 ha"), (5, "2–5 ha"), (10, "5–10 ha"), (50, "10–50 ha"),
         (None, "50 ha and more")]
DENSITY = [(1, "#F7FCB9", "1–10%"), (10, "#ADDD8E", "10–25%"), (25, "#78C679", "25–50%"), (50, "#31A354", "50–75%"),
           (75, "#006837", "75% and more")]
MAX_OUTLINES = 30_000
CAVEAT = ("Fields of The World polygons are model predictions from Sentinel-2 imagery, not surveyed or legal parcels; "
          "smallholder fields are often under-detected.")


def run(ctx):
    year = (ctx.params.get("fields_dataset") or "ftw_fields_2025").rsplit("_", 1)[-1]
    min_score = float(ctx.params.get("min_score") or 0)
    cell_m = float(ctx.params.get("cell_m") or 1000)
    layer = ctx.features("fields")
    ctx.progress(45)
    zones = ctx.vzones(int(ctx.params.get("zone_level") or 2))
    z = zones.assign(layer.geoms)
    score = np.array([float(p.get("score") or 0) for p in layer.props])
    keep = (z > 0) & (score >= min_score)
    fields = layer.subset(keep)
    z, score = z[keep], score[keep]
    n = len(fields)
    ctx.log(f"{len(layer):,} fields in the search box, {n:,} inside the area with score ≥ {min_score:g}")
    area_m2 = np.array([float(p.get("area_m2") or 0) for p in fields.props])
    missing = area_m2 <= 0
    if missing.any():
        area_m2[missing] = shapely.area(fields.geoms[missing])
    ha = area_m2 / 1e4
    total_km2 = float(area_m2.sum()) / 1e6
    area_km2 = ctx.area_km2 or float(zones.area_km2.sum())
    ctx.progress(60)

    # Size classes -------------------------------------------------------------------------
    edges = [b for b, _ in SIZES if b is not None]
    k = np.digitize(ha, edges)
    size_rows = []
    for c, (_, label) in enumerate(SIZES):
        sel = k == c
        size_rows.append({"label": label, "fields": int(sel.sum()), "share": round(100 * sel.sum() / n, 1) if n else 0,
                          "area_km2": round(float(area_m2[sel].sum()) / 1e6, 2),
                          "area_share": round(100 * float(area_m2[sel].sum()) / float(area_m2.sum()), 1) if n else 0})

    # Per unit -------------------------------------------------------------------------------
    counts = zones.count(z)
    by_zone_km2 = zones.count(z, weights=area_m2) / 1e6 if n else np.zeros(zones.size)
    per_zone = []
    for i, gid, name, a in zones.rows():
        sel = z == i
        per_zone.append({"unit": name, "area_km2": round(a, 1), "fields": int(counts[i]),
                         "field_km2": round(float(by_zone_km2[i]), 2),
                         "share": round(100 * float(by_zone_km2[i]) / a, 1) if a else 0,
                         "median_ha": round(float(np.median(ha[sel])), 2) if sel.any() else None})
    per_zone.sort(key=lambda r: (-r["fields"], r["unit"]))
    ctx.progress(75)

    # Density grid: share of each cell's land in fields (fields placed by representative point) ---
    anchors = vector.anchor(fields.geoms)
    cells, cell_share = [], []
    if n:
        ij = np.floor(shapely.get_coordinates(anchors) / cell_m).astype(np.int64)
        keys, inv = np.unique(ij, axis=0, return_inverse=True)
        sums = np.bincount(inv.ravel(), weights=area_m2)
        boxes = shapely.box(keys[:, 0] * cell_m, keys[:, 1] * cell_m, (keys[:, 0] + 1) * cell_m, (keys[:, 1] + 1) * cell_m)
        clipped = shapely.intersection(boxes, zones.union)
        land = shapely.area(clipped)
        ok = land > 0
        cells = clipped[ok]
        cell_share = np.minimum(100 * sums[ok] / land[ok], 100)
    vector.write_geojson(ctx.path("density.geojson"), ctx.frame, cells,
                         [{"share": round(float(s), 1)} for s in cell_share])

    # Outputs ------------------------------------------------------------------------------
    share = 100 * total_km2 / area_km2 if area_km2 else 0
    median = float(np.median(ha)) if n else 0
    ctx.add_metric("field_count", f"Fields ({year})", n, "")
    ctx.add_metric("field_area", "Land in fields", round(total_km2, 1), "km²")
    ctx.add_metric("field_share", "Share of the area in fields", round(share, 1), "%")
    ctx.add_metric("median_size", "Median field size", round(median, 2), "ha")
    ctx.add_table("size_classes", "Fields by size", [
        {"key": "label", "label": "Size"}, {"key": "fields", "label": "Fields"}, {"key": "share", "label": "Of fields", "unit": "%"},
        {"key": "area_km2", "label": "Area", "unit": "km²"}, {"key": "area_share", "label": "Of field land", "unit": "%"}],
        size_rows, note=CAVEAT)
    ctx.add_table("per_zone", "Fields per administrative unit", [
        {"key": "unit", "label": "Unit"}, {"key": "area_km2", "label": "Area", "unit": "km²"},
        {"key": "fields", "label": "Fields"}, {"key": "field_km2", "label": "In fields", "unit": "km²"},
        {"key": "share", "label": "Share", "unit": "%"}, {"key": "median_ha", "label": "Median size", "unit": "ha"}],
        per_zone, note=CAVEAT)
    ctx.add_vector("density", f"Land in fields (per {cell_m / 1000:g} km cell)", "density.geojson", {
        "property": "share", "opacity": 0.75, "steps": [{"from": lo, "color": c, "label": lab} for lo, c, lab in DENSITY]})
    if 0 < n <= MAX_OUTLINES:
        props = [{"area_ha": round(float(h), 2), "score": int(s)} for h, s in zip(ha, score)]
        vector.write_geojson(ctx.path("fields.geojson"), ctx.frame, fields.geoms, props)
        ctx.add_vector("fields", f"Field boundaries {year}", "fields.geojson",
                       {"color": "#15803D", "opacity": 0.6, "width": 0.8})
    elif n:
        ctx.log(f"{n:,} fields: outlines not drawn (more than {MAX_OUTLINES:,}); see the density grid "
                "or the Field boundaries layer in the Data Catalog")
    if not n:
        ctx.summary(f"No Fields of The World polygons for {year} inside the area (score ≥ {min_score:g}). "
                    "Absence of polygons doesn't prove there are no fields: coverage differs by region.")
        return
    ctx.summary(f"{n:,} fields predicted in {year}, covering {total_km2:,.1f} km² ({share:.1f}% of the area); "
                f"median size {median:.2f} ha. Model predictions, not surveyed parcels.")
