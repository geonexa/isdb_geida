"""
What a report shows, gathered from the project and the chosen runs: build(report) returns the context for the
template. Maps and charts are SVG strings (with embedded images); the rest is plain data, kept with the version
(snapshot) so a version stays as generated even if runs are deleted later.
"""
from datetime import date

from django.utils import timezone

from . import charts, maps

CATEGORY_COLORS = {
    "terrain": "#8C6D46", "water": "#2B7BB9", "land": "#2F8F4E", "hazards": "#D9822B", "people": "#B5527A",
    "infrastructure": "#5B5F97", "planning": "#C9A25B", "monitoring": "#3E7C7B",
}


def _category_titles():
    """{id: title} from analyses/categories.yaml (the names the Analyses tab shows)."""
    import yaml
    from apps.analysis.core.registry import analyses_dir
    path = analyses_dir() / "categories.yaml"
    try:
        return {c["id"]: c["title"] for c in (yaml.safe_load(path.read_text()) or {}).get("categories", [])}
    except (OSError, ValueError, KeyError, TypeError):
        return {}
MAX_TABLE_ROWS = 25


def _label(pairs, key):
    return dict(pairs).get(key, key or "")


def _fmt_value(v):
    if isinstance(v, bool) or v is None:
        return "" if v is None else ("Yes" if v else "No")
    if isinstance(v, (int, float)):
        if isinstance(v, float) and not v.is_integer():
            return f"{v:,.2f}".rstrip("0").rstrip(".") if abs(v) < 100 else f"{v:,.0f}"
        return f"{int(v):,}"
    try:
        f = float(v)
        return _fmt_value(int(f) if f.is_integer() else f)
    except (TypeError, ValueError):
        return str(v)


def _person(u):
    return (u.get_full_name() or u.username) if u else ""


def project_facts(p):
    from apps.projects import choices as C
    area = getattr(p, "area", None)
    facts = [("Project code", p.code), ("Country", p.country_name), ("Sector", _label(C.SECTORS, p.sector)),
             ("Cycle stage", _label(C.STAGES, p.stage)), ("Status", _label(C.STATUSES, p.status)),
             ("Start", p.start_date.strftime("%d %b %Y") if p.start_date else ""),
             ("Expected completion", p.end_date.strftime("%d %b %Y") if p.end_date else ""),
             ("Operations team leader", p.otl), ("Regional hub", _label(C.HUBS, p.hub)), ("Location", p.location)]
    out = {"facts": [{"label": k, "value": v} for k, v in facts if v],
           "components": [c for c in (p.components or []) if isinstance(c, dict) and c.get("name")],
           "area": None, "indicators": []}
    if area is not None:
        out["area"] = {"km2": area.area_km2, "method": _label(C.AREA_METHODS, area.method),
                       "source": area.source_name}
    for i in p.indicators.select_related("cri").all():
        ev = i.evidence.filter(status="accepted").order_by("-created").first()
        out["indicators"].append({
            "level": _label(C.LEVELS, i.level), "statement": i.statement, "unit": i.unit,
            "cri": i.cri.code if i.cri else "",
            "baseline": f"{_fmt_value(i.baseline_value)} ({i.baseline_year})" if i.baseline_value is not None and i.baseline_year else _fmt_value(i.baseline_value),
            "target": f"{_fmt_value(i.target_value)} ({i.target_year})" if i.target_value is not None and i.target_year else _fmt_value(i.target_value),
            "evidence": (f"{_fmt_value(ev.value)} {ev.unit}".strip() + (f" ({ev.reference_date})" if ev.reference_date else ""))
            if ev else "",
        })
    return out


def _method_html(module_id):
    import markdown
    from apps.analysis.core.registry import analysis_folders
    folder = analysis_folders().get(module_id)
    path = folder / "METHOD.md" if folder else None
    if not path or not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):         # the section already has the analysis title
        text = "\n".join(lines[1:])
    return markdown.markdown(text, extensions=["tables", "sane_lists"])


