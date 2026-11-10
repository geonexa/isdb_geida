"""
Data Catalog raster layers, cut to a project's area of influence.

    GET /api/projects/<code>/satellite/                             layers available, by group
    GET /api/projects/<code>/satellite/<id>/tiles/?year=&cmap=&range= XYZ template (GEIDA's tile route below)
    GET /api/projects/<code>/satellite/<id>/xyz/<z>/<x>/<y>.png       one tile, transparent outside the area
    GET /api/projects/<code>/satellite/<id>/download/?year=          GeoTIFF masked to the area

Tiles wholly inside the area redirect to the tile server; tiles across the
boundary are fetched and masked here; tiles outside are empty. Read access
follows the project (anyone who can see it).
"""
import logging
from functools import lru_cache

from django.contrib.gis.geos import Polygon
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.views.decorators.http import require_GET

from . import raster
from .catalog import CATALOG

log = logging.getLogger(__name__)

LAYER_FIELDS = ("id", "name", "source", "res", "period", "years", "year", "legend", "attribution", "desc", "opacity", "kind", "pmtiles",
                "scale", "minzoom", "maxzoom", "view_only", "period_label")
# Raster layers shown cut to an area: cloud-optimised files ("cog", which also download)
# and view-only pictures from outside services ("tiles", masked here).
LAYERS = {l["id"]: l for g in CATALOG for l in g["layers"]
          if (g["type"] == "raster" and (l.get("cog") or l["kind"] == "tiles")) or l["kind"] == "pmtiles"}
MASKED_TTL = 60 * 60 * 6


def _phases(layer):
    """Project phases a layer is offered in: its catalogue "phases" list, else all of them."""
    from apps.analysis.models import PHASES

    allowed = [k for k, _ in PHASES]
    return [p for p in layer.get("phases", allowed) if p in allowed]


def _layers():
    from .views import catalog_with_periods

    groups = []
    for g in catalog_with_periods(CATALOG):
        layers = [{**{k: l[k] for k in LAYER_FIELDS if k in l}, **({"minzoom": 0} if l.get("overview") else {}), **_style_info(l),
                   "phases": _phases(l)}
                  for l in g["layers"] if l["id"] in LAYERS]
        if layers:
            groups.append({"group": g["group"], "layers": layers})
    return groups


def _style_info(layer):
    """For layers whose palette and range users may change: the defaults to start from."""
    if not raster.is_styleable(layer):
        return {}
    r = layer["render"]
    lo, hi = (float(v) for v in r.get("rescale", "0,1").split(","))
    return {"style": {"cmap": r["colormap_name"], "range": [lo, hi]}}


def _style(request):
    return raster.parse_style(request.GET.get("cmap"), request.GET.get("range"))


def _project(request, code):
    from apps.projects.views import _get  # same visibility rules as the project page

    p, err = _get(request, code)
    if err:
        return None, err
    area = getattr(p, "area", None)
    if area is None:
        return None, JsonResponse({"error": "This project has no area of influence yet."}, status=400)
    return p, None


def _version(area):
    return int(area.updated.timestamp())


@lru_cache(maxsize=32)
def _area_3857(code, version, wkb):
    """The area in Web Mercator, prepared for fast tile tests (cached per area version)."""
    from django.contrib.gis.geos import GEOSGeometry

    g = GEOSGeometry(memoryview(wkb), srid=4326)
    w, s, e, n = g.extent
    tol = max(e - w, n - s) / 4000
    if tol > 0:
        g = g.simplify(tol, preserve_topology=True)
    g = g.transform(3857, clone=True)
    return g, g.prepared


def _layer(layer_id):
    layer = LAYERS.get(layer_id)
    return layer, (None if layer else JsonResponse({"error": "Unknown layer."}, status=404))


@require_GET
def satellite_list(request, code):
    p, err = _project(request, code)
    if err:
        return err
    return JsonResponse({"groups": _layers()})


