"""
Toolbox inputs: what a tool can read from the project, and how each is prepared as a file for the engine.
Every input is cut to the area of influence (plus a margin) and put in the project's UTM zone, so distances and
areas are in metres. Vectors become GeoPackages with a plain layer name (the engine reads GDAL's GeoPackages well,
but not GDAL's FlatGeobuf files; it writes its vector outputs as FlatGeobuf, see runner.py), rasters GeoTIFFs,
tables CSV.

References (stored with each run):
    {"kind": "area"}                                the area of influence
    {"kind": "admin", "level": 1 | 2}               admin units cut to the area
    {"kind": "catalog", "id": "elevation", "year": 2021}   a Data Catalog raster
    {"kind": "osm", "layer": "schools"}             an OpenStreetMap layer
    {"kind": "run", "run": 12, "output": "streams"} a vector or raster output of an analysis run
    {"kind": "tool", "run": 5, "output": "output"}  an output of an earlier Toolbox run
    {"kind": "upload", "id": 3}                     a file uploaded to the project
"""
import math
import shutil
from pathlib import Path

from apps.core.geo import utm_epsg

MARGIN_M = 1000


class InputError(Exception):
    pass


def project_epsg(project):
    c = project.area.geom.centroid
    return utm_epsg(c.x, c.y)


def project_bbox(project, margin_m=MARGIN_M):
    w, s, e, n = project.area.geom.extent
    dlat = margin_m / 111_320
    dlon = dlat / max(0.2, math.cos(math.radians((s + n) / 2)))
    return (w - dlon, s - dlat, e + dlon, n + dlat)


# What can be picked ---------------------------------------------------------------------------------------
def available(project, user):
    """Inputs a tool can read for this project: [{ref, label, kind, group, years?}]."""
    from apps.analysis.data import DATASETS
    from apps.analysis.models import ModuleRun
    from apps.boundaries.models import AdminUnit
    from apps.projects.access import can_view

    out = [{"ref": {"kind": "area"}, "label": "Area of influence", "kind": "vector", "group": "Project"}]
    for level in (1, 2, 3):
        if AdminUnit.objects.filter(iso3=project.country_iso3, level=level, geom__intersects=project.area.geom).exists():
            out.append({"ref": {"kind": "admin", "level": level}, "label": f"Admin units, level {level} (cut to the area)",
                        "kind": "vector", "group": "Project"})
    for ds_id, ds in DATASETS.items():
        if ds.kind == "raster" and not ds_id.startswith(("worldpop_", "copernicus_", "esa_")):
            years = list(getattr(ds, "years", None) or (getattr(ds, "layer", {}) or {}).get("years") or [])
            out.append({"ref": {"kind": "catalog", "id": ds_id}, "label": ds.title, "kind": "raster",
                        "group": "Data Catalog", **({"years": years} if years else {})})
    for ds_id, ds in DATASETS.items():
        if ds_id.startswith("osm_") and not ds_id.endswith("_points") and ds.kind == "vector":
            out.append({"ref": {"kind": "osm", "layer": ds_id[4:]}, "label": f"OSM: {ds.title}", "kind": "vector",
                        "group": "OpenStreetMap"})
    for r in ModuleRun.objects.filter(project=project, status="done").select_related("module").order_by("-created")[:60]:
        for o in r.outputs or []:
            if o.get("type") == "vector" or (o.get("type") == "raster" and o.get("data_file")):
                out.append({"ref": {"kind": "run", "run": r.pk, "output": o["name"]},
                            "label": f"{o.get('title') or o['name']} (#{r.pk} {r.module.title})",
                            "kind": "vector" if o["type"] == "vector" else "raster", "group": "Analysis results"})
    from .models import ToolRun, ToolUpload
    for t in ToolRun.objects.filter(project=project, status="done")[:100]:
        for o in t.outputs or []:
            if o.get("kind") in ("vector", "raster", "table"):
                out.append({"ref": {"kind": "tool", "run": t.pk, "output": o["name"]},
                            "label": f"{t.name} · {o.get('title') or o['name']} (#{t.pk})", "kind": o["kind"],
                            "group": "Toolbox results"})
    for u in ToolUpload.objects.filter(project=project):
        out.append({"ref": {"kind": "upload", "id": u.pk}, "label": u.name, "kind": u.kind, "group": "Uploads"})
    return out


