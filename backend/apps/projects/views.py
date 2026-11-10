"""
Project onboarding API (JSON). Routes in urls.py; see docs/specs/project-onboarding.md.
"""
import json

from django.contrib.gis.db.models import Union
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.core.api import BadRequest, error, json_body

from . import choices as C
from .access import can_edit, can_view, is_reviewer, visible
from .geometry import (GeometryError, buffer_point, clean, merge_features, read_upload, summary)
from .models import CRI, Indicator, Project, ProjectArea, ProjectDocument, ProjectLog
from .serializers import (clean_documents, clean_identity, clean_indicators, cri_dict,
                          missing_to_submit, project_detail, project_list_item)

PAGE = 500


def _need_sign_in():
    return error("Sign in to work on projects.", status=401)


def log(project, user, action, **detail):
    ProjectLog.objects.create(project=project, user=user if user.is_authenticated else None,
                              action=action, detail=detail)


def _perms(user, p):
    reviewer = is_reviewer(user)
    editable = can_edit(user, p)
    return {
        "can_edit": editable,
        "can_review": reviewer,
        "can_submit": editable and p.status == "draft",
        "can_return": reviewer and p.status in ("review", "published"),
        "can_publish": reviewer and p.status in ("draft", "review"),
        "can_delete": user.is_authenticated and p.status == "draft" and (reviewer or p.owner_id == user.id),
    }


def _detail(request, p):
    p = Project.objects.select_related("owner", "area").get(pk=p.pk)
    return JsonResponse({"project": project_detail(p, request.user, _perms(request.user, p))})


def _get(request, code, edit=False):
    p = Project.objects.select_related("owner").filter(code=code.upper()).first()
    if p is None or not can_view(request.user, p):
        return None, error("Project not found.", status=404)
    if edit and not can_edit(request.user, p):
        if not request.user.is_authenticated:
            return None, _need_sign_in()
        msg = ("This project is under review; a reviewer must return it before you can edit it."
               if p.status == "review" else "You can't edit this project.")
        return None, error(msg, status=403)
    return p, None


# Reference data ---------------------------------------------------------------

@require_GET
def meta(request):
    return JsonResponse({
        "countries": C.member_countries(),
        "sectors": C.as_options(C.SECTORS),
        "themes": C.as_options(C.THEMES),
        "stages": C.as_options(C.STAGES),
        "hubs": C.as_options(C.HUBS),
        "statuses": C.as_options(C.STATUSES),
        "levels": C.as_options(C.LEVELS),
        "tiers": C.as_options(C.TIERS),
        "geo_roles": C.as_options(C.GEO_ROLES),
        "doc_types": C.as_options(C.DOC_TYPES),
        "area_methods": C.as_options(C.AREA_METHODS),
        "user": {"signed_in": request.user.is_authenticated, "is_reviewer": is_reviewer(request.user)},
    })


@require_GET
def cri_search(request):
    q = request.GET.get("q", "").strip()
    qs = CRI.objects.all()
    if q:
        qs = qs.filter(Q(code__startswith=q) | Q(name__icontains=q) | Q(group_name__icontains=q))
    return JsonResponse({"cri": [cri_dict(c) for c in qs[:100]]})


# Projects -----------------------------------------------------------------------

@require_http_methods(["GET", "POST"])
def project_list(request):
    if request.method == "POST":
        return _create(request)
    qs = visible(Project.objects.select_related("owner", "area"), request.user)
    qs = qs.annotate(n_indicators=Count("indicators"))
    g = request.GET
    if g.get("status"):
        qs = qs.filter(status__in=g["status"].split(","))
    if g.get("country"):
        qs = qs.filter(country_iso3=g["country"].upper())
    if g.get("sector"):
        qs = qs.filter(sector=g["sector"])
    if g.get("stage"):
        qs = qs.filter(stage=g["stage"])
    if g.get("mine") and request.user.is_authenticated:
        qs = qs.filter(owner=request.user)
    if g.get("q"):
        q = g["q"].strip()
        qs = qs.filter(Q(code__icontains=q) | Q(title__icontains=q) | Q(country_name__icontains=q))
    items = list(qs[: PAGE + 1])
    user = request.user
    return JsonResponse({
        "projects": [project_list_item(p, user, can_edit(user, p)) for p in items[:PAGE]],
        "truncated": len(items) > PAGE,
        "counts": dict(visible(Project.objects.all(), user).values_list("status").annotate(n=Count("id"))),
    })


