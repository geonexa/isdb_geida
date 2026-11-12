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


def _version(cmd):
    import subprocess
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return (out.stdout or out.stderr).strip().splitlines()[0] if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError, IndexError):
        return ""


@functools.lru_cache(maxsize=1)
def engines():
    """{engine: (available, detail)} for the engines a manifest can require (gdal, grass, whitebox)."""
    import shutil

    out = {}
    try:
        from osgeo import gdal
        problem = raster_env_problem()
        out["gdal"] = (not problem, problem or f"GDAL {gdal.__version__}")
    except ImportError as exc:
        out["gdal"] = (False, f"GDAL Python bindings missing ({exc})")
    grass = shutil.which("grass")
    out["grass"] = (bool(grass), (_version([grass, "--version"]) or grass) if grass else "GRASS GIS not found on PATH")
    try:
        import whitebox  # noqa: F401
        out["whitebox"] = (True, "WhiteboxTools (whitebox Python package; executable fetched on first use or WHITEBOX_DIR)")
    except ImportError:
        out["whitebox"] = (False, "WhiteboxTools not installed (pip install whitebox)")
    return out


def missing_engines(manifest):
    """Engines a manifest requires that this machine doesn't have."""
    have = engines()
    return [e for e in manifest.get("requires", []) or [] if not have.get(e, (False,))[0]]
