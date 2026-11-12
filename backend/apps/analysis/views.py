"""
Analysis API.

    GET  /api/analysis/datasets/
    GET  /api/analysis/modules/?project=CODE        modules + availability for the project
    GET  /api/analysis/runs/?project=CODE[&phase=]
    POST /api/analysis/runs/                         {project, module, phase, params}
    GET  /api/analysis/runs/<id>/
    POST /api/analysis/runs/<id>/cancel/
    GET  /api/analysis/runs/<id>/files/<name>
    GET  /api/analysis/evidence/?project=CODE
    POST /api/analysis/evidence/<id>/accept/  |  /reject/
"""
import logging
import mimetypes

from django.db import transaction
from django.http import FileResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.core.api import BadRequest, error, json_body
from apps.projects.access import can_edit, can_view, is_reviewer
from apps.projects.models import Project

from .data import DATASETS
from .models import PHASE_INSTRUMENT, PHASES, Evidence, Module, ModuleRun
from .core.manifest import parse_point
from .core.registry import availability, manifest_public, read_categories, read_planned, sync_modules
from .tasks import enqueue

log = logging.getLogger(__name__)

MAX_ACTIVE_RUNS_PER_PROJECT = 5


def _project(request, code):
    p = Project.objects.select_related("area").filter(code=(code or "").upper()).first()
    if p is None or not can_view(request.user, p):
        return None
    return p


def _run_dict(r, detail=False, user=None):
    d = {
        "id": r.id, "project": r.project.code, "module": r.module_id, "module_title": r.module.title,
        "module_version": r.module_version, "phase": r.phase, "instrument": PHASE_INSTRUMENT[r.phase],
        "params": r.params, "status": r.status, "progress": r.progress, "error": r.error,
        "created": r.created.isoformat(), "started": r.started.isoformat() if r.started else None,
        "finished": r.finished.isoformat() if r.finished else None,
        "created_by": (r.created_by.get_full_name() or r.created_by.username) if r.created_by else "",
        "summary": r.summary,
        "can_delete": bool(user and _delete_problem(user, r) is None),
    }
    if detail:
        d.update({"outputs": r.outputs, "datasets": r.datasets, "log": r.log,
                  "evidence": [_evidence_dict(e) for e in r.evidence.all()]})
    return d


def _evidence_dict(e):
    return {
        "id": e.id, "run": e.run_id, "cri": e.cri_code, "indicator": e.indicator_id,
        "indicator_statement": e.indicator.statement if e.indicator else "",
        "phase": e.phase, "instrument": e.instrument, "label": e.label, "value": e.value, "unit": e.unit,
        "value_male": e.value_male, "value_female": e.value_female, "reference_date": e.reference_date,
        "role": e.role, "method": e.method, "data": e.data, "caveats": e.caveats, "status": e.status,
        "reviewed_by": (e.reviewed_by.get_full_name() or e.reviewed_by.username) if e.reviewed_by else "",
        "reviewed_at": e.reviewed_at.isoformat() if e.reviewed_at else None, "created": e.created.isoformat(),
    }


@require_GET
def datasets(request):
    return JsonResponse({"datasets": [d.describe() for d in DATASETS.values()]})


@require_GET
def modules(request):
    problems = []
    try:
        manifests = sync_modules(problems)
    except ValueError as exc:  # categories.yaml / planned.yaml problems
        return error(f"Analysis registry problem: {exc}", status=500)
    for p_ in problems:  # a broken analysis folder is left out; developers see why here and in check_analyses
        log.error("Analysis left out of the catalogue: %s", p_)
    p = _project(request, request.GET.get("project")) if request.GET.get("project") else None
    from apps.projects.models import CRI
    cri_names = {c.code: (c.name, c.unit) for c in CRI.objects.only("code", "name", "unit")}
    out = []
    for m in manifests.values():
        item = manifest_public(m)
        item["cri"] = [{**c, "name": cri_names.get(c["code"], ("", ""))[0], "unit": cri_names.get(c["code"], ("", ""))[1]}
                       for c in item.get("cri") or []]
        if p:
            item["availability"] = availability(m, p)
            item["cri_in_project"] = sorted(
                {c["code"] for c in m.get("cri", []) or []} & set(p.indicators.values_list("cri_id", flat=True)))
        out.append(item)
    out.sort(key=lambda x: (not x.get("cri_in_project"), x["title"]))
    counts = {}
    for item in out:
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    planned = read_planned(built=set(manifests))
    pcounts = {}
    for item in planned:
        pcounts[item["category"]] = pcounts.get(item["category"], 0) + 1
    categories = [{**c, "modules": counts.get(c["id"], 0), "planned": pcounts.get(c["id"], 0)} for c in read_categories()]
    return JsonResponse({"modules": out, "planned": planned, "categories": categories, "phases": [{"value": k, "label": v, "instrument": PHASE_INSTRUMENT[k]}
                                                    for k, v in PHASES]})


