"""Raster helpers for analyses: windowed reads from (cloud-optimised) GeoTIFFs, masks, zones, pixel areas.
Map previews (PNG, colours) are in apps.analysis.render.preview."""
import math
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask, rasterize
from rasterio.merge import merge
from rasterio.transform import from_bounds

EARTH_M_PER_DEG = 111_320.0


def open_sources(sources):
    """Open the sources that exist (missing ocean tiles return 404 and are skipped)."""
    out = []
    for s in sources:
        try:
            out.append(rasterio.open(s))
        except rasterio.errors.RasterioIOError:
            continue
    return out


def read_bbox(sources, bbox, *, max_pixels=25_000_000, resampling=Resampling.average, dtype=None):
    """
    Mosaic and clip `sources` to bbox (lon/lat). Reads at native resolution unless that
    exceeds max_pixels, then coarsens (resampling=sum keeps totals, mode keeps classes).
    Returns (array, transform, nodata, coarsened_factor) or None when no source covers the bbox.
    """
    if isinstance(resampling, str):
        resampling = Resampling[resampling]
    ds = open_sources(sources)
    if not ds:
        return None
    try:
        rx, ry = ds[0].res
        w, s, e, n = bbox
        nx, ny = (e - w) / rx, (n - s) / ry
        factor = max(1.0, math.sqrt(nx * ny / max_pixels))
        res = (rx * factor, ry * factor)
        nodata = ds[0].nodata
        # "sum" (keep totals, e.g. people) isn't allowed for reads: average, then scale by the cell-size ratio.
        keep_total = resampling == Resampling.sum
        read_with = Resampling.average if keep_total else resampling
        arr, transform = merge(ds, bounds=(w, s, e, n), res=res, nodata=nodata, resampling=read_with)
        a = arr[0]
        if dtype:
            a = a.astype(dtype)
        if keep_total:
            ratio = (abs(transform.a) * abs(transform.e)) / (rx * ry)
            if abs(ratio - 1) > 1e-6:
                valid = a != nodata if nodata is not None else np.isfinite(a)
                a = np.where(valid, a * ratio, a).astype(a.dtype)
        return a, transform, nodata, factor
    finally:
        for d in ds:
            d.close()


def write_tif(path, arr, transform, nodata=None, crs="EPSG:4326"):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
                       dtype=arr.dtype, crs=crs, transform=transform, nodata=nodata, compress="deflate") as dst:
        dst.write(arr, 1)
    return str(path)


def read_tif(path):
    with rasterio.open(path) as src:
        return src.read(1), src.transform, src.nodata


def pixel_area_km2(transform, shape):
    """Area of each pixel (km²) for a lon/lat grid: rows differ by latitude."""
    rows = np.arange(shape[0]) + 0.5
    lat = transform.f + rows * transform.e
    dx = abs(transform.a) * EARTH_M_PER_DEG * np.cos(np.radians(lat))
    dy = abs(transform.e) * EARTH_M_PER_DEG
    return np.repeat((dx * dy / 1e6)[:, None], shape[1], axis=1)


def pixel_size_m(transform, lat):
    """(dy_m, dx_m) of a lon/lat pixel at latitude `lat`."""
    return abs(transform.e) * EARTH_M_PER_DEG, abs(transform.a) * EARTH_M_PER_DEG * math.cos(math.radians(lat))


def area_mask(geojson, transform, shape):
    """True inside the geometry (pixel centres)."""
    return geometry_mask([geojson], out_shape=shape, transform=transform, invert=True)


def zone_raster(zones, transform, shape):
    """Rasterise [(geojson, zone_index>=1)] into an int32 grid (0 = no zone)."""
    if not zones:
        return np.zeros(shape, dtype=np.int32)
    return rasterize(zones, out_shape=shape, transform=transform, fill=0, dtype="int32")


def slope_degrees(dem, transform, nodata=None):
    a = dem.astype("float64")
    if nodata is not None:
        a[dem == nodata] = np.nan
    lat = transform.f + (np.arange(a.shape[0]) + 0.5) * transform.e
    dy = abs(transform.e) * EARTH_M_PER_DEG
    dx = abs(transform.a) * EARTH_M_PER_DEG * np.cos(np.radians(lat))[:, None]
    gy, gx = np.gradient(a)
    return np.degrees(np.arctan(np.hypot(gx / dx, gy / dy)))





def bbox_grid(bbox, res_deg):
    w, s, e, n = bbox
    width, height = max(1, round((e - w) / res_deg)), max(1, round((n - s) / res_deg))
    return from_bounds(w, s, e, n, width, height), (height, width)


def label_points(coords, zones, bbox, max_pixels=16_000_000):
    """
    Which zone each point falls in, via a fine zone grid (fast for 100k+ points).
    coords: [(lon, lat)]; zones: [(index, gid, name, geojson)] (clipped to the area).
    Returns (labels int array, 0 = outside every zone; {index: zone area km²}).
    """
    w, s, e, n = bbox
    res = max(0.0003, math.sqrt((e - w) * (n - s) / max_pixels))
    transform, shape = bbox_grid(bbox, res)
    z = zone_raster([(g, i) for i, _, _, g in zones], transform, shape)
    pa = pixel_area_km2(transform, shape)
    areas = {i: float(pa[z == i].sum()) for i, *_ in zones}
    if not len(coords):
        return np.zeros(0, dtype=np.int32), areas
    xy = np.asarray(coords, dtype="float64")
    cols = np.floor((xy[:, 0] - transform.c) / transform.a).astype(int)
    rows = np.floor((xy[:, 1] - transform.f) / transform.e).astype(int)
    ok = (rows >= 0) & (rows < shape[0]) & (cols >= 0) & (cols < shape[1])
    labels = np.zeros(len(xy), dtype=np.int32)
    labels[ok] = z[rows[ok], cols[ok]]
    return labels, areas
