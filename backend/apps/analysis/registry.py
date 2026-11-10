"""
Analysis modules live in backend/modules/<id>/ (manifest.yaml + run.py). Adding an
analysis = adding a folder. The manifest is synced into the Module table.

Folders starting with "_" (e.g. modules/_parked/) are not modules: parked modules
leave the catalogue, but their Module rows, past runs and evidence stay.
Categories (modules/categories.yaml) group the catalogue; each manifest names one.
"""
import importlib.util
from pathlib import Path

import yaml
from django.conf import settings

from .datasets import DATASETS
from .models import Module

REQUIRED_KEYS = ("id", "version", "title", "category", "phases", "inputs")
RASTER_TYPES = {"raster"}


def modules_dir():
    return Path(settings.MODULES_DIR)


def read_categories():
    """[{id, title, description, icon, order}] sorted by order."""
    path = modules_dir() / "categories.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cats = [{"id": c["id"], "title": c["title"], "description": c.get("description", ""),
             "icon": c.get("icon", ""), "order": c.get("order", 99)} for c in data.get("categories", []) or []]
    return sorted(cats, key=lambda c: (c["order"], c["title"]))


def read_manifests():
    out = {}
    categories = {c["id"] for c in read_categories()}
    for path in sorted(modules_dir().glob("*/manifest.yaml")):
        if path.parent.name.startswith(("_", ".")):
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        missing = [k for k in REQUIRED_KEYS if k not in data]
        if missing:
            raise ValueError(f"{path}: missing {', '.join(missing)}")
        if data["id"] != path.parent.name:
            raise ValueError(f"{path}: id '{data['id']}' must match the folder name")
        if categories and data["category"] not in categories:
            raise ValueError(f"{path}: category '{data['category']}' isn't in categories.yaml")
        if not (path.parent / "run.py").exists():
            raise ValueError(f"{path.parent}: run.py is missing")
        out[data["id"]] = data
    return out


def sync_modules():
    """Upsert Module rows from the manifests; deactivate modules whose folder is gone."""
    manifests = read_manifests()
    for mid, m in manifests.items():
        Module.objects.update_or_create(id=mid, defaults={
            "version": str(m["version"]), "title": m["title"], "question": m.get("question", ""),
            "status": m.get("status", "curated"), "manifest": m, "active": True})
    Module.objects.exclude(id__in=manifests).update(active=False)
    return manifests


def load_run_function(module_id):
    path = modules_dir() / module_id / "run.py"
    spec = importlib.util.spec_from_file_location(f"geida_modules.{module_id}", path)
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
