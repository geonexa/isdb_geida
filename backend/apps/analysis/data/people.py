"""
People datasets:

    worldpop      WorldPop Global2 R2025A: people per 100 m cell, every year 2015–2030, from the WorldPop API
                  (POST /raster, cut to the area); worldpop_under_5, worldpop_age_5_14, worldpop_women_15_49,
                  worldpop_age_65_plus: the same for an age / sex group
    ghsl_pop      GHS-POP R2023A: residents per 100 m cell, epochs 1975–2030 (5-yearly; 2025, 2030 projected)
    ghsl_smod     GHS-SMOD R2023A: degree of urbanisation (settlement model, level 2), 1 km, same epochs
    ghsl_built    GHS-BUILT-S R2023A: built-up surface (m² per 100 m cell), same epochs
    map_tt_cities           travel time to the nearest city of 50,000+ people, 2015 (minutes, ~1 km)
    map_tt_health_motor     travel time to the nearest health facility by motorised transport, 2019 (minutes)
    map_tt_health_walk      the same on foot (minutes)

GHSL is published as zipped GeoTIFF tiles (1,000 km squares in World Mollweide, ESRI:54009) on JRC's
open data server, which doesn't serve partial reads: the tiles covering the area are downloaded once
into DATA_DIR/ghsl/<product>/ and read by GDAL inside the zip (/vsizip/). The Malaria Atlas Project maps
are cut to the area by MAP's WCS and cached in DATA_DIR/<dataset>/. Both are then clipped and
reprojected like catalogue layers (data/cog.py); population is resampled with "sum" (counts kept).
"""
import json
import math
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from django.conf import settings

from .base import DatasetUnavailable, part_path
from .cog import CatalogRaster

GHSL_URL = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL"
GHSL_EPOCHS = list(range(1975, 2031, 5))
GHSL_NOTE = ("GHSL Data Package 2023, European Commission Joint Research Centre (Schiavina, Melchiorri, Pesaresi et al.), "
             "CC BY 4.0")
# product -> (folder template, file stem template, version, resolution m, label)
GHSL_PRODUCTS = {
    "pop": ("GHS_POP_GLOBE_R2023A/GHS_POP_E{e}_GLOBE_R2023A_54009_100/V1-0", "GHS_POP_E{e}_GLOBE_R2023A_54009_100_V1_0", 100,
            "Residential population (GHS-POP)"),
    "smod": ("GHS_SMOD_GLOBE_R2023A/GHS_SMOD_E{e}_GLOBE_R2023A_54009_1000/V2-0", "GHS_SMOD_E{e}_GLOBE_R2023A_54009_1000_V2_0", 1000,
             "Degree of urbanisation (GHS-SMOD)"),
    "built": ("GHS_BUILT_S_GLOBE_R2023A/GHS_BUILT_S_E{e}_GLOBE_R2023A_54009_100/V1-0", "GHS_BUILT_S_E{e}_GLOBE_R2023A_54009_100_V1_0", 100,
              "Built-up surface (GHS-BUILT-S)"),
}
TILE_M = 1_000_000          # tiles are 1,000 km squares
X0, Y0 = -18_041_000, 9_000_000   # top-left of tile R1_C1 in ESRI:54009

# GHS-SMOD level 2 classes: code -> (label, colour, group)
SMOD_CLASSES = {30: ("Urban centre", "#C00000", "urban"), 23: ("Dense urban cluster", "#E26B0A", "urban"),
                22: ("Semi-dense urban cluster", "#F4A460", "urban"), 21: ("Suburban or peri-urban", "#FFD966", "peri-urban"),
                13: ("Rural cluster", "#548235", "rural"), 12: ("Low density rural", "#A9D18E", "rural"),
                11: ("Very low density rural", "#E2F0D9", "rural"), 10: ("Water", "#7CAFDD", "water")}