@require_http_methods(["GET", "POST"])
def runs(request):
    if request.method == "GET":
        p = _project(request, request.GET.get("project"))
        if p is None:
            return error("Project not found.", status=404)
        qs = p.runs.select_related("module", "created_by", "project").prefetch_related("evidence")
        if request.GET.get("phase"):
            qs = qs.filter(phase=request.GET["phase"])
        return JsonResponse({"runs": [_run_dict(r, user=request.user) for r in qs[:200]]})

    if not request.user.is_authenticated:
        return error("Sign in to run analyses.", status=401)
    try:
        data = json_body(request)
    except BadRequest as exc:
        return error(str(exc))
    p = _project(request, data.get("project"))
    if p is None:
        return error("Project not found.", status=404)
    if not (can_edit(request.user, p) or is_reviewer(request.user) or p.owner_id == request.user.id):
        return error("Only the project's owner or a reviewer can run analyses on it.", status=403)
    manifests = sync_modules()
    m = manifests.get(data.get("module"))
    if m is None:
        return error("Unknown module.")
    phase = data.get("phase")
    if phase not in dict(PHASES) or phase not in m.get("phases", []):
        return error("This module doesn't run in that phase.")
    av = availability(m, p)
    if av["status"] != "ready":
        return error(av["reasons"][0] if av["reasons"] else "This module can't run for this project.")
    params, errs = _clean_params(m, data.get("params") or {}, area=p.area.geom)
    if errs:
        return JsonResponse({"error": next(iter(errs.values())), "errors": errs}, status=400)
    if p.runs.filter(status__in=("queued", "running")).count() >= MAX_ACTIVE_RUNS_PER_PROJECT:
        return error("Several analyses are already running for this project. Wait for them to finish.")
    module = Module.objects.get(pk=m["id"])
    r = ModuleRun.objects.create(project=p, module=module, module_version=module.version, phase=phase,
                                 params=params, created_by=request.user)
    # Queue after the row is committed, so the worker can always read it.
    transaction.on_commit(lambda: enqueue(r))
    return JsonResponse({"run": _run_dict(r, user=request.user)}, status=201)


POINT_MAX_DISTANCE_KM = 10   # a point parameter may sit just outside the area (a dam or bridge downstream)


def _km_from_area(lonlat, area):
    """Distance in km from a point to the area (0 inside), measured in the point's UTM zone."""
    from django.contrib.gis.geos import Point
    from apps.core.geo import utm_epsg
    epsg = utm_epsg(*lonlat)
    pt, a = Point(*lonlat, srid=4326), area.clone()
    pt.transform(epsg)
    a.transform(epsg)
    return a.distance(pt) / 1000


def _clean_params(manifest, raw, area=None):
    out, errs = {}, {}
    for spec in manifest.get("parameters", []) or []:
        name, kind = spec["name"], spec.get("type", "number")
        v = raw.get(name, spec.get("default"))
        if kind == "number":
            try:
                v = float(v)
            except (TypeError, ValueError):
                errs[name] = f"{spec.get('label', name)} must be a number."
                continue
            lo, hi = spec.get("min"), spec.get("max")
            if (lo is not None and v < lo) or (hi is not None and v > hi):
                errs[name] = f"{spec.get('label', name)} must be between {lo} and {hi}."
                continue
        elif kind == "choice":
            match = [c["value"] for c in spec.get("choices", []) if str(c["value"]) == str(v)]
            if not match:
                errs[name] = f"Choose a value for {spec.get('label', name)}."
                continue
            v = match[0]
        elif kind == "criteria":
            from .core.manifest import parse_criteria
            v, problem = parse_criteria(v, spec.get("layers") or [])
            if problem:
                errs[name] = problem
                continue
        elif kind == "point":
            label = spec.get("label", name)
            if v in (None, "", []):
                errs[name] = f"Pick a point on the map for {label}."
                continue
            v = parse_point(v)
            if v is None:
                errs[name] = f"{label}: type longitude, latitude in degrees, e.g. 34.25, 2.31."
                continue
            if area is not None and _km_from_area(v, area) > POINT_MAX_DISTANCE_KM:
                errs[name] = f"{label} is more than {POINT_MAX_DISTANCE_KM} km from the area of influence."
                continue
        out[name] = v
    return out, errs


@require_http_methods(["GET", "DELETE"])
def run_detail(request, run_id):
    r = ModuleRun.objects.select_related("project", "module", "created_by").filter(pk=run_id).first()
    if r is None or not can_view(request.user, r.project):
        return error("Run not found.", status=404)
    if request.method == "DELETE":
        problem = _delete_problem(request.user, r)
        if problem:
            return error(problem, status=403 if "only delete" in problem else 400)
        return JsonResponse({"deleted": [_delete_run(request.user, r)]})
    d = _run_dict(r, detail=True, user=request.user)
    d["size_bytes"] = _folder_bytes(r.workdir)
    return JsonResponse({"run": d})