def _params_text(run, manifest):
    """The run's settings as readable rows (criteria and points summarised)."""
    labels = {p.get("id") or p.get("name"): p.get("label") or p.get("id") for p in manifest.get("parameters") or []}
    rows = []
    for k, v in (run.params or {}).items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            v = f"{len(v)} conditions" if k == "criteria" else f"{len(v)} items"
        elif isinstance(v, dict):
            v = ", ".join(f"{a}: {b}" for a, b in v.items())
        text = str(v) if isinstance(v, int) and not isinstance(v, bool) else _fmt_value(v)   # 2024, not 2,024
        rows.append({"label": labels.get(k, k.replace("_", " ").capitalize()), "value": text})
    return rows


def _legend_colors(run):
    """{label: colour} from the run's raster legends and vector classes, for chart bars."""
    out = {}
    for o in run.outputs or []:
        for item in (o.get("legend") or []) + ((o.get("style") or {}).get("classes") or []):
            if item.get("label") and item.get("color"):
                out.setdefault(str(item["label"]), item["color"])
    return out


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _cell(key, v):
    """A table value as text; years stay as they are (2024, not 2,024)."""
    if _is_num(v) and "year" in key.lower():
        return str(int(v)) if float(v).is_integer() else str(v)
    return _fmt_value(v)


def run_section(run, chosen, note, area, basemap, figure_no):
    """One analysis section. chosen: output names to show (None = defaults)."""
    m = run.module.manifest or {}
    outs = run.outputs or []
    if chosen is None:
        first_map = next((o["name"] for o in outs if o.get("type") in ("raster", "vector")), None)
        first_table = next((o["name"] for o in outs if o.get("type") == "table"), None)
        first_chart = next((o["name"] for o in outs if o.get("type") == "chart"), None)
        chosen = {o["name"] for o in outs if o.get("type") == "metric"} | {first_map, first_table, first_chart, "summary"}
    chosen = set(chosen)
    cat = m.get("category") or ""
    sec = {
        "run": run.pk, "module": run.module_id, "title": run.module.title, "question": m.get("question") or "",
        "category": _category_titles().get(cat, cat.capitalize()), "category_id": cat,
        "color": CATEGORY_COLORS.get(cat, "#0B3B47"), "date": run.created.strftime("%d %b %Y"),
        "version": run.module_version, "summary": run.summary if "summary" in chosen else "", "note": note or "",
        "metrics": [], "maps": [], "tables": [], "charts": [], "params": _params_text(run, m),
        "datasets": [{"title": d.get("title") or d.get("id"), "citation": d.get("citation") or "",
                      "resolution": d.get("resolution") or "", "date": str(d.get("reference_date") or "")}
                     for d in run.datasets or []],
        "description": (m.get("description") or "").strip(),
        "method_html": _method_html(run.module_id) if "method" in chosen else "",
    }
    colors = _legend_colors(run)
    for o in outs:
        if o.get("name") not in chosen:
            continue
        t = o.get("type")
        if t == "metric":
            sec["metrics"].append({"label": o.get("title"), "value": _fmt_value(o.get("value")), "unit": o.get("unit") or "",
                                   "note": o.get("note") or ""})
        elif t == "raster" and o.get("file"):
            mp = maps.map_svg(area, basemap, raster=(run.workdir / o["file"], o.get("bounds")))
            figure_no[0] += 1
            web = {"kind": "raster", "bounds": o.get("bounds"), "view": mp["bbox"], "title": o.get("title"),
                   "legend": [{"color": i.get("color"), "label": i.get("label")} for i in o.get("legend") or []]}
            sec["maps"].append({"no": figure_no[0], "title": o.get("title"), "svg": mp["svg"], "web": web,
                                "legend": [{"color": i.get("color"), "label": i.get("label"), "kind": "fill"}
                                           for i in o.get("legend") or []],
                                "unit": o.get("unit") or "", "res": o.get("resolution_m")})
        elif t == "vector" and o.get("file"):
            mp = maps.map_svg(area, basemap, vector=(run.workdir / o["file"], o.get("style") or {}))
            figure_no[0] += 1
            legend = mp["legend"]
            if len(legend) == 1 and not legend[0]["label"]:
                legend[0]["label"] = o.get("title")
            fc = maps.web_geojson(run.workdir / o["file"], o.get("style") or {})
            web = {"kind": "vector", "data": fc, "style": o.get("style") or {}, "view": mp["bbox"],
                   "title": o.get("title"), "legend": legend} if fc else None
            sec["maps"].append({"no": figure_no[0], "title": o.get("title"), "svg": mp["svg"], "legend": legend,
                                "web": web,
                                "unit": "", "res": None})
        elif t == "chart":
            svg = charts.series_chart(o)
            if svg:
                figure_no[0] += 1
                sec["charts"].append({"no": figure_no[0], "title": o.get("title"), "unit": o.get("unit") or "",
                                      "svg": svg, "legend": charts.series_legend(o), "note": o.get("note") or ""})
        elif t == "table":
            cols = o.get("columns") or []
            rows = o.get("rows") or []
            shown = rows[:MAX_TABLE_ROWS]
            # A column is numeric (right-aligned) when its values are numbers.
            nums = [any(_is_num(r.get(c["key"])) for r in shown)
                    and all(_is_num(r.get(c["key"])) or r.get(c["key"]) in (None, "") for r in shown) for c in cols]
            sec["tables"].append({
                "title": o.get("title"), "note": o.get("note") or "",
                "columns": [{"label": c.get("label") or c["key"], "unit": c.get("unit") or "", "num": n}
                            for c, n in zip(cols, nums)],
                "rows": [[{"v": _cell(c["key"], r.get(c["key"])), "num": n} for c, n in zip(cols, nums)] for r in shown],
                "more": max(0, len(rows) - MAX_TABLE_ROWS),
                "chart": charts.bar_chart(o, colors),
            })
    return sec


