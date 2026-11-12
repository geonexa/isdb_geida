"""Site suitability: the land meeting the user's conditions, a weighted score per cell, classes and the best sites."""
import json

import numpy as np
import shapely
from scipy import ndimage

from apps.analysis.core.errors import AnalysisError
from apps.analysis.core.manifest import parse_criteria
from apps.analysis.data.base import DatasetUnavailable
from apps.analysis.ops import hydro, terrain
from apps.analysis.ops import landcover as LC
from apps.analysis.ops import people as P

DIST_BUFFER_M = 10_000      # OSM features this far outside the area count for distances
MAX_SITES_ON_MAP = 300
SITES_IN_TABLE = 25
# condition layer -> (manifest input, what it is)
DISTANCES = {"dist_roads": ("roads", "roads"), "dist_waterways": ("waterways", "rivers and streams"),
             "dist_places": ("places", "named places"), "dist_power": ("power_lines", "power lines"),
             "dist_schools": ("schools", "schools"), "dist_health": ("health", "health facilities")}
RASTERS = {"treecover": "treecover", "biomass": "biomass", "precipitation": "precipitation", "eta": "eta",
           "water": "water", "travel": "travel"}
YEARLY = {"biomass", "precipitation", "eta"}
# class value, label, colour
CLASSES = [(0, "Not suitable (fails a must-have)", "#BDBDBD"), (1, "Low (score under 50%)", "#FFFFCC"),
           (2, "Moderate (50–74%)", "#C2E699"), (3, "High (75–99%)", "#78C679"), (4, "All conditions met (100%)", "#238443")]
SCORE_RAMP = ["#FFFFCC", "#D9F0A3", "#ADDD8E", "#78C679", "#31A354", "#006837"]


def condition_text(row, layer, year=None):
    if layer["kind"] == "classes":
        names = {str(c["value"]): c["label"] for c in layer.get("classes", [])}
        return f"{layer['label']}: " + ", ".join(names.get(str(v), str(v)) for v in row["classes"])
    label = f"{layer['label']} ({year})" if year and layer["id"] in YEARLY else layer["label"]
    layer = {**layer, "label": label}
    unit = ("" if layer.get("unit") in ("°", "%") else " ") + layer["unit"] if layer.get("unit") else ""
    lo, hi = row.get("min"), row.get("max")
    if lo is not None and hi is not None:
        return f"{layer['label']} {lo:g}–{hi:g}{unit}"
    return f"{layer['label']} {'≥' if lo is not None else '≤'} {lo if lo is not None else hi:g}{unit}"


class Layers:
    """Values of each condition layer on the DEM's grid, read once."""

    def __init__(self, ctx, dem, year):
        self.ctx, self.dem, self.year, self._cache = ctx, dem, year, {}

    def get(self, lid):
        if lid not in self._cache:
            self._cache[lid] = self._read(lid)
        return self._cache[lid]

    def _read(self, lid):
        ctx, dem = self.ctx, self.dem
        if lid == "elevation":
            return dem.data
        if lid == "slope":
            return terrain.slope(dem, "degrees").data
        if lid == "landcover":
            r = ctx.raster("landcover")
            codes = LC.codes_of(r, LC.WORLDCOVER).astype("float32")
            return np.where(codes > 0, codes, np.nan)
        if lid == "population":
            pop, src = P.read_population(ctx, 2025, "worldpop")
            ctx.log(f"Population density from {src['name']} {src['year']}, over 1 km blocks")
            return P.block_density(pop.data, dem.grid.res).astype("float32")
        if lid in RASTERS:
            return ctx.raster(RASTERS[lid], year=self.year if lid in YEARLY else None).data
        if lid in DISTANCES:
            name, what = DISTANCES[lid]
            layer = ctx.try_features(name, ctx.bbox(buffer_m=DIST_BUFFER_M))
            if layer is None or not len(layer):
                ctx.log(f"No {what} in OpenStreetMap within {DIST_BUFFER_M // 1000} km of the area: distances count as over 10 km")
                return np.full(dem.data.shape, np.inf, dtype="float32")
            geoms = P.to_grid_coords(ctx.frame.to_deg(layer.geoms), dem.crs)
            d = P.distance_to(geoms, dem.grid)
            return (d / 1000).astype("float32") if d is not None else np.full(dem.data.shape, np.inf, dtype="float32")
        raise AnalysisError(f"Unknown condition layer: {lid}.")


def met(values, row, layer):
    if layer["kind"] == "classes":
        return np.isin(values, [float(c) for c in row["classes"]])
    ok = np.isfinite(values) | np.isposinf(values)
    with np.errstate(invalid="ignore"):
        if row.get("min") is not None:
            ok &= values >= row["min"]
        if row.get("max") is not None:
            ok &= values <= row["max"]
    return ok


