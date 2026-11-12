"""
Map export layouts kept in the database, per user, so they follow the user to any computer or browser:

    GET  /api/projects/<code>/map-layout/   {layout, dpi, templates, stored: {layout, settings}}
    PUT  /api/projects/<code>/map-layout/   {layout?, dpi?}     the last layout for this project, the export resolution
    GET  /api/projects/map-templates/       {templates}
    POST /api/projects/map-templates/       {name, layout} or {templates: [{name, layout, saved?}]} (moving browser templates)
    DELETE /api/projects/map-templates/     {name}

Signed-in users only (anyone else keeps layouts in the browser). Anyone who can view a project can keep their own
layout for it: it is only their export page, not project data.
"""
import json

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.core.api import BadRequest, error, json_body

from .models import MapLayout, MapSettings, MapTemplate

MAX_LAYOUT_BYTES = 8 * 1024 * 1024     # pictures are stored in the layout; keep each one reasonable
MAX_TEMPLATES = 20
DPIS = {96, 150, 200, 300, 600}


def _need_sign_in():
    return error("Sign in to keep map layouts.", status=401)


def _layout(v):
    """A valid layout (a version 2 page with items), or BadRequest."""
    if not isinstance(v, dict) or v.get("version") != 2 or not isinstance(v.get("items"), list):
        raise BadRequest("That isn't a map layout.")
    if len(json.dumps(v)) > MAX_LAYOUT_BYTES:
        raise BadRequest("The layout is too large to keep (over 8 MB); use smaller pictures.")
    return v


def _templates(user):
    return [{"name": t.name, "saved": t.saved.isoformat(), "layout": t.layout} for t in MapTemplate.objects.filter(user=user)]


def _dpi(user):
    s = MapSettings.objects.filter(user=user).first()
    return (s.dpi if s else 300), s is not None


@require_http_methods(["GET", "PUT"])
def map_layout(request, code):
    from .views import _get
    if not request.user.is_authenticated:
        return _need_sign_in()
    p, err = _get(request, code)
    if err:
        return err
    if request.method == "PUT":
        try:
            data = json_body(request)
            if "layout" in data:
                MapLayout.objects.update_or_create(user=request.user, project=p, defaults={"layout": _layout(data["layout"])})
            if "dpi" in data:
                dpi = int(data["dpi"]) if str(data["dpi"]).isdigit() else 0
                if dpi not in DPIS:
                    raise BadRequest(f"Resolution must be one of {', '.join(map(str, sorted(DPIS)))} dpi.")
                MapSettings.objects.update_or_create(user=request.user, defaults={"dpi": dpi})
        except BadRequest as exc:
            return error(str(exc))
        return JsonResponse({"saved": True})
    saved = MapLayout.objects.filter(user=request.user, project=p).first()
    dpi, has_settings = _dpi(request.user)
    return JsonResponse({"layout": saved.layout if saved else None, "dpi": dpi, "templates": _templates(request.user),
                         "stored": {"layout": saved is not None, "settings": has_settings}})


@require_http_methods(["GET", "POST", "DELETE"])
def map_templates(request):
    if not request.user.is_authenticated:
        return _need_sign_in()
    user = request.user
    if request.method == "GET":
        return JsonResponse({"templates": _templates(user)})
    try:
        data = json_body(request)
        if request.method == "DELETE":
            MapTemplate.objects.filter(user=user, name=str(data.get("name") or "")).delete()
            return JsonResponse({"templates": _templates(user)})
        items = data["templates"] if isinstance(data.get("templates"), list) else [data]
        for it in items:
            name = str((it or {}).get("name") or "").strip()[:80]
            if not name:
                raise BadRequest("Give the template a name.")
            MapTemplate.objects.update_or_create(user=user, name=name, defaults={"layout": _layout(it.get("layout"))})
    except BadRequest as exc:
        return error(str(exc))
    # Keep the most recent MAX_TEMPLATES, as the browser version did.
    old = MapTemplate.objects.filter(user=user).values_list("pk", flat=True)[MAX_TEMPLATES:]
    MapTemplate.objects.filter(pk__in=list(old)).delete()
    return JsonResponse({"templates": _templates(user)})
