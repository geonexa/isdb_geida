"""Biomass production (FAO WaPOR v3 level 1, 300 m, global): totals, per hectare, on cropland, per admin unit, change against another year."""
import numpy as np

from apps.analysis.core.errors import AnalysisError
from apps.analysis.data.base import DatasetUnavailable
from apps.analysis.ops import landcover as L

YLGN = ["#FFFFE5", "#EDF8B2", "#BBE395", "#78C679", "#379E54", "#0C713B", "#004529"]
CHANGE = ["#8C510A", "#D8B365", "#F6E8C3", "#F5F5F5", "#C7EAE5", "#5AB4AC", "#01665E"]


def run(ctx):
    year = int(ctx.params["year"])
    other = int(ctx.params.get("compare_year") or 0)
    if other and other == year:
        raise AnalysisError("Choose a comparison year different from the year analysed (or 0 for none).")
    bio = ctx.raster("biomass", year=year)
    ctx.progress(30)
    inside = ctx.area_mask(bio)
    ok = inside & bio.valid
    if not ok.any():
        raise AnalysisError("WaPOR has no biomass values inside the area for this year.")
    px_ha = bio.grid.pixel_area_m2 / 1e4
    kg_ha = bio.data
    total_t = float(np.nansum(kg_ha[ok])) * px_ha / 1000
    mean = float(kg_ha[ok].mean())

    prev = None
    if other:
        prev = ctx.raster("biomass", year=other)
        ctx.progress(45)

    codes, lc_rows, crop_mean = None, None, None
    try:
        lc = ctx.raster("landcover")
        codes = L.codes_of(lc, L.WORLDCOVER)
        lc_rows = []
        for code, (label, _) in L.WORLDCOVER.items():
            sel = ok & (codes == code)
            if sel.sum() * px_ha >= 1:
                lc_rows.append({"label": label, "mean": round(float(kg_ha[sel].mean())),
                                "total_t": round(float(kg_ha[sel].sum()) * px_ha / 1000),
                                "area_km2": round(float(sel.sum()) * px_ha / 100, 1)})
        lc_rows.sort(key=lambda r: -r["total_t"])
        crop = ok & (codes == 40)
        crop_mean = float(kg_ha[crop].mean()) if crop.any() else None
    except (AnalysisError, DatasetUnavailable) as exc:
        ctx.log(f"Land cover not available, no cropland figures: {exc}")
    ctx.progress(60)

    zone_rows = []
    for _, _, name, m in ctx.zone_masks(bio, int(ctx.params.get("zone_level") or 2)):
        sel = ok & m
        if not sel.any():
            continue
        row = {"unit": name, "mean": round(float(kg_ha[sel].mean())), "total_t": round(float(kg_ha[sel].sum()) * px_ha / 1000),
               "area_km2": round(float(sel.sum()) * px_ha / 100, 1)}
        if codes is not None:
            c = sel & (codes == 40)
            row["crop_mean"] = round(float(kg_ha[c].mean())) if c.any() else None
        if prev is not None:
            both = sel & prev.valid
            before = float(prev.data[both].sum())
            row["change"] = round(100 * (float(kg_ha[both].sum()) - before) / before, 1) if before else None
        zone_rows.append(row)
    ctx.progress(75)

    ctx.add_metric("total_biomass", f"Total biomass {year}", round(total_t), "tonnes dry matter")
    ctx.add_metric("mean_biomass", "Mean biomass", round(mean), "kg/ha")
    if crop_mean is not None:
        ctx.add_metric("cropland_mean", "Mean on cropland", round(crop_mean), "kg/ha")
    change_pct = None
    if prev is not None:
        both = ok & prev.valid
        before = float(prev.data[both].sum())
        change_pct = 100 * (float(kg_ha[both].sum()) - before) / before if before else None
        if change_pct is not None:
            ctx.add_metric("change_pct", f"Change since {other}" if other < year else f"Change against {other}",
                           round(change_pct, 1), "%")
    cols = [{"key": "unit", "label": "Unit"}, {"key": "mean", "label": "Mean", "unit": "kg/ha"},
            {"key": "total_t", "label": "Total", "unit": "t"}, {"key": "area_km2", "label": "Area", "unit": "km²"}]
    if codes is not None:
        cols.insert(2, {"key": "crop_mean", "label": "On cropland", "unit": "kg/ha"})
    if prev is not None:
        cols.append({"key": "change", "label": f"Change vs {other}", "unit": "%"})
    ctx.add_table("per_zone", f"Biomass production {year} per administrative unit", cols, zone_rows)
    if lc_rows:
        ctx.add_table("by_landcover", f"Biomass production {year} by land cover class", [
            {"key": "label", "label": "Land cover"}, {"key": "mean", "label": "Mean", "unit": "kg/ha"},
            {"key": "total_t", "label": "Total", "unit": "t"}, {"key": "area_km2", "label": "Area", "unit": "km²"}], lc_rows,
            note="Land cover from ESA WorldCover 2021, resampled to WaPOR's 300 m pixels (class at the pixel centre).")
    ctx.add_raster("biomass", f"Biomass production {year}", bio,
                   legend={"type": "ramp", "palette": YLGN, "min": 0, "max": 25000, "unit": "kg/ha", "open_max": True})
    if prev is not None:
        with np.errstate(divide="ignore", invalid="ignore"):
            pct = np.where(prev.data > 100, 100 * (kg_ha - prev.data) / prev.data, np.nan)
        ctx.add_raster("change", f"Biomass change {other}–{year}" if other < year else f"Biomass {year} against {other}",
                       bio.like(np.clip(pct, -100, 100).astype("float32")),
                       legend={"type": "ramp", "palette": CHANGE, "min": -50, "max": 50, "unit": "%",
                               "open_min": True, "open_max": True})
    ctx.summary(f"The area produced about {total_t:,.0f} t of biomass (dry matter) in {year}, {mean:,.0f} kg/ha on average"
                + (f", {crop_mean:,.0f} kg/ha on cropland" if crop_mean is not None else "")
                + (f"; {change_pct:+.0f}% against {other}" if change_pct is not None else "") + ". FAO WaPOR v3 level 1, 300 m.")
