"""
Toolbox API.

    GET    /api/toolbox/tools/                       curated tools with their forms
    GET    /api/toolbox/<code>/inputs/               layers a tool can read for this project
    GET    /api/toolbox/<code>/runs/                 the project's Toolbox runs
    POST   /api/toolbox/<code>/runs/                 {tool, params, inputs, name?}
    GET    /api/toolbox/runs/<id>/                   one run, with outputs and log
    PATCH  /api/toolbox/runs/<id>/                   {name}
    DELETE /api/toolbox/runs/<id>/
    POST   /api/toolbox/runs/delete/                 {ids: [...]}
    GET    /api/toolbox/runs/<id>/files/<name>       an output file (?download=1)
    GET    /api/toolbox/<code>/uploads/              files uploaded for the Toolbox
    POST   /api/toolbox/<code>/uploads/              multipart: file, name?
    DELETE /api/toolbox/uploads/<id>/

Running and uploading: the project's owner or a reviewer (as for analyses). Deleting and renaming: the person who
made the run or upload, or a reviewer. Deletions are recorded in the project's Activity log.
"""
import mimetypes
import shutil
from pathlib import Path

from django.http import FileResponse, JsonResponse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.core.api import BadRequest, error, json_body
from apps.projects.access import can_edit, can_view, is_reviewer
from apps.projects.models import Project

from . import engine, inputs, runner
from .models import ToolRun, ToolUpload
from .tasks import enqueue

MAX_ACTIVE_PER_PROJECT = 4
MAX_UPLOAD_BYTES = 200 * 1024 * 1024
VECTOR_EXT = {".geojson", ".json", ".gpkg", ".kml", ".kmz", ".zip", ".shp", ".fgb", ".gml", ".gpx", ".parquet"}
RASTER_EXT = {".tif", ".tiff", ".vrt", ".img", ".asc"}
TABLE_EXT = {".csv", ".txt", ".tsv"}


def _project(request, code):
    p = Project.objects.select_related("area").filter(code=(code or "").upper()).first()
    return p if p is not None and can_view(request.user, p) else None


def _can_work(user, p):
    return user.is_authenticated and (can_edit(user, p) or is_reviewer(user) or p.owner_id == user.id)


def _can_manage(user, obj):
    return user.is_authenticated and (obj.created_by_id == user.id or is_reviewer(user))


def _person(u):
    return (u.get_full_name() or u.username) if u else ""


def _run_dict(t, user, detail=False):
    d = {"id": t.pk, "project": t.project.code, "tool": t.tool, "tool_title": t.tool_title, "engine": t.engine,
         "name": t.name, "status": t.status, "error": t.error, "created": t.created.isoformat(),
         "finished": t.finished.isoformat() if t.finished else None, "created_by": _person(t.created_by),
         "size_bytes": t.size_bytes, "outputs": t.outputs, "can_delete": _can_manage(user, t) and t.status != "running"}
    if detail:
        d.update({"params": t.params, "inputs": t.inputs, "report": t.report, "log": t.log})
    return d


@require_GET
def tools(request):
    try:
        return JsonResponse(runner.catalog())
    except engine.EngineError as exc:
        return error(str(exc), status=503)


@require_GET
def project_inputs(request, code):
    p = _project(request, code)
    if p is None:
        return error("Project not found.", status=404)
    if getattr(p, "area", None) is None:
        return error("The project has no area of influence.")
    return JsonResponse({"inputs": inputs.available(p, request.user)})


