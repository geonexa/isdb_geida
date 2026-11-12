"""
Raster layers from cloud-optimised GeoTIFFs (COGs), rendered by TiTiler.

GEIDA keeps no copy of these datasets: it reads them where their producers host
them (FAO, ESA, Copernicus on AWS) and asks TiTiler (settings.TITILER_URL) to
draw tiles or cut GeoTIFFs. A layer's "cog" entry in catalog.py says where its
files are:

    {"url": ".../WAPOR-3.L1-AETI-A.{year}.tif"}   one global COG (per year)
    {"stac": "cop-dem-glo-30"}                    tiles found by a STAC search (settings.STAC_API_URL)
    {"grid": "worldcover"} / {"grid": "jrc"}      tiles on a fixed grid of known file names

Tiled datasets are combined per request into an in-line GDAL VRT, which TiTiler
reads like a single file. Its "render" entry holds TiTiler's drawing options
(rescale, colormap_name or colormap, algorithm such as hillshade or slope).

Nothing here needs a key or an account.
"""
import json
import logging
import math
import struct
import urllib.error
import urllib.parse
import urllib.request
import zlib
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.core.cache import cache

log = logging.getLogger(__name__)

MAX_SOURCES = 12          # files in one VRT (keeps TiTiler request URLs well under 8 KB)
MAX_PIXELS = 9_000_000    # largest GeoTIFF cut in one request (~3000 x 3000)
NODATA = -9999.0
TIMEOUT = 120
STAC_CACHE = 60 * 60 * 24
STAC_BLOCK = 5            # STAC searches are cached per 5° block


class RasterError(Exception):
    """A layer can't be drawn or cut (bad year, area too large, upstream failure). The message is for users."""


# ---------------------------------------------------------------------------
# Years
# ---------------------------------------------------------------------------
def periods(layer):
    """The years (or other periods, e.g. "2024-06" months or Wayback release dates) a layer offers."""
    source = layer.get("periods_from") or ""
    if source == "wayback":
        return sorted(wayback_releases())
    if source.startswith("wapor:"):
        return wapor_periods(source[6:])
    return layer.get("years") or []


WAPOR_API = "https://data.apps.fao.org/gismgr/api/v2/catalog/workspaces/WAPOR-3/mapsets/{mapset}/rasters"