# Preparing files ------------------------------------------------------------------------------------------
def _gdal():
    from osgeo import gdal, ogr
    gdal.UseExceptions()
    ogr.UseExceptions()
    return gdal, ogr


def align_rasters(paths):
    """Warp every raster onto the first one's grid (same extent, size and resolution; nearest neighbour keeps class
    values), so tools that combine rasters cell by cell accept them."""
    gdal, _ = _gdal()
    if len(paths) < 2:
        return
    ref = gdal.Open(str(paths[0]))
    gt, w, h, wkt = ref.GetGeoTransform(), ref.RasterXSize, ref.RasterYSize, ref.GetProjection()
    bounds = (gt[0], gt[3] + gt[5] * h, gt[0] + gt[1] * w, gt[3])
    ref = None
    for p in paths[1:]:
        ds = gdal.Open(str(p))
        same = ds.RasterXSize == w and ds.RasterYSize == h and ds.GetGeoTransform() == gt
        ds = None
        if same:
            continue
        tmp = Path(str(p) + ".aligned.tif")
        gdal.Warp(str(tmp), str(p), format="GTiff", dstSRS=wkt, outputBounds=bounds, width=w, height=h,
                  resampleAlg="near", creationOptions=["TILED=YES", "COMPRESS=DEFLATE"])
        tmp.replace(p)


def write_vector(path, geoms, epsg, rows=None, layer="layer"):
    """GEOS geometries (EPSG:4326) -> a GeoPackage in `epsg` (multi-part polygons), with optional attribute rows."""
    gdal, ogr = _gdal()
    from osgeo import osr
    sr = osr.SpatialReference()
    sr.ImportFromEPSG(int(epsg))
    ds = ogr.GetDriverByName("GPKG").CreateDataSource(str(path))
    lyr = ds.CreateLayer(Path(path).stem, sr, ogr.wkbMultiPolygon)
    keys = list((rows or [{}])[0].keys()) if rows else []
    for k in keys:
        lyr.CreateField(ogr.FieldDefn(k, ogr.OFTString))
    for i, g in enumerate(geoms):
        g = g.clone()
        g.transform(int(epsg))
        f = ogr.Feature(lyr.GetLayerDefn())
        for k in keys:
            f.SetField(k, str(rows[i].get(k, "")))
        f.SetGeometry(ogr.ForceToMultiPolygon(ogr.CreateGeometryFromWkb(bytes(g.wkb))))
        lyr.CreateFeature(f)
    ds = None
    return path


def vector_source(path):
    """What GDAL should open for a vector file: zipped shapefiles and KMZ are read inside the archive."""
    path = Path(path)
    if path.suffix.lower() not in (".zip", ".kmz"):
        return str(path)
    _, ogr = _gdal()
    for src in (str(path), f"/vsizip/{path}", f"/vsizip/{path}/doc.kml"):
        try:
            if ogr.Open(src) is not None:
                return src
        except RuntimeError:
            continue
    return f"/vsizip/{path}"


def geometry_option(src):
    """GDAL's geometryType for a layer: keep single types as they are (points stay points: several engine tools
    refuse multi-points), promote to multi only when single and multi parts are mixed."""
    _, ogr = _gdal()
    try:
        ds = ogr.Open(str(src))
        lyr = ds.GetLayer(0)
        names = set()
        for i, f in enumerate(lyr):
            g = f.GetGeometryRef()
            if g is not None:
                names.add(g.GetGeometryName().upper())
            if i >= 5000:
                break
        ds = None
    except (RuntimeError, AttributeError):
        return None
    families = {n.replace("MULTI", "") for n in names}
    if len(families) == 1 and len(names) == 2:
        return "PROMOTE_TO_MULTI"
    if len(families) > 1:
        return "GEOMETRY"
    return None


def to_vector(src, dest, epsg, bbox=None):
    """Any vector GDAL reads -> a GeoPackage in `epsg` with a plain layer name (cut to bbox, lon/lat, when given)."""
    gdal, _ = _gdal()
    opts = {"format": "GPKG", "dstSRS": f"EPSG:{epsg}", "makeValid": True, "layerName": Path(dest).stem,
            "layerCreationOptions": ["FID=geida_fid"]}
    if gtype := geometry_option(src):
        opts["geometryType"] = gtype
    if bbox:
        opts.update(spatFilter=list(bbox), spatSRS="EPSG:4326")
    gdal.VectorTranslate(str(dest), str(src), **opts)
    return dest