@require_http_methods(["GET", "POST"])
def project_runs(request, code):
    p = _project(request, code)
    if p is None:
        return error("Project not found.", status=404)
    if request.method == "GET":
        qs = p.tool_runs.select_related("created_by", "project")[:300]
        return JsonResponse({"runs": [_run_dict(t, request.user) for t in qs]})
    if not _can_work(request.user, p):
        return error("Only the project's owner or a reviewer can run tools on it.", status=403)
    if getattr(p, "area", None) is None:
        return error("The project has no area of influence.")
    try:
        data = json_body(request)
    except BadRequest as exc:
        return error(str(exc))
    tool = str(data.get("tool") or "")
    if tool not in runner.curated_ids():
        return error("Unknown tool.")
    m = runner.tool_manifest(tool)
    if m is None:
        return error("This tool isn't available in the engine.")
    if p.tool_runs.filter(status__in=("queued", "running")).count() >= MAX_ACTIVE_PER_PROJECT:
        return error("Several tools are already running for this project. Wait for them to finish.")
    params = data.get("params") if isinstance(data.get("params"), dict) else {}
    ins = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    # Required values and layers are checked here, so the form shows the problem at once.
    for fp in runner.form_params(m):
        if fp["required"] and fp["kind"] == "layer" and not ins.get(fp["name"]):
            return error(f"Choose a layer for {fp['label'].lower()}.")
        if fp["required"] and fp["kind"] != "layer" and params.get(fp["name"]) in (None, ""):
            return error(f"Enter a value for {fp['label'].lower()}.")
    title = m.get("display_name") or tool
    t = ToolRun.objects.create(project=p, created_by=request.user, tool=tool, tool_title=title,
                               engine="geida" if tool in runner.GEIDA_TOOLS else engine.NAME,
                               name=str(data.get("name") or title)[:200], params=params, inputs=ins)
    from django.db import transaction
    transaction.on_commit(lambda: enqueue(t))
    return JsonResponse({"run": _run_dict(t, request.user)}, status=201)


def _delete_run(user, t):
    from apps.projects.views import log
    shutil.rmtree(t.workdir, ignore_errors=True)
    log(t.project, user, "deleted toolbox run", run=t.pk, title=f"#{t.pk} {t.name} ({t.tool_title})")
    info = {"id": t.pk, "bytes": t.size_bytes}
    t.delete()
    return info


@require_http_methods(["GET", "PATCH", "DELETE"])
def run_detail(request, run_id):
    t = ToolRun.objects.select_related("project", "created_by").filter(pk=run_id).first()
    if t is None or not can_view(request.user, t.project):
        return error("Run not found.", status=404)
    if request.method == "GET":
        return JsonResponse({"run": _run_dict(t, request.user, detail=True)})
    if not _can_manage(request.user, t):
        return error("You can only change runs you made (reviewers can change any).", status=403)
    if request.method == "PATCH":
        try:
            name = str(json_body(request).get("name") or "").strip()
        except BadRequest as exc:
            return error(str(exc))
        if not name:
            return error("Give the result a name.")
        t.name = name[:200]
        t.save(update_fields=["name"])
        return JsonResponse({"run": _run_dict(t, request.user)})
    if t.status == "running":
        return error("This tool is still running. Wait until it ends, then delete it.")
    return JsonResponse({"deleted": [_delete_run(request.user, t)]})


@require_POST
def runs_delete(request):
    try:
        ids = [int(i) for i in (json_body(request).get("ids") or [])]
    except (BadRequest, TypeError, ValueError):
        return error("Send the ids of the runs to delete.")
    deleted, refused = [], []
    for t in ToolRun.objects.select_related("project").filter(pk__in=ids):
        if not can_view(request.user, t.project) or not _can_manage(request.user, t):
            refused.append({"id": t.pk, "reason": f"You can't delete run #{t.pk}."})
        elif t.status == "running":
            refused.append({"id": t.pk, "reason": f"Run #{t.pk} is still running."})
        else:
            deleted.append(_delete_run(request.user, t))
    return JsonResponse({"deleted": deleted, "refused": refused})