def wapor_periods(mapset):
    """Periods published for a WaPOR v3 mapset ("2024-06", "2024-06-D1", ...), from FAO's catalogue, cached a day."""
    key = f"wapor:periods:{mapset}"
    found = cache.get(key)
    if found is not None:
        return found
    url, codes = WAPOR_API.format(mapset=mapset), []
    try:
        for _ in range(60):  # 100 rasters per page
            req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "GEIDA/1.0 (+geida.terrawatch.net)"})
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (FAO's public catalogue)
                page = json.load(resp)["response"]
            codes += [item["code"].rsplit(".", 1)[-1] for item in page.get("items", [])]
            nxt = next((l["href"] for l in page.get("links", []) if l.get("rel") == "next"), None)
            if not nxt:
                break
            url = nxt
    except (OSError, ValueError, KeyError) as exc:
        log.warning("WaPOR catalogue %s: %s", mapset, exc)
        return []
    found = sorted(set(codes))
    cache.set(key, found, 60 * 60 * 24)
    return found


def pick_year(layer, year):
    """The requested period, or the layer's default; RasterError if the layer doesn't have it.

    Periods are years (ints) for most layers, strings for monthly or dated layers.
    """
    years = periods(layer)
    if not years:
        if layer.get("periods_from"):
            raise RasterError("The list of dates for this layer couldn't be loaded. Try again in a minute.")
        return None
    if year in (None, ""):
        return layer.get("year") if layer.get("year") in years else years[-1]
    value = int(year) if isinstance(years[0], int) and str(year).lstrip("-").isdigit() else str(year)
    if value not in years:
        raise RasterError(f"No data for {year}. Choose from {years[0]} to {years[-1]}.")
    return value


# ---------------------------------------------------------------------------
# External tile services (view only): WMS overviews, NASA GIBS, Terrascope, Esri Wayback
# ---------------------------------------------------------------------------
WAYBACK_CAPS = "https://wayback.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/WMTS/1.0.0/WMTSCapabilities.xml"


def wayback_releases():
    """{"2026-10-29": "43291", ...}: Esri World Imagery Wayback releases (date -> release number), cached a day."""
    import re

    found = cache.get("wayback:releases")
    if found is not None:
        return found
    try:
        with urllib.request.urlopen(WAYBACK_CAPS, timeout=30) as resp:  # noqa: S310 (Esri's public service)
            xml = resp.read().decode("utf-8", "replace")
    except OSError as exc:
        log.warning("Wayback capabilities: %s", exc)
        return {}
    found = {}
    for block in re.findall(r"<Layer>(.*?)</Layer>", xml, flags=re.S):
        date = re.search(r"Wayback (\d{4}-\d{2}-\d{2})", block)
        num = re.search(r"/tile/(\d+)/", block)
        if date and num:
            found[date.group(1)] = num.group(1)
    cache.set("wayback:releases", found, 60 * 60 * 24)
    return found


def _fill(template, layer, year):
    url = template.replace("{period}", str(year) if year is not None else "")
    if "{release}" in url:
        url = url.replace("{release}", wayback_releases().get(str(year), ""))
    return url


def external_template(layer, year):
    """XYZ template of a view-only layer drawn by an outside tile service ({z}/{x}/{y} left as placeholders).

    None for ArcGIS ImageServer layers ("export"): they are drawn tile by tile (external_url).
    """
    return None if layer.get("export") else _fill(layer["url"], layer, year)


def external_url(layer, year, z, x, y):
    if layer.get("export"):
        import datetime

        ex = layer["export"]
        _, merc = tile_bounds(z, x, y)
        params = {"bbox": ",".join(f"{v:.3f}" for v in merc), "bboxSR": "3857", "imageSR": "3857", "size": "256,256",
                  "format": "png32", "transparent": "true", "f": "image"}
        if year is not None:
            start = datetime.datetime(int(year), 1, 1, tzinfo=datetime.timezone.utc)
            end = datetime.datetime(int(year), 12, 31, 23, 59, tzinfo=datetime.timezone.utc)
            params["time"] = f"{int(start.timestamp() * 1000)},{int(end.timestamp() * 1000)}"
        if ex.get("rendering_rule"):
            params["renderingRule"] = json.dumps({"rasterFunction": ex["rendering_rule"]})
        return f"{ex['url']}/exportImage?{urllib.parse.urlencode(params)}"
    return external_template(layer, year).replace("{z}", str(z)).replace("{x}", str(x)).replace("{y}", str(y))


def overview_url(layer, year, merc_bounds):
    """A WMS picture for zooms below a tiled COG layer's minzoom (e.g. Terrascope WorldCover, 90 m DEM)."""
    ov = layer.get("overview")
    if not ov:
        return None
    names = ov["layers"]
    name = names.get(str(year)) if isinstance(names, dict) else names
    if not name:
        return None
    params = {"SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap", "LAYERS": name, "STYLES": "",
              "CRS": "EPSG:3857", "BBOX": ",".join(f"{v:.3f}" for v in merc_bounds), "WIDTH": "256", "HEIGHT": "256",
              "FORMAT": "image/png", "TRANSPARENT": "TRUE"}
    return f"{ov['wms']}?{urllib.parse.urlencode(params)}"


# ---------------------------------------------------------------------------
# Where the files are
# ---------------------------------------------------------------------------
def _https(href):
    """s3://bucket/key -> https://bucket.s3.amazonaws.com/key (public buckets)."""
    if href.startswith("s3://"):
        bucket, _, key = href[5:].partition("/")
        return f"https://{bucket}.s3.amazonaws.com/{key}"
    return href


def _stac_block(collection, bx, by):
    """STAC items of one 5° block: [(href, (w, s, e, n), (width, height))], cached."""
    key = f"stac:{collection}:{bx}:{by}"
    items = cache.get(key)
    if items is not None:
        return items
    body = json.dumps({"collections": [collection], "bbox": [bx, by, bx + STAC_BLOCK, by + STAC_BLOCK],
                       "limit": 200}).encode()
    req = urllib.request.Request(f"{settings.STAC_API_URL}/search", data=body,
                                 headers={"Content-Type": "application/json", "Accept": "application/geo+json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (configured STAC API)
            feats = json.load(resp).get("features", [])
    except OSError as exc:
        raise RasterError(f"The STAC catalogue didn't answer ({exc}). Try again in a minute.") from exc
    items = []
    for f in feats:
        p, asset = f.get("properties", {}), (f.get("assets") or {}).get("data")
        shape, tr = p.get("proj:shape"), p.get("proj:transform")
        if not asset or not shape or not tr:
            continue
        h, w = shape
        x0, y1 = tr[2], tr[5]
        items.append((_https(asset["href"]), (x0, y1 + tr[4] * h, x0 + tr[0] * w, y1), (w, h)))
    cache.set(key, items, STAC_CACHE)
    return items


def _stac_items(collection, bbox):
    w, s, e, n = bbox
    out, seen = [], set()
    for bx in range(int(math.floor(w / STAC_BLOCK)) * STAC_BLOCK, int(math.ceil(e / STAC_BLOCK)) * STAC_BLOCK, STAC_BLOCK):
        for by in range(int(math.floor(s / STAC_BLOCK)) * STAC_BLOCK, int(math.ceil(n / STAC_BLOCK)) * STAC_BLOCK, STAC_BLOCK):
            for it in _stac_block(collection, bx, by):
                if it[0] not in seen and _overlaps(it[1], bbox):
                    seen.add(it[0])
                    out.append(it)
    return out


def _overlaps(a, b):
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


# ESA WorldCover: 3° tiles named by their lower-left corner (N00E033); a grid file lists the land tiles.
WORLDCOVER = {
    2020: ("v100", "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v100/2020/esa_worldcover_2020_grid.geojson"),
    2021: ("v200", "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/esa_worldcover_grid.geojson"),
}
WORLDCOVER_URL = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/{v}/{year}/map/ESA_WorldCover_10m_{year}_{v}_{tile}_Map.tif"
# JRC Global Surface Water: 10° tiles named by their upper-left corner (30E_10N); ocean tiles don't exist.
JRC_URL = "https://storage.googleapis.com/global-surface-water/downloads2021/occurrence/occurrence_{lon}_{lat}v1_4_2021.tif"


@lru_cache(maxsize=4)
def _worldcover_tiles(year):
    """Names of the WorldCover tiles that exist (land), from ESA's grid file, cached on disk."""
    version, url = WORLDCOVER[year]
    path = Path(settings.DATA_DIR) / "raster" / f"worldcover_grid_{version}.json"
    if path.exists():
        return frozenset(json.loads(path.read_text()))
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:  # noqa: S310 (ESA's public bucket)
            feats = json.load(resp)["features"]
    except OSError as exc:
        raise RasterError(f"Couldn't read the WorldCover tile list ({exc}).") from exc
    names = sorted(f["properties"]["ll_tile"] for f in feats)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(names))
    return frozenset(names)


def _grid_items(grid, year, bbox):
    w, s, e, n = bbox
    out = []
    if grid == "worldcover":
        version = WORLDCOVER[year][0]
        exists = _worldcover_tiles(year)
        size = 36000
        for lat in range(int(math.floor(s / 3)) * 3, int(math.ceil(n / 3)) * 3, 3):
            for lon in range(int(math.floor(w / 3)) * 3, int(math.ceil(e / 3)) * 3, 3):
                tile = f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}{'E' if lon >= 0 else 'W'}{abs(lon):03d}"
                if tile in exists:
                    out.append((WORLDCOVER_URL.format(v=version, year=year, tile=tile), (lon, lat, lon + 3, lat + 3), (size, size)))
    elif grid == "jrc":
        size = 40000
        for top in range(int(math.ceil(n / 10)) * 10, int(math.floor(s / 10)) * 10, -10):
            for lon in range(int(math.floor(w / 10)) * 10, int(math.ceil(e / 10)) * 10, 10):
                name_lon = f"{abs(lon)}{'E' if lon >= 0 else 'W'}"
                name_lat = f"{abs(top)}{'N' if top >= 0 else 'S'}"
                out.append((JRC_URL.format(lon=name_lon, lat=name_lat), (lon, top - 10, lon + 10, top), (size, size)))
    else:
        raise RasterError(f"Unknown tile grid '{grid}'.")
    return out


def sources(layer, year, bbox):
    """[(href, (w, s, e, n), (width, height))] of the files covering bbox (lon/lat). Single COGs have no extent."""
    spec = layer["cog"]
    if "url" in spec:
        return [(spec["url"].format(year=year), None, None)]
    if "stac" in spec:
        return _stac_items(spec["stac"], bbox)
    return _grid_items(spec["grid"], year, bbox)


def dataset(layer, year, bbox):
    """What TiTiler opens: a COG URL, an in-line VRT over several COGs, or None when nothing covers bbox."""
    found = sources(layer, year, bbox)
    if not found:
        return None
    if len(found) == 1 and found[0][1] is None:
        return found[0][0]
    if len(found) > MAX_SOURCES:
        raise RasterError("This area is too large for this layer at full resolution. Zoom in or draw a smaller area.")
    return _vrt(found, layer["cog"].get("dtype", "Float32"), layer["cog"].get("nodata"))


def _vrt(found, dtype, nodata):
    """An in-line GDAL VRT mosaic of COG tiles, at the finest resolution among them."""
    w = min(b[0] for _, b, _ in found)
    s = min(b[1] for _, b, _ in found)
    e = max(b[2] for _, b, _ in found)
    n = max(b[3] for _, b, _ in found)
    res = min(min((b[2] - b[0]) / size[0], (b[3] - b[1]) / size[1]) for _, b, size in found)
    width, height = round((e - w) / res), round((n - s) / res)
    parts = [f'<VRTDataset rasterXSize="{width}" rasterYSize="{height}"><SRS>EPSG:4326</SRS>'
             f"<GeoTransform>{w!r},{res!r},0,{n!r},0,{-res!r}</GeoTransform>"
             f'<VRTRasterBand dataType="{dtype}" band="1">']
    if nodata is not None:
        parts.append(f"<NoDataValue>{nodata}</NoDataValue>")
    for href, (x0, y0, x1, y1), (sw, sh) in found:
        parts.append(f"<SimpleSource><SourceFilename>/vsicurl/{href}</SourceFilename><SourceBand>1</SourceBand>"
                     f'<SrcRect xOff="0" yOff="0" xSize="{sw}" ySize="{sh}"/><DstRect xOff="{round((x0 - w) / res)}" yOff="{round((n - y1) / res)}" '
                     f'xSize="{round((x1 - x0) / res)}" ySize="{round((y1 - y0) / res)}"/></SimpleSource>')
    parts.append("</VRTRasterBand></VRTDataset>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Tiles
# ---------------------------------------------------------------------------
# Colour palettes a user may pick for continuous layers (TiTiler / rio-tiler colormap
# names; each also exists reversed with "_r"). The frontend has the same list with
# colour stops for legends (frontend/src/shared/map/palettes.ts).
PALETTES = ("viridis", "plasma", "magma", "cividis", "ylgnbu", "gnbu", "ylgn", "ylorrd", "orrd",
            "rdylgn", "spectral", "blues", "greens", "reds", "greys", "terrain")


def is_styleable(layer):
    """A continuous layer drawn with a named colormap: its palette and value range can be changed."""
    return bool(layer.get("cog") and layer.get("render", {}).get("colormap_name"))


def parse_style(cmap=None, value_range=None):
    """Validated style overrides from request parameters: {"colormap_name", "rescale"} (either may be absent)."""
    style = {}
    if cmap:
        base = cmap[:-2] if cmap.endswith("_r") else cmap
        if base not in PALETTES:
            raise RasterError(f"Unknown palette {cmap!r}.")
        style["colormap_name"] = cmap
    if value_range:
        try:
            lo, hi = (float(v) for v in value_range.split(","))
        except ValueError as exc:
            raise RasterError("The value range must be two numbers: min,max.") from exc
        if not lo < hi:
            raise RasterError("The value range needs min below max.")
        style["rescale"] = f"{lo:g},{hi:g}"
    return style


def render_params(layer, for_data=False, style=None):
    """TiTiler query parameters for a layer. for_data: raw values (no colours), for GeoTIFF downloads.
    style: user overrides of colormap_name / rescale (only for styleable layers)."""
    r = dict(layer.get("render", {}))
    if style and is_styleable(layer):
        r.update(style)
    params = {}
    if layer["cog"].get("unscale"):
        params["unscale"] = "true"
    if r.get("algorithm"):
        params["algorithm"] = r["algorithm"]
        if r.get("algorithm_params"):
            params["algorithm_params"] = json.dumps(r["algorithm_params"], separators=(",", ":"))
        params["buffer"] = str(r.get("buffer", 3))
    if r.get("resampling"):
        params["resampling"] = r["resampling"]
    if for_data:
        return params
    if r.get("rescale"):
        params["rescale"] = r["rescale"]
    if r.get("colormap_name"):
        params["colormap_name"] = r["colormap_name"]
    if r.get("colormap"):
        params["colormap"] = json.dumps(r["colormap"], separators=(",", ":"))
    return params


def is_single(layer):
    return "url" in layer["cog"]


def tile_template(layer, year):
    """XYZ template straight to TiTiler, for single-COG layers ({z}/{x}/{y} left as placeholders)."""
    params = {"url": layer["cog"]["url"].format(year=year), **render_params(layer)}
    return f"{settings.TITILER_URL}/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}.png?{urllib.parse.urlencode(params)}"


def tile_bounds(z, x, y):
    """(w, s, e, n) in lon/lat and (minx, miny, maxx, maxy) in Web Mercator metres of an XYZ tile."""
    n2 = 2 ** z
    lon = lambda i: i / n2 * 360 - 180  # noqa: E731
    lat = lambda j: math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * j / n2))))  # noqa: E731
    half = 20037508.342789244
    size = 2 * half / n2
    return (lon(x), lat(y + 1), lon(x + 1), lat(y)), (-half + x * size, half - (y + 1) * size, -half + (x + 1) * size, half - y * size)


