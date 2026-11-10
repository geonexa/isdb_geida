"""Project <-> JSON."""
import json
import re
from datetime import date

from . import choices as C
from .models import CRI

CODE_RE = re.compile(r"^[A-Z]{3}[A-Z0-9\-]{1,14}$")
IDENTITY_FIELDS = ("code", "title", "country_iso3", "sector", "stage", "start_date", "end_date",
                   "otl", "hub", "location", "themes", "components")
REQUIRED_TO_SUBMIT = ("code", "title", "country_iso3", "sector", "stage")


def _label(pairs, key):
    return dict(pairs).get(key, key or "")


def person(user):
    if not user:
        return ""
    return user.get_full_name() or user.username


def area_brief(project):
    a = getattr(project, "area", None)
    if a is None:
        return None
    c = a.geom.centroid
    x0, y0, x1, y1 = a.geom.extent
    return {"method": a.method, "area_km2": a.area_km2, "centroid": [round(c.x, 5), round(c.y, 5)],
            "bbox": [x0, y0, x1, y1]}


def project_list_item(p, user, can_edit):
    return {
        "code": p.code,
        "title": p.title,
        "country_iso3": p.country_iso3,
        "country_name": p.country_name,
        "sector": p.sector,
        "sector_label": _label(C.SECTORS, p.sector),
        "stage": p.stage,
        "status": p.status,
        "status_label": _label(C.STATUSES, p.status),
        "source": p.source,
        "hub": p.hub,
        "owner": person(p.owner),
        "updated": p.updated.isoformat(),
        "area": area_brief(p),
        "indicator_count": getattr(p, "n_indicators", None),
        "can_edit": can_edit,
    }


def cri_dict(c):
    return {
        "code": c.code,
        "name": c.name,
        "unit": c.unit,
        "group_no": c.group_no,
        "group_name": c.group_name,
        "per_annum": c.per_annum,
        "sex_disaggregated": c.sex_disaggregated,
        "geida_role": c.geida_role,
        "candidate_module": c.candidate_module,
        "notes": c.notes,
    }


def indicator_dict(i):
    return {
        "id": i.id,
        "level": i.level,
        "statement": i.statement,
        "unit": i.unit,
        "cri": cri_dict(i.cri) if i.cri else None,
        "tier": i.tier,
        "baseline_value": i.baseline_value,
        "baseline_year": i.baseline_year,
        "target_value": i.target_value,
        "target_year": i.target_year,
        "means_of_verification": i.means_of_verification,
        "sex_disaggregated": i.sex_disaggregated,
        "geo_role": i.geo_role,
        "warnings": indicator_warnings(i.cri, i.unit),
        "evidence": latest_evidence(i),
    }


def latest_evidence(i):
    """Most recent accepted evidence value for an indicator (from analysis module runs)."""
    e = i.evidence.filter(status="accepted").order_by("-created").first() if hasattr(i, "evidence") else None
    if e is None:
        return None
    return {"value": e.value, "unit": e.unit, "instrument": e.instrument, "role": e.role,
            "reference_date": e.reference_date, "run": e.run_id}


def _norm_unit(u):
    u = (u or "").strip().lower().replace("²", "2").replace(" ", "")
    return {"sqkm": "km2", "km^2": "km2", "hectares": "ha", "hectare": "ha", "no.": "number", "nr": "number"}.get(u, u)


def indicator_warnings(cri, unit):
    out = []
    if cri is None:
        return out
    if cri.unit and unit and _norm_unit(cri.unit) != _norm_unit(unit):
        out.append(f"CRI {cri.code} is reported in {cri.unit}; this indicator uses {unit}. Values will need converting.")
    if cri.notes:
        out.append(f"CRI {cri.code}: {cri.notes}")
    if cri.sex_disaggregated == "to_confirm":
        out.append(f"Whether CRI {cri.code} needs male/female values is still to be confirmed.")
    return out


