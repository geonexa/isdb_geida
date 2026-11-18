"""
Static maps for reports, drawn on the server as SVG: one embedded basemap image (Esri tiles composed and cropped
to the map), raster results from their PNG previews (warped to Web Mercator), vector results as SVG paths, the
area of influence (outside dimmed), a scale bar, a north arrow and the attribution. Self-contained (images as
data URIs), so the same SVG goes into the web report and the PDF.
"""
import base64
import io
import json
import logging
import math
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from django.conf import settings

log = logging.getLogger(__name__)

TILE = 256
MAX_PX = 1400                 # longest side of a map, in pixels
ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services"
BASEMAPS = {
    "light": {"url": ESRI + "/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}", "max_zoom": 16,
              "attribution": "Basemap: Esri, HERE, Garmin, © OpenStreetMap contributors"},
    "satellite": {"url": ESRI + "/World_Imagery/MapServer/tile/{z}/{y}/{x}", "max_zoom": 18,
                  "attribution": "Imagery: Esri, Maxar, Earthstar Geographics"},
}
AREA_COLOR = "#0B3B47"


# Web Mercator ------------------------------------------------------------------------------------------------
def _mx(lon, z):
    return (lon + 180.0) / 360.0 * TILE * 2 ** z


def _my(lat, z):
    lat = max(min(lat, 85.0511), -85.0511)
    r = math.radians(lat)
    return (1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * TILE * 2 ** z


def _lat(my, z):
    n = math.pi - 2 * math.pi * my / (TILE * 2 ** z)
    return math.degrees(math.atan(math.sinh(n)))


class Frame:
    """The map's extent at a zoom level, and the scale from Mercator pixels to output pixels."""

    def __init__(self, bbox, max_zoom=16, pad=0.06):
        w, s, e, n = bbox
        dx, dy = (e - w) or 0.01, (n - s) or 0.01
        w, e, s, n = w - dx * pad, e + dx * pad, s - dy * pad, n + dy * pad
        z = max_zoom
        while z > 1 and max(_mx(e, z) - _mx(w, z), _my(s, z) - _my(n, z)) > MAX_PX:
            z -= 1
        self.z = z
        self.x0, self.y0 = _mx(w, z), _my(n, z)
        self.width = max(1, round(_mx(e, z) - self.x0))
        self.height = max(1, round(_my(s, z) - self.y0))
        self.bbox = (w, s, e, n)

    def px(self, lon, lat):
        return _mx(lon, self.z) - self.x0, _my(lat, self.z) - self.y0

    def metres_per_px(self):
        lat = (self.bbox[1] + self.bbox[3]) / 2
        return 156543.03392 * math.cos(math.radians(lat)) / 2 ** self.z


# Basemap -----------------------------------------------------------------------------------------------------
def _tile(style, z, x, y):
    cache = Path(settings.DATA_DIR) / "cache" / "report_tiles" / style / str(z) / str(x) / f"{y}.img"
    if cache.exists() and cache.stat().st_size > 0:
        return cache.read_bytes()
    url = BASEMAPS[style]["url"].format(z=z, x=x, y=y) + "?blankTile=false"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GEIDA report generator"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read()
    except OSError as exc:
        log.info("Basemap tile %s/%s/%s/%s unavailable: %s", style, z, x, y, exc)
        return None
    cache.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_suffix(".part")
    tmp.write_bytes(data)
    tmp.replace(cache)
    return data


def basemap_image(frame, style="light"):
    """The basemap cropped to the frame, as a JPEG data URI (None when no tile could be fetched)."""
    from PIL import Image
    style = style if style in BASEMAPS else "light"
    tx0, ty0 = int(frame.x0 // TILE), int(frame.y0 // TILE)
    tx1, ty1 = int((frame.x0 + frame.width) // TILE), int((frame.y0 + frame.height) // TILE)
    n = 2 ** frame.z
    jobs = [(x, y) for x in range(tx0, tx1 + 1) for y in range(ty0, ty1 + 1) if 0 <= y < n]
    if len(jobs) > 120:
        return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        tiles = list(pool.map(lambda xy: (xy, _tile(style, frame.z, xy[0] % n, xy[1])), jobs))
    canvas = Image.new("RGB", ((tx1 - tx0 + 1) * TILE, (ty1 - ty0 + 1) * TILE), (238, 238, 238))
    got = 0
    for (x, y), data in tiles:
        if not data:
            continue
        try:
            canvas.paste(Image.open(io.BytesIO(data)).convert("RGB"), ((x - tx0) * TILE, (y - ty0) * TILE))
            got += 1
        except OSError:
            continue
    if not got:
        return None
    ox, oy = round(frame.x0 - tx0 * TILE), round(frame.y0 - ty0 * TILE)
    img = canvas.crop((ox, oy, ox + frame.width, oy + frame.height))
    return _data_uri(img, "JPEG")


def _data_uri(img, fmt):
    buf = io.BytesIO()
    if fmt == "JPEG":
        img.save(buf, "JPEG", quality=84, optimize=True)
        mime = "image/jpeg"
    else:
        img.save(buf, "PNG", optimize=True)
        mime = "image/png"
    return f"data:{mime};base64,{base64.b64encode(buf.getvalue()).decode()}"


# Raster overlay ----------------------------------------------------------------------------------------------
def raster_image(frame, png_path, bounds):
    """A run's PNG preview (lon/lat grid, bounds [w, s, e, n]) warped onto the frame. (data URI, x, y, w, h)."""
    from PIL import Image
    w, s, e, n = bounds
    src = Image.open(png_path).convert("RGBA")
    x0, y0 = frame.px(w, n)
    x1, y1 = frame.px(e, s)
    ow, oh = max(1, round(x1 - x0)), max(1, round(y1 - y0))
    scale = min(1.0, 2000 / max(ow, oh))          # keep large overlays reasonable
    ow, oh = max(1, round(ow * scale)), max(1, round(oh * scale))
    a = np.asarray(src.resize((ow, src.height), Image.NEAREST))
    # Each output row is a Mercator row: find its latitude, then the source row (rows are equal steps of latitude).
    rows = np.empty(oh, dtype=int)
    for i in range(oh):
        lat = _lat(frame.y0 + y0 + (i + 0.5) * (y1 - y0) / oh, frame.z)
        rows[i] = min(src.height - 1, max(0, int((n - lat) / ((n - s) or 1) * src.height)))
    out = Image.fromarray(a[rows])
    return _data_uri(out, "PNG"), x0, y0, x1 - x0, y1 - y0


# Vectors -----------------------------------------------------------------------------------------------------
def _project(geom, frame):
    import shapely
    z, X0, Y0 = frame.z, frame.x0, frame.y0
    k = TILE * 2 ** z

    def f(c):
        lon, lat = c[:, 0], np.clip(c[:, 1], -85.0511, 85.0511)
        x = (lon + 180.0) / 360.0 * k - X0
        r = np.radians(lat)
        y = (1 - np.log(np.tan(r) + 1 / np.cos(r)) / np.pi) / 2 * k - Y0
        return np.column_stack([x, y])
    return shapely.transform(geom, f)


def _path_d(geom):
    parts = []
    gtype = geom.geom_type
    if gtype in ("Polygon",):
        for ring in [geom.exterior, *geom.interiors]:
            c = np.asarray(ring.coords)
            if len(c) >= 3:
                parts.append("M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in c) + "Z")
    elif gtype == "LineString":
        c = np.asarray(geom.coords)
        if len(c) >= 2:
            parts.append("M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in c))
    elif gtype.startswith("Multi") or gtype == "GeometryCollection":
        for g in geom.geoms:
            parts.append(_path_d(g))
    return "".join(parts)


def _feature_style(props, style):
    color = style.get("color") or "#1f77b4"
    width = style.get("width") or 1.6
    prop = style.get("property")
    if prop and style.get("classes"):
        v = props.get(prop)
        for c in style["classes"]:
            if c.get("value") == v or str(c.get("value")) == str(v):
                return c.get("color") or color, c.get("width") or width
    return color, width


def vector_svg(frame, geojson_path, style):
    """SVG elements for a GeoJSON layer, and its legend rows."""
    import shapely
    from shapely.geometry import shape
    data = json.loads(Path(geojson_path).read_text())
    feats = data.get("features") or []
    style = style or {}
    out = []
    shape_kind = style.get("shape")
    opacity = style.get("opacity", 0.35)
    points = 0
    for f in feats:
        g = f.get("geometry")
        if not g:
            continue
        try:
            geom = _project(shape(g), frame)
        except Exception:      # noqa: BLE001 - a broken geometry is skipped, not fatal
            continue
        color, width = _feature_style(f.get("properties") or {}, style)
        gt = geom.geom_type
        if gt in ("Point", "MultiPoint"):
            points += 1
            r = 2.2 if len(feats) > 2000 else 3.6
            for p in getattr(geom, "geoms", [geom]):
                out.append(f'<circle cx="{p.x:.1f}" cy="{p.y:.1f}" r="{r}" fill="{color}" stroke="#fff" stroke-width="0.8"/>')
            continue
        geom = shapely.simplify(geom, 0.6)
        if geom.is_empty:
            continue
        d = _path_d(geom)
        if not d:
            continue
        if "Polygon" in gt:
            outline = style.get("outline") or color
            out.append(f'<path d="{d}" fill="{color}" fill-opacity="{opacity}" stroke="{outline}" '
                       f'stroke-width="{min(width, 2)}" fill-rule="evenodd"/>')
            shape_kind = shape_kind or "polygon"
        else:
            out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" '
                       f'stroke-linecap="round" stroke-linejoin="round"/>')
            shape_kind = shape_kind or "line"
    kind = "point" if points and not shape_kind else (shape_kind or "polygon")
    if style.get("classes"):
        legend = [{"color": c.get("color"), "label": c.get("label") or str(c.get("value")), "kind": kind}
                  for c in style["classes"]]
    else:
        legend = [{"color": style.get("color") or "#1f77b4", "label": "", "kind": kind}]
    return "".join(out), legend


# Area of influence -------------------------------------------------------------------------------------------
def area_svg(frame, area_geom, dim=True, dim_color="#ffffff"):
    import shapely
    from shapely import wkb
    geom = _project(wkb.loads(bytes(area_geom.wkb)), frame)
    geom = shapely.simplify(geom, 0.5)
    d = _path_d(geom)
    parts = []
    if dim:
        parts.append(f'<path d="M0 0H{frame.width}V{frame.height}H0Z{d}" fill="{dim_color}" '
                     f'fill-opacity="{0.5 if dim_color == "#ffffff" else 0.4}" fill-rule="evenodd"/>')
    parts.append(f'<path d="{d}" fill="none" stroke="#ffffff" stroke-width="4.5" stroke-linejoin="round" opacity="0.8"/>')
    parts.append(f'<path d="{d}" fill="none" stroke="{AREA_COLOR}" stroke-width="2.2" stroke-linejoin="round"/>')
    return "".join(parts)


# Globe locator ----------------------------------------------------------------------------------------------
GLOBE = {"ocean": "#ffffff", "land": "#e5e7eb", "border": "#9ca3af", "highlight": AREA_COLOR, "marker": "#d7263d"}


def _ortho(lon0, lat0, cx, cy, r):
    """Orthographic projection; points on the far side are pushed to the rim (as the print layout's globe)."""
    s0, c0 = math.sin(math.radians(lat0)), math.cos(math.radians(lat0))

    def f(lon, lat):
        lam, phi = math.radians(lon - lon0), math.radians(lat)
        cp, sp, cl = math.cos(phi), math.sin(phi), math.cos(lam)
        x, y = cp * math.sin(lam), c0 * sp - s0 * cp * cl
        if s0 * sp + c0 * cp * cl >= 0:
            return cx + r * x, cy - r * y, True
        k = math.hypot(x, y) or 1
        return cx + r * x / k, cy - r * y / k, False
    return f


def _globe_path(polys, proj):
    d, seen = [], False
    for poly in polys:
        for ring in poly:
            pts, last = [], None
            for lon, lat in ring:
                x, y, vis = proj(lon, lat)
                seen = seen or vis
                if last and abs(x - last[0]) < 0.3 and abs(y - last[1]) < 0.3:
                    continue
                pts.append(f"{x:.1f} {y:.1f}")
                last = (x, y)
            if len(pts) > 2:
                d.append("M" + "L".join(pts) + "Z")
    return "".join(d) if seen else None


def globe_svg(cx, cy, r, iso3, marker=None, clip="globe-clip"):
    """An orthographic globe centred on the country (highlighted), neighbours grey, a 30° graticule and a marker
    at the project area. Vectors from GEIDA's world outlines, so it stays sharp in the PDF."""
    from shapely.geometry import shape
    try:
        from apps.boundaries.views import world_data
        feats = world_data()["features"]
    except Exception:          # noqa: BLE001 - no boundaries loaded: no globe
        log.info("World outlines unavailable for the globe locator", exc_info=True)
        return ""
    hit = next((f for f in feats if f["properties"]["gid"] == iso3), None)
    if hit:
        c = max(shape(hit["geometry"]).geoms, key=lambda g: g.area).centroid
        lon0, lat0 = c.x, c.y
    elif marker:
        lon0, lat0 = marker
    else:
        return ""
    proj = _ortho(lon0, max(-60, min(60, lat0)), cx, cy, r)
    g = GLOBE
    out = [f'<defs><clipPath id="{clip}"><circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}"/></clipPath></defs>',
           f'<circle cx="{cx:.1f}" cy="{cy + r * 0.04:.1f}" r="{r + 2:.1f}" fill="#000" opacity="0.25"/>',
           f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{g["ocean"]}"/>', '<g clip-path="url(#{clip})">']
    grat = []
    for lon in range(-180, 180, 30):
        grat.append([(lon, -90 + i * 3) for i in range(61)])
    for lat in range(-60, 61, 30):
        grat.append([(-180 + i * 3, lat) for i in range(121)])
    gd = []
    for line in grat:
        pen = False
        for lon, lat in line:
            x, y, vis = proj(lon, lat)
            if not vis:
                pen = False
                continue
            gd.append(f'{"L" if pen else "M"}{x:.1f} {y:.1f}')
            pen = True
    out.append(f'<path d="{"".join(gd)}" fill="none" stroke="{g["border"]}" stroke-opacity="0.45" stroke-width="0.6"/>')
    hit_d = ""
    for f in feats:
        d = _globe_path(f["geometry"]["coordinates"], proj)
        if not d:
            continue
        if f is hit:
            hit_d = d
            continue
        out.append(f'<path d="{d}" fill="{g["land"]}" stroke="{g["border"]}" stroke-width="0.5" stroke-linejoin="round"/>')
    if hit_d:
        out.append(f'<path d="{hit_d}" fill="{g["highlight"]}" stroke="{g["highlight"]}" stroke-width="0.6" stroke-linejoin="round"/>')
    if marker:
        x, y, vis = proj(*marker)
        if vis:
            m = max(2.5, r * 0.045)
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{m:.1f}" fill="{g["marker"]}" stroke="#fff" stroke-width="{m * 0.45:.1f}"/>')
    out.append(f'</g><circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="none" stroke="#ffffff" stroke-width="2.5"/>')
    return "".join(out)


# Furniture ---------------------------------------------------------------------------------------------------
def _nice_length(m):
    exp = 10 ** math.floor(math.log10(m))
    for k in (5, 2, 1):
        if k * exp <= m:
            return k * exp
    return exp


def furniture(frame, attribution):
    W, H = frame.width, frame.height
    mpp = frame.metres_per_px()
    length_m = _nice_length(mpp * W * 0.22)
    bar = length_m / mpp
    label = f"{length_m / 1000:g} km" if length_m >= 1000 else f"{length_m:g} m"
    fs = max(11, round(W / 85))
    x, y = 16, H - 18
    scale = (f'<g font-family="Outfit, sans-serif" font-size="{fs}" fill="#121114">'
             f'<rect x="{x - 8}" y="{y - fs - 12}" width="{bar + 16 + fs * 3.6}" height="{fs + 22}" fill="#fff" opacity="0.85"/>'
             f'<rect x="{x}" y="{y - 6}" width="{bar / 2:.1f}" height="6" fill="#121114"/>'
             f'<rect x="{x + bar / 2:.1f}" y="{y - 6}" width="{bar / 2:.1f}" height="6" fill="#fff" stroke="#121114"/>'
             f'<text x="{x + bar + 8:.1f}" y="{y}">{label}</text></g>')
    s = max(26, round(W / 30))
    nx, ny = W - s - 14, 14
    north = (f'<g transform="translate({nx},{ny})"><rect width="{s}" height="{s * 1.45:.0f}" fill="#fff" opacity="0.85"/>'
             f'<path d="M{s / 2} {s * 0.18:.1f}L{s * 0.78:.1f} {s * 0.95:.1f}L{s / 2} {s * 0.78:.1f}L{s * 0.22:.1f} {s * 0.95:.1f}Z" fill="#121114"/>'
             f'<text x="{s / 2}" y="{s * 1.33:.1f}" text-anchor="middle" font-family="Outfit, sans-serif" '
             f'font-size="{fs}" font-weight="700" fill="#121114">N</text></g>')
    afs = max(9, round(fs * 0.78))
    tw = len(attribution) * afs * 0.5 + 10          # a white box behind the text (no paint-order in WeasyPrint)
    attr = (f'<rect x="{W - tw:.0f}" y="{H - afs - 8}" width="{tw:.0f}" height="{afs + 8}" fill="#fff" opacity="0.8"/>'
            f'<text x="{W - 5}" y="{H - 5}" text-anchor="end" font-family="Outfit, sans-serif" font-size="{afs}" '
            f'fill="#333">{attribution}</text>')
    return scale + north + attr


def map_svg(area, basemap="satellite", raster=None, vector=None, bbox=None, dim=True, globe=None):
    """
    One map: area (ProjectArea or None), raster=(png_path, bounds) and/or vector=(geojson_path, style).
    globe: the country's ISO3 to add a globe locator (top left), as the print layout's overview map.
    Returns {"svg", "legend" (vector rows), "width", "height"}.
    """
    if bbox is None:
        bbox = area.geom.extent if area is not None else (raster[1] if raster else (-10, -10, 10, 10))
    # With a globe, a wider margin keeps the locator in the corner, clear of the area.
    frame = Frame(bbox, max_zoom=BASEMAPS.get(basemap, BASEMAPS["light"])["max_zoom"], pad=0.3 if globe else 0.06)
    parts = [f'<rect width="{frame.width}" height="{frame.height}" fill="#eeeeee"/>']
    base = basemap_image(frame, basemap)
    if base:
        parts.append(f'<image href="{base}" x="0" y="0" width="{frame.width}" height="{frame.height}"/>')
    legend = []
    if raster and Path(raster[0]).exists():
        uri, x, y, w, h = raster_image(frame, raster[0], raster[1])
        parts.append(f'<image href="{uri}" x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
                     f'preserveAspectRatio="none" opacity="0.92" class="ov"/>')
    if area is not None:
        parts.append(area_svg(frame, area.geom, dim=dim and not raster,
                              dim_color="#000000" if basemap == "satellite" else "#ffffff"))
    if vector and Path(vector[0]).exists():
        svg, legend = vector_svg(frame, vector[0], vector[1])
        parts.append(svg)
    attribution = BASEMAPS.get(basemap, BASEMAPS["light"])["attribution"]
    parts.append(furniture(frame, attribution))
    globe_alone = ""
    if globe:
        r = min(frame.width, frame.height) * 0.12
        c = area.geom.centroid if area is not None else None
        marker = (c.x, c.y) if c else None
        parts.append(globe_svg(r + 16, r + 16, r, globe, marker))
        g = globe_svg(64, 64, 60, globe, marker, clip="globe-clip-live")      # for the interactive cover map
        globe_alone = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 132" role="img" aria-label="Location">{g}</svg>' if g else ""
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {frame.width} {frame.height}" '
           f'width="100%" preserveAspectRatio="xMidYMid meet" role="img">{"".join(parts)}</svg>')
    return {"svg": svg, "legend": legend, "width": frame.width, "height": frame.height, "bbox": list(bbox),
            "globe": globe_alone}


# Interactive maps (web report) -------------------------------------------------------------------------------
WEB_MAX_BYTES = 6_000_000      # a vector layer larger than this stays a static picture in the web report
WEB_MAX_PROPS = 12


def _round(c, nd=5):
    if isinstance(c[0], (int, float)):
        return [round(c[0], nd), round(c[1], nd)]
    return [_round(x, nd) for x in c]


def web_geojson(path, style=None, max_bytes=WEB_MAX_BYTES):
    """A GeoJSON layer made light enough to embed in the web report (lon/lat, simplified, rounded, first
    properties only). Large layers get a second, coarser pass (about 1/800 of the extent, ~10 m coordinates).
    None when it would still be too large: that map stays a static picture."""
    import shapely
    from shapely.geometry import mapping, shape
    data = json.loads(Path(path).read_text())
    feats = data.get("features") or []
    geoms = []
    for f in feats:
        try:
            geoms.append(shape(f["geometry"]) if f.get("geometry") else None)
        except Exception:      # noqa: BLE001
            geoms.append(None)
    ok = [g for g in geoms if g is not None]
    if not ok:
        return None
    w, s_, e, n = shapely.GeometryCollection(ok).bounds
    size = max(e - w, n - s_)
    props = [{k: v for k, v in list((f.get("properties") or {}).items())[:WEB_MAX_PROPS]
              if isinstance(v, (str, int, float, bool)) or v is None} for f in feats]
    for div, nd in ((2500, 5), (800, 4)):
        out = []
        for g, pr in zip(geoms, props):
            if g is None:
                continue
            if g.geom_type not in ("Point", "MultiPoint"):
                g = shapely.simplify(g, size / div, preserve_topology=True)
                if g.is_empty:
                    continue
            geo = mapping(g)
            if "coordinates" in geo:
                geo = {"type": geo["type"], "coordinates": _round(geo["coordinates"], nd)}
            out.append({"type": "Feature", "properties": pr, "geometry": geo})
        fc = {"type": "FeatureCollection", "features": out}
        if len(json.dumps(fc, separators=(",", ":"))) <= max_bytes:
            return fc
    # Still too large (thousands of small features): one feature per legend class, details summarised.
    prop = (style or {}).get("property")
    groups = {}
    for g, pr in zip(geoms, props):
        if g is not None and g.geom_type not in ("Point", "MultiPoint"):
            groups.setdefault(pr.get(prop) if prop else None, []).append(g)
    if not groups:
        return None
    out = []
    for key, gs in groups.items():
        merged = shapely.simplify(shapely.union_all(gs) if "Polygon" in gs[0].geom_type
                                  else shapely.line_merge(shapely.MultiLineString(
                                      [ln for g in gs for ln in getattr(g, "geoms", [g])])), size / 800)
        geo = mapping(merged)
        pr = {prop: key} if prop else {}
        pr["features"] = len(gs)
        if "Line" in gs[0].geom_type:
            lat = math.radians((s_ + n) / 2)
            pr["length_km"] = round(sum(g.length for g in gs) * 111.32 * math.cos(lat), 1)   # approximate
        out.append({"type": "Feature", "properties": pr,
                    "geometry": {"type": geo["type"], "coordinates": _round(geo["coordinates"], 4)}})
    order = [str(c.get("value")) for c in (style or {}).get("classes") or []]
    rank = {v: i for i, v in enumerate(order)}
    out.sort(key=lambda f: -rank.get(str(f["properties"].get(prop)), len(order)))   # first legend class on top
    fc = {"type": "FeatureCollection", "features": out, "merged": True}
    return fc if len(json.dumps(fc, separators=(",", ":"))) <= max_bytes else None


def area_geojson(area):
    import shapely
    from shapely import wkb
    from shapely.geometry import mapping
    g = wkb.loads(bytes(area.geom.wkb))
    w, s_, e, n = g.bounds
    g = shapely.simplify(g, max(e - w, n - s_) / 4000, preserve_topology=True)
    geo = mapping(g)
    return {"type": geo["type"], "coordinates": _round(geo["coordinates"])}


def web_basemaps():
    return {k: {"url": v["url"] + "?blankTile=false", "max_zoom": v["max_zoom"], "attribution": v["attribution"]}
            for k, v in BASEMAPS.items()}
