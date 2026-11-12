"""
Hydrology on the run grid with WhiteboxTools (engines/whitebox.py): conditioned DEM, D8 flow direction and
accumulation, streams with Strahler order, and helpers to bring vector output back as lon/lat geometries.

    dem = ctx.raster("dem", buffer_m=MARGIN_M)
    f = hydro.flow(ctx, dem)                       # cached per DEM clip: dem, filled, dir, acc
    net = hydro.streams(ctx, f, threshold_cells)   # streams, Strahler order, stream lines (order per line)

DEM conditioning: least-cost breaching of depressions (Lindsay 2016), then filling what remains, so every
cell drains to the edge. D8 pointers use WhiteboxTools' encoding (1 NE, 2 E, 4 SE, 8 S, 16 SW, 32 W, 64 NW,
128 N).
"""
import json
from pathlib import Path

import numpy as np

from ..data import cache
from ..engines import whitebox
from . import grid as G

MARGIN_M = 5000
FLOW_VERSION = "wbt-1"
BREACH_MAX_CELLS = 200     # longest breach channel, in cells (6 km at 30 m); deeper pits are filled


class Flow:
    def __init__(self, folder, grid_):
        self.folder, self.grid = Path(folder), grid_
        self.dem, self.filled = self.folder / "dem.tif", self.folder / "filled.tif"
        self.dir, self.acc = self.folder / "dir.tif", self.folder / "acc.tif"

    def accumulation(self):
        """Upstream cells (including the cell itself) as a Raster."""
        return G.read(self.acc)


def flow(ctx, dem):
    """Conditioned DEM, D8 flow direction and accumulation (cells) for the DEM clip, cached."""
    src = Path(str(dem.info.get("source", "")))
    stamp = [src.stat().st_size, int(src.stat().st_mtime)] if src.is_file() else None   # a replaced DEM file is a new DEM
    parts = {"dem": dem.info, "file": stamp, "grid": [str(dem.crs), tuple(dem.transform), dem.data.shape], "v": FLOW_VERSION}
    folder = cache.path_for("flow", parts, suffix="")
    f = Flow(folder, dem.grid)
    if f.acc.exists() and f.dir.exists():
        ctx.log("Flow direction and accumulation reused from the cache")
        return f
    folder.mkdir(parents=True, exist_ok=True)
    whitebox.plain_tif(dem, f.dem)
    wbt = whitebox.tools(folder, log=ctx.log)
    whitebox.call(wbt, "breach_depressions_least_cost", f.dem.name, f.filled.name, dist=BREACH_MAX_CELLS, fill=True)
    whitebox.call(wbt, "d8_pointer", f.filled.name, f.dir.name)
    whitebox.call(wbt, "d8_flow_accumulation", f.filled.name, f.acc.name, out_type="cells")
    return f


class Network:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.streams, self.order, self.lines = self.folder / "streams.tif", self.folder / "order.tif", self.folder / "streams.shp"


def streams(ctx, f, threshold_cells, folder=None):
    """Stream cells where accumulation >= threshold_cells, their Strahler order, and lines (one per link, with its order)."""
    folder = Path(folder or ctx.scratch("hydro"))
    folder.mkdir(parents=True, exist_ok=True)
    net = Network(folder)
    wbt = whitebox.tools(folder, log=ctx.log)
    whitebox.call(wbt, "extract_streams", str(f.acc), net.streams.name, threshold=max(1.0, float(threshold_cells)))
    whitebox.call(wbt, "strahler_stream_order", str(f.dir), net.streams.name, net.order.name)
    whitebox.call(wbt, "raster_streams_to_vector", net.order.name, str(f.dir), net.lines.name)
    return net


