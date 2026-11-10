"""
Vector helpers for OpenStreetMap modules (shapely 2, vectorised).

    frame = vector.Frame.around(ctx.area)          # metric projection for the area
    layer = vector.read(path, frame)               # features with geometry in metres
    zones = vector.Zones(ctx.zones(level), frame)  # admin units clipped to the area
    z = zones.assign(layer.geoms)                  # zone index per feature (0 = outside)

Geometry is projected to a spherical Lambert azimuthal equal-area projection
centred on the area: areas are exact on the sphere and distances within a few
hundred km of the centre are off by less than 0.1%, which is plenty for
straight-line distances and counts. Zone indexes are the `i` of ctx.zones().
"""
import csv
import json
import math
from dataclasses import dataclass, field

import numpy as np
import shapely
from shapely import STRtree

R = 6_371_008.8  # mean Earth radius (m)


# Projection ---------------------------------------------------------------------------
class Frame:
    """Lambert azimuthal equal-area (sphere) around lon0, lat0; metres <-> degrees."""

    def __init__(self, lon0, lat0):
        self.lon0, self.lat0 = float(lon0), float(lat0)
        self._l0, self._p0 = math.radians(self.lon0), math.radians(self.lat0)
        self._sp0, self._cp0 = math.sin(self._p0), math.cos(self._p0)

    @classmethod
    def around(cls, geom):
        """Frame centred on a GEOS/shapely geometry or a (w, s, e, n) box."""
        if isinstance(geom, (tuple, list)):
            w, s, e, n = geom
        else:
            w, s, e, n = geom.extent if hasattr(geom, "extent") else geom.bounds
        return cls((w + e) / 2, (s + n) / 2)

    def _fwd(self, xy):
        lam = np.radians(xy[:, 0]) - self._l0
        phi = np.radians(xy[:, 1])
        sp, cp, cl = np.sin(phi), np.cos(phi), np.cos(lam)
        k = np.sqrt(2.0 / np.maximum(1.0 + self._sp0 * sp + self._cp0 * cp * cl, 1e-12))
        return np.column_stack([R * k * cp * np.sin(lam), R * k * (self._cp0 * sp - self._sp0 * cp * cl)])

    def _inv(self, xy):
        x, y = xy[:, 0], xy[:, 1]
        rho = np.hypot(x, y)
        c = 2.0 * np.arcsin(np.clip(rho / (2.0 * R), -1.0, 1.0))
        sc, cc = np.sin(c), np.cos(c)
        safe = np.where(rho == 0, 1.0, rho)
        phi = np.where(rho == 0, self._p0, np.arcsin(np.clip(cc * self._sp0 + y * sc * self._cp0 / safe, -1, 1)))
        lam = self._l0 + np.arctan2(x * sc, rho * self._cp0 * cc - y * self._sp0 * sc)
        return np.column_stack([np.degrees(lam), np.degrees(phi)])

    def to_m(self, geoms):
        return shapely.transform(geoms, self._fwd)

    def to_deg(self, geoms):
        return shapely.transform(geoms, self._inv)

    def lonlat_to_m(self, coords):
        return self._fwd(np.asarray(coords, dtype=float).reshape(-1, 2))


# Reading ------------------------------------------------------------------------------
@dataclass
class Layer:
    geoms: np.ndarray  # shapely geometries in metres (Frame)
    props: list = field(default_factory=list)

    def __len__(self):
        return len(self.geoms)

    def subset(self, mask_or_idx):
        idx = np.flatnonzero(mask_or_idx) if np.asarray(mask_or_idx).dtype == bool else np.asarray(mask_or_idx)
        return Layer(self.geoms[idx], [self.props[i] for i in idx])


def read(path, frame):
    """GeoJSON FeatureCollection -> Layer in the frame's metres. Features without geometry are dropped."""
    with open(path, encoding="utf-8") as fh:
        feats = json.load(fh).get("features", [])
    feats = [f for f in feats if f.get("geometry")]
    if not feats:
        return Layer(np.empty(0, dtype=object), [])
    if all(f["geometry"]["type"] == "Point" for f in feats):
        xy = np.array([f["geometry"]["coordinates"][:2] for f in feats], dtype=float)
        geoms = shapely.points(frame.lonlat_to_m(xy))
    else:
        geoms = frame.to_m(np.array([shapely.geometry.shape(f["geometry"]) for f in feats], dtype=object))
        geoms = shapely.make_valid(geoms)
    return Layer(geoms, [f.get("properties") or {} for f in feats])