@require_GET
def satellite_tiles(request, code, layer_id):
    p, err = _project(request, code)
    if err:
        return err
    layer, err = _layer(layer_id)
    if err:
        return err
    if layer["kind"] == "pmtiles":
        return JsonResponse({"error": "Vector tiles are read by the browser straight from the PMTiles archive."}, status=400)
    try:
        year = raster.pick_year(layer, request.GET.get("year"))
        style = _style(request) if raster.is_styleable(layer) else {}
    except raster.RasterError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    from urllib.parse import urlencode

    extra = {**({"year": year} if year is not None else {}),
             **({"cmap": style["colormap_name"]} if "colormap_name" in style else {}),
             **({"range": style["rescale"]} if "rescale" in style else {})}
    query = f"?v={_version(p.area)}" + (f"&{urlencode(extra)}" if extra else "")
    url = f"/api/projects/{p.code}/satellite/{layer_id}/xyz/{{z}}/{{x}}/{{y}}.png{query}"
    minzoom = 0 if layer.get("overview") else layer.get("minzoom", 0)
    return JsonResponse({"tiles": [url], "year": year, "minzoom": minzoom, "maxzoom": layer.get("maxzoom"),
                         "view_only": bool(layer.get("view_only")), "attribution": layer.get("attribution", "")})


@require_GET
def satellite_xyz(request, code, layer_id, z, x, y):
    p, err = _project(request, code)
    if err:
        return err
    layer, err = _layer(layer_id)
    if err:
        return err
    geom, prepared = _area_3857(p.code, _version(p.area), bytes(p.area.geom.wkb))
    lonlat, merc = raster.tile_bounds(z, x, y)
    tile = Polygon.from_bbox(merc)
    tile.srid = 3857
    empty = HttpResponse(raster.empty_png(), content_type="image/png")
    empty["Cache-Control"] = "public, max-age=3600"
    if not prepared.intersects(tile):
        return empty
    try:
        year = raster.pick_year(layer, request.GET.get("year"))
        style = _style(request) if raster.is_styleable(layer) else {}
        if layer["kind"] == "xyz":  # a public tile service draws it; only the mask is ours
            url = layer["url"].replace("{z}", str(z)).replace("{x}", str(x)).replace("{y}", str(y))
            if z > layer.get("maxZoom", 22):
                return empty
        else:
            url = raster.tile_url(layer, year, z, x, y, style=style)
        if url is None:
            return empty
        if prepared.contains(tile):
            resp = HttpResponseRedirect(url)
        else:
            key = f"masked:{p.code}:{_version(p.area)}:{layer_id}:{year}:{style.get('colormap_name', '')}:{style.get('rescale', '')}:{z}/{x}/{y}"
            png = cache.get(key)
            if png is None:
                png = raster.masked_tile(raster.fetch(url), geom, merc)
                cache.set(key, png, MASKED_TTL)
            resp = HttpResponse(png, content_type="image/png")
    except raster.RasterError as exc:
        log.warning("Project tile %s %s %s/%s/%s: %s", p.code, layer_id, z, x, y, exc)
        return empty
    resp["Cache-Control"] = "public, max-age=3600"
    return resp


@require_GET
def satellite_download(request, code, layer_id):
    p, err = _project(request, code)
    if err:
        return err
    layer, err = _layer(layer_id)
    if err:
        return err
    if layer["kind"] == "pmtiles":
        return JsonResponse({"error": "Field boundaries can't be downloaded here yet."}, status=400)
    if layer.get("view_only") or not layer.get("cog"):
        return JsonResponse({"error": "This layer is view only: a picture from an outside service, with no values to download."}, status=400)
    try:
        data, info = raster.clip_geotiff(layer, request.GET.get("year"), p.area.geom, mask=True)
    except raster.RasterError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:  # noqa: BLE001
        log.exception("Download failed for %s %s", code, layer_id)
        return JsonResponse({"error": f"Couldn't prepare this layer: {exc}"}, status=502)
    resp = HttpResponse(data, content_type="image/tiff")
    resp["Content-Disposition"] = f'attachment; filename="{p.code}_{layer_id}_{info["year"] or "static"}.tif"'
    resp["X-GEIDA-EPSG"] = str(info["epsg"])
    resp["X-GEIDA-Scale"] = str(info["scale"])
    resp["Access-Control-Expose-Headers"] = "X-GEIDA-EPSG, X-GEIDA-Scale"
    return resp