def read_lines(path, crs, field="STRM_VAL"):
    """Lines of a vector file in `crs` as ([value of field], [shapely geometry in lon/lat])."""
    import shapely
    from osgeo import ogr
    from rasterio.warp import transform

    ogr.UseExceptions()
    ds = ogr.Open(str(path))
    layer = ds.GetLayer(0)
    values, geoms = [], []
    for feat in layer:
        g = feat.GetGeometryRef()
        if g is None or "LINE" not in g.GetGeometryName().upper():
            continue
        values.append(feat.GetField(field))
        geoms.append(shapely.from_wkb(bytes(g.ExportToWkb())))
    ds = None
    if not geoms:
        return [], np.empty(0, dtype=object)

    def to_ll(xy):
        xs, ys = transform(crs, "EPSG:4326", xy[:, 0].tolist(), xy[:, 1].tolist())
        return np.column_stack([xs, ys])
    return values, shapely.transform(np.array(geoms, dtype=object), to_ll)


def write_lines_geojson(path, geoms_ll, props, precision=6):
    import shapely
    geoms = shapely.transform(np.asarray(geoms_ll, dtype=object), lambda xy: np.round(xy, precision))
    feats = [{"type": "Feature", "geometry": json.loads(shapely.to_geojson(g)), "properties": p} for g, p in zip(geoms, props)]
    Path(path).write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    return path


# Sub-catchments -----------------------------------------------------------------------------------------
# WhiteboxTools D8 pointer -> (row offset, column offset)
WBT_D8 = {1: (-1, 1), 2: (0, 1), 4: (1, 1), 8: (1, 0), 16: (1, -1), 32: (0, -1), 64: (-1, -1), 128: (-1, 0)}


def subbasins(ctx, f, threshold_cells, folder=None):
    """Sub-catchments split at stream confluences (WhiteboxTools Subbasins on streams from threshold_cells): label Raster."""
    folder = Path(folder or ctx.scratch("hydro"))
    folder.mkdir(parents=True, exist_ok=True)
    wbt = whitebox.tools(folder, log=ctx.log)
    whitebox.call(wbt, "extract_streams", str(f.acc), "basin_streams.tif", threshold=max(1.0, float(threshold_cells)))
    whitebox.call(wbt, "subbasins", str(f.dir), "basin_streams.tif", "subbasins.tif")
    labels = G.read(folder / "subbasins.tif")
    return labels, G.read(folder / "basin_streams.tif")


def downstream(rows, cols, dirs):
    """(row, col) of the cell each given cell drains into (-1, -1 where it leaves the grid or has no direction)."""
    d = np.where(np.isfinite(dirs[rows, cols]), dirs[rows, cols], 0).astype(int)
    r2, c2 = np.full(rows.shape, -1), np.full(cols.shape, -1)
    for code, (dr, dc) in WBT_D8.items():
        sel = d == code
        r2[sel], c2[sel] = rows[sel] + dr, cols[sel] + dc
    h, w = dirs.shape
    off = (r2 < 0) | (r2 >= h) | (c2 < 0) | (c2 >= w)
    r2[off], c2[off] = -1, -1
    return r2, c2


