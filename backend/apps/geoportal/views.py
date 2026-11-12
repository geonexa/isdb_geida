"""
Data Catalog (Geo-Portal) API.

    GET  /api/geoportal/config/                         catalog, basemaps, toolbox, member countries
    GET  /api/geoportal/basemaps/                       basemaps only (shared with the project map)
    GET  /api/geoportal/layers/<id>/tiles/?year=        XYZ template for a cloud-optimised layer
    GET  /api/geoportal/layers/<id>/xyz/<z>/<x>/<y>.png tile of a tiled dataset (redirect to TiTiler)
    POST /api/geoportal/layers/<id>/clip/               GeoTIFF of a layer over a project area
    (saved project areas: see areas.py)
"""
import json
import logging
from urllib.parse import urlencode

from django.contrib.gis.geos import GEOSException, GEOSGeometry
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from . import raster
from .catalog import BASEMAPS, CATALOG

log = logging.getLogger(__name__)
LAYERS = {l["id"]: l for g in CATALOG for l in g["layers"]}
# The global Data Catalog page leaves out layers computed on the fly for project areas only.
PORTAL_CATALOG = [{**g, "layers": [l for l in g["layers"] if not l.get("projects_only")]} for g in CATALOG]
PORTAL_LAYERS = {l["id"]: l for g in PORTAL_CATALOG for l in g["layers"]}
_countries = None


def member_countries():
    """IsDB member countries [{iso, name}] sorted by name, read once from the boundary file."""
    global _countries
    if _countries is None:
        from apps.reference.catalog import CatalogError, dataset_file
        try:
            path = dataset_file("member_countries")  # REFERENCE_DATA_DIR/catalog.json
            feats = json.loads(path.read_text(encoding="utf-8"))["features"]
            _countries = sorted(
                ({"iso": f["properties"].get("iso", ""), "name": f["properties"].get("name", "")} for f in feats),
                key=lambda c: c["name"],
            )
        except (OSError, ValueError, KeyError, CatalogError):
            log.exception("Couldn't read the IsDB member countries")
            return []
    return _countries


@require_GET
def basemaps(request):
    """The basemap list alone, for other maps (the project map) that use the same basemaps."""
    return JsonResponse({"basemaps": BASEMAPS})


def catalog_with_periods(catalog):
    """The catalogue with periods filled in for layers whose dates come from their service (Wayback)."""
    out = []
    for g in catalog:
        layers = []
        for l in g["layers"]:
            if l.get("periods_from"):
                years = raster.periods(l)
                l = {**l, "years": years, "year": years[-1] if years else None}
            layers.append(l)
        out.append({**g, "layers": layers})
    return out


@require_GET
def config(request):
    return JsonResponse({
        "catalog": catalog_with_periods(PORTAL_CATALOG),
        "basemaps": BASEMAPS,
        "countries": member_countries(),
        "live_count": sum(1 for l in PORTAL_LAYERS.values() if l["kind"] != "planned"),
        "total_count": len(PORTAL_LAYERS),
    })


def _tile_response(url):
    """Redirect to a tile, or an empty tile when there is nothing to draw."""
    if url is None:
        resp = HttpResponse(raster.empty_png(), content_type="image/png")
    else:
        resp = HttpResponseRedirect(url)
    resp["Cache-Control"] = "public, max-age=3600"
    return resp


@require_GET
def layer_tiles(request, layer_id):
    """XYZ tile template for a cloud-optimised layer: TiTiler itself for one COG, GEIDA's tile route for tiled datasets."""
    layer = LAYERS.get(layer_id)
    if layer is None:
        return JsonResponse({"error": "Unknown layer."}, status=404)
    if layer["kind"] not in ("cog", "tiles"):
        return JsonResponse({"error": "This layer doesn't need a tile request."}, status=400)
    try:
        year = raster.pick_year(layer, request.GET.get("year"))
    except raster.RasterError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    route = f"/api/geoportal/layers/{layer_id}/xyz/{{z}}/{{x}}/{{y}}.png" + (f"?{urlencode({'year': year})}" if year is not None else "")
    if layer["kind"] == "tiles":  # view only: straight to the outside service when it has an XYZ template
        url = raster.external_template(layer, year) or route
    elif raster.is_single(layer) and not layer.get("overview"):
        url = raster.tile_template(layer, year)
    else:
        url = route
    # Layers with a WMS overview draw at every zoom; others only from their minzoom.
    minzoom = 0 if layer.get("overview") else layer.get("minzoom", 0)
    return JsonResponse({"tiles": [url], "year": year, "minzoom": minzoom, "maxzoom": layer.get("maxzoom"),
                         "view_only": bool(layer.get("view_only")), "attribution": layer.get("attribution", "")})


@require_GET
def layer_xyz(request, layer_id, z, x, y):
    """One tile of a tiled dataset (DEM, WorldCover): the files under it, mosaicked by TiTiler."""
    layer = LAYERS.get(layer_id)
    if layer is None or layer["kind"] not in ("cog", "tiles"):
        return JsonResponse({"error": "Unknown layer."}, status=404)
    try:
        url = raster.tile_url(layer, raster.pick_year(layer, request.GET.get("year")), z, x, y)
    except raster.RasterError as exc:
        log.warning("Tile %s %s/%s/%s: %s", layer_id, z, x, y, exc)
        url = None
    return _tile_response(url)


@require_POST
def layer_clip(request, layer_id):
    """GeoTIFF of a layer's raw values over a project area (for the Toolbox)."""
    layer = LAYERS.get(layer_id)
    if layer is None or not layer.get("cog") or layer.get("view_only"):
        return JsonResponse({"error": "This layer can't be clipped for analysis."}, status=400)
    try:
        body = json.loads(request.body or b"{}")
        geom = GEOSGeometry(json.dumps(body["geometry"]), srid=4326)
    except (ValueError, KeyError, TypeError, GEOSException):
        return JsonResponse({"error": "Send the project area as GeoJSON geometry."}, status=400)
    try:
        data, info = raster.clip_geotiff(layer, body.get("year"), geom)
    except raster.RasterError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:  # noqa: BLE001
        log.exception("Clip failed for %s", layer_id)
        return JsonResponse({"error": f"Couldn't prepare the data: {exc}"}, status=502)
    resp = HttpResponse(data, content_type="image/tiff")
    resp["Content-Disposition"] = f'attachment; filename="{layer_id}_{info["year"] or "static"}.tif"'
    resp["X-GEIDA-EPSG"] = str(info["epsg"])
    resp["X-GEIDA-Scale"] = str(info["scale"])
    resp["X-GEIDA-Year"] = str(info["year"] or "")
    resp["Access-Control-Expose-Headers"] = "X-GEIDA-EPSG, X-GEIDA-Scale, X-GEIDA-Year"
    return resp
