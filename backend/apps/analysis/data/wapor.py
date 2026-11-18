"""
FAO WaPOR v3 read straight from FAO's cloud-optimised GeoTIFFs: the periods a mapset publishes and the window of one
period around a place. Shared by the water analyses (level 1 only: GEIDA's analyses use the global 300 m product).
"""
import hashlib
import json
from pathlib import Path

import numpy as np
from django.conf import settings

BUCKET = "https://storage.googleapis.com/fao-gismgr-wapor-3-data/DATA/WAPOR-3/MAPSET"


def periods(mapset):
    """Published periods of a mapset ("2024", "2024-06", "2024-06-D1"), from FAO's catalogue (cached a day)."""
    from apps.geoportal.raster import wapor_periods
    return wapor_periods(mapset)


def cog_url(mapset, period):
    return f"{BUCKET}/{mapset}/WAPOR-3.{mapset}.{period}.tif"


def _cache_dir():
    d = Path(settings.DATA_DIR) / "cache" / "wapor_windows"
    d.mkdir(parents=True, exist_ok=True)
    return d


def read_window(mapset, period, bbox):
    """
    (array, transform, crs) of a WaPOR layer for one period inside bbox (lon/lat), scale factor applied, NaN for no
    data; None when the file can't be read. Cached on disk per mapset, period and bbox.
    """
    import rasterio
    from rasterio.windows import Window, from_bounds

    key = hashlib.sha1(json.dumps([mapset, period, [round(v, 5) for v in bbox]]).encode()).hexdigest()[:20]
    npy, meta = _cache_dir() / f"{key}.npy", _cache_dir() / f"{key}.json"
    if npy.exists() and meta.exists():
        m = json.loads(meta.read_text())
        return np.load(npy), rasterio.Affine(*m["transform"]), m["crs"]
    env = {"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR", "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
           "GDAL_HTTP_MAX_RETRY": "3", "GDAL_HTTP_RETRY_DELAY": "1"}
    try:
        with rasterio.Env(**env), rasterio.open(f"/vsicurl/{cog_url(mapset, period)}") as src:
            w = from_bounds(*bbox, transform=src.transform).round_offsets().round_lengths()
            w = Window(w.col_off, w.row_off, max(1, w.width), max(1, w.height))
            fill = src.nodata if src.nodata is not None else 0
            arr = src.read(1, window=w, boundless=True, fill_value=fill)
            data = arr.astype("float32")
            if src.nodata is not None:
                data[arr == src.nodata] = np.nan
            data = data * float(src.scales[0] or 1) + float(src.offsets[0] or 0)
            transform, crs = src.window_transform(w), src.crs.to_string()
    except Exception:  # noqa: BLE001 - a missing or unreadable period is reported and skipped by the caller
        return None
    np.save(npy, data)
    meta.write_text(json.dumps({"transform": list(transform)[:6], "crs": crs}))
    return data, transform, crs
