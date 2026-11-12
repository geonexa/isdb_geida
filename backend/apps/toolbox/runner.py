"""
Running a Toolbox tool: prepare its inputs, run it (GeoLibre engine or a GEIDA tool), and keep its outputs:
vectors as GeoPackage (download) + GeoJSON in lon/lat (map), rasters as GeoTIFF (download) + PNG preview with a
legend (map), tables as CSV (download and a preview), the tool's report (statistics) as JSON.
"""
import csv
import json
import logging
import re
import shutil
import tempfile
import time
import traceback
from pathlib import Path

import numpy as np
from django.utils import timezone

from . import engine
from .catalog import CATEGORIES, GEIDA_TOOLS, NUMBER_PARAMS, PARAM_OVERRIDES
from .inputs import InputError, align_rasters, geometry_option, prepare
from .models import ToolRun

log = logging.getLogger(__name__)

LAYER_KINDS = ("vector", "raster", "table")
PALETTE = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf", "#8c564b", "#e377c2"]
CLASS_COLORS = ["#1b9e77", "#d95f02", "#7570b3", "#e7298a", "#66a61e", "#e6ab02", "#a6761d", "#666666",
                "#1f78b4", "#b2df8a", "#fb9a99", "#cab2d6"]
TABLE_PREVIEW_ROWS = 500
FID_NAMES = {"fid", "gpkg_fid", "geida_fid", "ogc_fid", "objectid", "join_geida_fid", "join_fid"}


class ToolError(Exception):
    pass


# The catalogue: curated tools with forms built from the engine's manifests -------------------------------
def _label(name):
    return name.replace("_", " ").strip().capitalize()


def _is_multi(p):
    return bool(re.search(r"\barray\b|\blist\b|comma", (p.get("description") or "").lower()))


def form_params(m):
    """A tool's parameters for the run form: layers to pick, values to type; outputs are named by the server."""
    defaults = m.get("defaults") or {}
    out = []
    for p in m.get("params", []):
        kind, role, schema = p.get("data_kind"), p.get("io_role"), p.get("schema") or {}
        if role == "output":
            continue
        base = {"name": p["name"], "label": _label(p["name"]), "description": p.get("description") or "",
                "required": bool(p.get("required"))}
        if role == "input" and kind in LAYER_KINDS:
            out.append({**base, "kind": "layer", "layer_kind": kind, "multiple": _is_multi(p)})
            continue
        d = defaults.get(p["name"])
        if isinstance(d, list):
            # the engine takes lists as "a,b,c" and tables as "a,b,c;d,e,f"
            num = lambda v: f"{v:g}" if isinstance(v, float) else str(v)   # noqa: E731
            d = ";".join(",".join(map(num, row)) for row in d) if d and all(isinstance(r, list) for r in d) else ",".join(map(num, d))
        elif isinstance(d, dict):
            d = json.dumps(d)
        if isinstance(d, str) and ("field" in p["name"] or re.search(r"\.(shp|tif|tiff|csv|geojson|gpkg|json|txt|html)$", d, re.I)):
            d = None   # placeholder field names and file names from the engine's examples
        if role == "input" and kind not in LAYER_KINDS:
            role = None
        if schema.get("kind") == "enum":
            out.append({**base, "kind": "choice", "choices": [o.get("value") for o in schema.get("options") or []],
                        "default": d})
        elif kind == "bool" or schema.get("kind") == "bool":
            out.append({**base, "kind": "bool", "default": bool(d) if d is not None else False})
        elif kind == "number":
            out.append({**base, "kind": "number", "integer": schema.get("scalar") == "integer", "default": d})
        else:
            out.append({**base, "kind": "text", "default": d if isinstance(d, (str, int, float)) else None})
    return out


def tool_manifest(tool_id):
    """The tool's manifest, with GEIDA's corrections applied (catalog.PARAM_OVERRIDES)."""
    if tool_id in GEIDA_TOOLS:
        return {"id": tool_id, **GEIDA_TOOLS[tool_id]}
    m = engine.manifests().get(tool_id)
    if m is None:
        return None
    params = []
    for p in m.get("params", []):
        fix = PARAM_OVERRIDES.get((tool_id, p["name"]))
        if fix is None and p["name"] in NUMBER_PARAMS and p.get("data_kind") in LAYER_KINDS:
            fix = {"data_kind": "number", "io_role": None, "schema": {"kind": "scalar", "scalar": "float"}}
        params.append({**p, **fix} if fix else p)
    return {**m, "params": params}