def run(ctx):
    spec = next(p for p in ctx.manifest["parameters"] if p["name"] == "criteria")
    layers = {l["id"]: l for l in spec["layers"]}
    rows, problem = parse_criteria(ctx.params.get("criteria"), spec["layers"])
    if problem:
        raise AnalysisError(problem)
    year = int(ctx.params.get("year") or 2024)
    min_score = float(ctx.params.get("min_score") or 75)
    min_site_km2 = float(ctx.params.get("min_site_km2") or 0)
    level = int(ctx.params.get("zone_level") or 2)

    dem = ctx.raster("dem", buffer_m=terrain.DEM_BUFFER_M)       # sets the 30 m grid (same clip as terrain analyses)
    inside = ctx.area_mask(dem)
    px_km2 = dem.grid.pixel_area_m2 / 1e6
    area_km2 = float(inside.sum()) * px_km2
    src = Layers(ctx, dem, year)
    ctx.progress(15)

    # Each condition: met or not, per cell ------------------------------------------------------------
    weights = np.array([r["weight"] for r in rows], dtype="float64")
    total_w = weights.sum()
    score = np.zeros(dem.data.shape, dtype="float32")
    excluded = np.zeros(dem.data.shape, dtype=bool)
    all_met = np.ones(dem.data.shape, dtype=bool)
    crit_rows = []
    for n, row in enumerate(rows):
        layer = layers[row["layer"]]
        try:
            m = met(src.get(row["layer"]), row, layer)
        except DatasetUnavailable as exc:
            raise AnalysisError(f"{layer['label']}: {exc}") from None
        all_met &= m
        if total_w > 0:
            score += (row["weight"] / total_w * 100) * m
        if row["must"]:
            excluded |= ~m
        crit_rows.append({"condition": condition_text(row, layer, year), "weight": round(100 * row["weight"] / total_w, 1) if total_w else 0,
                          "must": "yes" if row["must"] else "", "met_km2": round(float((m & inside).sum()) * px_km2, 2),
                          "met_share": round(100 * float((m & inside).sum()) / max(int(inside.sum()), 1), 1)})
        ctx.progress(15 + 55 * (n + 1) / len(rows))
    if total_w == 0:                     # only must-haves: suitable where all are met
        score = np.where(all_met, 100.0, 0.0).astype("float32")
    score = np.round(score, 3)

    cls = np.select([excluded, score >= 100 - 1e-3, score >= 75, score >= 50], [0, 4, 3, 2], default=1).astype("float32")
    cls[~inside] = np.nan
    suitable = inside & ~excluded & (score >= min_score - 1e-3)
    suit_km2 = float(suitable.sum()) * px_km2

    class_rows = [{"class": label, "area_km2": round(float(((cls == v) & inside).sum()) * px_km2, 2),
                   "share": round(100 * float(((cls == v) & inside).sum()) / max(int(inside.sum()), 1), 1)}
                  for v, label, _ in CLASSES]
    zone_rows = []
    for _, _, name, z in ctx.zone_masks(dem, level):
        z = z & inside
        if not z.any():
            continue
        zone_rows.append({"unit": name, "area_km2": round(float(z.sum()) * px_km2, 1),
                          "suitable_km2": round(float((z & suitable).sum()) * px_km2, 2),
                          "suitable_share": round(100 * float((z & suitable).sum()) / float(z.sum()), 1),
                          "excluded_share": round(100 * float((z & excluded).sum()) / float(z.sum()), 1)})
    zone_rows.sort(key=lambda r: -r["suitable_km2"])
    ctx.progress(80)

    # Sites: connected suitable cells -------------------------------------------------------------
    labels, n_lab = ndimage.label(suitable, structure=np.ones((3, 3), bool))
    sizes = np.bincount(labels.ravel())
    min_cells = max(1, int(np.ceil(min_site_km2 / px_km2))) if min_site_km2 > 0 else 1
    keep = [int(k) for k in np.argsort(-sizes) if k > 0 and sizes[k] >= min_cells]
    site_rows, geoms, props = [], [], []
    if keep:
        mean_score = ndimage.mean(score, labels=labels, index=keep)
        centres = ndimage.center_of_mass(suitable, labels=labels, index=keep)
        polys = hydro.polygons(labels, dem.transform, set(keep[:MAX_SITES_ON_MAP]))
        cx = [dem.transform * (c + 0.5, r + 0.5) for r, c in centres]
        ll = hydro.to_lonlat([shapely.Point(x, y) for x, y in cx], dem.crs)
        for i, k in enumerate(keep):
            row = {"site": f"S-{i + 1:02d}", "area_km2": round(float(sizes[k]) * px_km2, 2),
                   "mean_score": round(float(mean_score[i]), 1), "lon": round(ll[i].x, 5), "lat": round(ll[i].y, 5)}
            if i < SITES_IN_TABLE:
                site_rows.append(row)
            if k in polys:
                geoms.append(polys[k])
                props.append({"site": row["site"], "area_km2": row["area_km2"], "mean_score": row["mean_score"]})
    path = ctx.path("sites.geojson")
    if geoms:
        g_ll = hydro.to_lonlat(geoms, dem.crs)
        feats = [{"type": "Feature", "geometry": json.loads(shapely.to_geojson(shapely.set_precision(g, 1e-6))), "properties": p}
                 for g, p in zip(g_ll, props)]
    else:
        feats = []
    path.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    ctx.progress(90)

    # Outputs -----------------------------------------------------------------------------------
    share = 100 * suit_km2 / area_km2 if area_km2 else 0
    excl_share = 100 * float((excluded & inside).sum()) / max(int(inside.sum()), 1)
    ctx.add_metric("suitable_km2", f"Suitable land (score {min_score:g}% or more)", round(suit_km2, 1), "km²")
    ctx.add_metric("suitable_share", "Of the area", round(share, 1), "%")
    ctx.add_metric("excluded_share", "Excluded by a must-have", round(excl_share, 1), "%")
    ctx.add_metric("site_count", f"Sites of {min_site_km2:g} km² or more", len(keep), "")
    ctx.add_table("criteria", "Conditions", [
        {"key": "condition", "label": "Condition"}, {"key": "weight", "label": "Weight", "unit": "%"},
        {"key": "must", "label": "Must-have"}, {"key": "met_km2", "label": "Area meeting it", "unit": "km²"},
        {"key": "met_share", "label": "Of the area", "unit": "%"}], crit_rows,
        note="Weights are scaled to 100%. A cell with no data for a layer counts as not meeting that condition.")
    ctx.add_table("classes", "Suitability classes", [
        {"key": "class", "label": "Class"}, {"key": "area_km2", "label": "Area", "unit": "km²"},
        {"key": "share", "label": "Of the area", "unit": "%"}], class_rows,
        note="Score = weighted share of the conditions a cell meets. Cells failing a must-have are not suitable, whatever their score.")
    ctx.add_table("per_zone", "Suitable land per administrative unit", [
        {"key": "unit", "label": "Unit"}, {"key": "area_km2", "label": "Area", "unit": "km²"},
        {"key": "suitable_km2", "label": "Suitable", "unit": "km²"}, {"key": "suitable_share", "label": "Suitable", "unit": "%"},
        {"key": "excluded_share", "label": "Excluded", "unit": "%"}], zone_rows)
    ctx.add_table("sites", "Largest suitable sites", [
        {"key": "site", "label": "Site"}, {"key": "area_km2", "label": "Area", "unit": "km²"},
        {"key": "mean_score", "label": "Mean score", "unit": "%"}, {"key": "lon", "label": "Longitude"},
        {"key": "lat", "label": "Latitude"}], site_rows,
        note=f"Connected cells with a score of {min_score:g}% or more, at least {min_site_km2:g} km²; the {SITES_IN_TABLE} largest.")
    ctx.add_raster("suitability", "Suitability", dem.like(cls),
                   legend={"type": "classes", "items": [{"value": v, "color": c, "label": l} for v, l, c in CLASSES]})
    ctx.add_raster("score", "Suitability score", dem.like(np.where(excluded, np.nan, score).astype("float32")),
                   legend={"type": "ramp", "palette": SCORE_RAMP, "min": 0, "max": 100, "unit": "%"})
    ctx.add_vector("site_polygons", "Suitable sites", "sites.geojson",
                   {"color": "#1B7837", "outline": "#00441B", "opacity": 0.3, "width": 2, "shape": "polygon"})
    best = site_rows[0] if site_rows else None
    ctx.summary(f"{suit_km2:,.1f} km² ({share:.0f}% of the area) meet the conditions with a score of {min_score:g}% or more; "
                f"{excl_share:.0f}% of the area fails a must-have. "
                + (f"{len(keep)} sites of {min_site_km2:g} km² or more; the largest is {best['area_km2']:,.1f} km² "
                   f"(mean score {best['mean_score']:.0f}%). " if best else "No site reaches the smallest size. ")
                + f"{len(rows)} conditions on a 30 m grid.")
