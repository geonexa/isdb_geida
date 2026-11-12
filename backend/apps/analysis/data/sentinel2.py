"""
Sentinel-2 L2A cloud-free composites on the run grid.

Scenes are found with a STAC search (settings.STAC_API_URL, Earth Search on AWS: collection
sentinel-2-c1-l2a, public cloud-optimised GeoTIFFs). For each MGRS tile the least cloudy scenes
below a cloud limit are kept (at most `per_tile`). Each band is warped by GDAL from the COG
straight onto the run grid (only the bytes covering the area; overviews when the grid is
coarser than 10 m), converted to reflectance with the STAC scale and offset, and masked with
the scene classification layer (SCL): no data, saturated, cloud shadow, medium / high
probability cloud, thin cirrus and snow are dropped. A vegetation index is computed per scene;
the composite is the median of the clear observations per pixel.

    items = search(bbox, "2024-04-01", "2024-09-30", max_cloud=40, per_tile=8)
    index, count = composite(items, grid, "ndvi", log)
"""
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from django.conf import settings

from ..ops.grid import Grid, Raster
from .base import DatasetUnavailable
from .cog import GDAL_REMOTE

COLLECTION = "sentinel-2-c1-l2a"
CITATION = "Copernicus Sentinel-2 L2A (ESA), collection 1, via Earth Search (Element 84) on AWS Open Data"
SCL_BAD = (0, 1, 3, 8, 9, 10, 11)   # no data, saturated, cloud shadow, cloud medium / high, cirrus, snow
INDICES = {
    "ndvi": {"bands": ("red", "nir"), "label": "NDVI", "title": "Normalised difference vegetation index"},
    "evi": {"bands": ("blue", "red", "nir"), "label": "EVI", "title": "Enhanced vegetation index"},
    "savi": {"bands": ("red", "nir"), "label": "SAVI", "title": "Soil-adjusted vegetation index"},
    "ndmi": {"bands": ("nir08", "swir16"), "label": "NDMI", "title": "Normalised difference moisture index"},
}
SCALE = 10000          # indices stored as int16 x 10,000 while stacking scenes
EMPTY = np.int16(-32768)


