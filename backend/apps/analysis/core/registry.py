"""
Analyses live in backend/analyses/<category>/<id>/ (manifest.yaml + run.py). Adding an
analysis = adding a folder; the platform core doesn't change. Manifests are synced into
the Module table (the model keeps its first name).

- <category> is an id from analyses/categories.yaml; the manifest's `category` must match it.
- <id> is the analysis id, unique across all categories and stable (runs and evidence refer to it).
- Folders starting with "_" or "." are skipped at either level: analyses/_parked/ and
  analyses/_template/ aren't listed; parked analyses keep their Module rows, runs and evidence.
- analyses/planned.yaml lists analyses not built yet (see read_planned).
"""
import importlib.util
from pathlib import Path

import yaml
from django.conf import settings

from ..data import DATASETS
from ..models import Module
from .manifest import validate_manifest
RASTER_TYPES = {"raster"}


def analyses_dir():
    return Path(settings.ANALYSES_DIR)


def _hidden(name):
    return name.startswith(("_", "."))


def analysis_folders():
    """{id: folder} for every analysis under analyses/<category>/<id>/ (hidden folders skipped)."""
    out = {}
    for path in sorted(analyses_dir().glob("*/*/manifest.yaml")):
        folder = path.parent
        if _hidden(folder.name) or _hidden(folder.parent.name):
            continue
        if folder.name in out:
            raise ValueError(f"{folder}: analysis id '{folder.name}' is also used by {out[folder.name]}")
        out[folder.name] = folder
    return out


def read_categories():
    """[{id, title, description, icon, order}] sorted by order."""
    path = analyses_dir() / "categories.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cats = [{"id": c["id"], "title": c["title"], "description": c.get("description", ""),
             "icon": c.get("icon", ""), "order": c.get("order", 99)} for c in data.get("categories", []) or []]
    return sorted(cats, key=lambda c: (c["order"], c["title"]))


def read_planned(built=()):
    """
    Planned analyses (modules/planned.yaml) not yet built: [{id, title, question, category, phases}].
    Shown in the catalogue as "Planned"; an entry disappears once a module with its id exists.
    """
    path = analyses_dir() / "planned.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    categories = {c["id"] for c in read_categories()}
    valid_phases = {"preparation", "implementation", "completion"}
    out = []
    for p in data.get("planned", []) or []:
        if p["id"] in built:
            continue
        if categories and p["category"] not in categories:
            raise ValueError(f"planned.yaml: '{p['id']}' has category '{p['category']}', which isn't in categories.yaml")
        bad = set(p.get("phases", [])) - valid_phases
        if bad or not p.get("phases"):
            raise ValueError(f"planned.yaml: '{p['id']}' needs phases from {sorted(valid_phases)}")
        out.append({"id": p["id"], "title": p["title"], "question": p.get("question", ""),
                    "category": p["category"], "phases": list(p["phases"])})
    return out


def read_manifests(errors=None):
    """
    {id: manifest} for every analysis, validated (core/manifest.py).
    errors=None: the first problem raises ValueError. errors=[]: problems are appended to the
    list and the broken analysis is left out, so one bad folder doesn't hide the catalogue.
    """
    out = {}
    categories = {c["id"] for c in read_categories()}
    for aid, folder in analysis_folders().items():
        path = folder / "manifest.yaml"
        try:
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as exc:
                raise ValueError(f"{path}: not valid YAML ({exc})") from None
            validate_manifest(data, path)
            if data["id"] != aid:
                raise ValueError(f"{path}: id '{data['id']}' must match the folder name")
            if data["category"] != folder.parent.name:
                raise ValueError(f"{path}: category '{data['category']}' must match its category folder '{folder.parent.name}'")
            if categories and data["category"] not in categories:
                raise ValueError(f"{path}: category '{data['category']}' isn't in categories.yaml")
            if not (folder / "run.py").exists():
                raise ValueError(f"{folder}: run.py is missing")
        except ValueError as exc:
            if errors is None:
                raise
            errors.append(str(exc))
            continue
        out[aid] = data
    return out


