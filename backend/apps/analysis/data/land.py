"""
Land datasets read in place that aren't Data Catalog layers (yet):

    lulc_annual             Esri / Impact Observatory annual land use and land cover, 10 m, 2017–2023
                            (v02), from Microsoft Planetary Computer (STAC search + anonymous SAS token)
    hansen_treecover2000    Hansen / UMD Global Forest Change v1.12: tree canopy cover in 2000 (%), 30 m
    hansen_lossyear         the same: year of forest loss (1–24 = 2001–2024, 0 = no loss), 30 m
    ftw_fields_<year>       Fields of The World 2nd edition field boundaries (GeoParquet per UTM zone)

The rasters are CatalogRaster subclasses: clipped, cut and reprojected with GDAL like catalogue
layers (data/cog.py), only the list of source files differs. Local overrides
(DATA_DIR/datasets/<id>/) work the same way, for tests and offline work.
"""
import json
import math
import urllib.parse
import urllib.request
from pathlib import Path

from django.core.cache import cache

from .base import Dataset, DatasetUnavailable, part_path
from .cog import GDAL_REMOTE, CatalogRaster

# Esri / Impact Observatory annual LULC (v02): class code -> (label, colour)
LULC_CLASSES = {1: ("Water", "#419BDF"), 2: ("Trees", "#397D49"), 4: ("Flooded vegetation", "#7A87C6"),
                5: ("Crops", "#E49635"), 7: ("Built area", "#C4281B"), 8: ("Bare ground", "#A59B8F"),
                9: ("Snow and ice", "#A8EBFF"), 10: ("Clouds", "#616161"), 11: ("Rangeland", "#E3E2C3")}
PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
PC_TOKEN = "https://planetarycomputer.microsoft.com/api/sas/v1/token/{collection}"


def _get_json(url, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json",
                                                          "Accept": "application/json", "User-Agent": "GEIDA"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed public services)
        return json.load(resp)


class LulcAnnual(CatalogRaster):
    COLLECTION = "io-lulc-annual-v02"

    def __init__(self):
        super().__init__({
            "id": "lulc_annual", "name": "Land use and land cover (yearly)", "source": "Esri / Impact Observatory",
            "res": "10 m", "scale": 10, "period": "Yearly, 2017 to 2023", "years": list(range(2017, 2024)), "year": 2023,
            "cog": {"nodata": 0}, "legend": {"type": "classes"}, "licence": "CC BY 4.0",
            "attribution": "Esri, Impact Observatory, Microsoft: 10 m annual land use / land cover v02 (CC BY 4.0), "
                           "read from Microsoft Planetary Computer"})

    def _token(self):
        key = f"pc-token:{self.COLLECTION}"
        token = cache.get(key)
        if not token:
            token = _get_json(PC_TOKEN.format(collection=self.COLLECTION))["token"]
            cache.set(key, token, 30 * 60)  # tokens last about an hour
        return token

    def source_files(self, year, bbox):
        try:
            found = _get_json(f"{PC_STAC}/search", {
                "collections": [self.COLLECTION], "bbox": list(bbox), "limit": 100,
                "datetime": f"{year}-01-01T00:00:00Z/{year}-12-31T23:59:59Z"})
            token = self._token()
        except OSError as exc:
            raise DatasetUnavailable(f"{self.title}: Planetary Computer didn't answer ({exc}). Try again in a minute.") from None
        hrefs = [f["assets"]["data"]["href"] for f in found.get("features", [])
                 if str(f["properties"].get("start_datetime", "")).startswith(str(year))]
        if not hrefs:
            raise DatasetUnavailable(f"{self.title} has no {year} map over the area.")
        return [f"{h}?{token}" for h in hrefs]


HANSEN = ("https://storage.googleapis.com/earthenginepartners-hansen/GFC-2024-v1.12/"
          "Hansen_GFC-2024-v1.12_{layer}_{lat}_{lon}.tif")
HANSEN_NOTE = ("Hansen, M. C. et al. 2013. High-Resolution Global Maps of 21st-Century Forest Cover Change. "
               "Science 342: 850–853. Data: Global Forest Change 2000–2024 v1.12, University of Maryland (CC BY 4.0)")