def tile_url(layer, year, z, x, y, style=None):
    """URL of one tile: TiTiler for COG layers (a WMS overview below their minzoom), the outside service for view-only layers; None when nothing covers it."""
    if layer.get("kind") == "tiles":
        return None if z > layer.get("maxzoom", 22) else external_url(layer, year, z, x, y)
    lonlat, merc = tile_bounds(z, x, y)
    if z < layer.get("minzoom", 0):
        return overview_url(layer, year, merc)
    ds = dataset(layer, year, lonlat)
    if ds is None:
        return None
    params = {"url": ds, **render_params(layer, style=style)}
    return f"{settings.TITILER_URL}/cog/tiles/WebMercatorQuad/{z}/{x}/{y}.png?{urllib.parse.urlencode(params)}"


def fetch(url, timeout=60):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 (TiTiler or a catalogue tile service)
            return resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:300].decode("utf-8", "replace")
        raise RasterError(f"The tile server answered {exc.code}: {detail}") from exc
    except OSError as exc:
        raise RasterError(f"The tile server didn't answer ({exc}).") from exc


def png_rgba(arr):
    """Encode an (h, w, 4) uint8 array as PNG (no Pillow needed)."""
    h, w, _ = arr.shape
    raw = b"".join(b"\x00" + arr[i].tobytes() for i in range(h))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