def build(report, user=None):
    """The template context for a report as it is now."""
    from apps.analysis.models import ModuleRun
    p = report.project
    c = report.content or {}
    opts = c.get("options") or {}
    basemap = opts.get("basemap") if opts.get("basemap") in maps.BASEMAPS else "satellite"
    area = getattr(p, "area", None)
    runs = {r.pk: r for r in ModuleRun.objects.filter(project=p, status="done",
                                                       pk__in=[s.get("run") for s in c.get("sections") or []])
            .select_related("module")}
    figure_no = [0]
    cover = maps.map_svg(area, basemap, globe=p.country_iso3) if area is not None else None
    area_map = cover["svg"] if cover else ""
    if area_map:
        figure_no[0] += 1
    sections, missing = [], []
    for s in c.get("sections") or []:
        r = runs.get(s.get("run"))
        if r is None:
            missing.append(s.get("run"))
            continue
        sections.append(run_section(r, s.get("outputs"), s.get("note"), area, basemap, figure_no))
    key_figures = [dict(m, section=sec["title"]) for sec in sections for m in sec["metrics"][:2]][:8]
    datasets, seen = [], set()
    for sec in sections:
        for d in sec["datasets"]:
            if d["title"] not in seen:
                seen.add(d["title"])
                datasets.append(d)
    now = timezone.localtime()
    return {
        "report": {"title": report.title, "subtitle": report.subtitle, "summary": c.get("summary") or "",
                   "author": _person(report.author), "generated_by": _person(user),
                   "date": now.strftime("%d %B %Y"), "year": date.today().year},
        "project": {"code": p.code, "title": p.title, "country": p.country_name, **project_facts(p)},
        "options": {"project": opts.get("project", True), "annex": opts.get("annex", True), "basemap": basemap},
        "area_map": area_map,
        "area_map_attribution": maps.BASEMAPS[basemap]["attribution"],
        # What the web report's interactive maps need (not kept in the database: see frozen()).
        "web_maps": {"basemap": basemap, "basemaps": maps.web_basemaps(),
                     "area": maps.area_geojson(area) if area is not None else None,
                     "area_view": cover["bbox"] if cover else None},
        "cover_globe": cover["globe"] if cover else "",
        "sections": sections,
        "key_figures": key_figures,
        "datasets": datasets,
        "missing_runs": missing,
    }


def frozen(context):
    """The context without its pictures: what a version keeps in the database."""
    def strip(sec):
        return {**sec, "maps": [{k: v for k, v in mp.items() if k not in ("svg", "web")} for mp in sec["maps"]],
                "tables": [{k: v for k, v in t.items() if k != "chart"} for t in sec["tables"]],
                "charts": [{k: v for k, v in c.items() if k != "svg"} for c in sec.get("charts", [])]}
    return {**{k: v for k, v in context.items() if k not in ("area_map", "sections", "web_maps", "cover_globe")},
            "sections": [strip(s) for s in context["sections"]]}
