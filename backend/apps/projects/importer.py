"""
Bulk import (Route B: GEIDA template) and form import (Route C: Project Data
Submission Form export). Both preview first, then commit the rows the user keeps.

    GET  /api/projects/import/template/   -> .xlsx template
    POST /api/projects/import/preview/    multipart: kind=template|form, file, [boundaries=zip]
         -> {token, rows: [{row, code, title, country, action, errors, warnings, suggestion, boundary}]}
    POST /api/projects/import/commit/     {token, rows: [{row, apply_suggestion}]}
         -> {created, updated, skipped, results: [...]}
"""
import io
import json
import os
import re
import secrets
import shutil
import zipfile
from datetime import date, datetime
from pathlib import Path

from django.conf import settings
from django.contrib.gis.db.models import Union
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from apps.core.api import BadRequest, error, json_body

from . import choices as C
from .access import can_edit
from .geometry import GeometryError, buffer_point, clean, merge_features, read_path, summary
from .models import Project, ProjectArea, ProjectDocument, ProjectLog
from .serializers import clean_identity

IMPORT_DIR = Path(settings.MEDIA_ROOT) / "imports"
MAX_ROWS = 500
TEMPLATE_COLUMNS = [
    ("code", "Project code", "Required. e.g. UGA1072"),
    ("title", "Title", "Required"),
    ("country_iso3", "Country (ISO3)", "Required. e.g. UGA"),
    ("sector", "Sector", "See Lists sheet"),
    ("stage", "Cycle stage", "PCN, PPRR, PAD, PIASR, PCR or PPER"),
    ("start_date", "Start date", "YYYY-MM-DD"),
    ("end_date", "Expected completion", "YYYY-MM-DD"),
    ("otl", "OTL", "Operations team leader"),
    ("hub", "Regional hub", "See Lists sheet"),
    ("location", "Location", "Villages, towns, districts"),
    ("themes", "Themes", "Separate with ; e.g. water;agriculture"),
    ("components", "Components", "Separate with ;"),
]


# Template -------------------------------------------------------------------------