def _create(request):
    if not request.user.is_authenticated:
        return _need_sign_in()
    try:
        data = json_body(request)
    except BadRequest as exc:
        return error(str(exc))
    errors = {}
    fields = clean_identity({
        "code": data.get("code"), "title": data.get("title"), "country_iso3": data.get("country_iso3"),
        **{k: data[k] for k in ("sector", "stage", "start_date", "end_date", "otl", "hub", "location",
                                "themes", "components") if k in data},
    }, errors)
    if errors:
        return JsonResponse({"error": next(iter(errors.values()))[0], "errors": errors}, status=400)
    existing = Project.objects.filter(code=fields["code"]).first()
    if existing:
        return JsonResponse({
            "error": f"{existing.code} already exists. Open it to update it instead.",
            "exists": {"code": existing.code, "title": existing.title,
                       "can_edit": can_edit(request.user, existing),
                       "visible": can_view(request.user, existing)},
        }, status=409)
    p = Project.objects.create(owner=request.user, source="manual", **fields)
    log(p, request.user, "created")
    return _detail(request, p)


@require_http_methods(["GET", "PATCH", "DELETE"])
def project_detail_view(request, code):
    if request.method == "GET":
        p, err = _get(request, code)
        return err or _detail(request, p)
    p, err = _get(request, code, edit=True)
    if err:
        return err
    if request.method == "DELETE":
        if not _perms(request.user, p)["can_delete"]:
            return error("Only draft projects can be deleted.", status=403)
        p.delete()
        return JsonResponse({"deleted": code.upper()})
    try:
        data = json_body(request)
    except BadRequest as exc:
        return error(str(exc))
    errors = {}
    fields = clean_identity({k: v for k, v in data.items() if k in (
        "code", "title", "country_iso3", "sector", "stage", "start_date", "end_date", "otl", "hub",
        "location", "themes", "components")}, errors)
    if errors:
        return JsonResponse({"error": next(iter(errors.values()))[0], "errors": errors}, status=400)
    if "code" in fields and fields["code"] != p.code and Project.objects.filter(code=fields["code"]).exists():
        return JsonResponse({"error": f"{fields['code']} already exists.", "errors": {"code": ["This code is already used."]}}, status=409)
    changed = [k for k, v in fields.items() if getattr(p, k) != v]
    for k, v in fields.items():
        setattr(p, k, v)
    p.save()
    if changed:
        log(p, request.user, "edited", fields=changed)
    return _detail(request, p)


# Area of influence -------------------------------------------------------------

def _area_from_request(request):
    """Build (MultiPolygon, notes, meta) from a preview/save request. Raises GeometryError."""
    if request.content_type and request.content_type.startswith("multipart/"):
        f = request.FILES.get("file")
        if not f:
            raise GeometryError("Choose a file to upload.")
        features, notes = read_upload(f)
        idx = request.POST.get("features")
        indexes = None
        if idx:
            try:
                indexes = {int(x) for x in idx.split(",")}
            except ValueError as exc:
                raise GeometryError("Choose features from the list.") from exc
        merged, more = merge_features(features, indexes)
        mp, notes = clean(merged, notes + more)
        listing = [{"index": x["index"], "name": x["name"], "geom_type": x["geom_type"],
                    "whole_world": x["whole_world"],
                    "selected": (x["index"] in indexes) if indexes is not None else
                    (not x["whole_world"] and x["geom_type"] in ("Polygon", "MultiPolygon"))}
                   for x in features]
        return mp, notes, {"method": "upload", "source_name": f.name, "features": listing,
                           "iso3": request.POST.get("country_iso3", "")}
    data = json_body(request)
    method = data.get("method")
    iso3 = (data.get("country_iso3") or "").upper()
    if method == "draw":
        from django.contrib.gis.geos import GEOSException, GEOSGeometry

        raw = data.get("geometry")
        if not isinstance(raw, dict) or raw.get("type") not in ("Polygon", "MultiPolygon"):
            raise GeometryError("Draw a polygon on the map first.")
        try:
            g = GEOSGeometry(json.dumps(raw), srid=4326)
        except (GEOSException, ValueError) as exc:
            raise GeometryError("The drawn shape isn't valid.") from exc
        mp, notes = clean(g)
        return mp, notes, {"method": "draw", "iso3": iso3}
    if method == "buffer":
        try:
            lon, lat, km = float(data.get("lon")), float(data.get("lat")), float(data.get("km") or 5)
        except (TypeError, ValueError) as exc:
            raise GeometryError("Enter longitude, latitude and a radius in km.") from exc
        mp = buffer_point(lon, lat, km)
        return mp, [f"Circle of {km:g} km radius around {lat:.5f}, {lon:.5f}."], {
            "method": "buffer", "buffer": {"lon": lon, "lat": lat, "km": km}, "iso3": iso3}
    if method in ("admin", "country"):
        from apps.boundaries.models import AdminUnit

        gids = data.get("gids") or []
        if method == "country":
            unit = AdminUnit.objects.filter(level=0, iso3=iso3, disputed=False).first()
            if unit is None:
                raise GeometryError("Country boundaries aren't loaded yet (run load_admin_units).")
            gids = [unit.gid]
        if not isinstance(gids, list) or not gids:
            raise GeometryError("Pick at least one administrative unit.")
        if len(gids) > 500:
            raise GeometryError("Pick at most 500 administrative units.")
        qs = AdminUnit.objects.filter(gid__in=gids)
        if qs.count() != len(set(gids)):
            raise GeometryError("Some administrative units weren't found.")
        merged = qs.aggregate(g=Union("geom"))["g"]
        names = list(qs.values_list("name", flat=True)[:6])
        mp, notes = clean(merged)
        label = ", ".join(names) + ("…" if len(gids) > 6 else "")
        return mp, notes + [f"Merged {len(gids)} unit(s): {label}." if method == "admin" else "Whole country (GADM 4.1)."], {
            "method": method, "admin_gids": gids, "iso3": iso3}
    raise GeometryError("Choose how to define the area: upload, draw, admin units or point and buffer.")


