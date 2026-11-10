"""
Area-of-influence geometry: read uploads, check and repair, reproject to
EPSG:4326, compute area, buffer points, union admin units.

Every change made to a geometry is reported back as a note so the user can see
it; nothing is fixed silently.
"""
import os
import re
import tempfile
import zipfile

from django.contrib.gis.gdal import DataSource, GDALException, OGRGeometry, SpatialReference
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Point, Polygon

from apps.core.geo import utm_epsg

EQUAL_AREA = 6933  # WGS 84 / NSIDC EASE-Grid 2.0 Global (equal area)
MAX_VERTICES = 250_000
MAX_UPLOAD_MB = 50
VECTOR_EXT = (".geojson", ".json", ".kml", ".gpkg", ".shp", ".gml")
UPLOAD_EXT = VECTOR_EXT + (".zip", ".kmz")
NAME_FIELDS = ("name", "Name", "NAME", "title", "Title", "label", "id", "ID")


class GeometryError(ValueError):
    pass


def area_km2(geom):
    g = geom.transform(EQUAL_AREA, clone=True)
    return round(g.area / 1e6, 3)


def to_multipolygon(geom):
    """Polygon parts of any geometry as a MultiPolygon (or None)."""
    if geom is None or geom.empty:
        return None
    if geom.geom_type == "MultiPolygon":
        return geom
    if geom.geom_type == "Polygon":
        return MultiPolygon(geom, srid=4326)
    parts = []
    if geom.geom_type in ("GeometryCollection",):
        for g in geom:
            mp = to_multipolygon(g)
            if mp:
                parts.extend(list(mp))
    return MultiPolygon(parts, srid=4326) if parts else None


def clean(geom, notes=None):
    """Valid MultiPolygon in EPSG:4326, with notes for every change."""
    notes = list(notes or [])
    if geom.srid and geom.srid != 4326:
        geom = geom.transform(4326, clone=True)
    geom.srid = 4326
    if geom.hasz:
        geom = GEOSGeometry(_drop_z(geom), srid=4326)
        notes.append("Dropped elevation (Z) values; GEIDA stores 2D boundaries.")
    if geom.num_coords > MAX_VERTICES:
        raise GeometryError(
            f"The boundary has {geom.num_coords:,} points (limit {MAX_VERTICES:,}). Simplify it and try again.")
    if not geom.valid:
        reason = geom.valid_reason
        geom = geom.make_valid()
        notes.append(f"Repaired an invalid geometry ({reason}).")
    mp = to_multipolygon(geom)
    if mp is None:
        raise GeometryError("No polygon area found. Upload or draw a polygon, or use a point with a buffer.")
    x0, y0, x1, y1 = mp.extent
    if x0 < -180 or x1 > 180 or y0 < -90 or y1 > 90:
        raise GeometryError("Coordinates are outside longitude/latitude range. Check the file's coordinate system.")
    return mp, notes


def _flatten(ogr):
    """Drop Z (and M) from an OGR geometry in place."""
    if hasattr(ogr, "set_3d"):
        ogr.set_3d(False)
        if hasattr(ogr, "set_measured"):
            ogr.set_measured(False)
    else:  # Django < 5.1
        ogr.coord_dim = 2
    return ogr


def _drop_z(geom):
    return _flatten(OGRGeometry(geom.wkb)).wkb


def summary(mp, notes, iso3=None):
    """Result of a geometry check: geometry + area + notes (incl. country check)."""
    import json

    notes = list(notes)
    km2 = area_km2(mp)
    inside = country_share(mp, iso3) if iso3 else None
    if inside is not None:
        if inside < 0.5:
            notes.append(f"Only {inside * 100:.0f}% of the area lies inside the selected country. Check the country or the file.")
        elif inside < 0.98:
            notes.append(f"{(1 - inside) * 100:.0f}% of the area lies outside the selected country.")
    x0, y0, x1, y1 = mp.extent
    return {
        "geometry": json.loads(mp.geojson),
        "area_km2": km2,
        "parts": len(mp),
        "bbox": [x0, y0, x1, y1],
        "inside_country": None if inside is None else round(inside, 4),
        "notes": notes,
    }


def country_share(mp, iso3):
    """Share (0-1) of the area inside the country, or None if boundaries aren't loaded."""
    from apps.boundaries.models import AdminUnit

    unit = AdminUnit.objects.filter(level=0, iso3=iso3, disputed=False).first()
    if unit is None:
        return None
    country = unit.geom_display or unit.geom
    try:
        inter = mp.intersection(country)
        total = area_km2(mp)
        return 0 if total == 0 else min(1.0, area_km2(inter) / total) if not inter.empty else 0.0
    except Exception:
        return None


