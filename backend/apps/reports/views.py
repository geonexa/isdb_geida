"""
Reports API.

    GET    /api/reports/<code>/                  the project's reports
    GET    /api/reports/<code>/runs/             finished analysis runs a report can include, with their outputs
    POST   /api/reports/<code>/                  {title, subtitle?, content?}
    GET    /api/reports/<id>/                    one report, with its versions
    PATCH  /api/reports/<id>/                    {title?, subtitle?, content?}
    DELETE /api/reports/<id>/
    GET    /api/reports/<id>/preview/            the report as it would be generated now (HTML, not saved)
    POST   /api/reports/<id>/generate/           freeze and build a new version (queued)
    POST   /api/reports/<id>/share/              {expires_days?: 1-365 | null} -> share link (a new one each time)
    DELETE /api/reports/<id>/share/              revoke the share link
    GET    /api/reports/versions/<id>/           the version's web report (HTML)
    GET    /api/reports/versions/<id>/pdf        the version's PDF, shown in the browser (?download=1 to save it)
    GET    /api/reports/shared/<token>/          the latest version, without signing in (and .../pdf)

Creating, editing and generating: the project's owner, editors and reviewers (as for analyses). Deleting and
sharing: the report's author or a reviewer. Reading: anyone who can open the project; share links show one report.
"""
from datetime import timedelta

from django.http import FileResponse, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.core.api import BadRequest, error, json_body
from apps.projects.access import can_edit, can_view, is_reviewer
from apps.projects.models import Project

from .models import Report, ReportVersion, default_content
from .tasks import PDF_URL, enqueue

MAX_ACTIVE = 2          # versions building at once per report


def _project(request, code):
    if not request.user.is_authenticated:
        return None, error("Sign in to see projects.", status=401)
    p = Project.objects.select_related("area").filter(code=(code or "").upper()).first()
    if p is None or not can_view(request.user, p):
        return None, error("Project not found.", status=404)
    return p, None


def _report(request, report_id):
    if not request.user.is_authenticated:
        return None, error("Sign in to see reports.", status=401)
    r = Report.objects.select_related("project", "project__area", "author").filter(pk=report_id).first()
    if r is None or not can_view(request.user, r.project):
        return None, error("Report not found.", status=404)
    return r, None


def _can_work(user, p):
    return user.is_authenticated and (can_edit(user, p) or is_reviewer(user) or p.owner_id == user.id)


def _can_manage(user, r):
    return user.is_authenticated and (r.author_id == user.id or is_reviewer(user))


def _person(u):
    return (u.get_full_name() or u.username) if u else ""


def _log(p, user, action, **detail):
    from apps.projects.views import log
    log(p, user, action, **detail)


def _version_dict(v):
    return {"id": v.pk, "number": v.number, "status": v.status, "error": v.error, "pages": v.pages,
            "size_bytes": v.size_bytes, "created": v.created.isoformat(), "created_by": _person(v.created_by),
            "finished": v.finished.isoformat() if v.finished else None,
            "html_url": f"/api/reports/versions/{v.pk}/" if v.status == "done" else None,
            "pdf_url": f"/api/reports/versions/{v.pk}/pdf" if v.status == "done" else None}


def _report_dict(r, user, versions=True):
    d = {"id": r.pk, "project": r.project.code, "title": r.title, "subtitle": r.subtitle, "author": _person(r.author),
         "created": r.created.isoformat(), "updated": r.updated.isoformat(), "content": r.content,
         "can_edit": _can_work(user, r.project), "can_manage": _can_manage(user, r),
         "share": {"active": r.share_active, "url": f"/api/reports/shared/{r.share_token}/" if r.share_active else None,
                   "expires": r.share_expires.isoformat() if r.share_expires else None}}
    if versions:
        d["versions"] = [_version_dict(v) for v in r.versions.select_related("created_by")[:30]]
    return d