@require_GET
def template(request):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    ws = wb.active
    ws.title = "Projects"
    ws.append([c[1] for c in TEMPLATE_COLUMNS])
    ws.append([c[2] for c in TEMPLATE_COLUMNS])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="0B3B47")
    for cell in ws[2]:
        cell.font = Font(italic=True, color="5C5C60")
    ws.append(["UGA1072", "Example project – delete this row", "UGA", "education", "PIASR",
               "2024-01-01", "2028-12-31", "", "Kampala", "Moroto District", "education", "Schools;Teacher training"])
    for i, _ in enumerate(TEMPLATE_COLUMNS):
        ws.column_dimensions[chr(65 + i)].width = 22
    ws.freeze_panes = "A3"

    lists = wb.create_sheet("Lists")
    cols = [("Sector", C.SECTORS), ("Cycle stage", C.STAGES), ("Regional hub", C.HUBS),
            ("Theme", C.THEMES), ("Country", [(c["iso3"], c["name"]) for c in C.member_countries()])]
    for ci, (title, pairs) in enumerate(cols):
        lists.cell(row=1, column=ci * 2 + 1, value=f"{title} value").font = Font(bold=True)
        lists.cell(row=1, column=ci * 2 + 2, value="Meaning").font = Font(bold=True)
        for ri, (k, v) in enumerate(pairs, start=2):
            lists.cell(row=ri, column=ci * 2 + 1, value=k)
            lists.cell(row=ri, column=ci * 2 + 2, value=v)
    for col, (_, pairs) in zip(("D", "E", "I"), cols[:3]):
        src = {"D": "A", "E": "C", "I": "E"}[col]
        dv = DataValidation(type="list", formula1=f"=Lists!${src}$2:${src}${len(pairs) + 1}", allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(f"{col}3:{col}1000")

    info = wb.create_sheet("Read me")
    for line in [
        "GEIDA bulk project import",
        "One row per project. Row 2 explains each column; data starts at row 3.",
        "A code that already exists updates that project (if you may edit it).",
        "Boundaries: upload a separate .zip with one file per project named by code,",
        "e.g. UGA1072.geojson, AZE1028.kml, TCD1052.gpkg or UGA1080.zip (zipped shapefile).",
    ]:
        info.append([line])
    buf = io.BytesIO()
    wb.save(buf)
    resp = HttpResponse(buf.getvalue(),
                        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = 'attachment; filename="geida_project_import_template.xlsx"'
    return resp


# Parsing --------------------------------------------------------------------------

def _str(v):
    if v is None:
        return ""
    if isinstance(v, (datetime, date)):
        return v.strftime("%Y-%m-%d")
    return str(v).strip()


def _choice(value, pairs):
    v = _str(value).strip().rstrip(";").strip()
    if not v:
        return ""
    low = v.lower()
    for k, label in pairs:
        if low == k.lower() or low == label.lower() or low.startswith(k.lower() + " "):
            return k
    return None


SECTOR_WORDS = {
    "line of finance": "finance", "finance": "finance", "agriculture": "agriculture", "water": "water",
    "energy": "energy", "transport": "transport", "education": "education", "health": "health",
    "urban": "urban", "infrastructure": "infrastructure",
}
STAGE_WORDS = [("PIASR", "PIASR"), ("PPRR", "PPRR"), ("PPER", "PPER"), ("PCR", "PCR"), ("PCN", "PCN"),
               ("PAD", "PAD"), ("implementation", "PIASR"), ("appraisal", "PAD"), ("completion report", "PCR")]
HUB_WORDS = [("headquarters", "HQ"), ("jeddah", "HQ"), ("abuja", "Abuja"), ("almaty", "Almaty"),
             ("ankara", "Ankara"), ("cairo", "Cairo"), ("dakar", "Dakar"), ("dhaka", "Dhaka"),
             ("jakarta", "Jakarta"), ("kampala", "Kampala"), ("paramaribo", "Paramaribo"),
             ("rabat", "Rabat"), ("kuala lumpur", "KualaLumpur")]
COORD_RES = [
    re.compile(r"(-?\d{1,2}\.\d{3,})\s*°?\s*([NS])\s*[,;\s]\s*(-?\d{1,3}\.\d{3,})\s*°?\s*([EW])", re.I),
    re.compile(r"@(-?\d{1,2}\.\d{3,}),(-?\d{1,3}\.\d{3,}),"),  # Google Earth/Maps link
]


def find_point(text):
    if not text:
        return None
    m = COORD_RES[0].search(text)
    if m:
        lat = float(m.group(1)) * (-1 if m.group(2).upper() == "S" else 1)
        lon = float(m.group(3)) * (-1 if m.group(4).upper() == "W" else 1)
        return lat, lon
    m = COORD_RES[1].search(text)
    if m:
        # Google Earth links carry the camera distance ("...,2361149.5d,"); a view
        # from more than ~50 km up shows a region, not a project site.
        d = re.search(r",(\d+(?:\.\d+)?)d,", text[m.end() - 1:])
        if d and float(d.group(1)) > 50_000:
            return None
        return float(m.group(1)), float(m.group(2))
    return None


def _country_from(code, location):
    c = C.country_by_iso3(code[:3]) if code else None
    if c:
        return c
    low = (location or "").lower().replace("'", "").replace("’", "")
    for c in C.member_countries():
        if c["name"].lower().replace("'", "").replace("’", "") in low:
            return c
    if "ivoire" in low:
        return C.country_by_iso3("CIV")
    return None


def _rows_from_sheet(fileobj):
    from openpyxl import load_workbook

    try:
        wb = load_workbook(fileobj, read_only=False, data_only=True)
    except Exception as exc:
        raise BadRequest("The file can't be opened as an Excel workbook (.xlsx).") from exc
    ws = wb["Projects"] if "Projects" in wb.sheetnames else wb.worksheets[0]
    rows = [r for r in ws.iter_rows(values_only=True)]
    if not rows:
        raise BadRequest("The workbook is empty.")
    return [_str(h) for h in rows[0]], rows[1:]


def parse_template(fileobj):
    header, body = _rows_from_sheet(fileobj)
    labels = {c[1].lower(): c[0] for c in TEMPLATE_COLUMNS} | {c[0]: c[0] for c in TEMPLATE_COLUMNS}
    keys = [labels.get(h.lower().strip()) for h in header]
    if "code" not in keys or "title" not in keys:
        raise BadRequest("This doesn't look like the GEIDA template (missing 'Project code' or 'Title' columns).")
    out = []
    for n, r in enumerate(body, start=2):
        vals = {k: r[i] for i, k in enumerate(keys) if k and i < len(r)}
        if not any(_str(v) for v in vals.values()):
            continue
        if _str(vals.get("code")).lower().startswith("required"):
            continue  # the help row
        rec = {"row": n, "warnings": [], "documents": [], "suggestion": None, "source": "import"}
        rec["data"] = {
            "code": _str(vals.get("code")), "title": _str(vals.get("title")),
            "country_iso3": _str(vals.get("country_iso3")).upper(),
            "start_date": _str(vals.get("start_date")) or None, "end_date": _str(vals.get("end_date")) or None,
            "otl": _str(vals.get("otl")), "location": _str(vals.get("location")),
            "components": [{"name": c.strip(), "description": ""} for c in _str(vals.get("components")).split(";") if c.strip()],
        }
        for field, pairs in (("sector", C.SECTORS), ("stage", C.STAGES), ("hub", C.HUBS)):
            v = _choice(vals.get(field), pairs)
            if v is None:
                rec["warnings"].append(f"{field.title()} '{_str(vals.get(field))}' isn't in the list; left blank.")
                v = ""
            rec["data"][field] = v
        themes = []
        for t in _str(vals.get("themes")).split(";"):
            k = _choice(t, C.THEMES)
            if k:
                themes.append(k)
            elif t.strip():
                rec["warnings"].append(f"Theme '{t.strip()}' isn't in the list; skipped.")
        rec["data"]["themes"] = themes
        out.append(rec)
    return out


def parse_form(fileobj):
    header, body = _rows_from_sheet(fileobj)
    low = [h.lower() for h in header]

    def col(*starts):
        for s in starts:
            for i, h in enumerate(low):
                if h.startswith(s):
                    return i
        return None

    idx = {
        "code": col("project code"), "title": col("project name"), "location": col("location of the project"),
        "sector": col("sector"), "stage": col("project cycle stage"), "has": col("do you have a project boundary"),
        "boundary": col("upload the project location", "upload the project"), "maps": col("add a project map"),
        "name": col("full name"), "email": col("email address"), "work": col("your work location"),
        "dept": col("department"), "done": col("completion time"),
    }
    if idx["code"] is None or idx["title"] is None:
        raise BadRequest("This doesn't look like the Project Data Submission Form export.")
    get = lambda r, k: _str(r[idx[k]]) if idx[k] is not None and idx[k] < len(r) else ""
    out = []
    for n, r in enumerate(body, start=2):
        if not any(_str(v) for v in r):
            continue
        rec = {"row": n, "warnings": [], "documents": [], "suggestion": None, "source": "form"}
        code = get(r, "code").upper().replace(" ", "")
        title = get(r, "title")
        if code and title.upper().startswith(code):
            title = title[len(code):].lstrip(" –-:").strip()
        location = get(r, "location")
        country = _country_from(code, location)
        sectors = [s.strip().lower() for s in get(r, "sector").split(";") if s.strip()]
        mapped = [SECTOR_WORDS.get(s) for s in sectors]
        stage_txt = get(r, "stage")
        stage = next((v for w, v in STAGE_WORDS if w.lower() in stage_txt.lower()), "")
        if "near completion" in stage_txt.lower():
            stage = "PIASR"
            rec["warnings"].append("Stage 'Near completion' set to PIASR; change to PCR once the completion report starts.")
        work = get(r, "work").lower()
        hub = next((v for w, v in HUB_WORDS if w in work), "")
        rec["data"] = {
            "code": code, "title": title, "country_iso3": country["iso3"] if country else "",
            "sector": next((m for m in mapped if m), ""),
            "themes": [m for m in mapped if m in C.keys(C.THEMES)],
            "stage": stage, "hub": hub, "location": location[:400],
            "start_date": None, "end_date": None, "otl": "", "components": [],
        }
        if not country:
            rec["warnings"].append("Country couldn't be worked out from the code or location; choose it after import.")
        rec["source_info"] = {"submitted_by": get(r, "name"), "email": get(r, "email"),
                              "work_location": get(r, "work"), "department": get(r, "dept"),
                              "submitted": get(r, "done")}
        boundary, maps = get(r, "boundary"), get(r, "maps")
        if boundary.startswith("http"):
            rec["documents"].append({"doc_type": "boundary", "title": "Boundary (link from submission form)", "url": boundary})
        if maps.startswith("http") and maps != boundary:
            rec["documents"].append({"doc_type": "map", "title": "Project map (from submission form)", "url": maps})
        rec["boundary_text"] = boundary
        texts = " ".join([location, boundary, maps])
        point = find_point(texts)
        if "entire country" in texts.lower() and country:
            rec["suggestion"] = {"type": "country", "label": f"Use the whole of {country['name']} as the area"}
        elif point:
            lat, lon = point
            rec["suggestion"] = {"type": "point", "lat": lat, "lon": lon, "km": 5,
                                 "label": f"5 km around {lat:.5f}, {lon:.5f} (from the form)"}
        rec["boundary_is_link"] = boundary.startswith("http")
        out.append(rec)
    return out


# Boundaries zip ------------------------------------------------------------------

def _extract_boundaries(upload, dest):
    files = {}
    if not upload:
        return files
    zpath = dest / "boundaries.zip"
    with open(zpath, "wb") as fh:
        for chunk in upload.chunks():
            fh.write(chunk)
    try:
        zf = zipfile.ZipFile(zpath)
    except zipfile.BadZipFile as exc:
        raise BadRequest("The boundaries file must be a .zip.") from exc
    bdir = dest / "boundaries"
    bdir.mkdir(exist_ok=True)
    for name in zf.namelist():
        base = os.path.basename(name)
        if not base or name.startswith("__MACOSX"):
            continue
        stem, ext = os.path.splitext(base)
        ext = ext.lower()
        if ext not in (".geojson", ".json", ".kml", ".kmz", ".gpkg", ".zip"):
            continue
        target = bdir / re.sub(r"[^\w.\-]", "_", base)
        with zf.open(name) as src, open(target, "wb") as out:
            shutil.copyfileobj(src, out)
        files[stem.upper().split("_")[0]] = str(target)
    return files


# Views ----------------------------------------------------------------------------

def _row_check(rec, user, boundaries):
    errors = {}
    data = clean_identity({k: rec["data"].get(k) for k in rec["data"]}, errors)
    rec["errors"] = [f"{k.replace('_', ' ').title()}: {v[0]}" for k, v in errors.items()]
    rec["clean"] = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in data.items()}
    code = data.get("code")
    existing = Project.objects.filter(code=code).first() if code else None
    if rec["errors"]:
        rec["action"] = "error"
    elif existing and not can_edit(user, existing):
        rec["action"] = "error"
        rec["errors"].append(f"{code} already exists and you can't edit it.")
    else:
        rec["action"] = "update" if existing else "new"
    rec["boundary"] = "file" if code and code in boundaries else ("link" if any(
        d["doc_type"] == "boundary" for d in rec["documents"]) else "none")
    if rec["boundary"] == "file":
        rec["boundary_file"] = os.path.basename(boundaries[code])
    link_msg = "Boundary was sent as a link, not a file: download it and add it to the boundaries zip, or upload it in step 2 after import."
    rec["warnings"] = [w for w in rec["warnings"] if w != link_msg]
    if rec.get("boundary_is_link") and rec["boundary"] != "file":
        rec["warnings"].append(link_msg)
    return rec


@require_POST
def preview(request):
    if not request.user.is_authenticated:
        return error("Sign in to import projects.", status=401)
    kind = request.POST.get("kind", "template")
    f = request.FILES.get("file")
    if not f:
        return error("Choose the Excel file to import.")
    token = secrets.token_urlsafe(16)
    dest = IMPORT_DIR / token
    dest.mkdir(parents=True, exist_ok=True)
    try:
        rows = parse_form(f) if kind == "form" else parse_template(f)
        boundaries = _extract_boundaries(request.FILES.get("boundaries"), dest)
    except BadRequest as exc:
        shutil.rmtree(dest, ignore_errors=True)
        return error(str(exc))
    if not rows:
        shutil.rmtree(dest, ignore_errors=True)
        return error("No project rows found in the file.")
    if len(rows) > MAX_ROWS:
        shutil.rmtree(dest, ignore_errors=True)
        return error(f"Import at most {MAX_ROWS} projects at a time.")
    seen = set()
    for rec in rows:
        _row_check(rec, request.user, boundaries)
        code = rec["clean"].get("code")
        if code and code in seen:
            rec["action"] = "error"
            rec["errors"].append(f"{code} appears more than once in the file.")
        seen.add(code)
    state = {"kind": kind, "user": request.user.id, "file": f.name, "rows": rows, "boundaries": boundaries}
    (dest / "state.json").write_text(json.dumps(state, default=str), encoding="utf-8")
    unused = sorted(set(boundaries) - seen)
    public = [{k: rec.get(k) for k in ("row", "action", "errors", "warnings", "suggestion", "boundary",
                                        "boundary_file", "documents", "source_info")}
              | {"code": rec["clean"].get("code"), "title": rec["clean"].get("title"),
                 "country": rec["clean"].get("country_name", ""), "sector": rec["clean"].get("sector", ""),
                 "stage": rec["clean"].get("stage", "")} for rec in rows]
    return JsonResponse({"token": token, "kind": kind, "file": f.name, "rows": public,
                         "unused_boundaries": unused})


def _apply_area(project, path=None, suggestion=None):
    if path:
        features, notes = read_path(path)
        merged, more = merge_features(features)
        mp, notes = clean(merged, notes + more)
        method, meta = "upload", {"source_name": os.path.basename(path)}
    elif suggestion and suggestion["type"] == "point":
        mp = buffer_point(suggestion["lon"], suggestion["lat"], suggestion.get("km", 5))
        notes = [f"Circle of {suggestion.get('km', 5)} km radius from the submission form coordinates."]
        method, meta = "buffer", {"buffer": {k: suggestion[k] for k in ("lon", "lat")} | {"km": suggestion.get("km", 5)}}
    elif suggestion and suggestion["type"] == "country":
        from apps.boundaries.models import AdminUnit

        unit = AdminUnit.objects.filter(level=0, iso3=project.country_iso3, disputed=False).first()
        if unit is None:
            raise GeometryError("Country boundaries aren't loaded (run load_admin_units).")
        mp, notes = clean(unit.geom)
        notes.append("Whole country (GADM 4.1).")
        method, meta = "country", {"admin_gids": [unit.gid]}
    else:
        return None
    s = summary(mp, notes, project.country_iso3)
    ProjectArea.objects.update_or_create(project=project, defaults={
        "method": method, "geom": mp, "area_km2": s["area_km2"], "notes": s["notes"],
        "source_name": meta.get("source_name", ""), "admin_gids": meta.get("admin_gids", []),
        "buffer": meta.get("buffer", {})})
    return s["area_km2"]


@require_POST
def commit(request):
    if not request.user.is_authenticated:
        return error("Sign in to import projects.", status=401)
    try:
        data = json_body(request)
    except BadRequest as exc:
        return error(str(exc))
    token = str(data.get("token") or "")
    if not re.fullmatch(r"[\w\-]{10,40}", token):
        return error("Upload the file again.")
    dest = IMPORT_DIR / token
    state_file = dest / "state.json"
    if not state_file.exists():
        return error("This import has expired. Upload the file again.")
    state = json.loads(state_file.read_text(encoding="utf-8"))
    if state["user"] != request.user.id:
        return error("This import belongs to another user.", status=403)
    choices = {int(x["row"]): x for x in (data.get("rows") or []) if isinstance(x, dict) and "row" in x}
    results, created, updated = [], 0, 0
    for rec in state["rows"]:
        pick = choices.get(rec["row"])
        if pick is None or rec["action"] == "error":
            continue
        rec = _row_check(rec, request.user, state["boundaries"])
        if rec["action"] == "error":
            results.append({"row": rec["row"], "code": rec["clean"].get("code"), "status": "error", "errors": rec["errors"]})
            continue
        fields = {k: v for k, v in rec["clean"].items() if v not in (None, "", [])}
        for k in ("start_date", "end_date"):
            if k in fields:
                fields[k] = date.fromisoformat(fields[k])
        code = fields.pop("code")
        p = Project.objects.filter(code=code).first()
        if p is None:
            p = Project.objects.create(code=code, owner=request.user, source=rec["source"],
                                       source_info={**(rec.get("source_info") or {}), "file": state["file"]},
                                       **fields)
            created += 1
            action = "imported"
        else:
            for k, v in fields.items():
                setattr(p, k, v)
            p.save()
            updated += 1
            action = "updated by import"
        have = set(p.documents.values_list("url", flat=True))
        for d in rec["documents"]:
            if d["url"] not in have:
                ProjectDocument.objects.create(project=p, **d)
        area_msg = None
        try:
            path = state["boundaries"].get(code)
            sug = rec.get("suggestion") if pick.get("apply_suggestion") else None
            km2 = _apply_area(p, path=path, suggestion=sug)
            if km2 is not None:
                area_msg = f"area {km2:,.1f} km²"
            elif ProjectArea.objects.filter(project=p).exists():
                area_msg = "area unchanged"
        except GeometryError as exc:
            area_msg = f"area not set: {exc}"
        ProjectLog.objects.create(project=p, user=request.user, action=action,
                                  detail={"file": state["file"], "row": rec["row"], "area": area_msg})
        results.append({"row": rec["row"], "code": code, "status": action, "area": area_msg})
    shutil.rmtree(dest, ignore_errors=True)
    return JsonResponse({"created": created, "updated": updated, "results": results})
