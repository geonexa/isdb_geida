"""Checks that the raster stack (rasterio + PROJ) works in this Python environment."""
import functools

FIX = (
    "rasterio and Django's GDAL are using different PROJ installations. "
    "Install rasterio from conda-forge into the same environment as GDAL: "
    "`pip uninstall -y rasterio && conda install -c conda-forge rasterio`, then restart the worker."
)


@functools.lru_cache(maxsize=1)
def raster_env_problem() -> str:
    """'' if rasterio can resolve EPSG codes, else a user-facing message."""
    try:
        from rasterio.crs import CRS
        CRS.from_epsg(4326)
        CRS.from_epsg(6933)
    except ImportError as exc:
        return (f"rasterio is missing or broken ({exc}). Reinstall it from conda-forge: "
                "`pip uninstall -y rasterio; conda install -c conda-forge rasterio`, then restart the worker.")
    except Exception as exc:  # CRSError from a PROJ mismatch
        return f"{FIX} Details: {exc}"
    return ""