def catalog():
    """{categories: [{id, title, icon, tools: [{id, title, summary, params}]}], count, engine}."""
    cats, n = [], 0
    for cid, title, icon, ids in CATEGORIES:
        tools = []
        for tid in ids:
            m = tool_manifest(tid)
            if m is None:
                log.warning("Toolbox: %s isn't in the engine; left out", tid)
                continue
            tools.append({"id": tid, "title": m.get("display_name") or _label(tid), "summary": m.get("summary") or "",
                          "params": form_params(m), "engine": "geida" if tid in GEIDA_TOOLS else "geolibre"})
        n += len(tools)
        cats.append({"id": cid, "title": title, "icon": icon, "tools": tools})
    return {"categories": cats, "count": n, "engine": engine.NAME}


def curated_ids():
    return {t for _, _, _, ids in CATEGORIES for t in ids}


# Running ----------------------------------------------------------------------------------------------
def _output_ext(p, tool_kinds):
    kind = p.get("data_kind")
    if kind == "vector":
        return ".geojson"   # the engine writes GeoJSON in lon/lat; its FlatGeobuf writer can emit unreadable features
    if kind == "raster":
        return ".tif"
    if kind == "table":
        return ".csv"
    if kind == "json":
        return ".json"
    if kind == "text":
        return ".html"
    # "file": the engine doesn't say; raster tools write rasters
    return ".tif" if "raster" in tool_kinds else ".geojson"


def _wanted_output(p):
    return p.get("io_role") == "output" and (p.get("required") or p["name"] == "output")


def _friendly(lines):
    msgs = [ln.strip() for ln in lines if ln.strip() and not ln.startswith("running") and not ln.lstrip().startswith("{")]
    text = " ".join(msgs[-4:]) or "The tool stopped without a message."
    return re.sub(r"^validation error:\s*", "", text)