@require_GET
def run_file(request, run_id, name):
    t = ToolRun.objects.select_related("project").filter(pk=run_id).first()
    if t is None or not can_view(request.user, t.project):
        return error("Run not found.", status=404)
    allowed = {o.get(k) for o in t.outputs for k in ("file", "geojson", "preview") if o.get(k)}
    if name not in allowed or not (t.workdir / name).exists():
        return error("File not found.", status=404)
    ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
    if name.endswith(".geojson"):
        ctype = "application/geo+json"
    elif name.endswith(".gpkg"):
        ctype = "application/geopackage+sqlite3"
    download = request.GET.get("download") == "1"
    fname = f"{t.project.code}_tool{t.pk}_{name}"
    return FileResponse(open(t.workdir / name, "rb"), content_type=ctype, as_attachment=download, filename=fname)


# Uploads ------------------------------------------------------------------------------------------------
def _upload_dict(u, user):
    return {"id": u.pk, "name": u.name, "kind": u.kind, "size_bytes": u.size_bytes, "info": u.info,
            "created": u.created.isoformat(), "created_by": _person(u.created_by), "can_delete": _can_manage(user, u)}


def _inspect(path, kind):
    from osgeo import gdal, ogr
    gdal.UseExceptions()
    if kind == "vector":
        from .inputs import vector_source
        ds = ogr.Open(vector_source(path))
        if ds is None or ds.GetLayerCount() == 0:
            raise BadRequest("That file has no vector layer GEIDA can read.")
        lyr = ds.GetLayer(0)
        return {"features": lyr.GetFeatureCount(), "geometry": ogr.GeometryTypeToName(lyr.GetGeomType()),
                "layer": lyr.GetName()}
    if kind == "raster":
        ds = gdal.Open(str(path))
        if ds is None:
            raise BadRequest("That file isn't a raster GEIDA can read.")
        return {"width": ds.RasterXSize, "height": ds.RasterYSize, "bands": ds.RasterCount}
    return {}


@require_http_methods(["GET", "POST"])
def project_uploads(request, code):
    p = _project(request, code)
    if p is None:
        return error("Project not found.", status=404)
    if request.method == "GET":
        return JsonResponse({"uploads": [_upload_dict(u, request.user) for u in p.tool_uploads.select_related("created_by")]})
    if not _can_work(request.user, p):
        return error("Only the project's owner or a reviewer can add files.", status=403)
    f = request.FILES.get("file")
    if f is None:
        return error("Choose a file.")
    if f.size > MAX_UPLOAD_BYTES:
        return error("The file is larger than 200 MB.")
    ext = Path(f.name).suffix.lower()
    kind = "vector" if ext in VECTOR_EXT else "raster" if ext in RASTER_EXT else "table" if ext in TABLE_EXT else None
    if kind is None:
        return error("Use GeoJSON, GeoPackage, KML/KMZ, zipped shapefile, GeoTIFF or CSV.")
    u = ToolUpload.objects.create(project=p, created_by=request.user, name=(request.POST.get("name") or f.name)[:200],
                                  kind=kind, file=f"data{ext}", size_bytes=f.size)
    u.folder.mkdir(parents=True, exist_ok=True)
    with open(u.path, "wb") as out:
        for chunk in f.chunks():
            out.write(chunk)
    try:
        u.info = _inspect(u.path, kind)
    except (BadRequest, RuntimeError) as exc:
        shutil.rmtree(u.folder, ignore_errors=True)
        u.delete()
        return error(str(exc) if isinstance(exc, BadRequest) else "GEIDA couldn't read that file.")
    u.save()
    return JsonResponse({"upload": _upload_dict(u, request.user)}, status=201)


@require_http_methods(["DELETE"])
def upload_detail(request, upload_id):
    u = ToolUpload.objects.select_related("project").filter(pk=upload_id).first()
    if u is None or not can_view(request.user, u.project):
        return error("File not found.", status=404)
    if not _can_manage(request.user, u):
        return error("You can only delete files you added (reviewers can delete any).", status=403)
    from apps.projects.views import log
    shutil.rmtree(u.folder, ignore_errors=True)
    log(u.project, request.user, "deleted toolbox file", title=u.name)
    u.delete()
    return JsonResponse({"deleted": upload_id})
