"""Executes a ModuleRun: builds the context a module's run(ctx) works with, records outputs and evidence."""
import json
import re
import shutil
import time
import traceback
from pathlib import Path

import numpy as np
from django.contrib.gis.db.models.functions import Intersection
from django.utils import timezone

from ..data import DatasetUnavailable, get_dataset
from .envcheck import raster_env_problem
from ..models import PHASE_INSTRUMENT, Evidence, ModuleRun
from .errors import AnalysisError, ModuleError  # noqa: F401 (ModuleError: older name)
from .registry import input_dataset, load_run_function, needs_raster


PREVIEW_MAX = 1600


def _preview_grid(raster):
    """(transform, shape) of a lon/lat grid covering a raster, at most PREVIEW_MAX px on the long side."""
    from rasterio.crs import CRS
    from rasterio.warp import calculate_default_transform

    rows, cols = raster.data.shape
    left, top = raster.transform.c, raster.transform.f
    right, bottom = left + cols * raster.transform.a, top + rows * raster.transform.e
    transform, width, height = calculate_default_transform(CRS.from_user_input(raster.crs), CRS.from_epsg(4326),
                                                           cols, rows, left, bottom, right, top)
    scale = max(1.0, max(width, height) / PREVIEW_MAX)
    if scale > 1:
        transform = transform * transform.scale(scale, scale)
        width, height = max(1, round(width / scale)), max(1, round(height / scale))
    return transform, (height, width)


