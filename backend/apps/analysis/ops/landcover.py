"""
Classified rasters (land cover and other class maps): legends, class areas, shares per admin unit,
transition matrices between two dates.

A class table is {code: (label, colour)}, e.g. WORLDCOVER or LULC_ANNUAL below.
"""
import numpy as np

WORLDCOVER = {10: ("Tree cover", "#006400"), 20: ("Shrubland", "#FFBB22"), 30: ("Grassland", "#FFFF4C"),
              40: ("Cropland", "#F096FF"), 50: ("Built-up", "#FA0000"), 60: ("Bare / sparse vegetation", "#B4B4B4"),
              70: ("Snow and ice", "#F0F0F0"), 80: ("Permanent water", "#0064C8"), 90: ("Herbaceous wetland", "#0096A0"),
              95: ("Mangroves", "#00CF75"), 100: ("Moss and lichen", "#FAE6A0")}
LULC_ANNUAL = {1: ("Water", "#419BDF"), 2: ("Trees", "#397D49"), 4: ("Flooded vegetation", "#7A87C6"),
               5: ("Crops", "#E49635"), 7: ("Built area", "#C4281B"), 8: ("Bare ground", "#A59B8F"),
               9: ("Snow and ice", "#A8EBFF"), 11: ("Rangeland", "#E3E2C3")}   # 10 (clouds) is treated as no data
PRODUCTS = {"landcover": WORLDCOVER, "esa_worldcover_2021": WORLDCOVER, "lulc_annual": LULC_ANNUAL}
CROPLAND = {"landcover": 40, "esa_worldcover_2021": 40, "lulc_annual": 5}
TREES = {"landcover": 10, "esa_worldcover_2021": 10, "lulc_annual": 2}
BUILT = {"landcover": 50, "esa_worldcover_2021": 50, "lulc_annual": 7}


def legend(classes, present=None):
    """A classes legend spec for ctx.add_raster (only the codes in `present`, when given)."""
    codes = [c for c in classes if present is None or c in present]
    return {"type": "classes", "items": [{"value": c, "color": classes[c][1], "label": classes[c][0]} for c in codes]}


def codes_of(r, classes):
    """Integer class codes of a raster, 0 where there is no data or the code isn't in the table."""
    a = np.where(np.isfinite(r.data), r.data, 0).astype(np.int32)
    return np.where(np.isin(a, list(classes)), a, 0)


def as_raster(like, codes):
    """Class codes as a Raster on like's grid (0 = no data -> NaN)."""
    return like.like(np.where(codes > 0, codes, np.nan).astype("float32"))


def class_rows(codes, classes, mask, px_km2):
    """[{code, label, area_km2, share}] for the classes present inside mask, largest first."""
    sel = codes[mask & (codes > 0)]
    total = sel.size
    counts = np.bincount(sel, minlength=max(classes) + 1) if total else np.zeros(max(classes) + 1, int)
    rows = [{"code": int(c), "label": classes[c][0], "area_km2": round(float(counts[c]) * px_km2, 2),
             "share": round(100 * float(counts[c]) / total, 2)} for c in classes if total and counts[c] > 0]
    return sorted(rows, key=lambda r: -r["area_km2"])


def zone_rows(codes, classes, zone_masks, inside, px_km2, show):
    """Per admin unit: area, main class and the share of each class in `show` ({key: code})."""
    rows = []
    for _, _, name, m in zone_masks:
        sel = codes[m & inside & (codes > 0)]
        if not sel.size:
            continue
        counts = np.bincount(sel, minlength=max(classes) + 1)
        main = int(np.argmax(counts))
        row = {"unit": name, "area_km2": round(sel.size * px_km2, 1), "main": classes.get(main, ("", ""))[0]}
        for key, code in show.items():
            row[key] = round(100 * float(counts[code]) / sel.size, 1)
        rows.append(row)
    return rows


def transitions(a, b, classes, mask, px_km2):
    """
    Changes between two class maps inside mask: ({(from, to): km²} for from != to, area compared in km²).
    Pixels without a class in either map are left out.
    """
    ok = mask & (a > 0) & (b > 0)
    n = max(classes) + 1
    pair = a[ok].astype(np.int64) * n + b[ok]
    counts = np.bincount(pair, minlength=n * n).reshape(n, n)
    out = {(int(i), int(j)): float(counts[i, j]) * px_km2 for i in classes for j in classes if i != j and counts[i, j]}
    return out, float(ok.sum()) * px_km2