# Deleting runs ---------------------------------------------------------------------------------------------
# The person who started a run, or a reviewer, can delete it once it has finished. Runs with accepted evidence
# stay (that evidence is the project's record): a reviewer rejects the evidence first. Proposed and rejected
# evidence goes with the run; its files are removed; the project's Activity log records the deletion.

def _delete_problem(user, r):
    """Why this user can't delete this run, or None."""
    if not user.is_authenticated or not (r.created_by_id == user.id or is_reviewer(user)):
        return "You can only delete runs you started (reviewers can delete any)."
    if r.status in ("queued", "running"):
        return "This run hasn't finished. Cancel it or wait until it ends, then delete it."
    accepted = [e.cri_code for e in r.evidence.all() if e.status == "accepted"]
    if accepted:
        return (f"Run #{r.pk} has accepted evidence (CRI {', '.join(sorted(set(accepted)))}), which is the project's "
                "record. Reject that evidence first.")
    return None


def _folder_bytes(folder):
    if not folder.exists():
        return 0
    return sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())


def _delete_run(user, r):
    import shutil
    from apps.projects.views import log
    info = {"id": r.pk, "title": r.module.title, "bytes": _folder_bytes(r.workdir)}
    shutil.rmtree(r.workdir, ignore_errors=True)
    log(r.project, user, "deleted analysis run", run=r.pk, title=f"#{r.pk} {r.module.title} ({r.get_phase_display()})")
    r.delete()
    return info


@require_POST
def runs_delete(request):
    """Delete several runs: {"ids": [...]} -> {"deleted": [...], "refused": [{id, reason}]}."""
    try:
        ids = [int(i) for i in (json_body(request).get("ids") or [])]
    except (BadRequest, TypeError, ValueError):
        return error("Send the ids of the runs to delete.")
    deleted, refused = [], []
    for r in ModuleRun.objects.select_related("project", "module").filter(pk__in=ids):
        if not can_view(request.user, r.project):
            refused.append({"id": r.pk, "reason": "Run not found."})
        elif problem := _delete_problem(request.user, r):
            refused.append({"id": r.pk, "reason": problem})
        else:
            deleted.append(_delete_run(request.user, r))
    return JsonResponse({"deleted": deleted, "refused": refused})


@require_POST
def run_cancel(request, run_id):
    r = ModuleRun.objects.select_related("project").filter(pk=run_id).first()
    if r is None or not can_view(request.user, r.project):
        return error("Run not found.", status=404)
    if not (r.created_by_id == request.user.id or is_reviewer(request.user)):
        return error("You can't cancel this run.", status=403)
    if ModuleRun.objects.filter(pk=r.pk, status="queued").update(status="cancelled", finished=timezone.now()):
        return JsonResponse({"cancelled": r.pk})
    return error("Only queued runs can be cancelled.")


@require_GET
def run_file(request, run_id, name):
    r = ModuleRun.objects.select_related("project").filter(pk=run_id).first()
    if r is None or not can_view(request.user, r.project):
        return error("Run not found.", status=404)
    allowed = {f for o in r.outputs for f in (o.get("file"), o.get("data_file")) if f}  # data_file: raster values
    if name not in allowed:
        return error("File not found.", status=404)
    path = r.workdir / name
    if not path.exists():
        return error("File not found.", status=404)
    ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
    if name.endswith(".geojson"):
        ctype = "application/geo+json"
    elif name.endswith(".tif"):
        ctype = "image/tiff"
    return FileResponse(open(path, "rb"), content_type=ctype, as_attachment=request.GET.get("download") == "1",
                        filename=f"{r.project.code}_{r.module_id}_{name}")


@require_GET
def evidence_list(request):
    p = _project(request, request.GET.get("project"))
    if p is None:
        return error("Project not found.", status=404)
    qs = p.evidence.select_related("indicator", "reviewed_by")
    if request.GET.get("status"):
        qs = qs.filter(status=request.GET["status"])
    return JsonResponse({"evidence": [_evidence_dict(e) for e in qs[:500]]})


@require_POST
def evidence_review(request, evidence_id, action):
    e = Evidence.objects.select_related("project", "indicator").filter(pk=evidence_id).first()
    if e is None or not can_view(request.user, e.project):
        return error("Evidence not found.", status=404)
    if not (is_reviewer(request.user) or e.project.owner_id == request.user.id):
        return error("Only the project owner or a reviewer can accept evidence.", status=403)
    if action not in ("accept", "reject"):
        return error("Unknown action.", status=404)
    e.status = "accepted" if action == "accept" else "rejected"
    e.reviewed_by, e.reviewed_at = request.user, timezone.now()
    e.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    from apps.projects.models import ProjectLog

    ProjectLog.objects.create(project=e.project, user=request.user, action=f"evidence {e.status}",
                              detail={"cri": e.cri_code, "value": e.value, "unit": e.unit, "run": e.run_id})
    return JsonResponse({"evidence": _evidence_dict(e)})