class RunContext:
    def __init__(self, run: ModuleRun):
        self.run = run
        self.project = run.project
        self.manifest = run.module.manifest
        self.params = {**{p["name"]: p.get("default") for p in self.manifest.get("parameters", []) or []}, **run.params}
        area = self.project.area
        self.area = area.geom  # GEOS MultiPolygon, EPSG:4326
        self.area_geojson = json.loads(area.geom.geojson)
        self.area_km2 = area.area_km2
        self.iso3 = self.project.country_iso3
        self.workdir = run.workdir
        if self.workdir.exists():
            shutil.rmtree(self.workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self._outputs, self._datasets, self._evidence, self._log = [], {}, [], []
        self._grid = None
        self._scratch = None
        self.phase = run.phase

    # Logging -------------------------------------------------------------------------
    def log(self, msg):
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        self._log.append(line)
        ModuleRun.objects.filter(pk=self.run.pk).update(log="\n".join(self._log[-400:]))

    def progress(self, pct):
        ModuleRun.objects.filter(pk=self.run.pk).update(progress=max(0, min(100, int(pct))))

    # Inputs --------------------------------------------------------------------------
    def bbox(self, buffer_m=0):
        w, s, e, n = self.area.extent
        if buffer_m:
            import math
            dlat = buffer_m / 111_320
            dlon = buffer_m / (111_320 * max(0.2, math.cos(math.radians((s + n) / 2))))
            w, s, e, n = w - dlon, s - dlat, e + dlon, n + dlat
        return (w, s, e, n)

    def dataset(self, input_name, bbox=None):
        """Local file for a manifest input (fetched and cached as needed)."""
        ds_id = input_dataset(self.manifest, input_name, self.params)
        if not ds_id:
            raise ModuleError(f"Input '{input_name}' isn't declared in the manifest.")
        ds = get_dataset(ds_id)
        path = ds.fetch(bbox or self.bbox(), self.iso3, log=self.log)
        self._datasets[ds.id] = ds.describe()
        return path

    def try_dataset(self, input_name, bbox=None):
        try:
            return self.dataset(input_name, bbox)
        except DatasetUnavailable as exc:
            self.log(f"Optional input '{input_name}' skipped: {exc}")
            return None

    def zones(self, level=None):
        """Admin units overlapping the area, clipped to it: [(index, gid, name, geojson)]."""
        from apps.boundaries.models import AdminUnit

        level = level or int(self.params.get("zone_level") or 2)
        qs = (AdminUnit.objects.filter(iso3=self.iso3, level=level, geom__intersects=self.area)
              .annotate(clip=Intersection("geom", self.area)).only("gid", "name"))
        out = []
        for i, u in enumerate(qs, start=1):
            if u.clip and not u.clip.empty and u.clip.geom_type in ("Polygon", "MultiPolygon"):
                out.append((i, u.gid, u.name, json.loads(u.clip.geojson)))
        if not out:
            out = [(1, "area", "Project area", self.area_geojson)]
        return out

    # Raster inputs on the run grid (apps.analysis.ops.grid) ------------------------------
    @property
    def folder(self):
        """The analysis folder (for legend files and other resources)."""
        from .registry import analysis_folders
        return analysis_folders().get(self.run.module_id)

    @property
    def epsg(self):
        """The area's UTM zone: every raster in the run is held in it."""
        from apps.core.geo import utm_epsg
        c = self.area.centroid
        return utm_epsg(c.x, c.y)

    @property
    def grid(self):
        """The run grid (set by the first raster read, or by set_grid)."""
        return self._grid

    def set_grid(self, grid):
        self._grid = grid

    def point(self, name):
        """A point parameter as (lon, lat); AnalysisError if it is missing or not a point."""
        from .manifest import parse_point
        v = parse_point(self.params.get(name))
        if v is None:
            label = next((p.get("label", name) for p in self.manifest.get("parameters", []) or [] if p["name"] == name), name)
            raise AnalysisError(f"{label}: pick a point on the map (longitude, latitude).")
        return tuple(v)

    def area_in(self, epsg=None):
        """The area of influence as GeoJSON in the run's UTM zone (or another EPSG code)."""
        return json.loads(self.area.transform(epsg or self.epsg, clone=True).geojson)

    def area_mask(self, raster_or_grid=None):
        """True for pixels inside the area of influence (on the run grid by default)."""
        g = raster_or_grid if raster_or_grid is not None else self._grid
        g = getattr(g, "grid", g)
        if g is None:
            raise AnalysisError("Analysis bug: read a raster (or set the grid) before asking for the area mask.")
        return g.mask(self.area_in(int(str(g.crs).split(":")[-1])))

    def raster(self, input_name, year=None, buffer_m=0, bbox=None, res=None):
        """
        A manifest raster input clipped to the area (plus buffer_m), or to `bbox` (lon/lat) when given, as a
        Raster on the run grid. Catalogue layers are read for `year` (default: the layer's default period);
        the first raster read sets the run grid (at `res` metres when given, else the data's own), later ones
        are resampled onto it.
        """
        from ..data.cog import CatalogRaster, _bbox_polygon
        from ..ops import grid as G

        ds_id = input_dataset(self.manifest, input_name, self.params)
        if not ds_id:
            raise AnalysisError(f"Input '{input_name}' isn't declared in the manifest.")
        ds = get_dataset(ds_id)
        if ds.kind != "raster":
            raise AnalysisError(f"Analysis bug: input '{input_name}' ({ds.title}) isn't a raster.")
        bbox = tuple(bbox) if bbox else self.bbox(buffer_m)
        if isinstance(ds, CatalogRaster):
            path, period = ds.clip(_bbox_polygon(bbox), self.iso3, year, log=self.log)
            categorical = ds.categorical
        else:
            path, period, categorical = ds.fetch(bbox, self.iso3, log=self.log), None, False
        r = G.read(path)
        r.info.update({"dataset": ds.id, "year": period, "title": ds.title})
        if self._grid is None:
            if r.crs != f"EPSG:{self.epsg}" or (res and abs(abs(r.transform.a) - res) > 1):
                r = G.reproject(r, G.utm_grid(r, self.epsg, res), "nearest" if categorical else ("average" if res else "bilinear"))
            self._grid = r.grid
        elif isinstance(ds, CatalogRaster) and ds.layer.get("resampling") == "sum" and r.crs.startswith("EPSG:32"):
            # Counts (people per pixel): totals are kept on a coarser grid (sum) and on a finer one (each source
            # pixel's count shared between the cells it covers).
            src_m2 = abs(r.transform.a * r.transform.e)
            if src_m2 < self._grid.pixel_area_m2:
                r = G.reproject(r, self._grid, "sum")
            else:
                r = G.reproject(r, self._grid, "nearest")
                r.data *= self._grid.pixel_area_m2 / src_m2
        else:
            coarser = r.transform.a > self._grid.res * 1.5 if r.crs == self._grid.crs else False
            r = G.reproject(r, self._grid, "nearest" if categorical else ("bilinear" if coarser else "average"))
        self._datasets[f"{ds.id}:{period}" if period else ds.id] = {**ds.describe(), "reference_date": str(period) if period else (ds.reference_date or "")}
        if not r.valid.any():
            raise AnalysisError(f"{ds.title} has no data over the area of influence.")
        return r

    def record_dataset(self, key, info):
        """Record a dataset read outside ctx.raster / ctx.dataset (e.g. a Sentinel-2 composite) with the run."""
        self._datasets[key] = info

    def zone_masks(self, raster_or_grid=None, level=None):
        """Admin units clipped to the area as pixel masks on the run grid: [(index, gid, name, mask)]."""
        from django.contrib.gis.geos import GEOSGeometry

        g = raster_or_grid if raster_or_grid is not None else self._grid
        g = getattr(g, "grid", g)
        epsg = int(str(g.crs).split(":")[-1])
        out = []
        for i, gid, name, gj in self.zones(level):
            geom = GEOSGeometry(json.dumps(gj), srid=4326).transform(epsg, clone=True)
            out.append((i, gid, name, g.mask(json.loads(geom.geojson))))
        return out

    def cached(self, name, parts, compute):
        """
        A derived raster from the cache, or compute() it and store it. `parts` lists what the
        result depends on (input rasters' info, parameters, a version string); the area and the
        run grid are added automatically.
        """
        from ..data import cache
        from ..ops import grid as G

        key_parts = {"parts": parts, "area": self.area.wkt, "grid": [str(self._grid.crs), tuple(self._grid.transform),
                                                                        self._grid.shape] if self._grid else None}
        path = cache.path_for(name, key_parts)
        if path.exists():
            self.log(f"{name}: reused from the cache")
            return G.read(path)
        r = compute()
        G.write(r, path)
        cache.trim()
        return r

    # Vector inputs (apps.analysis.vector) ----------------------------------------------
    @property
    def frame(self):
        """Metric projection centred on the area (shared by all vector helpers in a run)."""
        if getattr(self, "_frame", None) is None:
            from ..ops import vector
            self._frame = vector.Frame.around(self.area)
        return self._frame

    def features(self, input_name, bbox=None):
        """A manifest input read as a vector.Layer (geometry in self.frame metres)."""
        from ..ops import vector
        return vector.read(self.dataset(input_name, bbox), self.frame)

    def try_features(self, input_name, bbox=None):
        """Like features(), but None (logged) when the dataset is unavailable."""
        from ..ops import vector
        path = self.try_dataset(input_name, bbox)
        return vector.read(path, self.frame) if path else None

    def vzones(self, level=None):
        """ctx.zones() as vector.Zones (metric polygons with ids, names and areas)."""
        from ..ops import vector
        return vector.Zones(self.zones(level), self.frame)

    def snapshot(self):
        """The OSM snapshot date(s) used so far, e.g. '2026-11-01' ('' if none)."""
        dates = sorted({d.get("reference_date") for d in self._datasets.values()
                        if d.get("id", "").startswith("osm_") and re.match(r"\d{4}-\d{2}-\d{2}", d.get("reference_date") or "")})
        return ", ".join(dates)

    # Outputs -------------------------------------------------------------------------
    def path(self, name):
        return self.workdir / name

    def scratch(self, name="work"):
        """A folder for intermediate files (e.g. WhiteboxTools rasters), deleted when the run ends: only outputs
        stay in the run folder."""
        import tempfile
        if self._scratch is None:
            self._scratch = Path(tempfile.mkdtemp(prefix=f"geida-run{self.run.pk}-"))
        folder = self._scratch / name
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def cleanup(self):
        if self._scratch is not None:
            shutil.rmtree(self._scratch, ignore_errors=True)
            self._scratch = None

    def add_table(self, name, title, columns, rows, note=""):
        """columns: [{key, label, unit?}]; rows: [dict]."""
        self._outputs.append({"type": "table", "name": name, "title": title, "columns": columns,
                              "rows": rows, "note": note})

    def add_image(self, name, title, png_path, bounds, legend=None):
        """A raster preview drawn on the map (PNG + [w, s, e, n])."""
        self._outputs.append({"type": "image", "name": name, "title": title, "file": Path(png_path).name,
                              "bounds": bounds, "legend": legend or []})

    def add_raster(self, name, title, raster, legend=None, unit="", mask_to_area=True):
        """
        A raster result: values as a cloud-optimised GeoTIFF (download), a coloured PNG
        preview on the map, its legend and statistics inside the area.
        legend: a dict, a legend file in the analysis folder (e.g. "legend.yaml"), or None for
        a ramp stretched over the data.
        """
        from ..ops import grid as G
        from ..render import legend as L
        from ..render.preview import write_png

        spec = L.load(legend, self.folder) if legend is not None else L.ramp(raster.data, unit=unit)
        if unit and not spec.get("unit"):
            spec = {**spec, "unit": unit}
        inside = self.area_mask(raster) if mask_to_area else None
        values = raster.like(np.where(inside, raster.data, np.nan)) if inside is not None else raster
        tif = self.path(f"{name}.tif")
        G.write(values, tif, cog=True)

        # Preview in lon/lat for the map: at most PREVIEW_MAX px on the long side.
        geo = G.reproject(values, G.Grid("EPSG:4326", *_preview_grid(values)),
                          "nearest" if spec["type"] == "classes" else "bilinear")
        png = self.path(f"{name}.png")
        bounds = write_png(png, L.colorize(geo.data, spec), geo.transform)
        stats = values.stats()
        self._outputs.append({
            "type": "raster", "name": name, "title": title, "file": png.name, "data_file": tif.name,
            "bounds": bounds, "legend": L.items(spec), "legend_spec": spec, "unit": spec.get("unit", unit),
            "stats": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in stats.items()},
            "resolution_m": round(raster.grid.res, 2), "crs": raster.crs,
        })

    def add_vector(self, name, title, geojson_path, style=None):
        self._outputs.append({"type": "vector", "name": name, "title": title,
                              "file": Path(geojson_path).name, "style": style or {}})

    def add_file(self, name, title, path):
        self._outputs.append({"type": "file", "name": name, "title": title, "file": Path(path).name})

    def add_metric(self, name, label, value, unit="", note=""):
        self._outputs.append({"type": "metric", "name": name, "title": label, "value": value, "unit": unit, "note": note})

    def summary(self, text):
        self.run.summary = text

    def propose_evidence(self, cri, label, value, unit, role, caveats="", reference_date="", male=None, female=None):
        self._evidence.append(dict(cri=cri, label=label, value=value, unit=unit, role=role, caveats=caveats,
                                   reference_date=reference_date, male=male, female=female))

    # Finish -------------------------------------------------------------------------
    def check_outputs(self, names):
        """Every output the manifest declares (not optional) must be produced; extra outputs are only logged."""
        declared = self.manifest.get("outputs", []) or []

        def matches(o, n):
            return n.startswith(o["name"][:-1]) if o["name"].endswith("*") else n == o["name"]

        missing = [o["name"] for o in declared if not o.get("optional") and not any(matches(o, n) for n in names)]
        if missing:
            raise AnalysisError(f"Analysis bug: it didn't produce the outputs its manifest declares ({', '.join(missing)}).")
        if extra := [n for n in names if not any(matches(o, n) for o in declared)]:
            self.log(f"Note: outputs not declared in the manifest: {', '.join(extra)}")

    def save(self):
        run = self.run
        names = [o["name"] for o in self._outputs]
        if dupes := sorted({n for n in names if names.count(n) > 1}):
            raise AnalysisError(f"Analysis bug: output names must be unique (repeated: {', '.join(dupes)}).")
        self.check_outputs(names)
        run.outputs = self._outputs
        run.datasets = list(self._datasets.values())
        run.log = "\n".join(self._log[-400:])
        indicators = {i.cri_id: i for i in self.project.indicators.filter(cri__isnull=False)}
        for e in self._evidence:
            Evidence.objects.create(
                project=self.project, run=run, indicator=indicators.get(e["cri"]), cri_code=e["cri"] or "",
                phase=run.phase, instrument=PHASE_INSTRUMENT[run.phase], label=e["label"], value=e["value"],
                unit=e["unit"], value_male=e["male"], value_female=e["female"],
                reference_date=e["reference_date"], role=e["role"],
                method={"module": run.module_id, "version": run.module_version, "params": self.params},
                data=run.datasets, caveats=e["caveats"])