def _clean_content(raw, project):
    """The editable content, checked: sections refer to the project's finished runs."""
    from apps.analysis.models import ModuleRun
    if not isinstance(raw, dict):
        raise BadRequest("content must be an object.")
    base = default_content()
    summary = str(raw.get("summary") or "")[:8000]
    opts = raw.get("options") if isinstance(raw.get("options"), dict) else {}
    options = {"project": bool(opts.get("project", True)), "annex": bool(opts.get("annex", True)),
               "basemap": opts.get("basemap") if opts.get("basemap") in ("light", "satellite") else "satellite"}
    sections = []
    ids = [s.get("run") for s in raw.get("sections") or [] if isinstance(s, dict)]
    valid = set(ModuleRun.objects.filter(project=project, status="done", pk__in=[i for i in ids if isinstance(i, int)])
                .values_list("pk", flat=True))
    for s in raw.get("sections") or []:
        if not isinstance(s, dict) or s.get("run") not in valid:
            continue
        outs = s.get("outputs")
        sections.append({"run": s["run"], "outputs": [str(o) for o in outs][:60] if isinstance(outs, list) else None,
                         "note": str(s.get("note") or "")[:3000]})
    if len(sections) > 40:
        raise BadRequest("A report can include up to 40 analyses.")
    return {**base, "summary": summary, "options": options, "sections": sections}


OUTPUT_KINDS = {"metric": "Figures", "raster": "Map", "vector": "Map", "table": "Table", "chart": "Chart"}


@require_GET
def project_runs(request, code):
    p, err = _project(request, code)
    if err:
        return err
    from apps.analysis.models import ModuleRun
    from .snapshot import CATEGORY_COLORS, _category_titles
    titles = _category_titles()
    out = []
    for r in ModuleRun.objects.filter(project=p, status="done").select_related("module", "created_by")[:300]:
        cat = (r.module.manifest or {}).get("category") or ""
        outs = [{"name": o["name"], "type": o.get("type"), "kind": OUTPUT_KINDS[o.get("type")], "title": o.get("title") or o["name"]}
                for o in r.outputs or [] if o.get("type") in OUTPUT_KINDS and o.get("name")]
        out.append({"id": r.pk, "module": r.module_id, "title": r.module.title, "category": cat,
                    "category_title": titles.get(cat, cat.capitalize()), "color": CATEGORY_COLORS.get(cat, "#0B3B47"),
                    "created": r.created.isoformat(), "created_by": _person(r.created_by), "summary": r.summary,
                    "outputs": outs})
    return JsonResponse({"runs": out})


@require_http_methods(["GET", "POST"])
def project_reports(request, code):
    p, err = _project(request, code)
    if err:
        return err
    if request.method == "GET":
        qs = p.reports.select_related("author", "project")
        return JsonResponse({"reports": [_report_dict(r, request.user, versions=False) | {
            "latest": _version_dict(v) if (v := r.versions.order_by("-number").first()) else None,
            "latest_done": _version_dict(d) if (d := r.latest_done()) else None} for r in qs],
            "can_create": _can_work(request.user, p)})
    if not _can_work(request.user, p):
        return error("Only the project's owner, editors or a reviewer can create reports.", status=403)
    try:
        data = json_body(request)
        title = str(data.get("title") or "").strip()[:200]
        if not title:
            raise BadRequest("Give the report a title.")
        content = _clean_content(data.get("content") or default_content(), p)
    except BadRequest as exc:
        return error(str(exc))
    r = Report.objects.create(project=p, title=title, subtitle=str(data.get("subtitle") or "")[:300],
                              author=request.user, content=content)
    _log(p, request.user, "report created", title=r.title, report=r.pk)
    return JsonResponse({"report": _report_dict(r, request.user)}, status=201)


@require_http_methods(["GET", "PATCH", "DELETE"])
def report_detail(request, report_id):
    r, err = _report(request, report_id)
    if err:
        return err
    if request.method == "GET":
        return JsonResponse({"report": _report_dict(r, request.user)})
    if request.method == "DELETE":
        if not _can_manage(request.user, r):
            return error("Only the report's author or a reviewer can delete it.", status=403)
        import shutil
        folder = r.folder
        title, p = r.title, r.project
        r.delete()
        shutil.rmtree(folder, ignore_errors=True)
        _log(p, request.user, "report deleted", title=title)
        return JsonResponse({"deleted": report_id})
    if not _can_work(request.user, r.project):
        return error("You can't edit this report.", status=403)
    try:
        data = json_body(request)
        if "title" in data:
            t = str(data.get("title") or "").strip()[:200]
            if not t:
                raise BadRequest("Give the report a title.")
            r.title = t
        if "subtitle" in data:
            r.subtitle = str(data.get("subtitle") or "")[:300]
        if "content" in data:
            r.content = _clean_content(data["content"], r.project)
    except BadRequest as exc:
        return error(str(exc))
    r.save()
    return JsonResponse({"report": _report_dict(r, request.user)})