@lru_cache(maxsize=1)
def empty_png():
    import numpy as np

    return png_rgba(np.zeros((256, 256, 4), dtype=np.uint8))


def decode_rgba(data):
    """Any tile image (PNG, JPEG; RGBA, RGB, grey, paletted) -> (h, w, 4) uint8."""
    import warnings

    import numpy as np
    from rasterio.errors import NotGeoreferencedWarning
    from rasterio.io import MemoryFile

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NotGeoreferencedWarning)
        with MemoryFile(data) as f, f.open() as src:
            bands = src.read()
            cmap = src.colormap(1) if src.count == 1 and src.colorinterp[0].name == "palette" else None
    if cmap:
        lut = np.zeros((256, 4), dtype=np.uint8)
        for k, v in cmap.items():
            lut[k] = v
        return lut[bands[0]]
    count = bands.shape[0]
    if count == 1:
        g = bands[0]
        return np.dstack([g, g, g, np.full_like(g, 255)])
    if count == 2:
        g, a = bands
        return np.dstack([g, g, g, a])
    if count == 3:
        return np.dstack([*bands, np.full_like(bands[0], 255)])
    return np.dstack(bands[:4])


def masked_tile(data, geom_3857, merc_bounds):
    """Tile image with everything outside geom_3857 made transparent (PNG)."""
    import numpy as np
    from rasterio.features import geometry_mask
    from rasterio.transform import from_bounds

    rgba = decode_rgba(data)
    h, w = rgba.shape[:2]
    outside = geometry_mask([json.loads(geom_3857.geojson)], out_shape=(h, w),
                            transform=from_bounds(*merc_bounds, w, h), all_touched=False)
    rgba = rgba.copy()
    rgba[outside, 3] = 0
    return png_rgba(np.ascontiguousarray(rgba))


