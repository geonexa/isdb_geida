"""
Cut an area out of a country extract with GDAL's OSM driver, then split it into the
taxonomy's themed layers.

    <region>.osm.pbf ──(GDAL OSM driver, bbox filter)──► cache/osm/<region>/<snapshot>/<box>.gpkg
                                                              │ taxonomy rules (SQL filter + check)
                                                              ▼
                                                   <box>.<layer>.geojson   (what modules read)

The GeoPackage holds the points, lines and multipolygons layers with every tag key
the taxonomy uses as a column, so any themed layer for that box is a quick query.
The box is snapped outward to a 0.02° grid so runs with slightly different buffers
share one cache entry.
"""
import hashlib
import json
import math
import os
import re
import time
from pathlib import Path

from django.conf import settings

from . import taxonomy

GRID = 0.02
_LAUNDER = re.compile(r"[^A-Za-z0-9_]")


def snap_bbox(bbox, grid=GRID):
    w, s, e, n = bbox
    f = lambda v, op: round(op(v / grid) * grid, 6)  # noqa: E731
    return (f(w, math.floor), f(s, math.floor), f(e, math.ceil), f(n, math.ceil))


def cache_dir(region_id, snap):
    d = Path(settings.DATA_DIR) / "osm" / region_id.replace("/", "_") / snap
    d.mkdir(parents=True, exist_ok=True)
    return d


def _box_key(bbox, keys):
    return hashlib.sha1(json.dumps([bbox, keys]).encode()).hexdigest()[:12]


# --- GDAL OSM driver configuration --------------------------------------------------

def _default_osmconf():
    from osgeo import gdal

    found = gdal.FindFile("gdal", "osmconf.ini")
    if not found:
        raise RuntimeError("GDAL's osmconf.ini wasn't found; is GDAL_DATA set (conda activate geida)?")
    return Path(found).read_text()


def osmconf(keys, directory):
    """Write an osmconf.ini that turns every taxonomy key into a column; return its path."""
    attrs = ",".join(["name"] + [k for k in keys if k != "name"])
    text = _default_osmconf()
    out, section = [], None
    for line in text.splitlines():
        m = re.match(r"\s*\[(\w+)\]", line)
        if m:
            section = m.group(1)
        if section in ("points", "lines", "multipolygons") and line.startswith("attributes="):
            line = f"attributes={attrs}"
        if section in ("points", "lines", "multipolygons") and line.startswith("other_tags="):
            continue
        if section == "general" and line.startswith("closed_ways_are_polygons="):
            line += ",healthcare,power,water"
        out.append(line)
        if m and section in ("points", "lines", "multipolygons"):
            out.append("other_tags=no")
    path = directory / f"osmconf_{hashlib.sha1(attrs.encode()).hexdigest()[:8]}.ini"
    if not path.exists():
        path.write_text("\n".join(out) + "\n")
    return path


# --- Area GeoPackage ----------------------------------------------------------------

def area_gpkg(pbf, region_id, snap, bbox, log=print):
    """GeoPackage of everything the taxonomy needs inside bbox (cached per extract snapshot)."""
    from osgeo import gdal

    keys = taxonomy.all_keys()
    box = snap_bbox(bbox)
    d = cache_dir(region_id, snap)
    out = d / f"{_box_key(box, keys)}.gpkg"
    if out.exists():
        return out, box
    conf = osmconf(keys, d)
    log(f"OpenStreetMap: extracting the area from the {region_id} extract ({snap})")
    started = time.time()
    tmp = out.with_suffix(f".{os.getpid()}.part.gpkg")
    gdal.UseExceptions()
    prev = {k: gdal.GetConfigOption(k) for k in ("OSM_CONFIG_FILE", "OSM_USE_CUSTOM_INDEXING", "OGR_INTERLEAVED_READING")}
    gdal.SetConfigOption("OSM_CONFIG_FILE", str(conf))
    # Unclosed rings at the box edge are expected; keep them out of the run log.
    gdal.PushErrorHandler("CPLQuietErrorHandler")
    try:
        res = gdal.VectorTranslate(
            str(tmp), str(pbf), format="GPKG", spatFilter=list(box),
            layers=["points", "lines", "multipolygons"],
            layerCreationOptions=["SPATIAL_INDEX=YES"],
        )
        if res is None:
            raise RuntimeError(gdal.GetLastErrorMsg() or "GDAL VectorTranslate failed")
        res = None  # flush and close
        tmp.replace(out)
    finally:
        gdal.PopErrorHandler()
        for k, v in prev.items():
            gdal.SetConfigOption(k, v)
        if tmp.exists():
            tmp.unlink()
    log(f"OpenStreetMap: area extracted in {time.time() - started:.0f} s")
    return out, box


# --- Themed layers ------------------------------------------------------------------

def _sql_literal(v):
    return "'" + str(v).replace("'", "''") + "'"


def _column(key):
    """GDAL's OSM driver launders tag keys into column names: isced:level -> isced_level."""
    return _LAUNDER.sub("_", key)


