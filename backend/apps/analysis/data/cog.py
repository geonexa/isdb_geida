"""
Catalogue layers as analysis datasets.

Every layer of the shared catalogue (data/catalog.py) with a "cog" entry is an analysis
dataset under its id (`elevation`, `eta`, `pcp`, `landcover`, ...), except layers TiTiler
computes on the fly (slope, hillshade: analyses compute those themselves) and view-only ones.

clip() returns raw values over an area as a float32 GeoTIFF in the area's UTM zone at the
layer's native resolution (the catalogue's "scale", e.g. 30 m for the DEM, 10 m for
WorldCover, 300 m for WaPOR L1). The source files are found as the Data Catalog finds them
(STAC search for the DEM, a URL per year for WaPOR, tile grids for WorldCover and JRC;
apps.geoportal.raster.sources) and read directly with GDAL: remote COGs over HTTP range
requests (only the bytes covering the area), mosaicked, cut and reprojected in one gdal.Warp.
WaPOR scale factors are applied; classes are resampled with nearest neighbour, counts (a layer's
"resampling": "sum", e.g. population) with sum so totals are kept.
A local override (DATA_DIR/datasets/<id>/<ISO3>.tif or a shared mosaic there) is read
instead when present: offline work and tests. Areas above MAX_PIXELS are read coarser (logged).
Clips are cached in DATA_DIR/<id>/ per area, period and code version.
"""
from pathlib import Path
from .base import Dataset, DatasetUnavailable


def _bbox_polygon(bbox):
    """A lon/lat rectangle as a GEOS polygon with its SRID (EPSG:4326)."""
    from django.contrib.gis.geos import Polygon
    p = Polygon.from_bbox(bbox)
    p.srid = 4326
    return p

CLIP_VERSION = "2"  # bump when clipping changes, so cached clips are refreshed (2: native resolution, GDAL)
MAX_PIXELS = 150_000_000  # about 600 MB of float32; larger areas are read coarser (logged)
GDAL_REMOTE = {  # reading COGs over HTTP: only the byte ranges needed, no directory listings
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR", "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.tiff,.vrt",
    "GDAL_HTTP_MULTIRANGE": "YES", "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES", "VSI_CACHE": "TRUE",
    "GDAL_HTTP_MAX_RETRY": "3", "GDAL_HTTP_RETRY_DELAY": "2",
}


