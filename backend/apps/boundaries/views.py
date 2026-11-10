"""
Admin boundaries (GADM 4.1, levels 0-3) for the IsDB member countries.

    GET  /api/boundaries/units/?iso3=UGA&level=1[&parent=UGA.1_1][&q=kamp]
         -> {"units": [{gid, name, level, type, parent_gid, path, area_km2, bbox}, ...]}
    GET  /api/boundaries/units/geojson/?iso3=UGA&level=1[&parent=...]
         -> FeatureCollection with the simplified (display) geometry, for the picker map
    GET  /api/boundaries/units/<gid>/[?full=1]
         -> Feature (display geometry, or full resolution with full=1)
    GET  /api/boundaries/at/?lon=32.58&lat=0.32[&level=3]
         -> {"units": [...]} the units containing the point, country down to level 3
    GET  /api/boundaries/world/
         -> FeatureCollection of every country (level 0), heavily simplified, for small-scale
            maps such as the globe locator in map export (cached)
    POST /api/boundaries/union/  {"gids": ["UGA.1_1", "UGA.2_1"]}
         -> {"geometry": MultiPolygon (full resolution), "area_km2", "gids"}
"""
import json

from django.contrib.gis.db.models import Union
from django.contrib.gis.geos import MultiPolygon, Point
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from apps.core.api import BadRequest, error, json_body

from .models import AdminUnit

MAX_LIST = 5000
MAX_GEOJSON = 3000
MAX_UNION = 500
LEVELS = (0, 1, 2, 3)


def _bbox(geom):
    if not geom:
        return None
    x0, y0, x1, y1 = geom.extent
    return [round(x0, 5), round(y0, 5), round(x1, 5), round(y1, 5)]


def _props(u):
    return {
        "gid": u.gid,
        "name": u.name,
        "name_local": u.name_local,
        "level": u.level,
        "type": u.type,
        "iso3": u.iso3,
        "country": u.country,
        "parent_gid": u.parent_gid,
        "path": u.path,
        "area_km2": round(u.area_km2, 3),
        "disputed": u.disputed,
    }


def _filtered(request):
    qs = AdminUnit.objects.all()
    iso3 = request.GET.get("iso3", "").upper()
    level = request.GET.get("level")
    parent = request.GET.get("parent", "")
    q = request.GET.get("q", "").strip()
    if not (iso3 or parent):
        raise BadRequest("Choose a country (iso3) or a parent unit.")
    if iso3:
        qs = qs.filter(iso3=iso3)
    if parent:
        qs = qs.filter(parent_gid=parent)
    if level not in (None, ""):
        try:
            level = int(level)
        except ValueError as exc:
            raise BadRequest("Level must be 0, 1, 2 or 3.") from exc
        if level not in LEVELS:
            raise BadRequest("Level must be 0, 1, 2 or 3.")
        qs = qs.filter(level=level)
    if q:
        qs = qs.filter(name__icontains=q)
    return qs


@require_GET
def unit_list(request):
    try:
        qs = _filtered(request)
    except BadRequest as exc:
        return error(str(exc))
    units = list(qs.defer("geom")[: MAX_LIST + 1])
    return JsonResponse({
        "units": [{**_props(u), "bbox": _bbox(u.geom_display)} for u in units[:MAX_LIST]],
        "truncated": len(units) > MAX_LIST,
    })


@require_GET
def unit_geojson(request):
    try:
        qs = _filtered(request)
    except BadRequest as exc:
        return error(str(exc))
    units = list(qs.defer("geom")[: MAX_GEOJSON + 1])
    if len(units) > MAX_GEOJSON:
        return error("Too many units to draw. Pick a parent unit or a higher level.")
    return JsonResponse({
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "id": u.gid, "properties": _props(u),
             "geometry": json.loads(u.geom_display.geojson) if u.geom_display else None}
            for u in units
        ],
    })