def ghsl_tiles(bbox):
    """(row, col) of the GHSL Mollweide tiles covering a lon/lat bbox."""
    from osgeo import osr
    osr.UseExceptions()
    src, dst = osr.SpatialReference(), osr.SpatialReference()
    src.ImportFromEPSG(4326)
    dst.ImportFromProj4("+proj=moll +lon_0=0 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs")
    src.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    tr = osr.CoordinateTransformation(src, dst)
    w, s, e, n = bbox
    pts = [(w + (e - w) * i / 10, s + (n - s) * j / 10) for i in range(11) for j in range(11)]  # edges bend in Mollweide
    xy = [tr.TransformPoint(lon, lat)[:2] for lon, lat in pts]
    cols = range(int((min(x for x, _ in xy) - X0) // TILE_M) + 1, int((max(x for x, _ in xy) - X0) // TILE_M) + 2)
    rows = range(int((Y0 - max(y for _, y in xy)) // TILE_M) + 1, int((Y0 - min(y for _, y in xy)) // TILE_M) + 2)
    return [(r, c) for r in rows for c in cols]


def _download(url, dest, log):
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = part_path(dest)  # unique per call: two runs may download the same tile at once
    req = urllib.request.Request(url, headers={"User-Agent": "GEIDA"})
    try:
        with urllib.request.urlopen(req, timeout=300) as resp, open(tmp, "wb") as fh:  # noqa: S310 (fixed public server)
            while chunk := resp.read(1 << 20):
                fh.write(chunk)
    except urllib.error.HTTPError as exc:
        tmp.unlink(missing_ok=True)
        if exc.code == 404:
            return None
        raise DatasetUnavailable(f"Download failed ({exc.code}): {url}") from None
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise DatasetUnavailable(f"Download failed ({exc}): {url}") from None
    tmp.rename(dest)
    log(f"downloaded {dest.name} ({dest.stat().st_size / 1e6:.0f} MB)")
    return dest


class GHSL(CatalogRaster):
    def __init__(self, product):
        folder, stem, res, label = GHSL_PRODUCTS[product]
        self.product, self.folder_t, self.stem_t = product, folder, stem
        classes = product == "smod"
        super().__init__({
            "id": f"ghsl_{product}", "name": label, "source": "GHSL R2023A (JRC)", "res": f"{res} m", "scale": res,
            "period": "1975–2030, every 5 years", "years": GHSL_EPOCHS, "year": 2020, "cog": {"nodata": None},
            "legend": {"type": "classes" if classes else "ramp"}, "licence": "CC BY 4.0", "attribution": GHSL_NOTE,
            **({"resampling": "sum"} if product == "pop" else {})})
        self._log = print

    def clip(self, geom, iso3, year=None, log=print):
        self._log = log
        return super().clip(geom, iso3, year, log)

    def source_files(self, year, bbox):
        folder, stem = self.folder_t.format(e=year), self.stem_t.format(e=year)
        out = []
        for r, c in ghsl_tiles(bbox):
            name = f"{stem}_R{r}_C{c}"
            dest = Path(settings.DATA_DIR) / "ghsl" / self.product / f"{name}.zip"
            if not dest.exists():
                self._log(f"{self.title} {year}: downloading tile R{r} C{c} (once)")
                if _download(f"{GHSL_URL}/{folder}/tiles/{name}.zip", dest, self._log) is None:
                    continue  # ocean tiles aren't published
            out.append(f"/vsizip/{dest}/{name}.tif")
        if not out:
            raise DatasetUnavailable(f"{self.title} has no tile over the area.")
        return out


MAP_WCS = "https://data.malariaatlas.org/geoserver/Accessibility/ows"
MAP_NOTE = {
    "cities": "Weiss, D. J. et al. 2018. A global map of travel time to cities to assess inequalities in accessibility in 2015. "
              "Nature 553: 333–336. Malaria Atlas Project, CC BY 4.0",
    "health": "Weiss, D. J. et al. 2020. Global maps of travel time to healthcare facilities. Nature Medicine 26: 1835–1838. "
              "Malaria Atlas Project, CC BY 4.0",
}


class MAPAccess(CatalogRaster):
    def __init__(self, id, coverage, name, period, note):
        self.coverage = coverage
        super().__init__({"id": id, "name": name, "source": "Malaria Atlas Project", "res": "1 km", "scale": 1000,
                          "period": period, "cog": {"nodata": -9999}, "legend": {"type": "ramp"},
                          "licence": "CC BY 4.0", "attribution": note})

    def source_files(self, year, bbox):
        w, s, e, n = bbox
        dest = self.cache_path(bbox, "wcs", ".tif")
        if not dest.exists():
            q = urllib.parse.urlencode([("service", "WCS"), ("version", "2.0.1"), ("request", "GetCoverage"),
                                        ("coverageId", self.coverage), ("format", "image/tiff"),
                                        ("subset", f"Long({w - 0.02},{e + 0.02})"), ("subset", f"Lat({s - 0.02},{n + 0.02})")])
            if _download(f"{MAP_WCS}?{q}", dest, lambda *_: None) is None:
                raise DatasetUnavailable(f"{self.title}: the Malaria Atlas Project service has no data here.")
            if dest.read_bytes()[:5] in (b"<?xml", b"<ows:", b"<Serv"):
                dest.unlink()
                raise DatasetUnavailable(f"{self.title}: the Malaria Atlas Project service returned an error. Try again later.")
        return [str(dest)]


def people_datasets():
    return [WorldPop(), *[WorldPop(g) for g in WORLDPOP_GROUPS], GHSL("pop"), GHSL("smod"), GHSL("built"),
            MAPAccess("map_tt_cities", "Accessibility__201501_Global_Travel_Time_to_Cities",
                      "Travel time to cities (50,000+ people)", "2015", MAP_NOTE["cities"]),
            MAPAccess("map_tt_health_motor", "Accessibility__202001_Global_Motorized_Travel_Time_to_Healthcare",
                      "Travel time to health care, motorised", "2019", MAP_NOTE["health"]),
            MAPAccess("map_tt_health_walk", "Accessibility__202001_Global_Walking_Only_Travel_Time_To_Healthcare",
                      "Travel time to health care, walking", "2019", MAP_NOTE["health"])]


# WorldPop API (https://api.worldpop.org/v3, settings.WORLDPOP_API_URL; key optional: WORLDPOP_API_KEY) --------
WORLDPOP_YEARS = list(range(2015, 2031))
WORLDPOP_NOTE = ("WorldPop (www.worldpop.org), Global2 R2025A v1, 100 m population and age-sex structures, "
                 "DOI 10.5258/SOTON/WP00839 / WP00841, University of Southampton, CC BY 4.0")
# group id -> (age range, sex, label for people of the group)
WORLDPOP_GROUPS = {
    "under_5": ([0, 4], "both", "children under 5"),
    "age_5_14": ([5, 14], "both", "school-age children (5–14)"),
    "women_15_49": ([15, 49], "female", "women aged 15–49"),
    "age_65_plus": ([65, 90], "both", "people aged 65 and over"),
}


def worldpop_post(path, body, raw=False, timeout=120):
    """POST to the WorldPop API: the JSON answer (or the bytes and headers with raw=True). Errors -> DatasetUnavailable."""
    headers = {"Content-Type": "application/json", "User-Agent": "GEIDA"}
    if getattr(settings, "WORLDPOP_API_KEY", ""):
        headers["X-API-Key"] = settings.WORLDPOP_API_KEY
    req = urllib.request.Request(f"{settings.WORLDPOP_API_URL}{path}", data=json.dumps(body).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (configured API)
            data = resp.read()
            return (data, dict(resp.headers)) if raw else json.loads(data)
    except urllib.error.HTTPError as exc:
        try:
            err = json.loads(exc.read())
        except ValueError:
            err = {}
        code = err.get("error", "")
        if exc.code == 429:
            msg = ("the WorldPop API's request limit is reached (1,000 a day without a key); "
                   "set WORLDPOP_API_KEY or try again later") if code == "rate_limit_exceeded" else "the WorldPop API is busy, try again in a minute"
        else:
            msg = err.get("message") or f"HTTP {exc.code}"
        raise DatasetUnavailable(f"WorldPop: {msg}") from None
    except OSError as exc:
        raise DatasetUnavailable(f"WorldPop API unreachable ({exc})") from None


def simple_geojson(geojson, tolerance=0.0002, max_vertices=40000):
    """A (Multi)Polygon GeoJSON simplified enough for the API's vertex limit."""
    from django.contrib.gis.geos import GEOSGeometry
    g = GEOSGeometry(json.dumps(geojson), srid=4326)
    while g.num_coords > max_vertices and tolerance < 0.05:
        g = g.simplify(tolerance, preserve_topology=True)
        tolerance *= 2
    return json.loads(g.geojson)


class WorldPop(CatalogRaster):
    def __init__(self, group=None):
        self.group = group
        label = WORLDPOP_GROUPS[group][2].capitalize() if group else "Population"
        super().__init__({
            "id": f"worldpop_{group}" if group else "worldpop", "name": f"{label} (WorldPop)", "source": "WorldPop Global2 R2025A",
            "res": "100 m", "scale": 100, "period": "Yearly, 2015–2030", "years": WORLDPOP_YEARS, "year": 2025,
            "cog": {"nodata": -99999}, "legend": {"type": "ramp"}, "licence": "CC BY 4.0", "attribution": WORLDPOP_NOTE,
            "resampling": "sum"})

    @property
    def people_label(self):
        return WORLDPOP_GROUPS[self.group][2] if self.group else "people"

    def source_files(self, year, bbox):
        w, s, e, n = bbox
        dest = self.cache_path(bbox, "api", f"_{year}.tif")
        from .cog import readable_tif
        if dest.exists() and not readable_tif(dest):
            dest.unlink()                      # left empty by an interrupted run
        if not dest.exists():
            ring = [[w - 0.005, s - 0.005], [e + 0.005, s - 0.005], [e + 0.005, n + 0.005], [w - 0.005, n + 0.005], [w - 0.005, s - 0.005]]
            body = {"geojson": {"type": "Polygon", "coordinates": [ring]}, "year": year}
            if self.group:
                ages, sex, _ = WORLDPOP_GROUPS[self.group]
                body.update(layer="agesex", age_range=ages, sex=sex, bands="sum")
            try:
                data, _ = worldpop_post("/raster", body, raw=True)
            except DatasetUnavailable as exc:
                if "too large" not in str(exc).lower() and "raster_too_large" not in str(exc):
                    raise
                data, _ = worldpop_post("/raster", {**body, "resolution": "1km"}, raw=True)  # very large areas: 1 km cells
            part = part_path(dest)
            part.write_bytes(data)
            part.replace(dest)
        return [str(dest)]