def project_detail(p, user, perms):
    a = getattr(p, "area", None)
    area = None
    if a is not None:
        area = {**area_brief(p), "notes": a.notes, "source_name": a.source_name,
                "admin_gids": a.admin_gids, "buffer": a.buffer,
                "geometry": json.loads(a.geom.geojson), "updated": a.updated.isoformat()}
    indicators = [indicator_dict(i) for i in p.indicators.select_related("cri")]
    support = []
    seen = set()
    for i in p.indicators.select_related("cri"):
        c = i.cri
        if c and c.geida_role != "none" and c.code not in seen:
            seen.add(c.code)
            support.append({"cri": c.code, "name": c.name, "role": c.geida_role,
                            "module": c.candidate_module, "status": "planned"})
    return {
        **project_list_item(p, user, perms["can_edit"]),
        "start_date": p.start_date.isoformat() if p.start_date else None,
        "end_date": p.end_date.isoformat() if p.end_date else None,
        "otl": p.otl,
        "location": p.location,
        "themes": p.themes,
        "components": p.components,
        "source_info": p.source_info,
        "review_comment": p.review_comment,
        "submitted_at": p.submitted_at.isoformat() if p.submitted_at else None,
        "published_at": p.published_at.isoformat() if p.published_at else None,
        "created": p.created.isoformat(),
        "area": area,
        "indicators": indicators,
        "documents": [{"id": d.id, "doc_type": d.doc_type, "title": d.title, "url": d.url}
                      for d in p.documents.all()],
        "geida_support": support,
        "log": [{"action": l.action, "user": person(l.user), "detail": l.detail,
                 "created": l.created.isoformat()} for l in p.log.select_related("user")[:40]],
        "missing_to_submit": missing_to_submit(p),
        "permissions": perms,
    }


def missing_to_submit(p):
    missing = [f for f in REQUIRED_TO_SUBMIT if not getattr(p, f)]
    if getattr(p, "area", None) is None:
        missing.append("area")
    return missing


# Validation -----------------------------------------------------------------

def _date(v, field, errors):
    if v in (None, ""):
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        errors[field] = ["Use a date like 2026-01-31."]
        return None


def clean_identity(data, errors):
    """Validate identity fields present in `data`. Returns the cleaned subset."""
    out = {}
    if "code" in data:
        code = str(data.get("code") or "").strip().upper().replace(" ", "")
        if not code:
            errors["code"] = ["Enter the project code, for example UGA1072."]
        elif not CODE_RE.match(code):
            errors["code"] = ["Project codes start with three letters, then numbers (for example UGA1072)."]
        out["code"] = code
    if "title" in data:
        title = str(data.get("title") or "").strip()
        if not title:
            errors["title"] = ["Enter the project title."]
        out["title"] = title[:300]
    if "country_iso3" in data:
        country = C.country_by_iso3(data.get("country_iso3"))
        if not country:
            errors["country_iso3"] = ["Choose an IsDB member country."]
        else:
            out["country_iso3"] = country["iso3"]
            out["country_name"] = country["name"]
    for field, pairs in (("sector", C.SECTORS), ("stage", C.STAGES), ("hub", C.HUBS)):
        if field in data:
            v = data.get(field) or ""
            if v and v not in C.keys(pairs):
                errors[field] = ["Choose a value from the list."]
            out[field] = v
    if "start_date" in data:
        out["start_date"] = _date(data.get("start_date"), "start_date", errors)
    if "end_date" in data:
        out["end_date"] = _date(data.get("end_date"), "end_date", errors)
    s, e = out.get("start_date"), out.get("end_date")
    if s and e and e < s:
        errors["end_date"] = ["Expected completion must be after the start date."]
    for field in ("otl", "location"):
        if field in data:
            out[field] = str(data.get(field) or "").strip()[:400]
    if "themes" in data:
        themes = data.get("themes") or []
        if not isinstance(themes, list) or any(t not in C.keys(C.THEMES) for t in themes):
            errors["themes"] = ["Choose themes from the list."]
        else:
            out["themes"] = list(dict.fromkeys(themes))
    if "components" in data:
        comps = data.get("components") or []
        if not isinstance(comps, list):
            errors["components"] = ["Send components as a list."]
        else:
            cleaned = []
            for c in comps:
                if not isinstance(c, dict):
                    continue
                name = str(c.get("name") or "").strip()[:200]
                desc = str(c.get("description") or "").strip()[:1000]
                if name or desc:
                    cleaned.append({"name": name, "description": desc})
            out["components"] = cleaned
    return out