def execute(run: ModuleRun):
    run.status, run.started, run.progress, run.error = "running", timezone.now(), 1, ""
    run.save(update_fields=["status", "started", "progress", "error"])
    ctx = None
    try:
        if getattr(run.project, "area", None) is None:
            raise ModuleError("The project has no area of influence.")
        if needs_raster(run.module.manifest) and (problem := raster_env_problem()):
            raise ModuleError(f"The analysis worker isn't set up correctly. {problem}")
        ctx = RunContext(run)
        ctx.log(f"{run.module.title} {run.module_version} · {run.project.code} · {run.get_phase_display()}")
        fn = load_run_function(run.module_id)
        fn(ctx)
        ctx.save()
        run.status, run.progress = "done", 100
        ctx.log("Finished.")
    except (AnalysisError, DatasetUnavailable) as exc:
        run.status, run.error = "failed", str(exc)
    except Exception as exc:  # unexpected: keep the traceback for developers
        run.status = "failed"
        run.error = f"Unexpected error: {exc}"
        tb = traceback.format_exc()
        if ctx:
            ctx.log(tb)
        else:
            run.log = tb
    if ctx:
        ctx.cleanup()
    if ctx and run.status == "failed":
        run.log = "\n".join(ctx._log[-400:])
    run.finished = timezone.now()
    run.save()
    return run
