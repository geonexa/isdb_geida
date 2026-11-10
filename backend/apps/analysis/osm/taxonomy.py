"""The OSM tag taxonomy (seeds/data/osm_taxonomy.yaml): layer definitions and tag matching."""
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml
from django.conf import settings

GEOMETRIES = ("point", "line", "polygon")
# GDAL OSM driver layers each geometry type is read from.
SOURCES = {"point": ("points", "multipolygons"), "line": ("lines",), "polygon": ("multipolygons",)}


@dataclass(frozen=True)
class Layer:
    id: str
    label: str
    category: str
    geometry: str
    match: tuple
    exclude: tuple = ()
    keep: tuple = ()
    sources: tuple = field(default=())

    @property
    def keys(self):
        """Every tag key the layer reads: filters and kept tags."""
        ks = {k for rule in self.match + self.exclude for k in rule}
        return ks | set(self.keep)

    def matches(self, tags):
        """tags: {key: value}. True if any match rule fits and no exclude rule does."""
        return any(_fits(r, tags) for r in self.match) and not any(_fits(r, tags) for r in self.exclude)


def _fits(rule, tags):
    for key, values in rule.items():
        v = tags.get(key)
        if v in (None, ""):
            return False
        if "*" not in values and v not in values:
            return False
    return True


def _rules(raw, where):
    out = []
    for rule in raw or []:
        if not isinstance(rule, dict) or not rule:
            raise ValueError(f"{where}: each rule must be a non-empty mapping of key: [values]")
        out.append({str(k): tuple(str(v) for v in (vals if isinstance(vals, list) else [vals])) for k, vals in rule.items()})
    return tuple(out)


def parse(data):
    layers = {}
    for lid, spec in (data.get("layers") or {}).items():
        where = f"osm_taxonomy layer '{lid}'"
        geom = spec.get("geometry")
        if geom not in GEOMETRIES:
            raise ValueError(f"{where}: geometry must be one of {GEOMETRIES}")
        match = _rules(spec.get("match"), where)
        if not match:
            raise ValueError(f"{where}: needs at least one match rule")
        layers[lid] = Layer(id=lid, label=spec.get("label") or lid, category=spec.get("category", ""),
                            geometry=geom, match=match, exclude=_rules(spec.get("exclude"), where),
                            keep=tuple(spec.get("keep") or ()), sources=SOURCES[geom])
    return layers


def taxonomy_path():
    return Path(settings.SEEDS_DIR) / "data" / "osm_taxonomy.yaml"


@lru_cache(maxsize=4)
def _load(path, mtime):
    return parse(yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {})


def layers():
    """{layer id: Layer}, re-read when the file changes."""
    p = taxonomy_path()
    return _load(str(p), p.stat().st_mtime)


def get_layer(layer_id):
    try:
        return layers()[layer_id]
    except KeyError as exc:
        raise KeyError(f"Unknown OSM layer '{layer_id}' (see seeds/data/osm_taxonomy.yaml)") from exc


def all_keys():
    """Union of tag keys used by any layer (columns to extract from the PBF)."""
    return sorted({k for layer in layers().values() for k in layer.keys})