def _num(v, field, errors, i):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        errors.setdefault(str(i), {}).setdefault(field, ["Enter a number."])
        return None


def _year(v, field, errors, i):
    if v in (None, ""):
        return None
    try:
        y = int(v)
    except (TypeError, ValueError):
        y = 0
    if not 1990 <= y <= 2100:
        errors.setdefault(str(i), {}).setdefault(field, ["Enter a year between 1990 and 2100."])
        return None
    return y


def clean_indicators(items, errors):
    if not isinstance(items, list):
        errors["_"] = ["Send the indicators as a list."]
        return []
    cris = {c.code: c for c in CRI.objects.filter(code__in=[str((x or {}).get("cri") or "") for x in items])}
    out = []
    for i, x in enumerate(items):
        if not isinstance(x, dict):
            continue
        row_err = {}
        statement = str(x.get("statement") or "").strip()
        cri_code = str(x.get("cri") or "").strip()
        cri = cris.get(cri_code) if cri_code else None
        if cri_code and cri is None:
            row_err["cri"] = [f"CRI {cri_code} isn't in the library."]
        if not statement:
            if cri:
                statement = cri.name
            else:
                row_err["statement"] = ["Enter the indicator statement, or pick a CRI."]
        level = x.get("level") or "output"
        if level not in C.keys(C.LEVELS):
            row_err["level"] = ["Choose impact, outcome or output."]
        tier = x.get("tier") or ("ta_cri" if cri and cri.code in C.TA_CRI_CODES else "project_cri" if cri else "project_specific")
        if tier not in C.keys(C.TIERS):
            row_err["tier"] = ["Choose a tier from the list."]
        geo_role = x.get("geo_role") or (cri.geida_role if cri else "none")
        if geo_role not in C.keys(C.GEO_ROLES):
            row_err["geo_role"] = ["Choose a geospatial role from the list."]
        sex = x.get("sex_disaggregated")
        if sex is None:
            sex = bool(cri and cri.sex_disaggregated == "yes")
        if row_err:
            errors[str(i)] = row_err
        out.append({
            "order": i,
            "level": level,
            "statement": statement[:500],
            "unit": str(x.get("unit") or (cri.unit if cri else "")).strip()[:60],
            "cri": cri,
            "tier": tier,
            "baseline_value": _num(x.get("baseline_value"), "baseline_value", errors, i),
            "baseline_year": _year(x.get("baseline_year"), "baseline_year", errors, i),
            "target_value": _num(x.get("target_value"), "target_value", errors, i),
            "target_year": _year(x.get("target_year"), "target_year", errors, i),
            "means_of_verification": str(x.get("means_of_verification") or "").strip()[:500],
            "sex_disaggregated": bool(sex),
            "geo_role": geo_role,
        })
    return out


def clean_documents(items, errors):
    from django.core.exceptions import ValidationError
    from django.core.validators import URLValidator

    if not isinstance(items, list):
        errors["_"] = ["Send the documents as a list."]
        return []
    check = URLValidator(schemes=["http", "https"])
    out = []
    for i, x in enumerate(items):
        if not isinstance(x, dict):
            continue
        url = str(x.get("url") or "").strip()
        if not url:
            continue
        try:
            check(url)
        except ValidationError:
            errors[str(i)] = {"url": ["Enter a full link starting with https://"]}
            continue
        t = x.get("doc_type") or "other"
        if t not in C.keys(C.DOC_TYPES):
            t = "other"
        out.append({"order": i, "doc_type": t, "title": str(x.get("title") or "").strip()[:255], "url": url[:1000]})
    return out
