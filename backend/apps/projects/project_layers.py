"""
A project's data layers, for the Analytics workspace (GeoLibre): the area of influence, the map outputs of the
project's finished analysis runs, and the outputs of its Toolbox runs. Analytics adds them to its map so its own
tools can work on them.

    GET /api/projects/<code>/layers/        {project, layers: [{id, group, title, source, kind, format, url, ...}]}
    GET /api/projects/<code>/layers/area/   the area of influence as GeoJSON
    GET /api/projects/<code>/layers/<id>/raster/   a raster layer's GeoTIFF for display, with its colours

Rasters keep their values, so Analytics tools can work on them. How to colour them goes in the X-GEIDA-Style
header (JSON): classified rasters come as a one-byte GeoTIFF with an embedded colour table (class values kept,
255 = no data) and {"colormap": "palette"}; continuous rasters come unchanged with their legend ramp
{"palette": [...], "min", "max", "unit"}, which Analytics matches to its nearest colour map.

Sign-in required, and the user must be able to see the project (as for the project page).
"""
import json

from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

from apps.core.api import error

from .access import can_view
from .models import Project

MAX_RUNS = 200


def _project(request, code):
    if not request.user.is_authenticated:
        return None, error("Sign in to see projects.", status=401)
    p = Project.objects.select_related("area").filter(code=(code or "").upper()).first()
    if p is None or not can_view(request.user, p):
        return None, error("Project not found.", status=404)
    return p, None


def _size(path):
    try:
        return path.stat().st_size
    except OSError:
        return None


def _peek_geometry(path):
    """polygon / line / point from the first geometries of a GeoJSON file (reads its first 64 kB), or None."""
    import re
    try:
        with open(path, "rb") as f:
            head = f.read(65536).decode("utf-8", "ignore")
    except OSError:
        return None
    kinds = re.findall(r'"type"\s*:\s*"(?:Multi)?(Polygon|LineString|Point)"', head)
    if not kinds:
        return None
    k = max(set(kinds), key=kinds.count)
    return {"Polygon": "polygon", "LineString": "line", "Point": "point"}[k]