@require_GET
def report_preview(request, report_id):
    r, err = _report(request, report_id)
    if err:
        return err
    from . import render, snapshot
    ctx = snapshot.build(r, request.user)
    return HttpResponse(render.render_html(ctx, mode="web", status="Preview: not yet generated"))


@require_POST
def report_generate(request, report_id):
    r, err = _report(request, report_id)
    if err:
        return err
    if not _can_work(request.user, r.project):
        return error("You can't generate this report.", status=403)
    if not r.content.get("sections") and not r.content.get("summary"):
        return error("Add at least one analysis or a summary first.")
    if r.versions.filter(status__in=("queued", "building")).count() >= MAX_ACTIVE:
        return error("A version of this report is already being generated. Wait for it to finish.")
    last = r.versions.order_by("-number").first()
    v = ReportVersion.objects.create(report=r, number=(last.number + 1) if last else 1, created_by=request.user)
    problem = enqueue(v)
    v.refresh_from_db()
    _log(r.project, request.user, "report generated", title=r.title, version=v.number)
    return JsonResponse({"version": _version_dict(v), "problem": problem}, status=201)


@require_http_methods(["POST", "DELETE"])
def report_share(request, report_id):
    r, err = _report(request, report_id)
    if err:
        return err
    if not _can_manage(request.user, r):
        return error("Only the report's author or a reviewer can share it.", status=403)
    if request.method == "DELETE":
        r.share_token, r.share_expires = "", None
        r.save(update_fields=["share_token", "share_expires", "updated"])
        _log(r.project, request.user, "report link revoked", title=r.title)
        return JsonResponse({"report": _report_dict(r, request.user)})
    try:
        data = json_body(request) if request.body else {}
    except BadRequest as exc:
        return error(str(exc))
    days = data.get("expires_days")
    if days not in (None, "") and not (isinstance(days, int) and 1 <= days <= 365):
        return error("The link can last 1 to 365 days, or have no end date.")
    if not r.versions.filter(status="done").exists():
        return error("Generate the report before sharing it.")
    r.new_token()
    r.share_expires = timezone.now() + timedelta(days=days) if days else None
    r.save(update_fields=["share_token", "share_expires", "updated"])
    _log(r.project, request.user, "report link created", title=r.title, expires_days=days)
    return JsonResponse({"report": _report_dict(r, request.user)})


def _serve_html(v, pdf_url):
    if not v.html_path.exists():
        return error("This version's files are missing.", status=404)
    html = v.html_path.read_text(encoding="utf-8")
    # Versions generated before the PDF opened in the browser had a download button.
    html = html.replace(f'href="{PDF_URL}">Download PDF</a>', f'href="{PDF_URL}" target="_blank" rel="noopener">Open PDF</a>')
    html = html.replace(PDF_URL, pdf_url)
    resp = HttpResponse(html)
    resp["X-Robots-Tag"] = "noindex"
    return resp


def _serve_pdf(request, v):
    if not v.pdf_path.exists():
        return error("This version's PDF is missing.", status=404)
    name = f"{v.report.project.code}_report_{v.report.pk}_v{v.number}.pdf"
    return FileResponse(open(v.pdf_path, "rb"), content_type="application/pdf",
                        as_attachment=request.GET.get("download") == "1", filename=name)


def _version(request, version_id):
    if not request.user.is_authenticated:
        return None, error("Sign in to see reports.", status=401)
    v = ReportVersion.objects.select_related("report", "report__project").filter(pk=version_id, status="done").first()
    if v is None or not can_view(request.user, v.report.project):
        return None, error("Report version not found.", status=404)
    return v, None


@require_GET
def version_html(request, version_id):
    v, err = _version(request, version_id)
    if err:
        return err
    return _serve_html(v, f"/api/reports/versions/{v.pk}/pdf")


@require_GET
def version_pdf(request, version_id):
    v, err = _version(request, version_id)
    if err:
        return err
    return _serve_pdf(request, v)


def _shared(token):
    r = Report.objects.select_related("project").filter(share_token=token).first() if token else None
    if r is None or not r.share_active:
        return None
    return r.latest_done()


@require_GET
def shared_html(request, token):
    v = _shared(token)
    if v is None:
        return error("This report link doesn't exist or has expired.", status=404)
    return _serve_html(v, f"/api/reports/shared/{token}/pdf")


@require_GET
def shared_pdf(request, token):
    v = _shared(token)
    if v is None:
        return error("This report link doesn't exist or has expired.", status=404)
    return _serve_pdf(request, v)