def execute(run: ToolRun):
    run.status, run.started, run.error = "running", timezone.now(), ""
    run.save(update_fields=["status", "started", "error"])
    lines_log = []

    def say(msg):
        lines_log.append(f"{time.strftime('%H:%M:%S')} {msg}")
        ToolRun.objects.filter(pk=run.pk).update(log="\n".join(lines_log[-300:]))

    work = Path(tempfile.mkdtemp(prefix=f"geida-tool{run.pk}-"))
    try:
        project = run.project
        if getattr(project, "area", None) is None:
            raise ToolError("The project has no area of influence.")
        m = tool_manifest(run.tool)
        if m is None:
            raise ToolError("This tool isn't available any more.")
        if run.workdir.exists():
            shutil.rmtree(run.workdir)
        run.workdir.mkdir(parents=True)
        say(f"{run.tool_title} · {run.engine} · {project.code}")
        kinds = {p.get("data_kind") for p in m.get("params", []) if p.get("io_role") == "input"}
        from .inputs import project_epsg
        epsg = project_epsg(project)

        # Inputs ------------------------------------------------------------------
        files = {}
        for p in m.get("params", []):
            if p.get("io_role") != "input" or p.get("data_kind") not in LAYER_KINDS:
                continue
            refs = run.inputs.get(p["name"])
            refs = [r for r in (refs if isinstance(refs, list) else [refs]) if r]
            if not refs:
                if p.get("required"):
                    raise ToolError(f"Choose a layer for {_label(p['name']).lower()}.")
                continue
            names = []
            for i, ref in enumerate(refs):
                say(f"Preparing {_label(p['name']).lower()}{f' {i + 1}' if len(refs) > 1 else ''}")
                names.append(prepare(ref, project, work, f"{p['name']}_{i}", log=say))
            files[p["name"]] = names
        rasters = [work / f for names in files.values() for f in names if f.endswith(".tif")]
        if len(rasters) > 1:
            say("Aligning the rasters to the first one's grid")
            align_rasters(rasters)

        # Run ---------------------------------------------------------------------
        outputs, report = [], None
        if run.tool in GEIDA_TOOLS:
            say("Running")
            produced = GEIDA_RUNNERS[run.tool](work, files, run.params)
            if not produced:
                raise ToolError("The tool produced no result.")
        else:
            argv, produced = [run.tool], []
            for p in m.get("params", []):
                name = p["name"]
                if name in files:
                    argv.append(f"--{name}=" + ",".join(f"/work/{f}" for f in files[name]))
                elif _wanted_output(p):
                    if name.endswith("_dir"):
                        (work / f"out_{name}").mkdir()
                        argv.append(f"--{name}=/work/out_{name}")
                        produced.append((name, f"out_{name}", "dir"))
                    else:
                        f = f"out_{name}{_output_ext(p, kinds)}"
                        argv.append(f"--{name}=/work/{f}")
                        produced.append((name, f, p.get("data_kind")))
                elif p.get("io_role") is None or p.get("io_role") not in ("input", "output"):
                    v = run.params.get(name)
                    if v is None or v == "":
                        continue
                    argv.append(f"--{name}=" + (("true" if v else "false") if isinstance(v, bool) else str(v)))
            say("Running " + " ".join(a if len(a) < 120 else a[:117] + "…" for a in argv))
            code, lines = engine.run(argv, work)
            for ln in lines[-20:]:
                if not ln.lstrip().startswith("{"):
                    say(ln)
            if code != 0:
                raise ToolError(_friendly(lines))
            res = engine.last_json(lines)
            rep = res.get("report")
            if isinstance(rep, str):
                try:
                    rep = json.loads(rep)
                except ValueError:
                    rep = {"text": rep}
            report = rep

        # Outputs -----------------------------------------------------------------
        for i, (name, fname, kind) in enumerate(produced):
            src = work / fname
            if kind == "dir":
                for j, f in enumerate(sorted(src.glob("*"))):
                    if f.suffix.lower() in (".fgb", ".gpkg", ".geojson", ".shp"):
                        outputs.append(_keep_vector(run, f, f"{name}_{j}", f.stem, len(outputs), epsg))
                continue
            if not src.exists():
                continue
            title = _label(name) if name != "output" else run.tool_title
            if src.suffix in (".geojson", ".fgb", ".gpkg"):
                outputs.append(_keep_vector(run, src, name, title, len(outputs), epsg))
            elif src.suffix == ".tif":
                outputs.append(_keep_raster(run, src, name, title))
            elif src.suffix == ".csv":
                outputs.append(_keep_table(run, src, name, title))
            else:
                dest = run.workdir / f"{name}{src.suffix}"
                shutil.move(src, dest)
                outputs.append({"name": name, "title": title, "kind": "file", "file": dest.name})
        if not outputs and report is None:
            raise ToolError("The tool finished but produced no result.")
        run.outputs, run.report = outputs, report
        run.size_bytes = sum(f.stat().st_size for f in run.workdir.rglob("*") if f.is_file())
        run.status = "done"
        say("Finished.")
    except (ToolError, InputError, engine.EngineError) as exc:
        run.status, run.error = "failed", str(exc)
    except Exception as exc:  # unexpected: keep the traceback for developers
        run.status, run.error = "failed", f"Unexpected error: {exc}"
        lines_log.append(traceback.format_exc())
    finally:
        shutil.rmtree(work, ignore_errors=True)
    run.log = "\n".join(lines_log[-300:])
    run.finished = timezone.now()
    run.save()
    return run