def anchor(geoms):
    """A point for each geometry: itself for points, a point on the surface otherwise."""
    geoms = np.asarray(geoms, dtype=object)
    if not len(geoms):
        return geoms
    is_pt = shapely.get_type_id(geoms) == 0
    return np.where(is_pt, geoms, shapely.point_on_surface(geoms))


# Zones --------------------------------------------------------------------------------
class Zones:
    """Admin units (from ctx.zones()) as metric polygons with an index, gid and name."""

    def __init__(self, zones, frame):
        self.ids = np.array([i for i, *_ in zones], dtype=np.int64)
        self.gids = [g for _, g, _, _ in zones]
        self.names = [n for _, _, n, _ in zones]
        self.geoms = shapely.make_valid(frame.to_m(np.array(
            [shapely.geometry.shape(gj) for *_, gj in zones], dtype=object)))
        self.area_km2 = shapely.area(self.geoms) / 1e6
        self.tree = STRtree(self.geoms)
        self.union = shapely.union_all(self.geoms)
        self.size = int(self.ids.max()) + 1 if len(self.ids) else 1

    def name(self, i):
        return dict(zip(self.ids.tolist(), self.names)).get(int(i), "")

    def rows(self):
        """[(i, gid, name, area_km2)] in input order."""
        return list(zip(self.ids.tolist(), self.gids, self.names, self.area_km2.tolist()))

    def assign(self, geoms):
        """Zone index for each geometry's anchor point (0 = outside every zone)."""
        out = np.zeros(len(geoms), dtype=np.int64)
        if not len(geoms):
            return out
        src, hit = self.tree.query(anchor(geoms), predicate="intersects")
        # A point on a shared border falls in two units: keep the first.
        first = np.unique(src, return_index=True)[1]
        out[src[first]] = self.ids[hit[first]]
        return out

    def count(self, labels, weights=None):
        """Per-zone totals of labels from assign(); index = zone id."""
        labels = np.asarray(labels, dtype=np.int64)
        return np.bincount(labels, weights=weights, minlength=self.size)[: max(self.size, 1)]

    def measure(self, geoms, classes=None):
        """Length (km, lines) or area (km², polygons) of geometries cut by each zone.

        Returns {zone_id: {class: value}}; class is None when classes isn't given.
        """
        out = {int(i): {} for i in self.ids}
        if not len(geoms):
            return out
        src, hit = self.tree.query(geoms, predicate="intersects")
        if not len(src):
            return out
        parts = shapely.intersection(geoms[src], self.geoms[hit])
        dims = shapely.get_dimensions(geoms[src])
        size = np.where(dims == 1, shapely.length(parts) / 1e3, shapely.area(parts) / 1e6)
        cls = [None] * len(src) if classes is None else [classes[j] for j in src]
        for z, c, v in zip(self.ids[hit].tolist(), cls, size.tolist()):
            out[z][c] = out[z].get(c, 0.0) + v
        return out


def clip(geoms, area):
    """(indexes, clipped geometries) of the lines/polygons that cross `area`, cut to it.

    Cuts that come out as mixed collections (a line touching the border leaves a point)
    keep only the parts of the original dimension, so they draw as plain lines or polygons.
    """
    geoms = np.asarray(geoms, dtype=object)
    if not len(geoms):
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=object)
    idx = np.flatnonzero(shapely.intersects(geoms, area))
    cut = shapely.intersection(geoms[idx], area) if len(idx) else np.empty(0, dtype=object)
    dims = shapely.get_dimensions(geoms[idx]) if len(idx) else np.empty(0)
    for k in np.flatnonzero(shapely.get_type_id(cut) == 7):  # GeometryCollection
        parts = shapely.get_parts(cut[k])
        parts = parts[shapely.get_dimensions(parts) == dims[k]]
        cut[k] = shapely.union_all(parts) if len(parts) else shapely.Point()
    keep = ~shapely.is_empty(cut)
    return idx[keep], cut[keep]