def hansen_tiles(bbox):
    """Names (lat, lon) of the 10° Hansen tiles covering bbox; tiles are named by their top-left corner."""
    w, s, e, n = bbox
    out = []
    for top in range(int(math.ceil(n / 10)) * 10, int(math.floor(s / 10)) * 10, -10):
        for left in range(int(math.floor(w / 10)) * 10, int(math.ceil(e / 10)) * 10, 10):
            out.append((f"{abs(top):02d}{'N' if top >= 0 else 'S'}", f"{abs(left):03d}{'E' if left >= 0 else 'W'}"))
    return out


class Hansen(CatalogRaster):
    def __init__(self, layer, name, categorical):
        self.hansen_layer = layer
        super().__init__({
            "id": f"hansen_{layer}", "name": name, "source": "Hansen / UMD Global Forest Change v1.12", "res": "30 m",
            "scale": 30, "period": "2000–2024", "cog": {"nodata": None},
            "legend": {"type": "classes" if categorical else "ramp"}, "licence": "CC BY 4.0", "attribution": HANSEN_NOTE})

    def source_files(self, year, bbox):
        return [HANSEN.format(layer=self.hansen_layer, lat=lat, lon=lon) for lat, lon in hansen_tiles(bbox)]


# Fields of The World ---------------------------------------------------------------------------
FTW = "https://data.source.coop/ftw/global-data-2e/vector/{year}/zone={zone:02d}/utm{zone:02d}.parquet"
FTW_YEARS = (2023, 2024, 2025)
FTW_NOTE = ("Fields of The World, Global Data 2nd Edition (Taylor Geospatial Engine / Kerner et al.), CC BY 4.0; "
            "model predictions from Sentinel-2 quarterly mosaics, not surveyed parcels")


def utm_zones(bbox):
    w, _, e, _ = bbox
    first, last = int((w + 180) // 6) + 1, int((min(e, 179.999) + 180) // 6) + 1
    return list(range(max(first, 1), min(last, 60) + 1))


class FTWFields(Dataset):
    """Field polygons of one year in a bbox, as GeoJSON with score (0–100) and area_m2."""

    kind = "vector"
    resolution = "polygons (from 10 m imagery)"
    licence = "CC BY 4.0"
    citation = FTW_NOTE
    source = "https://source.coop/ftw/global-data-2e"

    def __init__(self, year):
        self.year = year
        self.id = f"ftw_fields_{year}"
        self.title = f"Field boundaries {year} (Fields of The World)"
        self.version = "2e"
        self.reference_date = str(year)

    def fetch(self, bbox, iso3, log=print):
        local = self.local_files(iso3)
        if local:
            log(f"{self.title}: using {local[0].name}")
            return str(local[0])
        out = self.cache_path(bbox, iso3, ".geojson")
        if out.exists():
            return str(out)
        from osgeo import gdal
        gdal.UseExceptions()
        if gdal.GetDriverByName("Parquet") is None:
            raise DatasetUnavailable("GDAL's Parquet driver is missing on the analysis server "
                                     "(conda install -c conda-forge libgdal-arrow-parquet).")
        features = []
        for zone in utm_zones(bbox):
            url, layer = FTW.format(year=self.year, zone=zone), f"utm{zone:02d}"
            log(f"{self.title}: reading UTM zone {zone} by bounding box")
            tmp = part_path(out, f".z{zone}.geojson")
            try:
                with gdal.config_options({**GDAL_REMOTE, "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".parquet"}):
                    gdal.VectorTranslate(str(tmp), f"/vsicurl/{url}", format="GeoJSON", spatFilter=list(bbox),
                                         SQLStatement=f'SELECT score, "metrics:area" AS area_m2 FROM {layer}')
            except RuntimeError as exc:
                if "404" in str(exc) or "does not exist" in str(exc):
                    log(f"{self.title}: no file for UTM zone {zone}")
                    continue
                raise DatasetUnavailable(f"{self.title}: couldn't read zone {zone} ({exc})") from None
            features += json.loads(tmp.read_text()).get("features", [])
            tmp.unlink(missing_ok=True)
        part = part_path(out)
        part.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
        part.replace(out)
        return str(out)


def land_datasets():
    return [LulcAnnual(), Hansen("treecover2000", "Tree canopy cover in 2000", categorical=False),
            Hansen("lossyear", "Year of forest loss", categorical=True), *[FTWFields(y) for y in FTW_YEARS]]
