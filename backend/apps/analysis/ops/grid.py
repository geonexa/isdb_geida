"""
Rasters on a run's grid: every raster in a run is held on one metric grid in the area's
UTM zone, so pixels line up, areas are in m² and distances in metres.

    r = read(path)                      # Raster: float32 values (NaN = no data), transform, CRS
    g = Grid.of(r)                      # the grid a raster sits on
    r2 = reproject(other, g, "nearest") # another raster on the same grid
    write(r2, path)                     # GeoTIFF (float32, NaN as no data)
"""
from dataclasses import dataclass, field

import numpy as np
import rasterio
from affine import Affine
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.warp import calculate_default_transform
from rasterio.warp import reproject as _reproject

NODATA = np.float32(np.nan)


@dataclass
class Grid:
    crs: str                  # "EPSG:32642"
    transform: Affine
    shape: tuple              # (rows, cols)

    @classmethod
    def of(cls, raster):
        return cls(raster.crs, raster.transform, raster.data.shape)

    @property
    def res(self):
        """Pixel size in CRS units (metres for UTM)."""
        return abs(self.transform.a)

    @property
    def pixel_area_m2(self):
        return abs(self.transform.a * self.transform.e)

    @property
    def bounds(self):
        """(left, bottom, right, top) in the grid CRS."""
        rows, cols = self.shape
        left, top = self.transform.c, self.transform.f
        return (left, top + rows * self.transform.e, left + cols * self.transform.a, top)

    def mask(self, geojson):
        """True inside a (Multi)Polygon given in the grid CRS (pixel centres)."""
        return ~geometry_mask([geojson], out_shape=self.shape, transform=self.transform)


@dataclass
class Raster:
    data: np.ndarray          # float32, NaN where there is no data
    transform: Affine
    crs: str
    info: dict = field(default_factory=dict)   # dataset id, year, scale, ... (recorded with the run)

    @property
    def grid(self):
        return Grid.of(self)

    @property
    def valid(self):
        return np.isfinite(self.data)

    def like(self, data, **info):
        """A new raster with other values on the same grid."""
        return Raster(np.asarray(data, dtype="float32"), self.transform, self.crs, {**self.info, **info})

    def stats(self, mask=None):
        """min / max / mean / count of valid pixels (inside mask, when given)."""
        sel = self.valid if mask is None else self.valid & mask
        vals = self.data[sel]
        if not vals.size:
            return {"count": 0, "min": None, "max": None, "mean": None}
        return {"count": int(vals.size), "min": float(vals.min()), "max": float(vals.max()), "mean": float(vals.mean())}


def read(path, band=1):
    """A GeoTIFF band as a Raster (no-data values become NaN)."""
    with rasterio.open(path) as src:
        arr = src.read(band).astype("float32")
        if src.nodata is not None and not np.isnan(src.nodata):
            arr[arr == np.float32(src.nodata)] = np.nan
        crs = src.crs.to_string() if src.crs else "EPSG:4326"
        return Raster(arr, src.transform, crs, {"source": str(path)})


def write(raster, path, cog=False):
    """Write float32 with NaN as no data; cog=True writes a cloud-optimised GeoTIFF."""
    profile = {"driver": "GTiff", "width": raster.data.shape[1], "height": raster.data.shape[0], "count": 1,
               "dtype": "float32", "crs": raster.crs, "transform": raster.transform, "nodata": NODATA,
               "compress": "deflate", "predictor": 3, "tiled": True}
    data = np.ascontiguousarray(raster.data.astype("float32"))
    if not cog:
        with rasterio.open(path, "w", **profile) as dst:
            dst.write(data, 1)
        return path
    from rasterio.io import MemoryFile
    from rasterio.shutil import copy as rio_copy
    with MemoryFile() as mem:
        with mem.open(**profile) as tmp:
            tmp.write(data, 1)
        with mem.open() as tmp:
            rio_copy(tmp, path, driver="COG", compress="DEFLATE", predictor="3", overview_resampling="average")
    return path


def utm_grid(raster, epsg, res=None):
    """The UTM grid covering a raster (e.g. a lon/lat dataset), at res metres (default: about its own)."""
    rows, cols = raster.data.shape
    left, top = raster.transform.c, raster.transform.f
    right, bottom = left + cols * raster.transform.a, top + rows * raster.transform.e
    kwargs = {"resolution": res} if res else {}
    transform, width, height = calculate_default_transform(CRS.from_user_input(raster.crs), CRS.from_epsg(epsg),
                                                           cols, rows, left, bottom, right, top, **kwargs)
    return Grid(f"EPSG:{epsg}", transform, (height, width))


def reproject(raster, grid, resampling="bilinear"):
    """The raster resampled onto grid (nearest for classes, bilinear or average for values)."""
    if raster.crs == grid.crs and raster.transform == grid.transform and raster.data.shape == tuple(grid.shape):
        return raster
    out = np.full(grid.shape, np.nan, dtype="float32")
    _reproject(raster.data, out, src_transform=raster.transform, src_crs=raster.crs, src_nodata=np.nan,
               dst_transform=grid.transform, dst_crs=grid.crs, dst_nodata=np.nan,
               resampling=getattr(Resampling, resampling))
    return Raster(out, grid.transform, grid.crs, dict(raster.info))