def index_values(name, b):
    """Index from reflectance bands (dict of float arrays)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        if name == "ndvi":
            v = (b["nir"] - b["red"]) / (b["nir"] + b["red"])
        elif name == "evi":
            v = 2.5 * (b["nir"] - b["red"]) / (b["nir"] + 6 * b["red"] - 7.5 * b["blue"] + 1)
        elif name == "savi":
            v = 1.5 * (b["nir"] - b["red"]) / (b["nir"] + b["red"] + 0.5)
        elif name == "ndmi":
            v = (b["nir08"] - b["swir16"]) / (b["nir08"] + b["swir16"])
        else:
            raise ValueError(f"Unknown index {name}")
    return np.clip(v, -1, 1)


def search(bbox, start, end, max_cloud=40, per_tile=8, limit=500):
    """Scenes over bbox between two dates: [{id, date, tile, cloud, assets: {band: (href, scale, offset)}}]."""
    body = {"collections": [COLLECTION], "bbox": list(bbox), "limit": 100,
            "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z", "query": {"eo:cloud_cover": {"lt": max_cloud}}}
    feats, url = [], f"{settings.STAC_API_URL}/search"
    while body is not None and len(feats) < limit:
        req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json", "Accept": "application/geo+json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 (configured STAC API)
                page = json.load(resp)
        except OSError as exc:
            raise DatasetUnavailable(f"The Sentinel-2 catalogue didn't answer ({exc}). Try again in a minute.") from None
        feats += page.get("features", [])
        nxt = next((l for l in page.get("links", []) if l.get("rel") == "next"), None)
        body = nxt.get("body") if nxt else None
    items = []
    for f in feats:
        p, assets = f["properties"], {}
        for band, a in f["assets"].items():
            rb = (a.get("raster:bands") or [{}])[0]
            assets[band] = (a["href"], rb.get("scale", 1.0), rb.get("offset", 0.0))
        items.append({"id": f["id"], "date": p.get("datetime", "")[:10], "cloud": p.get("eo:cloud_cover", 100),
                      "tile": p.get("grid:code") or p.get("s2:mgrs_tile") or f["id"].split("_")[1], "assets": assets})
    by_tile = {}
    for it in sorted(items, key=lambda i: i["cloud"]):
        by_tile.setdefault(it["tile"], [])
        if len(by_tile[it["tile"]]) < per_tile:
            by_tile[it["tile"]].append(it)
    return sorted((i for v in by_tile.values() for i in v), key=lambda i: i["date"])


def _warp(href, grid, resampling):
    from osgeo import gdal
    gdal.UseExceptions()
    rows, cols = grid.shape
    left, bottom, right, top = grid.bounds
    with gdal.config_options(GDAL_REMOTE):
        ds = gdal.Warp("", f"/vsicurl/{href}" if href.startswith("http") else href, format="MEM",
                       dstSRS=grid.crs, outputBounds=(left, bottom, right, top), width=cols, height=rows,
                       resampleAlg=resampling, srcNodata=0, dstNodata=0, outputType=gdal.GDT_Float32)
        arr = ds.GetRasterBand(1).ReadAsArray()
    ds = None
    return arr


def read_item(item, bands, grid):
    """Reflectance for `bands` plus the SCL mask of one scene on the grid: ({band: float32}, clear bool)."""
    scl = _warp(item["assets"]["scl"][0], grid, "near")
    clear = (scl > 0) & ~np.isin(scl, SCL_BAD)
    if not clear.any():
        return None, clear
    out = {}
    for band in bands:
        href, scale, offset = item["assets"][band]
        dn = _warp(href, grid, "bilinear")
        clear &= dn > 0
        out[band] = dn * scale + offset
    return out, clear


def composite(items, grid, index, log=print, workers=6):
    """Median `index` over the clear observations of `items`, and the number of clear observations, as Rasters."""
    if not items:
        raise DatasetUnavailable("No Sentinel-2 scenes below the cloud limit for this period. "
                                 "Choose a longer period or a higher cloud limit.")
    bands = INDICES[index]["bands"]
    stack = np.full((len(items), *grid.shape), EMPTY, dtype=np.int16)
    done = [0]

    def one(k):
        b, clear = read_item(items[k], bands, grid)
        if b is not None:
            v = index_values(index, b)
            ok = clear & np.isfinite(v)
            stack[k][ok] = np.round(v[ok] * SCALE).astype(np.int16)
        done[0] += 1
        if done[0] % 5 == 0 or done[0] == len(items):
            log(f"Sentinel-2: {done[0]} of {len(items)} scenes read")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, range(len(items))))

    count = (stack != EMPTY).sum(axis=0).astype("float32")
    med = np.full(grid.shape, np.nan, dtype="float32")
    for r0 in range(0, grid.shape[0], 256):  # median by row blocks: float copies of a block only
        block = stack[:, r0:r0 + 256].astype("float32")
        block[block == EMPTY] = np.nan
        with np.errstate(all="ignore"):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                med[r0:r0 + 256] = np.nanmedian(block, axis=0) / SCALE
    info = {"dataset": "sentinel2_l2a", "index": index, "scenes": len(items)}
    return (Raster(med, grid.transform, grid.crs, dict(info)),
            Raster(np.where(count > 0, count, np.nan).astype("float32"), grid.transform, grid.crs, dict(info)))


def area_grid(area_utm, crs, max_pixels=16_000_000, finest=10.0):
    """A run grid over the area's bounds (UTM metres): 10 m, or coarser in 10 m steps to stay under max_pixels."""
    import math

    import shapely.geometry
    from affine import Affine
    w, s, e, n = shapely.geometry.shape(area_utm).bounds
    res = finest
    while (e - w) * (n - s) / res ** 2 > max_pixels:
        res += 10
    w, s = math.floor(w / res) * res, math.floor(s / res) * res
    e, n = math.ceil(e / res) * res, math.ceil(n / res) * res
    return Grid(crs, Affine(res, 0, w, 0, -res, n), (int(round((n - s) / res)), int(round((e - w) / res))))