# Keeping outputs ----------------------------------------------------------------------------------------------
def _keep_vector(run, src, name, title, index, epsg):
    from osgeo import gdal, ogr
    gdal.UseExceptions()
    gpkg = run.workdir / f"{name}.gpkg"          # GeoPackage written by GDAL, for download and chaining
    # The engine copies its input's ID column into the output as an attribute: drop ID-like fields, so they don't
    # clash with the GeoPackage's own ID column. Geometry types are kept (see inputs.geometry_option).
    src_ds = ogr.Open(str(src))
    sdefn = src_ds.GetLayer(0).GetLayerDefn()
    keep = [sdefn.GetFieldDefn(i).GetName() for i in range(sdefn.GetFieldCount())
            if sdefn.GetFieldDefn(i).GetName().lower() not in FID_NAMES]
    src_ds = None
    opts = dict(format="GPKG", layerName=name, selectFields=keep, layerCreationOptions=["FID=geida_fid"],
                dstSRS=f"EPSG:{epsg}", skipFailures=True)
    if gtype := geometry_option(src):
        opts["geometryType"] = gtype
    gdal.VectorTranslate(str(gpkg), str(src), **opts)
    geojson = run.workdir / f"{name}.geojson"
    gdal.VectorTranslate(str(geojson), str(gpkg), format="GeoJSON", dstSRS="EPSG:4326", skipFailures=True,
                         layerCreationOptions=["COORDINATE_PRECISION=6", "RFC7946=YES"])
    ds = ogr.Open(str(gpkg))
    lyr = ds.GetLayer(0)
    defn = lyr.GetLayerDefn()
    fields = [defn.GetFieldDefn(i).GetName() for i in range(defn.GetFieldCount())]
    count = lyr.GetFeatureCount()
    gtype = ogr.GeometryTypeToName(lyr.GetGeomType()).lower()
    if "unknown" in gtype or gtype == "geometry":           # mixed or unspecified: look at the features
        names = set()
        for i, f in enumerate(lyr):
            g = f.GetGeometryRef()
            if g is not None:
                names.add(g.GetGeometryName().lower())
            if i > 200:
                break
        gtype = " ".join(sorted(names))
    ds = None
    shape = "polygon" if "polygon" in gtype else "line" if "line" in gtype else "point"
    color = PALETTE[index % len(PALETTE)]
    return {"name": name, "title": title, "kind": "vector", "file": gpkg.name, "geojson": geojson.name,
            "features": count, "geometry": shape, "fields": fields,
            "style": {"color": color, "outline": color, "shape": shape, "opacity": 0.35 if shape == "polygon" else 0.9,
                      "width": 2, "radius": 5}}


def _keep_raster(run, src, name, title):
    from apps.analysis.core.runner import _preview_grid
    from apps.analysis.ops import grid as G
    from apps.analysis.render import legend as L
    from apps.analysis.render.preview import write_png

    tif = run.workdir / f"{name}.tif"
    shutil.move(src, tif)
    r = G.read(tif)
    vals = r.data[np.isfinite(r.data)]
    uniq = np.unique(vals) if vals.size and vals.size < 50_000_000 else np.array([])
    if 0 < uniq.size <= len(CLASS_COLORS) and np.all(np.mod(uniq, 1) == 0):
        spec = {"type": "classes", "items": [{"value": float(v), "color": CLASS_COLORS[i], "label": f"{v:g}"}
                                             for i, v in enumerate(uniq)]}
    else:
        spec = L.ramp(r.data)
    geo = G.reproject(r, G.Grid("EPSG:4326", *_preview_grid(r)), "nearest" if spec["type"] == "classes" else "bilinear")
    png = run.workdir / f"{name}.png"
    bounds = write_png(png, L.colorize(geo.data, spec), geo.transform)
    stats = r.stats()
    return {"name": name, "title": title, "kind": "raster", "file": tif.name, "preview": png.name, "bounds": bounds,
            "legend": L.items(spec), "stats": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in stats.items()},
            "resolution_m": round(r.grid.res, 2)}


def _keep_table(run, src, name, title):
    dest = run.workdir / f"{name}.csv"
    shutil.move(src, dest)
    with open(dest, newline="", encoding="utf-8", errors="replace") as f:
        rows = list(csv.reader(f))
    head, body = (rows[0], rows[1:]) if rows else ([], [])
    return {"name": name, "title": title, "kind": "table", "file": dest.name, "columns": head,
            "rows": body[:TABLE_PREVIEW_ROWS], "row_count": len(body)}