class CatalogRaster(Dataset):
    kind = "raster"

    def __init__(self, layer):
        self.layer = layer
        self.id = layer["id"]
        self.title = f"{layer['name']} ({layer['source']})" if layer.get("source") else layer["name"]
        self.reference_date = layer.get("period", "")
        self.licence = layer.get("licence", "")
        self.resolution = layer.get("res", "")
        self.citation = layer.get("attribution", "")
        self.source = layer.get("source", "")
        self.version = CLIP_VERSION
        self.scale_m = float(layer.get("scale") or 30)
        self.categorical = (layer.get("legend") or {}).get("type") == "classes"

    @property
    def periods(self):
        return list(self.layer.get("years") or [])

    def describe(self):
        return {**super().describe(), "periods": self.periods, "catalogue": True}

    def pick_period(self, year):
        from apps.geoportal.raster import RasterError, pick_year
        try:
            return pick_year(self.layer, year)
        except RasterError as exc:
            raise DatasetUnavailable(f"{self.title}: {exc}") from None

    def clip(self, geom, iso3, year=None, log=print):
        """
        Path of a float32 GeoTIFF of raw values over geom (GEOS, EPSG:4326, full rectangle) in the
        area's UTM zone at the layer's native resolution, and the period read.
        """
        year = self.pick_period(year)
        w, s, e, n = geom.extent
        out = self.cache_path((w, s, e, n), iso3, f"_{year or 'static'}.tif")
        if out.exists():
            if readable_tif(out):
                return str(out), year
            log(f"{self.title}: the cached clip is damaged (an earlier run was interrupted); reading it again")
            out.unlink(missing_ok=True)
        label = f"{self.title}{f' {year}' if year else ''}"
        local = self.local_files(iso3, year)
        part = out.with_name(out.stem + ".part.tif")   # written whole, then renamed: never a half file in the cache
        if local:
            log(f"{label}: reading the local file")
            files = [str(p) for p in local]
        else:
            files = [f"/vsicurl/{h}" if h.startswith(("http://", "https://")) else h
                     for h in self.source_files(year, (w, s, e, n))]
            log(f"{label}: reading {len(files)} source file(s) at native resolution")
        try:
            self._warp(files, geom, part, log, label)
            part.replace(out)
        finally:
            part.unlink(missing_ok=True)
        return str(out), year

    def source_files(self, year, bbox):
        """URLs or paths of the files covering bbox (lon/lat) for `year`. Catalogue layers find them as
        the Data Catalog does; datasets outside the catalogue (data/land.py) override this."""
        from apps.geoportal.raster import RasterError, sources
        try:
            return [h for h, _, _ in sources(self.layer, year, bbox)]
        except RasterError as exc:
            raise DatasetUnavailable(f"{self.title}: {exc}") from None

    def _warp(self, files, geom, out, log, label):
        """Mosaic, cut and reproject the source files with GDAL (range reads for remote COGs)."""
        import math

        import numpy as np
        from osgeo import gdal

        from apps.core.geo import utm_epsg

        gdal.UseExceptions()
        with gdal.config_options(GDAL_REMOTE):
            usable = []
            for f in files:  # tiles over the sea may not exist
                try:
                    if gdal.Open(f) is not None:
                        usable.append(f)
                except RuntimeError:
                    continue
            if not usable:
                raise DatasetUnavailable(f"{self.title} has no data over the area.")
            first_ds = gdal.Open(usable[0])  # keep the dataset open while its band is used
            first = first_ds.GetRasterBand(1)
            nodata = self.layer["cog"].get("nodata", first.GetNoDataValue())
            scale, offset = first.GetScale() or 1.0, first.GetOffset() or 0.0
            first = first_ds = None

            c = geom.centroid
            epsg = utm_epsg(c.x, c.y)
            box = _bbox_polygon(geom.extent).transform(epsg, clone=True)
            res = self.scale_m
            uw, us, ue, un = box.extent
            if (ue - uw) * (un - us) / res ** 2 > MAX_PIXELS:
                res = math.sqrt((ue - uw) * (un - us) / MAX_PIXELS)
                log(f"{label}: the area is very large, read at {res:.0f} m instead of {self.scale_m:.0f} m")
            uw, us = math.floor(uw / res) * res, math.floor(us / res) * res  # whole pixels on a res grid
            ue, un = math.ceil(ue / res) * res, math.ceil(un / res) * res
            coarser = res > self.scale_m * 1.5
            with gdal.quiet_errors():  # e.g. colour tables that can't be copied to a float file
                gdal.Warp(str(out), usable, format="GTiff", dstSRS=f"EPSG:{epsg}", outputBounds=(uw, us, ue, un),
                          xRes=res, yRes=res, targetAlignedPixels=False,
                          resampleAlg=self.layer.get("resampling") or ("near" if self.categorical else ("average" if coarser else "bilinear")),
                          srcNodata=nodata, dstNodata=float("nan"), outputType=gdal.GDT_Float32, multithread=True,
                          warpOptions=["NUM_THREADS=ALL_CPUS"],
                          creationOptions=["TILED=YES", "COMPRESS=DEFLATE", "PREDICTOR=3", "BIGTIFF=IF_SAFER"])

        if self.layer["cog"].get("unscale") and (scale != 1.0 or offset != 0.0):
            ds = gdal.Open(str(out), gdal.GA_Update)
            band = ds.GetRasterBand(1)
            arr = band.ReadAsArray().astype("float32")
            band.WriteArray(np.where(np.isfinite(arr), arr * scale + offset, np.nan).astype("float32"))
            band.SetScale(1.0)
            band.SetOffset(0.0)
            ds = None
        log(f"{label}: {res:.0f} m pixels in EPSG:{epsg}")

    def fetch(self, bbox, iso3, log=print):
        """ctx.dataset() compatibility: the default period over bbox."""
        path, _ = self.clip(_bbox_polygon(bbox), iso3, log=log)
        return path


def readable_tif(path):
    """True if a cached GeoTIFF is complete enough for GDAL to open (not empty, not cut short)."""
    from osgeo import gdal
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        with gdal.ExceptionMgr(useExceptions=True):
            ds = gdal.Open(str(path))
            ok = ds is not None and ds.RasterCount > 0
            ds = None
            return ok
    except RuntimeError:
        return False


def catalog_datasets():
    from .catalog import CATALOG

    out = []
    for group in CATALOG:
        for layer in group["layers"]:
            if not layer.get("cog") or layer.get("view_only") or layer.get("kind") == "planned":
                continue
            if (layer.get("render") or {}).get("algorithm"):  # slope, hillshade: computed by TiTiler
                continue
            out.append(CatalogRaster(layer))
    return out
