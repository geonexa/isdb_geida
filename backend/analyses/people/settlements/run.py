"""Settlements and urbanisation: GHSL degree of urbanisation with population, per admin unit; OSM named places."""
import numpy as np
from scipy.ndimage import uniform_filter

from apps.analysis.core.errors import AnalysisError
from apps.analysis.data.base import DatasetUnavailable
from apps.analysis.data.people import SMOD_CLASSES
from apps.analysis.ops import people as P
from apps.analysis.ops import vector

GROUPS = {"urban": "Urban", "peri-urban": "Peri-urban", "rural": "Rural"}
PLACE_ORDER = {"city": 0, "town": 1, "suburb": 2, "village": 3, "hamlet": 4, "isolated_dwelling": 5, "locality": 6}
MAX_PLACES = 40
RADIUS_M = 1000


def run(ctx):
    year = int(ctx.params.get("year") or 2020)
    pop = ctx.raster("population", year=year)
    ctx.progress(30)
    smod = ctx.raster("smod", year=year)
    ctx.progress(50)
    inside = ctx.area_mask(pop)
    cells = np.nan_to_num(pop.data, nan=0.0)
    codes = np.where(np.isfinite(smod.data), smod.data, 0).astype(np.int16)
    px_km2 = pop.grid.pixel_area_m2 / 1e6
    total = P.people(cells, inside)
    if not inside.any():
        raise AnalysisError("The area of influence is smaller than one grid cell.")
    area = float(inside.sum()) * px_km2

    rows = []
    for code, (label, _, group) in SMOD_CLASSES.items():
        sel = inside & (codes == code)
        if sel.any():
            p = P.people(cells, sel)
            rows.append({"label": label, "group": GROUPS.get(group, "Water"), "people": round(p),
                         "share": round(100 * p / total, 1) if total else 0, "area_km2": round(float(sel.sum()) * px_km2, 1),
                         "area_share": round(100 * float(sel.sum()) * px_km2 / area, 1)})
    share = {g: sum(r["share"] for r in rows if r["group"] == GROUPS[g]) for g in GROUPS}

    group_of = {c: g for c, (_, _, g) in SMOD_CLASSES.items()}
    zone_rows = []
    for _, _, name, m in ctx.zone_masks(pop, int(ctx.params.get("zone_level") or 2)):
        z = m & inside
        p = P.people(cells, z)
        if not z.any() or not p:
            continue
        row = {"unit": name, "people": round(p)}
        for g in GROUPS:
            sel = z & np.isin(codes, [c for c, gg in group_of.items() if gg == g])
            row[g.replace("-", "")] = round(100 * P.people(cells, sel) / p, 1)
        zone_rows.append(row)
    zone_rows.sort(key=lambda r: -r["people"])
    ctx.progress(70)

    # Named places: settlement class and people within ~1 km (window sum on the population grid)
    place_rows = None
    try:
        layer = ctx.try_features("places", ctx.bbox())
    except DatasetUnavailable as exc:
        layer = None
        ctx.log(f"OSM places not available: {exc}")
    if layer is not None and len(layer):
        lon, lat = vector.lonlat(ctx.frame, layer.geoms)
        import shapely
        pts = P.to_grid_coords(shapely.points(np.column_stack([lon, lat])), pop.crs)
        xy = shapely.get_coordinates(pts)
        col, row = (~pop.transform) * (xy[:, 0], xy[:, 1])
        col, row = np.floor(col).astype(int), np.floor(row).astype(int)
        ok = (row >= 0) & (row < cells.shape[0]) & (col >= 0) & (col < cells.shape[1])
        ok[ok] &= inside[row[ok], col[ok]]
        k = max(1, int(round(2 * RADIUS_M / pop.grid.res)) | 1)        # odd window of about 2 km
        around = uniform_filter(cells, size=k, mode="constant") * k * k * (np.pi / 4)   # disc of radius 1 km
        place_rows = []
        for i in np.flatnonzero(ok):
            p = layer.props[i]
            kind = (p.get("place") or "").strip()
            code = int(codes[row[i], col[i]])
            place_rows.append({"name": p.get("name") or p.get("name:en") or "(unnamed)", "type": kind.replace("_", " ") or "place",
                               "class": SMOD_CLASSES.get(code, ("Unclassified",))[0], "people_1km": round(float(around[row[i], col[i]]), -1),
                               "_order": PLACE_ORDER.get(kind, 9)})
        counts = {}
        for r in place_rows:
            counts[r["type"]] = counts.get(r["type"], 0) + 1
        place_rows.sort(key=lambda r: (-r["people_1km"], r["_order"]))
        n_places = len(place_rows)
        place_rows = [{k: v for k, v in r.items() if k != "_order"} for r in place_rows[:MAX_PLACES]]
    ctx.progress(85)

    label = f"{year}{' (projection)' if year > 2020 else ''}"
    ctx.add_metric("urban_share", "Urban population", round(share["urban"], 1), "% of people")
    ctx.add_metric("periurban_share", "Peri-urban population", round(share["peri-urban"], 1), "% of people")
    ctx.add_metric("rural_share", "Rural population", round(share["rural"], 1), "% of people")
    ctx.add_table("classes", f"Degree of urbanisation, {label}", [
        {"key": "label", "label": "Settlement class"}, {"key": "group", "label": "Group"}, {"key": "people", "label": "People"},
        {"key": "share", "label": "Of people", "unit": "%"}, {"key": "area_km2", "label": "Area", "unit": "km²"},
        {"key": "area_share", "label": "Of area", "unit": "%"}], rows,
        note="GHSL settlement model (degree of urbanisation, level 2): classes from 1 km population density and contiguity.")
    ctx.add_table("per_zone", "Urban, peri-urban and rural population per administrative unit", [
        {"key": "unit", "label": "Unit"}, {"key": "people", "label": "People"}, {"key": "urban", "label": "Urban", "unit": "%"},
        {"key": "periurban", "label": "Peri-urban", "unit": "%"}, {"key": "rural", "label": "Rural", "unit": "%"}], zone_rows)
    if place_rows is not None:
        ctx.add_metric("places_count", "Named places (OpenStreetMap)", n_places, "")
        ctx.add_table("places", "Largest named places", [
            {"key": "name", "label": "Place"}, {"key": "type", "label": "OSM type"}, {"key": "class", "label": "Settlement class"},
            {"key": "people_1km", "label": "People within 1 km"}], place_rows,
            note=f"{n_places} named places in the area ({', '.join(f'{v} {k}' for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))}). "
                 "People within 1 km of the OSM point, from GHSL; nearby places overlap.")
    present = {int(c) for c in np.unique(codes[inside]) if int(c) in SMOD_CLASSES}
    ctx.add_raster("smod", f"Degree of urbanisation, {label}", smod.like(np.where(codes > 0, codes, np.nan).astype("float32")),
                   legend={"type": "classes", "items": [{"value": c, "color": col, "label": lab}
                                                        for c, (lab, col, _) in SMOD_CLASSES.items() if c in present]})
    ctx.summary(f"In {label}, {share['urban']:.0f}% of the area's {total:,.0f} people lived in urban settlements, "
                f"{share['peri-urban']:.0f}% in peri-urban and {share['rural']:.0f}% in rural areas (GHSL degree of urbanisation)"
                + (f"; OpenStreetMap names {n_places} places" if place_rows is not None else "") + ".")