def outlets(labels, acc):
    """{label: (row, col)} of each unit's outlet, its cell of highest flow accumulation."""
    lab = np.where(np.isfinite(labels), labels, 0).astype(np.int64).ravel()
    a = np.where(np.isfinite(acc), acc, -1).ravel()
    sel = np.flatnonzero(lab > 0)
    order = sel[np.lexsort((a[sel], lab[sel]))]          # by label, then accumulation ascending
    last = np.r_[np.flatnonzero(np.diff(lab[order])), order.size - 1]
    w = labels.shape[1]
    return {int(lab[order[i]]): (int(order[i] // w), int(order[i] % w)) for i in last}


def merge_small(labels, acc, dirs, min_cells):
    """Merge units smaller than min_cells into the unit their outlet drains into (repeated until stable)."""
    lab = np.where(np.isfinite(labels), labels, 0).astype(np.int64)
    for _ in range(20):
        sizes = np.bincount(lab.ravel())
        outs = outlets(lab, acc)
        small = [k for k in outs if sizes[k] < min_cells]
        if not small:
            break
        rr = np.array([outs[k][0] for k in small])
        cc = np.array([outs[k][1] for k in small])
        r2, c2 = downstream(rr, cc, dirs)
        mapping = np.arange(lab.max() + 1)
        changed = False
        for k, r, c in zip(small, r2, c2):
            if r >= 0 and lab[r, c] > 0 and lab[r, c] != k:
                mapping[k] = lab[r, c]
                changed = True
        if not changed:
            break
        lab = mapping[lab]
    return lab


def exits(inside, streams, dirs, acc, max_steps=200_000):
    """
    Where streams leave the area for good: stream cells inside the area draining to a cell outside it whose
    flow path never comes back into the area (a river along the boundary crosses it many times; only its last
    crossing counts). [(row, col, upstream cells)], largest first.
    """
    rr, cc = np.nonzero(inside & np.isfinite(streams) & (streams > 0))
    r2, c2 = downstream(rr, cc, dirs)
    leaving = (r2 < 0) | ~inside[np.maximum(r2, 0), np.maximum(c2, 0)]
    out = []
    for r, c, nr, nc in zip(rr[leaving], cc[leaving], r2[leaving], c2[leaving]):
        back, steps = False, 0
        while nr >= 0 and steps < max_steps:          # follow the water outside the area
            if inside[nr, nc]:
                back = True
                break
            a, b = downstream(np.array([nr]), np.array([nc]), dirs)
            nr, nc, steps = int(a[0]), int(b[0]), steps + 1
        if not back:
            out.append((int(r), int(c), float(acc[r, c])))
    return sorted(out, key=lambda t: -t[2])


def to_lonlat(geoms, crs):
    """shapely geometries in `crs` -> lon/lat."""
    import shapely
    from rasterio.warp import transform

    def fn(xy):
        if not len(xy):
            return xy
        xs, ys = transform(crs, "EPSG:4326", xy[:, 0].tolist(), xy[:, 1].tolist())
        return np.column_stack([xs, ys])
    return shapely.transform(np.asarray(geoms, dtype=object), fn)


def polygons(labels, transform, keep):
    """{label: shapely (Multi)Polygon in the grid CRS} for the labels in `keep`, from the label raster."""
    import shapely
    from rasterio.features import shapes
    lab = labels.astype(np.int32)
    parts = {}
    for gj, v in shapes(lab, mask=np.isin(lab, list(keep)), transform=transform, connectivity=8):
        parts.setdefault(int(v), []).append(shapely.geometry.shape(gj))
    return {k: shapely.union_all(v) for k, v in parts.items()}


# Catchment from a point ------------------------------------------------------------------------------------
def snap_outlet(acc, row, col, res_m, snap_m, min_cells, mode="nearest"):
    """
    Move an outlet onto the stream it was meant for. mode "nearest" (Jenson 1991): the nearest cell within snap_m
    that drains at least min_cells; with no such cell, the cell of highest accumulation within reach. mode
    "largest" (as ArcGIS Snap Pour Point): the cell of highest accumulation within snap_m, e.g. the main river
    near a click. (row, col, metres moved).
    """
    h, w = acc.shape
    k = int(snap_m // res_m)
    if k < 1:
        return row, col, 0.0
    r0, r1, c0, c1 = max(0, row - k), min(h, row + k + 1), max(0, col - k), min(w, col + k + 1)
    win = acc[r0:r1, c0:c1]
    rr, cc = np.mgrid[r0:r1, c0:c1]
    d = np.hypot(rr - row, cc - col) * res_m
    ok = (d <= snap_m) & np.isfinite(win)
    if not ok.any():
        return row, col, 0.0
    stream = ok & (win >= min_cells)
    if mode == "largest":
        i = np.unravel_index(int(np.argmax(np.where(ok, win, -1))), win.shape)
        r, c = int(rr[i]), int(cc[i])
        return r, c, float(d[i])
    if stream.any():
        # nearest stream cell; among equally near ones, the larger stream
        key = np.where(stream, d - win / (win.max() + 1) * 1e-3, np.inf)
    else:
        key = np.where(ok, -win, np.inf)
    i = np.unravel_index(int(np.argmin(key)), key.shape)
    r, c = int(rr[i]), int(cc[i])
    if stream.any():
        # D8 can run a small twin channel right beside the main one: take the largest stream within two cells
        a0, a1, b0, b1 = max(0, r - 2), min(h, r + 3), max(0, c - 2), min(w, c + 3)
        near = np.where(np.isfinite(acc[a0:a1, b0:b1]), acc[a0:a1, b0:b1], -1)
        j = np.unravel_index(int(np.argmax(near)), near.shape)
        r, c = a0 + int(j[0]), b0 + int(j[1])
    return r, c, float(np.hypot(r - row, c - col) * res_m)


COMPASS = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"]


def _bearing(dr, dc):
    import math
    ang = (math.degrees(math.atan2(dc, -dr)) + 360) % 360       # 0 = north (up), clockwise
    return COMPASS[int((ang + 22.5) // 45) % 8]


def nearby_streams(acc, row, col, res_m, px_km2, min_cells, reach_m=3000):
    """Streams around a point, for telling the user where the real streams are:
    {"nearest": (metres, km², direction) of the nearest cell draining min_cells or more,
     "largest": (metres, km², direction) of the nearest point of the biggest stream} within reach_m (None if none)."""
    h, w = acc.shape
    k = int(reach_m // res_m)
    r0, r1, c0, c1 = max(0, row - k), min(h, row + k + 1), max(0, col - k), min(w, col + k + 1)
    win = np.where(np.isfinite(acc[r0:r1, c0:c1]), acc[r0:r1, c0:c1], -1)
    rr, cc = np.mgrid[r0:r1, c0:c1]
    d = np.hypot(rr - row, cc - col) * res_m
    inside = d <= reach_m
    out = {"nearest": None, "largest": None}
    stream = inside & (win >= min_cells)
    if stream.any():
        i = np.unravel_index(int(np.argmin(np.where(stream, d, np.inf))), d.shape)
        out["nearest"] = (float(d[i]), float(win[i]) * px_km2, _bearing(rr[i] - row, cc[i] - col))
    top = float(np.max(np.where(inside, win, -1)))
    if top > 0:
        # Where the biggest stream is closest: the nearest cell carrying at least half of the largest flow in reach
        # (the highest accumulation itself sits wherever the river leaves the search circle).
        big = inside & (win >= top / 2)
        i = np.unravel_index(int(np.argmin(np.where(big, d, np.inf))), d.shape)
        out["largest"] = (float(d[i]), float(win[i]) * px_km2, _bearing(rr[i] - row, cc[i] - col))
    return out


def watershed(ctx, f, row, col, folder=None):
    """Boolean mask of the cells draining through (row, col) (WhiteboxTools Watershed on the D8 pointer)."""
    folder = Path(folder or ctx.scratch("hydro"))
    folder.mkdir(parents=True, exist_ok=True)
    dem = G.read(f.dir)
    pour = np.full(dem.data.shape, np.nan, dtype="float32")
    pour[row, col] = 1
    whitebox.plain_tif(dem.like(pour), folder / "pour.tif")
    wbt = whitebox.tools(folder, log=ctx.log)
    whitebox.call(wbt, "watershed", str(f.dir), "pour.tif", "catchment.tif")
    ws = G.read(folder / "catchment.tif").data
    return np.isfinite(ws) & (ws > 0)


def edge_cells(mask, valid):
    """(rows, cols) of mask cells next to the edge of the data (grid border or no-data cells): a cut-off catchment."""
    from scipy.ndimage import binary_dilation
    outside = np.pad(~valid, 1, constant_values=True)
    near = binary_dilation(outside, structure=np.ones((3, 3), bool))[1:-1, 1:-1]
    return np.nonzero(mask & near)