@require_GET
def unit_detail(request, gid):
    full = request.GET.get("full") in ("1", "true")
    u = AdminUnit.objects.filter(gid=gid).first()
    if u is None:
        return error("Admin unit not found.", status=404)
    geom = u.geom if full or u.geom_display is None else u.geom_display
    return JsonResponse({
        "type": "Feature", "id": u.gid,
        "properties": {**_props(u), "bbox": _bbox(geom), "resolution": "full" if geom is u.geom else "display"},
        "geometry": json.loads(geom.geojson),
    })


WORLD_TOLERANCE = 0.12   # degrees (~13 km): enough for a globe or continent locator
WORLD_MIN_AREA = 0.15    # deg²: drop islands smaller than this (a country's largest part is always kept)
WORLD_CACHE_KEY = "boundaries:world:v2"


def _small_scale(geom):
    """GeoJSON coordinates of a country simplified for small-scale maps (0.1° grid, tiny islands dropped)."""
    polys = list(geom) if geom.geom_type == "MultiPolygon" else [geom]
    polys.sort(key=lambda p: p.area, reverse=True)
    kept = [p for i, p in enumerate(polys) if i == 0 or p.area >= WORLD_MIN_AREA]
    out = []
    for poly in kept:
        g = poly.simplify(WORLD_TOLERANCE, preserve_topology=True)
        if g.empty or g.geom_type != "Polygon":
            continue
        rings = []
        for ring in g:
            pts = []
            for x, y in ring.coords:
                pt = [round(x, 1), round(y, 1)]
                if not pts or pts[-1] != pt:
                    pts.append(pt)
            if len(pts) >= 4:
                rings.append(pts)
        if rings:
            out.append(rings)
    return out


@require_GET
def world(request):
    """Every country outline, simplified for maps at globe or continent scale (cached)."""
    data = cache.get(WORLD_CACHE_KEY)
    if data is None:
        features = []
        for u in AdminUnit.objects.filter(level=0).defer("geom").order_by("gid"):
            if u.geom_display is None:
                continue
            coords = _small_scale(u.geom_display)
            if coords:
                features.append({"type": "Feature", "id": u.gid, "properties": {"gid": u.gid, "name": u.name},
                                 "geometry": {"type": "MultiPolygon", "coordinates": coords}})
        data = {"type": "FeatureCollection", "features": features}
        cache.set(WORLD_CACHE_KEY, data, 60 * 60 * 24)
    resp = JsonResponse(data)
    resp["Cache-Control"] = "public, max-age=86400"
    return resp


@require_GET
def units_at(request):
    try:
        lon, lat = float(request.GET["lon"]), float(request.GET["lat"])
    except (KeyError, ValueError):
        return error("Send lon and lat as numbers.")
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return error("lon/lat are out of range.")
    try:
        max_level = int(request.GET.get("level", 3))
    except ValueError:
        return error("Level must be 0, 1, 2 or 3.")
    pt = Point(lon, lat, srid=4326)
    units = (AdminUnit.objects.filter(level__lte=max_level, geom__intersects=pt)
             .defer("geom", "geom_display").order_by("level"))
    return JsonResponse({"units": [_props(u) for u in units]})


@require_POST
def units_union(request):
    try:
        data = json_body(request)
    except BadRequest as exc:
        return error(str(exc))
    gids = data.get("gids")
    if not isinstance(gids, list) or not gids or not all(isinstance(g, str) for g in gids):
        return error("Send the admin units as a list of GADM ids (gids).")
    if len(gids) > MAX_UNION:
        return error(f"Pick at most {MAX_UNION} admin units.")
    qs = AdminUnit.objects.filter(gid__in=set(gids))
    found = set(qs.values_list("gid", flat=True))
    missing = sorted(set(gids) - found)
    if missing:
        return error("Some admin units weren't found.", missing=missing[:20])
    merged = qs.aggregate(g=Union("geom"))["g"]
    if merged.geom_type == "Polygon":
        merged = MultiPolygon(merged, srid=4326)
    area = sum(qs.values_list("area_km2", flat=True))
    return JsonResponse({
        "gids": sorted(found),
        "area_km2": round(area, 3),
        "bbox": _bbox(merged),
        "geometry": json.loads(merged.geojson),
    })