def raster_to_tif(src, dest, epsg, bbox=None):
    gdal, _ = _gdal()
    opts = {"format": "GTiff", "dstSRS": f"EPSG:{epsg}", "creationOptions": ["TILED=YES", "COMPRESS=DEFLATE", "BIGTIFF=IF_SAFER"]}
    if bbox:
        opts.update(outputBounds=list(bbox), outputBoundsSRS="EPSG:4326")
    gdal.Warp(str(dest), str(src), **opts)
    return dest


def prepare(ref, project, work, stem, log=print):
    """Write the input `ref` into the folder `work` as `stem`.<ext>; returns the file name."""
    from apps.analysis.data import DATASETS
    from apps.analysis.data.base import DatasetUnavailable
    from apps.analysis.data.cog import CatalogRaster, _bbox_polygon

    work, epsg, bbox, kind = Path(work), project_epsg(project), project_bbox(project), (ref or {}).get("kind")
    try:
        if kind == "area":
            return write_vector(work / f"{stem}.gpkg", [project.area.geom], epsg, [{"code": project.code}], "area").name
        if kind == "admin":
            from django.contrib.gis.db.models.functions import Intersection
            from apps.boundaries.models import AdminUnit
            level = int(ref.get("level") or 2)
            qs = (AdminUnit.objects.filter(iso3=project.country_iso3, level=level, geom__intersects=project.area.geom)
                  .annotate(clip=Intersection("geom", project.area.geom)))
            units = [u for u in qs if u.clip and not u.clip.empty]
            if not units:
                raise InputError(f"No admin units of level {level} cover the area.")
            return write_vector(work / f"{stem}.gpkg", [u.clip for u in units], epsg,
                              [{"gid": u.gid, "name": u.name} for u in units], f"admin{level}").name
        if kind == "catalog":
            ds = DATASETS.get(ref.get("id"))
            if ds is None or ds.kind != "raster":
                raise InputError("That Data Catalog layer isn't available.")
            if isinstance(ds, CatalogRaster):
                src, _ = ds.clip(_bbox_polygon(bbox), project.country_iso3, ref.get("year"), log=log)
            else:
                src = ds.fetch(bbox, project.country_iso3, log=log)
            return raster_to_tif(src, work / f"{stem}.tif", epsg).name
        if kind == "osm":
            from apps.analysis.data.registry import get_dataset
            src = get_dataset(f"osm_{ref.get('layer')}").fetch(bbox, project.country_iso3, log=log)
            return to_vector(src, work / f"{stem}.gpkg", epsg, bbox).name
        if kind == "run":
            from apps.analysis.models import ModuleRun
            r = ModuleRun.objects.filter(pk=ref.get("run"), project=project, status="done").first()
            o = next((o for o in (r.outputs if r else []) if o.get("name") == ref.get("output")), None)
            if o is None:
                raise InputError("That analysis result no longer exists.")
            if o["type"] == "vector":
                return to_vector(r.workdir / o["file"], work / f"{stem}.gpkg", epsg).name
            return raster_to_tif(r.workdir / o["data_file"], work / f"{stem}.tif", epsg).name
        if kind == "tool":
            from .models import ToolRun
            t = ToolRun.objects.filter(pk=ref.get("run"), project=project, status="done").first()
            o = next((o for o in (t.outputs if t else []) if o.get("name") == ref.get("output")), None)
            if o is None or not (t.workdir / o["file"]).exists():
                raise InputError("That Toolbox result no longer exists.")
            if o["kind"] == "vector":
                return to_vector(t.workdir / o["file"], work / f"{stem}.gpkg", epsg).name
            name = f"{stem}{Path(o['file']).suffix}"
            shutil.copyfile(t.workdir / o["file"], work / name)
            return name
        if kind == "upload":
            from .models import ToolUpload
            u = ToolUpload.objects.filter(pk=ref.get("id"), project=project).first()
            if u is None or not u.path.exists():
                raise InputError("That upload no longer exists.")
            if u.kind == "vector":
                return to_vector(vector_source(u.path), work / f"{stem}.gpkg", epsg).name
            if u.kind == "raster":
                return raster_to_tif(u.path, work / f"{stem}.tif", epsg).name
            name = f"{stem}{u.path.suffix}"
            shutil.copyfile(u.path, work / name)
            return name
    except DatasetUnavailable as exc:
        raise InputError(str(exc)) from None
    raise InputError("Unknown input.")
