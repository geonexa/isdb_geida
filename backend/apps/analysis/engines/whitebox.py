"""
WhiteboxTools (Lindsay, University of Guelph; MIT licence), the hydrology and terrain engine.

    from apps.analysis.engines import whitebox
    wbt = whitebox.tools(folder, log=ctx.log)
    whitebox.call(wbt, "d8_pointer", "dem.tif", "dir.tif")

The `whitebox` Python package (requirements.txt) wraps the WhiteboxTools executable and downloads it
from whiteboxgeo.com on first use; settings.WHITEBOX_DIR points to an installed copy instead (servers
without internet). Inputs must be plain GeoTIFFs: WhiteboxTools can't read DEFLATE with a floating-point
predictor, so write inputs with plain_tif().
"""
import time

from django.conf import settings

from ..core.errors import AnalysisError


def available():
    try:
        import whitebox  # noqa: F401
        return True
    except ImportError:
        return False


def tools(folder, log=print):
    """A WhiteboxTools instance working in `folder` (the executable is fetched once if it isn't installed)."""
    try:
        import whitebox
    except ImportError:
        raise AnalysisError("WhiteboxTools isn't installed on the analysis server (pip install whitebox).") from None
    wbt = whitebox.WhiteboxTools()
    if getattr(settings, "WHITEBOX_DIR", ""):
        wbt.set_whitebox_dir(settings.WHITEBOX_DIR)
    wbt.set_verbose_mode(False)
    wbt.set_working_dir(str(folder))
    wbt._geida_log = log
    return wbt


def call(wbt, tool, *args, **kwargs):
    """Run one tool; raise AnalysisError with WhiteboxTools' messages if it fails."""
    messages = []
    t = time.time()
    rc = getattr(wbt, tool)(*args, callback=messages.append, **kwargs)
    if rc != 0:
        detail = " ".join(m.strip() for m in messages if m.strip() and "%" not in m)[-400:]
        raise AnalysisError(f"WhiteboxTools {tool} failed: {detail or 'see the server log'}")
    getattr(wbt, "_geida_log", print)(f"WhiteboxTools {tool}: {time.time() - t:.1f} s")


def plain_tif(raster, path):
    """Write a Raster as an uncompressed GeoTIFF (readable by WhiteboxTools)."""
    import numpy as np
    import rasterio
    data = np.where(np.isfinite(raster.data), raster.data, -32768).astype("float32")
    with rasterio.open(path, "w", driver="GTiff", width=data.shape[1], height=data.shape[0], count=1, dtype="float32",
                       crs=raster.crs, transform=raster.transform, nodata=-32768) as dst:
        dst.write(data, 1)
    return path
