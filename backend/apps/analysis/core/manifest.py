"""
The analysis manifest schema (analyses/<category>/<id>/manifest.yaml).

A manifest says what an analysis is, which phases it serves, what it needs and what it
produces. It is validated here when analyses are loaded and by `manage.py check_analyses`;
errors name the file and the field. The validated manifest is still used as a plain dict
by the rest of the platform (registry, API, runner).
"""
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

PHASES = ("preparation", "implementation", "completion")
INPUT_TYPES = ("raster", "vector_point", "vector_line", "vector_polygon", "table")
OUTPUT_TYPES = ("metric", "table", "image", "vector", "file", "raster", "chart")
ENGINES = ("gdal", "grass", "whitebox")
QUEUES = ("light", "raster", "heavy")
ID_RE = r"^[a-z][a-z0-9_]{1,58}$"
SEMVER_RE = r"^\d+\.\d+\.\d+$"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Input(_Strict):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    type: Literal[INPUT_TYPES]
    label: str
    default: str | None = None          # dataset id (apps.analysis.data registry)
    source: Literal["project_area"] | None = None
    # Map style of the input layer when shown (vector inputs)
    color: str | None = None
    radius: float | None = None
    width: float | None = None


class Inputs(_Strict):
    required: list[Input] = []
    optional: list[Input] = []


def parse_point(v):
    """[lon, lat] (6 decimals) from a list or a "lon, lat" string; None if it isn't a valid point."""
    if isinstance(v, str):
        v = [x for x in v.replace(";", ",").replace(" ", ",").split(",") if x]
    try:
        lon, lat = (float(x) for x in v)
    except (TypeError, ValueError):
        return None
    return [round(lon, 6), round(lat, 6)] if -180 <= lon <= 180 and -90 <= lat <= 90 else None


class Choice(_Strict):
    value: str | int | float
    label: str


class CriteriaLayer(_Strict):
    """A layer a `criteria` parameter can use: a range of values (slope, elevation…) or classes (land cover)."""
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: str
    kind: Literal["range", "classes"]
    unit: str = ""
    classes: list[Choice] = []
    group: str = ""


def parse_criteria(value, layers):
    """
    Check a list of criteria against the layers a parameter offers. Each row:
        {"layer": id, "min": number|None, "max": number|None, "classes": [values], "weight": 0–100, "must": bool}
    A range row needs min or max; a classes row needs at least one class. Returns (rows, None) or (None, message).
    A JSON string is accepted too (the run form sends one).
    """
    import json
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None, "The criteria couldn't be read."
    if not isinstance(value, list) or not value:
        return None, "Add at least one criterion."
    by_id = {(l["id"] if isinstance(l, dict) else l.id): (l if isinstance(l, dict) else l.model_dump()) for l in layers}
    rows = []
    for n, r in enumerate(value, start=1):
        if not isinstance(r, dict) or r.get("layer") not in by_id:
            return None, f"Criterion {n}: choose a layer."
        lay = by_id[r["layer"]]
        try:
            weight = float(r.get("weight") or 0)
        except (TypeError, ValueError):
            return None, f"Criterion {n} ({lay['label']}): the weight must be a number."
        if not 0 <= weight <= 100:
            return None, f"Criterion {n} ({lay['label']}): the weight must be between 0 and 100."
        row = {"layer": lay["id"], "weight": weight, "must": bool(r.get("must"))}
        if lay["kind"] == "range":
            lo, hi = r.get("min"), r.get("max")
            try:
                lo = None if lo in (None, "") else float(lo)
                hi = None if hi in (None, "") else float(hi)
            except (TypeError, ValueError):
                return None, f"Criterion {n} ({lay['label']}): the limits must be numbers."
            if lo is None and hi is None:
                return None, f"Criterion {n} ({lay['label']}): give a minimum, a maximum or both."
            if lo is not None and hi is not None and lo > hi:
                return None, f"Criterion {n} ({lay['label']}): the minimum is above the maximum."
            row.update(min=lo, max=hi)
        else:
            allowed = {str(c["value"]) for c in lay.get("classes", [])}
            chosen = [c for c in (r.get("classes") or []) if str(c) in allowed]
            if not chosen:
                return None, f"Criterion {n} ({lay['label']}): choose at least one class."
            row["classes"] = chosen
        rows.append(row)
    if not any(r["weight"] > 0 for r in rows) and not all(r["must"] for r in rows):
        return None, "Give at least one criterion a weight, or mark the criteria as must-haves."
    return rows, None


