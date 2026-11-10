"""
Saved project areas: list, save and delete the signed-in user's areas (PostGIS).

    GET    /api/geoportal/areas/        -> {"areas": [...]}
    POST   /api/geoportal/areas/        {name, geometry, country_iso, country_name} -> {"area": {...}}
    PATCH  /api/geoportal/areas/<id>/   {name} -> {"area": {...}}
    DELETE /api/geoportal/areas/<id>/   -> {"deleted": id}
"""
import json

from django.contrib.gis.geos import GEOSException, GEOSGeometry, MultiPolygon
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.core.geo import utm_epsg
from .models import ProjectArea

MAX_AREAS_PER_USER = 200
MAX_VERTICES = 50_000


def _need_sign_in():
    return JsonResponse({"error": "Sign in to save project areas."}, status=401)


def _as_dict(a):
    return {
        "id": a.id,
        "name": a.name,
        "country_iso": a.country_iso,
        "country_name": a.country_name,
        "area_km2": round(a.area_km2, 3),
        "updated": a.updated.isoformat(),
        "geometry": json.loads(a.geom.geojson),
    }


def _to_multipolygon(raw):
    """GeoJSON geometry (Polygon or MultiPolygon, EPSG:4326) -> valid MultiPolygon."""
    if not isinstance(raw, dict) or raw.get("type") not in ("Polygon", "MultiPolygon"):
        raise ValueError("Send the project area as a GeoJSON Polygon or MultiPolygon.")
    try:
        geom = GEOSGeometry(json.dumps(raw), srid=4326)
    except (GEOSException, ValueError, TypeError) as exc:
        raise ValueError("The project area isn't valid GeoJSON.") from exc
    if geom.num_coords > MAX_VERTICES:
        raise ValueError("The project area has too many points. Simplify it and try again.")
    if not geom.valid:
        geom = geom.make_valid()
        polys = [g for g in (geom if geom.geom_type in ("GeometryCollection", "MultiPolygon") else [geom]) if g.geom_type in ("Polygon", "MultiPolygon")]
        parts = []
        for p in polys:
            parts.extend(p if p.geom_type == "MultiPolygon" else [p])
        if not parts:
            raise ValueError("The project area has no size. Draw a polygon or rectangle.")
        geom = MultiPolygon(parts, srid=4326)
    if geom.geom_type == "Polygon":
        geom = MultiPolygon(geom, srid=4326)
    if geom.empty:
        raise ValueError("The project area has no size. Draw a polygon or rectangle.")
    return geom


def _area_km2(geom):
    c = geom.centroid
    local = geom.transform(utm_epsg(c.x, c.y), clone=True)
    return local.area / 1e6


@require_http_methods(["GET", "POST"])
def area_list(request):
    if not request.user.is_authenticated:
        return _need_sign_in()
    mine = ProjectArea.objects.filter(owner=request.user)
    if request.method == "GET":
        return JsonResponse({"areas": [_as_dict(a) for a in mine]})

    try:
        body = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"error": "Couldn't read the request."}, status=400)
    name = (body.get("name") or "").strip()[:120]
    if not name:
        return JsonResponse({"error": "Give the area a name."}, status=400)
    if mine.count() >= MAX_AREAS_PER_USER:
        return JsonResponse({"error": f"You can save up to {MAX_AREAS_PER_USER} areas. Delete one to save another."}, status=400)
    try:
        geom = _to_multipolygon(body.get("geometry"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    area = ProjectArea.objects.create(
        owner=request.user,
        name=name,
        country_iso=(body.get("country_iso") or "").strip()[:3].upper(),
        country_name=(body.get("country_name") or "").strip()[:120],
        geom=geom,
        area_km2=_area_km2(geom),
    )
    return JsonResponse({"area": _as_dict(area)}, status=201)


@require_http_methods(["PATCH", "DELETE"])
def area_detail(request, area_id):
    if not request.user.is_authenticated:
        return _need_sign_in()
    if request.method == "PATCH":
        area = ProjectArea.objects.filter(owner=request.user, pk=area_id).first()
        if area is None:
            return JsonResponse({"error": "That area doesn't exist or isn't yours."}, status=404)
        try:
            body = json.loads(request.body or b"{}")
        except ValueError:
            return JsonResponse({"error": "Couldn't read the request."}, status=400)
        name = (body.get("name") or "").strip()[:120]
        if not name:
            return JsonResponse({"error": "Give the area a name."}, status=400)
        area.name = name
        area.save(update_fields=["name", "updated"])
        return JsonResponse({"area": _as_dict(area)})
    deleted, _ = ProjectArea.objects.filter(owner=request.user, pk=area_id).delete()
    if not deleted:
        return JsonResponse({"error": "That area doesn't exist or isn't yours."}, status=404)
    return JsonResponse({"deleted": area_id})
