"""
OpenStreetMap data for analysis modules.

    path, meta = fetch_layer("schools", bbox, log=ctx.log)

Source order (settings.OSM_SOURCE = "geofabrik", the default):
  1. Geofabrik extract for the smallest region covering the box, downloaded once
     to DATA_DIR/osm/ and cut per area with GDAL (cached in DATA_DIR/cache/osm/);
  2. the live Overpass API, if no extract can be used.
OSM_SOURCE = "overpass" skips step 1.

meta records where the data came from and its snapshot date, so evidence can name
the exact OSM state it was computed from.
"""
import dataclasses
import hashlib
import json
import time
from pathlib import Path

from django.conf import settings

from . import extract, geofabrik, overpass, taxonomy
from .geofabrik import GeofabrikUnavailable
from .overpass import OverpassUnavailable
from .taxonomy import get_layer, layers  # noqa: F401

CITATION = "© OpenStreetMap contributors (ODbL)"


class OSMUnavailable(Exception):
    pass


def fetch_layer(layer_id, bbox, as_points=False, log=print):
    """(GeoJSON path, meta) for a taxonomy layer inside bbox (w, s, e, n)."""
    layer = get_layer(layer_id)
    reasons = []
    if getattr(settings, "OSM_SOURCE", "geofabrik") != "overpass":
        try:
            return _from_extract(layer, bbox, as_points, log)
        except (GeofabrikUnavailable, RuntimeError) as exc:
            reasons.append(str(exc))
            log(f"OpenStreetMap: no local extract ({exc}); trying the live Overpass API")
    try:
        return _from_overpass(layer, bbox, as_points, log)
    except OverpassUnavailable as exc:
        reasons.append(str(exc))
    raise OSMUnavailable(" / ".join(reasons))


def _from_extract(layer, bbox, as_points, log):
    region = geofabrik.find_region(bbox)
    if region.get("partial"):
        log(f"OpenStreetMap: the area crosses the {region['name']} border; "
            f"features in neighbouring countries are not included")
    pbf = geofabrik.ensure_extract(region, log=log)
    snap = geofabrik.snapshot(pbf)
    gpkg, box = extract.area_gpkg(pbf, region["id"], snap, bbox, log=log)
    path = extract.themed_layer(gpkg, box, layer, as_points=as_points, log=log)
    return path, {"source": "geofabrik", "region": region["name"], "snapshot": snap,
                  "partial": bool(region.get("partial")), "url": region["url"], "citation": CITATION}


def _from_overpass(layer, bbox, as_points, log):
    if as_points and layer.geometry != "point":
        layer = dataclasses.replace(layer, geometry="point")
    day = time.strftime("%Y-%m-%d", time.gmtime())
    key = hashlib.sha1(json.dumps([layer.id, layer.geometry, [round(v, 5) for v in bbox]]).encode()).hexdigest()[:12]
    out = Path(settings.DATA_DIR) / "cache" / "osm" / "overpass" / day / f"{key}.{layer.id}.geojson"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        feats = overpass.fetch(layer, bbox, log=log)
        out.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
        log(f"OpenStreetMap: {len(feats):,} {layer.label.lower()} (live)")
    return out, {"source": "overpass", "region": "", "snapshot": day, "url": "https://overpass-api.de",
                 "citation": CITATION}
