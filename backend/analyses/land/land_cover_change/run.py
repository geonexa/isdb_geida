"""Land cover change between two years of the Esri / Impact Observatory map: transitions, gains and losses."""
import numpy as np

from apps.analysis.core.errors import AnalysisError
from apps.analysis.ops import landcover as L

CLASSES = L.LULC_ANNUAL
CROPS, TREES, BUILT = 5, 2, 7
MAX_TRANSITIONS = 20


def run(ctx):
    y0, y1 = int(ctx.params["year_from"]), int(ctx.params["year_to"])
    if y0 >= y1:
        raise AnalysisError("The 'to' year must be later than the 'from' year.")
    a_r = ctx.raster("landcover", year=y0)
    ctx.progress(30)
    b_r = ctx.raster("landcover", year=y1)
    ctx.progress(55)
    a, b = L.codes_of(a_r, CLASSES), L.codes_of(b_r, CLASSES)
    inside = ctx.area_mask(a_r)
    px_km2 = a_r.grid.pixel_area_m2 / 1e6
    pairs, compared = L.transitions(a, b, CLASSES, inside, px_km2)
    if not compared:
        raise AnalysisError("The two land cover maps have no classified pixels in common inside the area.")
    changed = sum(pairs.values())
    both = inside & (a > 0) & (b > 0)

    # Transitions and per-class balance ---------------------------------------------------
    trans = [{"from": CLASSES[i][0], "to": CLASSES[j][0], "area_km2": round(v, 2), "share": round(100 * v / compared, 2)}
             for (i, j), v in sorted(pairs.items(), key=lambda kv: -kv[1])[:MAX_TRANSITIONS]]
    class_rows = []
    for c, (label, _) in CLASSES.items():
        before = float((both & (a == c)).sum()) * px_km2
        after = float((both & (b == c)).sum()) * px_km2
        if before or after:
            class_rows.append({"label": label, "from_km2": round(before, 2), "to_km2": round(after, 2),
                               "change_km2": round(after - before, 2),
                               "change_pct": round(100 * (after - before) / before, 1) if before else None})
    class_rows.sort(key=lambda r: -abs(r["change_km2"]))
    net = {c: (float((both & (b == c)).sum()) - float((both & (a == c)).sum())) * px_km2 for c in (CROPS, TREES, BUILT)}

    zone_rows = []
    for _, _, name, m in ctx.zone_masks(a_r, int(ctx.params.get("zone_level") or 2)):
        z = both & m
        n = int(z.sum())
        if not n:
            continue
        row = {"unit": name, "area_km2": round(n * px_km2, 1), "changed": round(100 * float((z & (a != b)).sum()) / n, 1)}
        for key, c in (("crops", CROPS), ("trees", TREES), ("built", BUILT)):
            row[key] = round((float((z & (b == c)).sum()) - float((z & (a == c)).sum())) * px_km2, 2)
        zone_rows.append(row)
    ctx.progress(75)

    # Outputs ---------------------------------------------------------------------------------
    share = 100 * changed / compared
    ctx.add_metric("changed_share", f"Land that changed class {y0}–{y1}", round(share, 1), "% of area")
    ctx.add_metric("cropland_change", "Net change of crops", round(net[CROPS], 2), "km²")
    ctx.add_metric("tree_change", "Net change of trees", round(net[TREES], 2), "km²")
    ctx.add_metric("built_change", "Net change of built area", round(net[BUILT], 2), "km²")
    ctx.add_table("transitions", f"Main changes {y0} → {y1}", [
        {"key": "from", "label": f"From ({y0})"}, {"key": "to", "label": f"To ({y1})"},
        {"key": "area_km2", "label": "Area", "unit": "km²"}, {"key": "share", "label": "Share of area", "unit": "%"}], trans,
        note="Year-to-year differences include map errors; small changes (under about 1% of the area) are uncertain.")
    ctx.add_table("classes", "Gains and losses by class", [
        {"key": "label", "label": "Class"}, {"key": "from_km2", "label": str(y0), "unit": "km²"},
        {"key": "to_km2", "label": str(y1), "unit": "km²"}, {"key": "change_km2", "label": "Change", "unit": "km²"},
        {"key": "change_pct", "label": "Change", "unit": "%"}], class_rows)
    ctx.add_table("per_zone", "Change per administrative unit", [
        {"key": "unit", "label": "Unit"}, {"key": "area_km2", "label": "Area", "unit": "km²"},
        {"key": "changed", "label": "Changed", "unit": "%"}, {"key": "crops", "label": "Crops", "unit": "km²"},
        {"key": "trees", "label": "Trees", "unit": "km²"}, {"key": "built", "label": "Built area", "unit": "km²"}], zone_rows)
    present = set(np.unique(a[inside])) | set(np.unique(b[inside]))
    legend = L.legend(CLASSES, present)
    ctx.add_raster("cover_from", f"Land cover {y0}", L.as_raster(a_r, a), legend=legend)
    ctx.add_raster("cover_to", f"Land cover {y1}", L.as_raster(a_r, b), legend=legend)
    to_codes = np.where(both & (a != b), b, 0)
    new_classes = set(np.unique(to_codes)) - {0}
    ctx.add_raster("changes", f"Changed land, by its {y1} class", L.as_raster(a_r, to_codes),
                   legend=L.legend(CLASSES, new_classes) if new_classes else legend)
    main = trans[0] if trans else None
    ctx.summary(f"{share:.1f}% of the area changed class between {y0} and {y1}"
                + (f"; the largest change is {main['from'].lower()} to {main['to'].lower()} ({main['area_km2']:,.1f} km²)" if main else "")
                + f". Net change: crops {net[CROPS]:+,.1f} km², trees {net[TREES]:+,.1f} km², built area {net[BUILT]:+,.1f} km².")