def sync_modules(errors=None):
    """Upsert Module rows from the manifests; deactivate modules whose folder is gone (or is broken, with errors=[])."""
    manifests = read_manifests(errors)
    for mid, m in manifests.items():
        Module.objects.update_or_create(id=mid, defaults={
            "version": str(m["version"]), "title": m["title"], "question": m.get("question", ""),
            "status": m.get("status", "curated"), "manifest": m, "active": True})
    Module.objects.exclude(id__in=manifests).update(active=False)
    return manifests


def load_run_function(module_id):
    folder = analysis_folders().get(module_id)
    if folder is None:
        raise ValueError(f"No analysis folder for '{module_id}' under {analyses_dir()}")
    path = folder / "run.py"
    spec = importlib.util.spec_from_file_location(f"geida_analyses.{folder.parent.name}.{module_id}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "run"):
        raise ValueError(f"{path} has no run(ctx) function")
    return mod.run


def needs_raster(manifest):
    """True if any input is a raster (the worker then needs a working rasterio + PROJ)."""
    return any(inp.get("type") in RASTER_TYPES for group in ("required", "optional")
               for inp in manifest.get("inputs", {}).get(group, []) or [])


def input_dataset(manifest, name, params=None):
    for group in ("required", "optional"):
        for inp in manifest.get("inputs", {}).get(group, []) or []:
            if inp["name"] == name:
                return (params or {}).get(f"{name}_dataset") or inp.get("default")
    return None


def availability(manifest, project):
    """ready | needs_data | not_available, with reasons a user can act on."""
    reasons, missing_optional = [], []
    if getattr(project, "area", None) is None:
        return {"status": "needs_data", "reasons": ["Add the project's area of influence first (step 2)."]}
    if manifest.get("requires"):
        from .envcheck import missing_engines
        if missing := missing_engines(manifest):
            return {"status": "not_available",
                    "reasons": [f"The analysis server is missing {', '.join(missing)}, which this analysis needs."]}
    max_km2 = (manifest.get("limits") or {}).get("max_area_km2")
    if max_km2 and (project.area.area_km2 or 0) > max_km2:
        return {"status": "not_available",
                "reasons": [f"The area of influence ({project.area.area_km2:,.0f} km²) is larger than this analysis "
                            f"handles ({max_km2:,.0f} km²)."]}
    iso3 = project.country_iso3
    for inp in manifest.get("inputs", {}).get("required", []) or []:
        ds = DATASETS.get(inp.get("default", ""))
        if inp.get("source") == "project_area":
            continue
        if ds is None:
            reasons.append(f"No dataset is registered for '{inp['name']}'.")
        elif not ds.covers(iso3):
            reasons.append(f"{ds.title} doesn't cover {project.country_name}.")
    for inp in manifest.get("inputs", {}).get("optional", []) or []:
        ds = DATASETS.get(inp.get("default", ""))
        if ds is None or not ds.covers(iso3):
            missing_optional.append(inp.get("label") or inp["name"])
    if reasons:
        return {"status": "not_available", "reasons": reasons}
    notes = [f"Optional: {m} not available for {project.country_name}; results won't include it." for m in missing_optional]
    return {"status": "ready", "reasons": notes}


def manifest_public(m):
    """What the UI needs to list a module and build its form."""
    inputs = []
    for group in ("required", "optional"):
        for inp in m.get("inputs", {}).get(group, []) or []:
            ds = DATASETS.get(inp.get("default", ""))
            inputs.append({"name": inp["name"], "required": group == "required", "type": inp.get("type"),
                           "label": inp.get("label") or inp["name"],
                           "dataset": ds.describe() if ds else None})
    return {
        "id": m["id"], "version": str(m["version"]), "title": m["title"], "question": m.get("question", ""),
        "description": m.get("description", ""), "status": m.get("status", "curated"),
        "category": m.get("category", ""),
        "themes": m.get("themes", []), "phases": m.get("phases", []), "cri": m.get("cri", []),
        "inputs": inputs, "parameters": m.get("parameters", []), "outputs": m.get("outputs", []),
        "citations": m.get("citations", []),
    }