class Parameter(_Strict):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    # point: [lon, lat] picked on the map in the run form (e.g. a catchment outlet); default null = required
    # criteria: a list of conditions with weights (site suitability), on the layers listed in `layers`
    type: Literal["number", "choice", "text", "boolean", "point", "criteria"]
    label: str
    default: Any = None
    min: float | None = None
    max: float | None = None
    choices: list[Choice] = []
    layers: list[CriteriaLayer] = []

    @model_validator(mode="after")
    def _consistent(self):
        if self.type == "criteria":
            if not self.layers:
                raise ValueError("a criteria parameter needs layers")
            if self.default is not None:
                _, problem = parse_criteria(self.default, self.layers)
                if problem:
                    raise ValueError(f"default criteria: {problem}")
        if self.type == "choice":
            if not self.choices:
                raise ValueError("a choice parameter needs choices")
            if self.default is not None and str(self.default) not in {str(c.value) for c in self.choices}:
                raise ValueError(f"default {self.default!r} isn't one of the choices")
        if self.type == "point" and self.default is not None:
            ok = isinstance(self.default, (list, tuple)) and len(self.default) == 2 and all(isinstance(v, (int, float)) for v in self.default)
            if not ok or not (-180 <= self.default[0] <= 180 and -90 <= self.default[1] <= 90):
                raise ValueError("a point parameter's default is [lon, lat] or null")
        if self.type == "number" and self.default is not None:
            if not isinstance(self.default, (int, float)):
                raise ValueError("a number parameter needs a number default")
            if self.min is not None and self.default < self.min or self.max is not None and self.default > self.max:
                raise ValueError(f"default {self.default} is outside {self.min}–{self.max}")
        return self


class Output(_Strict):
    type: Literal[OUTPUT_TYPES]
    # A name, or a family of names ending in "*" (e.g. layer_* for one map layer per input)
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*\*?$")
    optional: bool = False              # may be missing (e.g. depends on optional data)
    legend: str | None = None           # legend file in the analysis folder (raster outputs)


class Cri(_Strict):
    code: str
    role: Literal["measure", "estimate", "verify", "context", "recorded"]


class Limits(_Strict):
    max_area_km2: float | None = Field(default=None, gt=0)


class Manifest(_Strict):
    id: str = Field(pattern=ID_RE)
    version: str = Field(pattern=SEMVER_RE)
    title: str = Field(min_length=3)
    question: str = ""
    description: str = ""
    status: Literal["curated", "experimental", "deprecated"] = "curated"
    category: str
    themes: list[str] = []
    phases: list[Literal[PHASES]] = Field(min_length=1)
    cri: list[Cri] = []
    inputs: Inputs = Inputs()
    parameters: list[Parameter] = []
    outputs: list[Output] = []
    requires: list[Literal[ENGINES]] = []
    limits: Limits = Limits()
    queue: Literal[QUEUES] = "light"
    runtime: str = ""                   # e.g. "under 1 minute for 10,000 km²"
    citations: list[str] = []
    steps: list[Any] = []               # outline of the method (documentation)
    acceptance: Any = None              # acceptance checks (documentation)

    @field_validator("version", mode="before")
    @classmethod
    def _version_str(cls, v):
        return str(v) if isinstance(v, (int, float)) else v

    @model_validator(mode="after")
    def _unique_names(self):
        for what, items in (("phases", self.phases), ("parameter names", [p.name for p in self.parameters]),
                            ("output names", [o.name for o in self.outputs]),
                            ("input names", [i.name for i in self.inputs.required + self.inputs.optional])):
            dupes = sorted({x for x in items if items.count(x) > 1})
            if dupes:
                raise ValueError(f"{what} must be unique (repeated: {', '.join(dupes)})")
        return self


def _where(loc):
    return ".".join(str(p) for p in loc) or "(top level)"


def validate_manifest(data, path=""):
    """Validate a manifest dict; returns it unchanged, or raises ValueError naming the file and fields."""
    if not isinstance(data, dict):
        raise ValueError(f"{path}: the manifest must be a YAML mapping")
    try:
        Manifest.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(f"{_where(e['loc'])}: {re.sub(r'^Value error, ', '', e['msg'])}" for e in exc.errors())
        raise ValueError(f"{path}: {problems}") from None
    return data