# ---------------------------------------------------------------------------
# GeoTIFF downloads
# ---------------------------------------------------------------------------
def clip_geotiff(layer, year, geom, mask=False):
    """
    Raw values of `layer` over `geom` (GEOS, EPSG:4326) as a float32 GeoTIFF in the local UTM zone.
    mask=False: the full bounding rectangle (neighbourhood tools need valid edges).
    mask=True: pixels outside the geometry are NODATA.
    Returns (bytes, info).
    """
    import numpy as np
    from rasterio.features import geometry_mask
    from rasterio.io import MemoryFile

    from apps.core.geo import utm_epsg

    year = pick_year(layer, year)
    w, s, e, n = geom.extent
    if e - w <= 0 or n - s <= 0:
        raise RasterError("The area has no size. Draw a polygon or rectangle.")
    c = geom.centroid
    epsg = utm_epsg(c.x, c.y)
    utm = geom.envelope.transform(epsg, clone=True)
    uw, us, ue, un = utm.extent
    native = float(layer.get("scale") or 30)
    scale = max(native, math.sqrt((ue - uw) * (un - us) / MAX_PIXELS))
    width, height = max(1, math.ceil((ue - uw) / scale)), max(1, math.ceil((un - us) / scale))
    ds = dataset(layer, year, (w, s, e, n))
    if ds is None:
        raise RasterError("This layer has no data over the area.")
    params = {"url": ds, "coord_crs": "EPSG:4326", "dst_crs": f"EPSG:{epsg}", **render_params(layer, for_data=True)}
    if layer.get("render", {}).get("resampling") is None and layer.get("legend", {}).get("type") == "classes":
        params["resampling"] = "nearest"
    url = (f"{settings.TITILER_URL}/cog/bbox/{w!r},{s!r},{e!r},{n!r}/{width}x{height}.tif?"
           f"{urllib.parse.urlencode(params)}")
    raw = fetch(url, timeout=TIMEOUT)

    with MemoryFile(raw) as f, f.open() as src:
        bands = src.read()
        profile = {"driver": "GTiff", "width": src.width, "height": src.height, "count": 1, "dtype": "float32",
                   "crs": src.crs, "transform": src.transform, "nodata": NODATA, "compress": "deflate",
                   "predictor": 3, "tiled": True}
    data = bands[0].astype("float32")
    if bands.shape[0] > 1:  # TiTiler adds the validity mask as a last band
        data[bands[-1] == 0] = NODATA
    if mask:
        shape = json.loads(geom.transform(epsg, clone=True).geojson)
        data[geometry_mask([shape], out_shape=data.shape, transform=profile["transform"])] = NODATA
    with MemoryFile() as out:
        with out.open(**profile) as dst:
            dst.write(np.ascontiguousarray(data), 1)
        result = out.read()
    info = {"epsg": epsg, "scale": round(scale, 2), "native_scale": native, "year": year, "bytes": len(result),
            "nodata": NODATA}
    return result, info