# Distances ----------------------------------------------------------------------------
def nearest(src, targets):
    """(index of nearest target, distance in m) for each source geometry; (-1, inf) if no targets."""
    n = len(src)
    if not len(targets) or not n:
        return np.full(n, -1, dtype=np.int64), np.full(n, np.inf)
    tree = STRtree(targets)
    pairs, dist = tree.query_nearest(src, return_distance=True, all_matches=False)
    idx = np.full(n, -1, dtype=np.int64)
    d = np.full(n, np.inf)
    idx[pairs[0]] = pairs[1]
    d[pairs[0]] = dist
    return idx, d


def within(src, targets, distance_m):
    """Boolean per source: is any target within distance_m?"""
    out = np.zeros(len(src), dtype=bool)
    if len(src) and len(targets):
        hits = STRtree(targets).query(src, predicate="dwithin", distance=distance_m)[0]
        out[np.unique(hits)] = True
    return out


def band_index(dist_m, bands_m):
    """0 for ≤ bands[0], 1 for ≤ bands[1], ..., len(bands) for beyond the last band."""
    return np.searchsorted(np.asarray(sorted(bands_m), dtype=float), np.asarray(dist_m, dtype=float), side="left")


def band_labels(bands_m):
    b = sorted(bands_m)
    km = [_km(x) for x in b]
    labels = [f"≤ {km[0]}"] + [f"{km[i - 1]}–{km[i]}" for i in range(1, len(b))]
    return labels + [f"> {km[-1]}"]


def _km(m):
    return f"{m / 1000:g} km" if m >= 1000 else f"{m:g} m"


# Grid ---------------------------------------------------------------------------------
def grid_counts(points, cell_m, clip=None):
    """Square cells (metres) with the number of points in each; empty cells omitted.

    Returns (cells, counts): cells clipped to `clip` when given.
    """
    if not len(points):
        return np.empty(0, dtype=object), np.empty(0, dtype=np.int64)
    xy = shapely.get_coordinates(points)
    ij = np.floor(xy / cell_m).astype(np.int64)
    keys, counts = np.unique(ij, axis=0, return_counts=True)
    cells = shapely.box(keys[:, 0] * cell_m, keys[:, 1] * cell_m, (keys[:, 0] + 1) * cell_m, (keys[:, 1] + 1) * cell_m)
    if clip is not None:
        cells = shapely.intersection(cells, clip)
        keep = ~shapely.is_empty(cells)
        cells, counts = cells[keep], counts[keep]
    return cells, counts


# Output -------------------------------------------------------------------------------
def write_geojson(path, frame, geoms, props, precision=6):
    """Write metric geometries back as lon/lat GeoJSON (coordinates rounded)."""
    geoms = frame.to_deg(np.asarray(geoms, dtype=object))
    geoms = shapely.transform(geoms, lambda xy: np.round(xy, precision))
    strings = shapely.to_geojson(geoms) if len(geoms) else []
    with open(path, "w", encoding="utf-8") as fh:
        fh.write('{"type":"FeatureCollection","features":[')
        for k, (g, p) in enumerate(zip(strings, props)):
            fh.write(("," if k else "") + '{"type":"Feature","geometry":' + g + ',"properties":'
                     + json.dumps(p, ensure_ascii=False, default=_json_default) + "}")
        fh.write("]}")
    return path


def write_csv(path, rows, columns=None):
    columns = columns or (list(rows[0].keys()) if rows else ["name"])
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return path


def _json_default(v):
    if isinstance(v, np.generic):
        return v.item()
    raise TypeError(type(v))


def osm_props(props, **computed):
    """A feature's OSM tags (empty ones dropped) followed by values the module computed.

    Map popups show these, so keep the tags as OSM has them (e.g. isced:level, surface).
    """
    out = {k: v for k, v in (props or {}).items() if v not in (None, "")}
    out.update(computed)
    return out


def osm_url(ref):
    """'way/123' -> https://www.openstreetmap.org/way/123 ('' for unknown refs)."""
    return f"https://www.openstreetmap.org/{ref}" if ref and "/" in str(ref) else ""


def lonlat(frame, geoms):
    """(lon, lat) arrays of each geometry's anchor point."""
    if not len(geoms):
        return np.empty(0), np.empty(0)
    xy = shapely.get_coordinates(frame.to_deg(anchor(geoms)))
    return xy[:, 0], xy[:, 1]