# GEIDA's own tools ---------------------------------------------------------------------------------------
def _zonal_statistics(work, files, params):
    """Statistics of a raster inside each polygon, added to the polygons (and a CSV)."""
    import rasterio
    from osgeo import gdal, ogr
    from rasterio.features import geometry_mask
    from shapely import wkb as swkb

    gdal.UseExceptions()
    raster, zones = work / files["input"][0], work / files["zones"][0]
    src = gdal.OpenEx(str(zones))
    out_path = work / "out_output.gpkg"
    gdal.VectorTranslate(str(out_path), src, format="GPKG", layerName="zones", geometryType="GEOMETRY")
    src = None
    ds = ogr.Open(str(out_path), 1)
    lyr = ds.GetLayer(0)
    stats_names = ["count", "mean", "min", "max", "median", "sum", "std"]
    for s in stats_names:
        lyr.CreateField(ogr.FieldDefn(f"z_{s}", ogr.OFTReal))
    rows = []
    with rasterio.open(raster) as r:
        nodata = r.nodata
        for feat in lyr:
            g = feat.GetGeometryRef()
            if g is None:
                continue
            geom = swkb.loads(bytes(g.ExportToWkb()))
            try:
                from rasterio.features import geometry_window
                win = geometry_window(r, [geom])          # the polygon's window, cut to the raster
                data = r.read(1, window=win, masked=False).astype("float64")
            except (rasterio.errors.WindowError, ValueError):
                data = np.empty((0, 0))
            if data.size == 0:
                vals = np.array([])
            else:
                inside = ~geometry_mask([geom], out_shape=data.shape, transform=r.window_transform(win), all_touched=False)
                ok = inside & np.isfinite(data) & ((data != nodata) if nodata is not None else True)
                vals = data[ok]
            st = ({"count": int(vals.size), "mean": float(vals.mean()), "min": float(vals.min()), "max": float(vals.max()),
                   "median": float(np.median(vals)), "sum": float(vals.sum()), "std": float(vals.std())}
                  if vals.size else {"count": 0})
            for s in stats_names:
                if s in st:
                    feat.SetField(f"z_{s}", st[s])
            lyr.SetFeature(feat)
            rows.append({"fid": feat.GetFID(), **{s: (round(st[s], 4) if isinstance(st.get(s), float) else st.get(s, ""))
                                                  for s in stats_names}})
    ds = None
    with open(work / "out_table.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["fid", *stats_names])
        w.writeheader()
        w.writerows(rows)
    return [("output", "out_output.gpkg", "vector"), ("table", "out_table.csv", "table")]


def _dissolve(work, files, params):
    """Merge features into one (or one per value of a field)."""
    import shapely
    from osgeo import gdal, ogr, osr
    gdal.UseExceptions()
    ds = ogr.Open(str(work / files["input"][0]))
    lyr = ds.GetLayer(0)
    field = str(params.get("field") or "").strip()
    defn = lyr.GetLayerDefn()
    names = [defn.GetFieldDefn(i).GetName() for i in range(defn.GetFieldCount())]
    if field and field not in names:
        raise ToolError(f"The layer has no field '{field}'. Fields: {', '.join(names[:20])}.")
    groups = {}
    for f in lyr:
        g = f.GetGeometryRef()
        if g is None:
            continue
        key = f.GetField(field) if field else "all"
        groups.setdefault(key, []).append(shapely.from_wkb(bytes(g.ExportToWkb())))
    srs = lyr.GetSpatialRef().Clone() if lyr.GetSpatialRef() else None
    ds = None
    if not groups:
        raise ToolError("The layer has no features to dissolve.")
    out = work / "out_output.gpkg"
    ods = ogr.GetDriverByName("GPKG").CreateDataSource(str(out))
    olyr = ods.CreateLayer("dissolved", srs or osr.SpatialReference(), ogr.wkbUnknown)
    olyr.CreateField(ogr.FieldDefn(field or "group", ogr.OFTString))
    olyr.CreateField(ogr.FieldDefn("count", ogr.OFTInteger))
    for key, geoms in groups.items():
        merged = shapely.union_all(shapely.make_valid(np.array(geoms, dtype=object)))
        f = ogr.Feature(olyr.GetLayerDefn())
        f.SetField(field or "group", str(key))
        f.SetField("count", len(geoms))
        f.SetGeometry(ogr.CreateGeometryFromWkb(shapely.to_wkb(merged)))
        olyr.CreateFeature(f)
    ods = None
    return [("output", "out_output.gpkg", "vector")]


GEIDA_RUNNERS = {"geida_zonal_statistics": _zonal_statistics, "geida_dissolve": _dissolve}
