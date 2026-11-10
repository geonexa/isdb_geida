"""Executes a ModuleRun: builds the context a module's run(ctx) works with, records outputs and evidence."""
import json
import re
import shutil
import time
import traceback
from pathlib import Path

from django.contrib.gis.db.models.functions import Intersection
from django.utils import timezone

from .datasets import DatasetUnavailable, get_dataset
from .envcheck import raster_env_problem
from .models import PHASE_INSTRUMENT, Evidence, ModuleRun
from .registry import input_dataset, load_run_function, needs_raster


class ModuleError(Exception):
    """Raise from a module for a clear, user-facing failure message."""


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

    # Vector inputs (apps.analysis.vector) ----------------------------------------------
    @property
    def frame(self):
        """Metric projection centred on the area (shared by all vector helpers in a run)."""
        if getattr(self, "_frame", None) is None:
            from . import vector
            self._frame = vector.Frame.around(self.area)
        return self._frame

    def features(self, input_name, bbox=None):
        """A manifest input read as a vector.Layer (geometry in self.frame metres)."""
        from . import vector
        return vector.read(self.dataset(input_name, bbox), self.frame)

    def try_features(self, input_name, bbox=None):
        """Like features(), but None (logged) when the dataset is unavailable."""
        from . import vector
        path = self.try_dataset(input_name, bbox)
        return vector.read(path, self.frame) if path else None

    def vzones(self, level=None):
        """ctx.zones() as vector.Zones (metric polygons with ids, names and areas)."""
        from . import vector
        return vector.Zones(self.zones(level), self.frame)

    def snapshot(self):
        """The OSM snapshot date(s) used so far, e.g. '2026-11-01' ('' if none)."""
        dates = sorted({d.get("reference_date") for d in self._datasets.values()
                        if d.get("id", "").startswith("osm_") and re.match(r"\d{4}-\d{2}-\d{2}", d.get("reference_date") or "")})
        return ", ".join(dates)

    # Outputs -------------------------------------------------------------------------
    def path(self, name):
        return self.workdir / name

    def add_table(self, name, title, columns, rows, note=""):
        """columns: [{key, label, unit?}]; rows: [dict]."""
        self._outputs.append({"type": "table", "name": name, "title": title, "columns": columns,
                              "rows": rows, "note": note})

    def add_image(self, name, title, png_path, bounds, legend=None):
        """A raster preview drawn on the map (PNG + [w, s, e, n])."""
        self._outputs.append({"type": "image", "name": name, "title": title, "file": Path(png_path).name,
                              "bounds": bounds, "legend": legend or []})

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
    def save(self):
        run = self.run
        names = [o["name"] for o in self._outputs]
        if dupes := sorted({n for n in names if names.count(n) > 1}):
            raise ModuleError(f"Module bug: output names must be unique (repeated: {', '.join(dupes)}).")
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
    except (ModuleError, DatasetUnavailable) as exc:
        run.status, run.error = "failed", str(exc)
    except Exception as exc:  # unexpected: keep the traceback for developers
        run.status = "failed"
        run.error = f"Unexpected error: {exc}"
        tb = traceback.format_exc()
        if ctx:
            ctx.log(tb)
        else:
            run.log = tb
    if ctx and run.status == "failed":
        run.log = "\n".join(ctx._log[-400:])
    run.finished = timezone.now()
    run.save()
    return run