def vector_layer_features(p, layer_id):
    """A project vector layer (by its id in project_layers_list) as a GeoJSON FeatureCollection in lon/lat."""
    import json
    if layer_id == "area":
        area = getattr(p, "area", None)
        if area is None:
            raise LookupError("The project has no area of influence.")
        return {"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"name": "Area of influence"}, "geometry": json.loads(area.geom.geojson)}]}
    from apps.analysis.models import ModuleRun
    from apps.toolbox.models import ToolRun
    kind, _, rest = layer_id.partition("-")
    pk, _, name = rest.partition("-")
    if kind == "run":
        r = ModuleRun.objects.filter(project=p, pk=pk, status="done").first()
        o = next((o for o in (r.outputs or []) if o.get("name") == name and o.get("type") == "vector"), None) if r else None
        path = r.workdir / o["file"] if o else None
    elif kind == "tool":
        t = ToolRun.objects.filter(project=p, pk=pk, status="done").first()
        o = next((o for o in (t.outputs or []) if o.get("name") == name and o.get("kind") == "vector"), None) if t else None
        path = t.workdir / o["geojson"] if o else None
    else:
        path = None
    if path is None or not path.exists():
        raise LookupError("That layer isn't in this project any more.")
    return json.loads(path.read_text())


def project_layers_list(p):
    out = []
    area = getattr(p, "area", None)
    if area is not None:
        out.append({"id": "area", "group": "Project", "title": "Area of influence", "source": p.code,
                    "kind": "vector", "format": "geojson", "url": f"/api/projects/{p.code}/layers/area/",
                    "geometry": "polygon", "area_km2": area.area_km2})

    from apps.analysis.models import ModuleRun
    runs = (ModuleRun.objects.filter(project=p, status="done").select_related("module")
            .order_by("-created")[:MAX_RUNS])
    for r in runs:
        source = f"#{r.pk} {r.module.title}"
        for o in r.outputs or []:
            base = {"group": "Analyses", "source": source, "run": r.pk, "module": r.module_id,
                    "created": r.created.isoformat(),
                    "title": o.get("title") or o.get("name")}
            if o.get("type") == "vector" and o.get("file"):
                out.append({**base, "id": f"run-{r.pk}-{o['name']}", "kind": "vector", "format": "geojson",
                            "url": f"/api/analysis/runs/{r.pk}/files/{o['file']}", "style": o.get("style") or {},
                            "geometry": _peek_geometry(r.workdir / o["file"]),
                            "size_bytes": _size(r.workdir / o["file"])})
            elif o.get("type") == "raster" and o.get("data_file"):
                out.append({**base, "id": f"run-{r.pk}-{o['name']}", "kind": "raster", "format": "geotiff",
                            "url": f"/api/projects/{p.code}/layers/run-{r.pk}-{o['name']}/raster/",
                            "unit": o.get("unit", ""),
                            "legend": o.get("legend") or [], "resolution_m": o.get("resolution_m"),
                            "size_bytes": _size(r.workdir / o["data_file"])})

    from apps.toolbox.models import ToolRun
    for t in ToolRun.objects.filter(project=p, status="done").order_by("-created")[:MAX_RUNS]:
        source = f"#{t.pk} {t.name or t.tool_title}"
        for o in t.outputs or []:
            base = {"group": "Toolbox", "source": source, "tool_run": t.pk, "tool": t.tool,
                    "created": t.created.isoformat(), "title": o.get("title") or o.get("name")}
            if o.get("kind") == "vector" and o.get("geojson"):
                out.append({**base, "id": f"tool-{t.pk}-{o['name']}", "kind": "vector", "format": "geojson",
                            "url": f"/api/toolbox/runs/{t.pk}/files/{o['geojson']}", "style": o.get("style") or {},
                            "geometry": o.get("geometry"), "features": o.get("features"),
                            "size_bytes": _size(t.workdir / o["geojson"])})
            elif o.get("kind") == "raster" and o.get("file"):
                out.append({**base, "id": f"tool-{t.pk}-{o['name']}", "kind": "raster", "format": "geotiff",
                            "url": f"/api/projects/{p.code}/layers/tool-{t.pk}-{o['name']}/raster/",
                            "legend": o.get("legend") or [],
                            "resolution_m": o.get("resolution_m"), "size_bytes": _size(t.workdir / o["file"])})
    return out


@require_GET
def project_layers(request, code):
    p, err = _project(request, code)
    if err:
        return err
    return JsonResponse({"project": {"code": p.code, "title": p.title, "country": p.country_name},
                         "layers": project_layers_list(p)})


@require_GET
def project_area_geojson(request, code):
    p, err = _project(request, code)
    if err:
        return err
    area = getattr(p, "area", None)
    if area is None:
        return error("The project has no area of influence.", status=404)
    fc = {"type": "FeatureCollection", "features": [{
        "type": "Feature", "geometry": json.loads(area.geom.geojson),
        "properties": {"project": p.code, "title": p.title, "area_km2": area.area_km2, "method": area.method}}]}
    return HttpResponse(json.dumps(fc), content_type="application/geo+json")


# Raster display ---------------------------------------------------------------------------------------------
DISPLAY_SUFFIX = ".display.tif"


def _raster_output(p, layer_id):
    """(path of the values GeoTIFF, legend spec or None) for a layer id from project_layers_list, or None."""
    from apps.analysis.models import ModuleRun
    from apps.toolbox.models import ToolRun
    kind, _, rest = layer_id.partition("-")
    run_id, _, name = rest.partition("-")
    if not run_id.isdigit() or not name:
        return None
    if kind == "run":
        r = ModuleRun.objects.filter(pk=int(run_id), project=p, status="done").first()
        o = next((o for o in (r.outputs if r else []) if o.get("type") == "raster" and o.get("name") == name), None)
        return (r.workdir / o["data_file"], o.get("legend_spec")) if o and o.get("data_file") else None
    if kind == "tool":
        t = ToolRun.objects.filter(pk=int(run_id), project=p, status="done").first()
        o = next((o for o in (t.outputs if t else []) if o.get("kind") == "raster" and o.get("name") == name), None)
        return (t.workdir / o["file"], o.get("legend_spec")) if o and o.get("file") else None
    return None


def _guess_spec(data):
    """A legend for a raster saved without one (Toolbox runs made before legends were kept)."""
    from apps.analysis.render import legend as L
    from apps.toolbox.runner import CLASS_COLORS
    import numpy as np
    vals = data[np.isfinite(data)]
    uniq = np.unique(vals) if vals.size else np.array([])
    if 0 < uniq.size <= len(CLASS_COLORS) and np.all(np.mod(uniq, 1) == 0):
        return {"type": "classes", "items": [{"value": float(v), "color": CLASS_COLORS[i], "label": f"{v:g}"}
                                             for i, v in enumerate(uniq)]}
    return L.ramp(data)


def _palette_ok(spec):
    vals = [i.get("value") for i in spec.get("items") or []]
    return bool(vals) and all(isinstance(v, (int, float)) and float(v).is_integer() and 0 <= v <= 254 for v in vals)


def _write_palette_tif(src, dest, spec):
    """Class values as one-byte GeoTIFF with a colour table and class names (255 = no data)."""
    import numpy as np
    from osgeo import gdal
    gdal.UseExceptions()
    ds = gdal.Open(str(src))
    band = ds.GetRasterBand(1)
    data = band.ReadAsArray().astype("float64")
    nd = band.GetNoDataValue()
    out = np.full(data.shape, 255, dtype=np.uint8)
    names = [""] * 256
    ct = gdal.ColorTable()
    for i in range(256):
        ct.SetColorEntry(i, (0, 0, 0, 0))
    for item in spec["items"]:
        v = int(item["value"])
        m = np.isfinite(data) & (data == v)
        if nd is not None:
            m &= data != nd
        out[m] = v
        h = item["color"].lstrip("#")
        ct.SetColorEntry(v, (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255))
        names[v] = str(item.get("label") or v)
    tmp = dest.with_name(dest.name + ".part")
    drv = gdal.GetDriverByName("GTiff")
    o = drv.Create(str(tmp), ds.RasterXSize, ds.RasterYSize, 1, gdal.GDT_Byte,
                   options=["COMPRESS=DEFLATE", "TILED=YES"])
    o.SetGeoTransform(ds.GetGeoTransform())
    o.SetProjection(ds.GetProjection())
    ob = o.GetRasterBand(1)
    ob.SetColorTable(ct)                    # before the pixels: TIFF can't change the photometric tag afterwards
    ob.SetColorInterpretation(gdal.GCI_PaletteIndex)
    ob.SetNoDataValue(255)
    ob.SetCategoryNames(names)
    ob.WriteArray(out)
    ob.FlushCache()
    o = ds = None
    tmp.replace(dest)


@require_GET
def project_layer_raster(request, code, layer_id):
    from django.http import FileResponse
    p, err = _project(request, code)
    if err:
        return err
    found = _raster_output(p, layer_id)
    if found is None or not found[0].exists():
        return error("Layer not found.", status=404)
    path, spec = found
    if not spec:
        from apps.analysis.ops import grid as G
        spec = _guess_spec(G.read(path).data)
    if spec.get("type") == "classes" and _palette_ok(spec):
        disp = path.with_name(path.stem + DISPLAY_SUFFIX)
        if not disp.exists() or disp.stat().st_mtime < path.stat().st_mtime:
            _write_palette_tif(path, disp, spec)
        style = {"colormap": "palette", "nodata": 255}
        path = disp
    elif spec.get("type") == "classes":            # classes that don't fit one byte: a ramp over their colours
        items = sorted(spec["items"], key=lambda i: i["value"])
        style = {"palette": [i["color"] for i in items], "min": items[0]["value"], "max": items[-1]["value"]}
    else:
        style = {"palette": spec.get("palette") or [], "min": spec.get("min"), "max": spec.get("max"),
                 "unit": spec.get("unit") or ""}
    resp = FileResponse(open(path, "rb"), content_type="image/tiff")
    resp["X-GEIDA-Style"] = json.dumps(style)
    resp["Access-Control-Expose-Headers"] = "X-GEIDA-Style"
    return resp