def _where(layer, columns):
    """SQL filter for a GDAL layer; None if the layer can't match (a key isn't a column)."""
    def rule_sql(rule):
        parts = []
        for k, vals in rule.items():
            if _column(k) not in columns:
                return None
            col = f'"{_column(k)}"'
            parts.append(f"{col} IS NOT NULL AND {col} <> ''" if "*" in vals
                         else f"{col} IN ({', '.join(_sql_literal(v) for v in vals)})")
        return "(" + " AND ".join(parts) + ")"

    ors = [s for s in (rule_sql(r) for r in layer.match) if s]
    if not ors:
        return None
    sql = "(" + " OR ".join(ors) + ")"
    nots = [s for s in (rule_sql(r) for r in layer.exclude) if s]
    if nots:
        sql += " AND NOT (" + " OR ".join(nots) + ")"
    return sql


def _osm_ref(source, feat, columns):
    if source == "points":
        return f"node/{feat.GetField('osm_id')}"
    if source == "lines":
        return f"way/{feat.GetField('osm_id')}"
    if "osm_way_id" in columns and feat.GetField("osm_way_id"):
        return f"way/{feat.GetField('osm_way_id')}"
    return f"relation/{feat.GetField('osm_id')}"


def themed_layer(gpkg, box, layer, as_points=False, log=print):
    """GeoJSON FeatureCollection path for one taxonomy layer inside the area GeoPackage."""
    from osgeo import gdal, ogr

    ogr.UseExceptions()
    point_out = as_points or layer.geometry == "point"
    out = gpkg.with_name(f"{gpkg.stem}.{layer.id}{'.pts' if as_points and layer.geometry != 'point' else ''}.geojson")
    if out.exists() and out.stat().st_mtime >= taxonomy.taxonomy_path().stat().st_mtime:
        return out
    ds = ogr.Open(str(gpkg))
    gdal.PushErrorHandler("CPLQuietErrorHandler")  # GEOS notes on edge-cut polygons; counted instead
    try:
        feats, skipped = _collect(ds, layer, point_out)
    finally:
        gdal.PopErrorHandler()
        ds = None
    tmp = out.with_suffix(f".{os.getpid()}.part")
    tmp.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    tmp.replace(out)
    log(f"OpenStreetMap: {len(feats):,} {layer.label.lower()}"
        + (f" ({skipped} with unusable geometry skipped)" if skipped else ""))
    return out


def _collect(ds, layer, point_out):
    """The layer's GeoJSON features from the area GeoPackage, and how many were unusable."""
    feats, seen, skipped = [], set(), 0
    for source in layer.sources:
        lyr = ds.GetLayerByName(source)
        if lyr is None:
            continue
        defn = lyr.GetLayerDefn()
        columns = {defn.GetFieldDefn(i).GetName() for i in range(defn.GetFieldCount())}
        where = _where(layer, columns)
        if where is None:
            continue
        lyr.SetAttributeFilter(where)
        key_cols = {k: _column(k) for k in layer.keys if _column(k) in columns}
        for f in lyr:
            tags = {k: v for k, c in key_cols.items() if (v := f.GetField(c)) not in (None, "")}
            if not layer.matches(tags):
                continue
            ref = _osm_ref(source, f, columns)
            if ref in seen:
                continue
            g = _usable(f.GetGeometryRef(), point_out)
            if g is None:
                skipped += 1
                continue
            seen.add(ref)
            props = {"osm_id": ref, "name": f.GetField("name") or ""}
            props.update({k: tags[k] for k in layer.keep if k in tags})
            feats.append({"type": "Feature", "geometry": json.loads(g.ExportToJson(["COORDINATE_PRECISION=7"])),
                          "properties": props})
    return feats, skipped


def _usable(g, point_out):
    """The geometry to write, repaired if needed; None if it can't be used.

    Features cut by the area box can arrive with broken rings (their remaining
    nodes lie outside the box); MakeValid repairs most of them.
    """
    from osgeo import ogr

    if g is None or g.IsEmpty():
        return None
    g = g.Clone()
    if g.GetDimension() == 2 and not g.IsValid():
        try:
            g = g.MakeValid()
        except RuntimeError:
            return None
        if g is None or g.IsEmpty():
            return None
        if g.GetGeometryType() not in (ogr.wkbPolygon, ogr.wkbMultiPolygon):  # collection after repair
            polys = ogr.Geometry(ogr.wkbMultiPolygon)
            for i in range(g.GetGeometryCount()):
                part = g.GetGeometryRef(i)
                if part.GetGeometryType() == ogr.wkbPolygon:
                    polys.AddGeometry(part)
            if polys.IsEmpty():
                return None
            g = polys
    if point_out and g.GetDimension() > 0:
        try:
            g = g.PointOnSurface() if g.GetDimension() == 2 else g.Centroid()
        except RuntimeError:
            return None
    return None if g is None or g.IsEmpty() else g
