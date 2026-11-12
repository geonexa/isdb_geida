"""Forest cover in 2000 and loss per year (Hansen / UMD Global Forest Change v1.12), per admin unit."""
import numpy as np

from apps.analysis.core.errors import AnalysisError

LAST_YEAR = 2024
PERIODS = [(2001, 2005, "#FFF7BC"), (2006, 2010, "#FEC44F"), (2011, 2015, "#FE9929"), (2016, 2020, "#D95F0E"),
           (2021, 2024, "#993404")]
GREENS = ["#F7FCF5", "#DBF1D5", "#ADDEA7", "#74C476", "#37A055", "#0C7734", "#00441B"]


def _span(a, b):
    return str(a) if a == b else f"{a}–{b}"


def run(ctx):
    thr = float(ctx.params["threshold"])
    y0 = int(ctx.params["from_year"])
    cover = ctx.raster("treecover")
    ctx.progress(30)
    loss = ctx.raster("lossyear")
    ctx.progress(55)
    inside = ctx.area_mask(cover) & cover.valid
    if not inside.any():
        raise AnalysisError("The forest change map has no data inside the area of influence.")
    px_km2 = cover.grid.pixel_area_m2 / 1e6
    forest = inside & (cover.data >= thr)
    ly = np.where(loss.valid, loss.data, 0).round().astype(np.int16) + 2000   # 2000 = no loss
    lost = forest & (ly >= y0) & (ly <= LAST_YEAR)
    forest_km2 = float(forest.sum()) * px_km2
    loss_km2 = float(lost.sum()) * px_km2
    area_km2 = float(inside.sum()) * px_km2

    by_year, cum = [], 0.0
    counts = np.bincount(ly[lost] - 2000, minlength=LAST_YEAR - 1999)
    for y in range(y0, LAST_YEAR + 1):
        km2 = float(counts[y - 2000]) * px_km2
        cum += km2
        by_year.append({"year": y, "loss_km2": round(km2, 2), "cumulative_km2": round(cum, 2),
                        "share": round(100 * km2 / forest_km2, 2) if forest_km2 else 0})

    zone_rows = []
    for _, _, name, m in ctx.zone_masks(cover, int(ctx.params.get("zone_level") or 2)):
        z = inside & m
        if not z.any():
            continue
        f = float((forest & m).sum()) * px_km2
        lo = float((lost & m).sum()) * px_km2
        zone_rows.append({"unit": name, "area_km2": round(float(z.sum()) * px_km2, 1), "forest_km2": round(f, 2),
                          "forest_share": round(100 * f / (float(z.sum()) * px_km2), 1), "loss_km2": round(lo, 2),
                          "loss_share": round(100 * lo / f, 1) if f else 0})
    zone_rows.sort(key=lambda r: -r["loss_km2"])
    ctx.progress(75)

    period_code = np.zeros(ly.shape, dtype="float32")
    shown = [(a, b, c) for a, b, c in PERIODS if b >= y0]
    for k, (a, b, _) in enumerate(shown, start=1):
        period_code[lost & (ly >= max(a, y0)) & (ly <= b)] = k
    since = f"{y0}–{LAST_YEAR}"
    ctx.add_metric("forest_2000", f"Forest in 2000 (canopy ≥ {thr:g}%)", round(forest_km2, 1), "km²")
    ctx.add_metric("forest_share", "Forest share in 2000", round(100 * forest_km2 / area_km2, 1), "% of area")
    ctx.add_metric("loss_km2", f"Forest lost {since}", round(loss_km2, 2), "km²")
    ctx.add_metric("loss_share", "Share of 2000 forest lost", round(100 * loss_km2 / forest_km2, 1) if forest_km2 else 0, "%")
    ctx.add_table("loss_by_year", "Forest loss per year", [
        {"key": "year", "label": "Year"}, {"key": "loss_km2", "label": "Loss", "unit": "km²"},
        {"key": "cumulative_km2", "label": "Cumulative", "unit": "km²"},
        {"key": "share", "label": "Of 2000 forest", "unit": "%"}], by_year,
        note="Stand-replacing loss of forest present in 2000 (clearing, fire, harvest); regrowth is not subtracted.")
    ctx.add_table("per_zone", "Forest and loss per administrative unit", [
        {"key": "unit", "label": "Unit"}, {"key": "area_km2", "label": "Area", "unit": "km²"},
        {"key": "forest_km2", "label": "Forest 2000", "unit": "km²"}, {"key": "forest_share", "label": "Forest", "unit": "%"},
        {"key": "loss_km2", "label": f"Loss {since}", "unit": "km²"}, {"key": "loss_share", "label": "Of forest", "unit": "%"}],
        zone_rows)
    ctx.add_raster("treecover", "Tree canopy cover in 2000", cover,
                   legend={"type": "ramp", "palette": GREENS, "min": 0, "max": 100, "unit": "%"})
    ctx.add_raster("loss", f"Forest loss {since}, by period", cover.like(np.where(period_code > 0, period_code, np.nan)),
                   legend={"type": "classes", "items": [{"value": k, "color": c, "label": _span(max(a, y0), b)}
                                                        for k, (a, b, c) in enumerate(shown, start=1)]})
    worst = max(by_year, key=lambda r: r["loss_km2"]) if by_year else None
    ctx.summary(f"Forest covered {forest_km2:,.1f} km² ({100 * forest_km2 / area_km2:.0f}% of the area) in 2000; "
                f"{loss_km2:,.1f} km² was lost from {y0} to {LAST_YEAR}"
                + (f" ({100 * loss_km2 / forest_km2:.1f}% of it)" if forest_km2 else "")
                + (f", most in {worst['year']} ({worst['loss_km2']:,.1f} km²)" if worst and worst["loss_km2"] else "") + ".")