@require_POST
def area_preview(request):
    """Check an area without saving it: geometry, area, and every change made."""
    if not request.user.is_authenticated:
        return _need_sign_in()
    try:
        mp, notes, meta_ = _area_from_request(request)
    except (GeometryError, BadRequest) as exc:
        return error(str(exc))
    return JsonResponse({**summary(mp, notes, meta_.get("iso3") or None), **{
        k: v for k, v in meta_.items() if k != "iso3"}})


@require_http_methods(["PUT", "POST", "DELETE"])
def project_area(request, code):
    p, err = _get(request, code, edit=True)
    if err:
        return err
    if request.method == "DELETE":
        ProjectArea.objects.filter(project=p).delete()
        log(p, request.user, "area removed")
        return _detail(request, p)
    try:
        mp, notes, meta_ = _area_from_request(request)
    except (GeometryError, BadRequest) as exc:
        return error(str(exc))
    s = summary(mp, notes, p.country_iso3)
    ProjectArea.objects.update_or_create(project=p, defaults={
        "method": meta_["method"],
        "geom": mp,
        "area_km2": s["area_km2"],
        "notes": s["notes"],
        "source_name": meta_.get("source_name", ""),
        "admin_gids": meta_.get("admin_gids", []),
        "buffer": meta_.get("buffer", {}),
    })
    p.save(update_fields=["updated"])
    log(p, request.user, "area set", method=meta_["method"], area_km2=s["area_km2"])
    return _detail(request, p)


# Results Framework and documents ------------------------------------------------

@require_http_methods(["PUT"])
def project_indicators(request, code):
    p, err = _get(request, code, edit=True)
    if err:
        return err
    try:
        data = json_body(request)
    except BadRequest as exc:
        return error(str(exc))
    errors = {}
    rows = clean_indicators(data.get("indicators"), errors)
    if errors:
        return JsonResponse({"error": "Check the highlighted indicators.", "errors": errors}, status=400)
    with transaction.atomic():
        p.indicators.all().delete()
        Indicator.objects.bulk_create([Indicator(project=p, **r) for r in rows])
        p.save(update_fields=["updated"])
    log(p, request.user, "results framework saved", indicators=len(rows))
    return _detail(request, p)


@require_http_methods(["PUT"])
def project_documents(request, code):
    p, err = _get(request, code, edit=True)
    if err:
        return err
    try:
        data = json_body(request)
    except BadRequest as exc:
        return error(str(exc))
    errors = {}
    rows = clean_documents(data.get("documents"), errors)
    if errors:
        return JsonResponse({"error": "Check the highlighted links.", "errors": errors}, status=400)
    with transaction.atomic():
        p.documents.all().delete()
        ProjectDocument.objects.bulk_create([ProjectDocument(project=p, **r) for r in rows])
        p.save(update_fields=["updated"])
    log(p, request.user, "documents saved", documents=len(rows))
    return _detail(request, p)


# Review workflow -----------------------------------------------------------------

@require_POST
def project_action(request, code, action):
    p, err = _get(request, code)
    if err:
        return err
    if not request.user.is_authenticated:
        return _need_sign_in()
    perms = _perms(request.user, p)
    try:
        data = json_body(request)
    except BadRequest as exc:
        return error(str(exc))
    now = timezone.now()
    if action == "submit":
        if not perms["can_submit"]:
            return error("Only draft projects you can edit can be submitted.", status=403)
        missing = missing_to_submit(p)
        if missing:
            return error("Complete the project before submitting.", missing=missing)
        p.status, p.submitted_at, p.review_comment = "review", now, ""
    elif action == "return":
        if not perms["can_return"]:
            return error("Only reviewers can return projects.", status=403)
        comment = str(data.get("comment") or "").strip()
        if not comment:
            return error("Say what needs changing so the owner can fix it.")
        p.status, p.review_comment = "draft", comment[:2000]
    elif action == "publish":
        if not perms["can_publish"]:
            return error("Only reviewers can publish projects.", status=403)
        missing = missing_to_submit(p)
        if missing:
            return error("The project needs its identity fields and an area before publishing.", missing=missing)
        p.status, p.published_at, p.review_comment = "published", now, ""
    else:
        return error("Unknown action.", status=404)
    p.save()
    log(p, request.user, {"submit": "submitted", "return": "returned", "publish": "published"}[action],
        **({"comment": p.review_comment} if action == "return" else {}))
    return _detail(request, p)