def buffer_point(lon, lat, km):
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise GeometryError("Longitude/latitude are out of range.")
    if not (0.05 <= km <= 200):
        raise GeometryError("Buffer radius must be between 0.05 and 200 km.")
    pt = Point(lon, lat, srid=4326)
    epsg = utm_epsg(lon, lat)
    local = pt.transform(epsg, clone=True)
    circle = local.buffer(km * 1000, quadsegs=32)
    circle.transform(4326)
    return MultiPolygon(circle, srid=4326)


# Uploads ---------------------------------------------------------------------

def read_upload(uploaded):
    """
    Read an uploaded vector file. Returns (features, notes) where features is
    [{index, name, geom (GEOS 4326, may be None), geom_type}].
    """
    name = uploaded.name
    ext = os.path.splitext(name)[1].lower()
    if ext not in UPLOAD_EXT:
        raise GeometryError("Upload a GeoJSON, KML/KMZ, GeoPackage or zipped shapefile.")
    if uploaded.size > MAX_UPLOAD_MB * 1024 * 1024:
        raise GeometryError(f"The file is larger than {MAX_UPLOAD_MB} MB.")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, re.sub(r"[^\w.\-]", "_", name))
        with open(path, "wb") as fh:
            for chunk in uploaded.chunks():
                fh.write(chunk)
        return read_path(path)


def read_path(path):
    ext = os.path.splitext(path)[1].lower()
    sources = [path]
    if ext in (".zip", ".kmz"):
        try:
            with zipfile.ZipFile(path) as zf:
                inner = [n for n in zf.namelist() if os.path.splitext(n)[1].lower() in VECTOR_EXT
                         and not n.startswith("__MACOSX")]
        except zipfile.BadZipFile as exc:
            raise GeometryError("The zip file can't be opened.") from exc
        if not inner:
            raise GeometryError("No GeoJSON, KML, GeoPackage or shapefile found inside the zip.")
        sources = [f"/vsizip/{path}/{n}" for n in inner]
    features, notes = [], []
    for src in sources:
        try:
            ds = DataSource(src)
        except GDALException as exc:
            raise GeometryError("The file can't be read as vector data.") from exc
        for layer in ds:
            srs = layer.srs
            epsg = None
            if srs is not None:
                try:
                    srs.identify_epsg()
                    epsg = srs.srid
                except Exception:
                    epsg = None
            if epsg and epsg != 4326:
                notes.append(f"Reprojected from EPSG:{epsg} to EPSG:4326.")
            elif srs is None:
                notes.append(f"Layer '{layer.name}' has no coordinate system; assumed longitude/latitude (EPSG:4326).")
            to4326 = SpatialReference(4326)
            fields = layer.fields
            for feat in layer:
                ogr = feat.geom
                if ogr is None:
                    continue
                if srs is not None and not (epsg == 4326):
                    try:
                        ogr.transform(to4326)
                    except GDALException:
                        pass
                if ogr.coord_dim == 3 or getattr(ogr, "is_measured", False):
                    _flatten(ogr)
                geos = GEOSGeometry(ogr.wkb, srid=4326)
                fname = next((str(feat.get(f)) for f in NAME_FIELDS if f in fields and feat.get(f)), "")
                x0, y0, x1, y1 = geos.extent
                features.append({
                    "index": len(features),
                    "name": fname or f"{layer.name} #{feat.fid}",
                    "geom": geos,
                    "geom_type": geos.geom_type,
                    # Google Earth exports often carry a whole-world placeholder polygon.
                    "whole_world": geos.geom_type in ("Polygon", "MultiPolygon") and (x1 - x0) >= 359 and (y1 - y0) >= 150,
                })
    if not features:
        raise GeometryError("The file has no features.")
    return features, sorted(set(notes), key=notes.index)


def merge_features(features, indexes=None):
    """Union of the chosen polygon features (all polygon features by default)."""
    notes = []
    if indexes is None:
        world = [f for f in features if f.get("whole_world")]
        if world:
            notes.append("Ignored " + ", ".join(f"'{f['name']}'" for f in world)
                         + " – covers the whole world (a placeholder, not a project area).")
        chosen = [f for f in features if not f.get("whole_world")]
    else:
        chosen = [f for f in features if f["index"] in indexes]
    polys = [f["geom"] for f in chosen if f["geom_type"] in ("Polygon", "MultiPolygon")]
    skipped = len(chosen) - len(polys)
    if skipped:
        notes.append(f"Ignored {skipped} point or line feature(s); only polygons form the area.")
    if not polys:
        pts = [f["geom"] for f in chosen if f["geom_type"] == "Point"]
        if pts:
            raise GeometryError("The file has points but no polygons. Use 'Point and buffer' to make an area around a point.")
        raise GeometryError("The file has no polygon features.")
    merged = polys[0]
    for g in polys[1:]:
        merged = merged.union(g)
    if len(polys) > 1:
        notes.append(f"Merged {len(polys)} polygon features into one area.")
    return merged, notes
