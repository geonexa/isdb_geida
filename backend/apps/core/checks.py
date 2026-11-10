"""Startup check: GeoDjango's GDAL can look up coordinate systems (needs a matching PROJ)."""
from django.core.checks import Error, register

FIX = (
    "GDAL loaded a PROJ library that doesn't match the proj.db it finds, usually because two "
    "installs are mixed (conda 'defaults' + conda-forge, pip wheels, or Homebrew). Recreate the "
    "environment from backend/environment.yml (conda-forge only): "
    "`conda env create -f environment.yml && conda activate geida`."
)


@register()
def gdal_proj_works(app_configs=None, **kwargs):
    try:
        from django.contrib.gis.gdal import SpatialReference

        SpatialReference(6933)  # the equal-area projection used for km²
    except Exception as exc:  # GDALException "OGR failure", or GDAL missing
        return [Error(f"GDAL can't read EPSG:6933 ({exc}).", hint=FIX, id="geida.E001")]
    return []
