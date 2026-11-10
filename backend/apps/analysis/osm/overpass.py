"""
Fallback when no Geofabrik extract can be used: the same taxonomy layer, fetched live
from the Overpass API. Fine for small areas; large, dense areas may time out.

Points come back as node positions or way/relation centres; lines and polygons as
way geometry. Multipolygon relations are skipped for line and polygon layers (rare
for the layers GEIDA uses); the run log says how many.
"""
import json
import re
import urllib.parse
import urllib.request

from django.conf import settings

from .geofabrik import USER_AGENT


class OverpassUnavailable(Exception):
    pass


def _rule_ql(rule):
    parts = []
    for k, vals in rule.items():
        key = json.dumps(k)
        if "*" in vals:
            parts.append(f"[{key}]")
        else:
            alt = "|".join(re.escape(v) for v in vals)
            parts.append(f"[{key}~{json.dumps(f'^({alt})$')}]")
    return "".join(parts)


def query(layer, bbox, timeout=180):
    w, s, e, n = bbox
    box = f"({s},{w},{n},{e})"
    kinds = {"point": ("nwr",), "line": ("way",), "polygon": ("way", "relation")}[layer.geometry]
    body = "".join(f"{k}{_rule_ql(r)}{box};" for r in layer.match for k in kinds)
    out = "out center tags;" if layer.geometry == "point" else "out geom tags;"
    return f"[out:json][timeout:{timeout}][maxsize:1073741824];({body});{out}"


def fetch(layer, bbox, log=print):
    """GeoJSON features for a taxonomy layer from Overpass (filtered by the layer's rules)."""
    endpoint = getattr(settings, "OVERPASS_URL", "https://overpass-api.de/api/interpreter")
    req = urllib.request.Request(endpoint, data=urllib.parse.urlencode({"data": query(layer, bbox)}).encode(),
                                 headers={"User-Agent": USER_AGENT})
    log(f"{layer.label}: querying OpenStreetMap live (Overpass)")
    try:
        with urllib.request.urlopen(req, timeout=200) as r:
            data = json.loads(r.read().decode())
    except Exception as exc:  # network errors, rate limits, timeouts
        raise OverpassUnavailable(f"OpenStreetMap query failed: {exc}") from exc
    feats, skipped = [], 0
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        if not layer.matches(tags):
            continue
        geom = _geometry(el, layer.geometry)
        if geom is None:
            skipped += 1
            continue
        props = {"osm_id": f"{el['type']}/{el['id']}", "name": tags.get("name", "")}
        props.update({k: tags[k] for k in layer.keep if k in tags})
        feats.append({"type": "Feature", "geometry": geom, "properties": props})
    if skipped:
        log(f"{layer.label}: {skipped} element(s) without usable geometry skipped")
    return feats


def _geometry(el, kind):
    if kind == "point":
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        return None if lon is None or lat is None else {"type": "Point", "coordinates": [lon, lat]}
    if el.get("type") != "way" or not el.get("geometry"):
        return None
    coords = [[p["lon"], p["lat"]] for p in el["geometry"]]
    if kind == "line":
        return {"type": "LineString", "coordinates": coords} if len(coords) >= 2 else None
    if len(coords) >= 4 and coords[0] == coords[-1]:
        return {"type": "Polygon", "coordinates": [coords]}
    return None
