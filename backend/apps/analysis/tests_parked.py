"""Parked raster modules (modules/_parked/): still runnable from tests so they don't rot.

Skipped when rasterio isn't installed. They come back to the catalogue in Cycle 2 (C2.4).
"""
import json
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.management import call_command
from django.test import TestCase, override_settings

try:
    import rasterio
    from rasterio.transform import from_origin
except ImportError:  # pragma: no cover
    rasterio = None

from apps.analysis import raster
from apps.analysis.models import Evidence, ModuleRun
from apps.projects.models import Indicator, Project, ProjectArea

TMP = Path(tempfile.mkdtemp(prefix="geida-test-"))
W, S, E, N = 34.0, 2.0, 34.5, 2.5  # 0.5° box
RES = 0.001


def _tif(path, arr, nodata=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
                       dtype=arr.dtype, crs="EPSG:4326", transform=from_origin(W - 0.1, N + 0.1, RES, RES),
                       nodata=nodata) as d:
        d.write(arr, 1)


def make_data():
    h = w = int(0.7 / RES)
    yy, xx = np.mgrid[0:h, 0:w]
    ds = TMP / "datasets"
    dx_m = RES * raster.EARTH_M_PER_DEG * math.cos(math.radians(2.25))
    _tif(ds / "copernicus_dem_30" / "UGA.tif", (1000 + xx * dx_m * 0.1).astype("float32"))  # 10% eastward rise
    _tif(ds / "esa_worldcover_2021" / "UGA.tif", np.where(xx < w // 2, 40, 30).astype("uint8"), 0)
    _tif(ds / "worldpop_2020" / "UGA.tif", np.ones((h, w), dtype="float32"), -99999)
    (ds / "osm_schools").mkdir(parents=True, exist_ok=True)
    (ds / "osm_schools" / "UGA.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [34.25, 2.25]}, "properties": {"name": "A"}}]}))
    (ds / "osm_buildings_points").mkdir(parents=True, exist_ok=True)
    pts = [[34.1 + i * 0.001, 2.1] for i in range(30)] + [[34.4, 2.4], [35.0, 3.0]]  # last one is outside
    (ds / "osm_buildings_points" / "UGA.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": c}, "properties": {}} for c in pts]}))


@unittest.skipIf(rasterio is None, "rasterio is not installed")
@override_settings(DATA_DIR=TMP, MEDIA_ROOT=TMP / "media", CELERY_TASK_ALWAYS_EAGER=True,
                   MODULES_DIR=Path(settings.MODULES_DIR) / "_parked")
class ParkedRasterModuleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        make_data()
        call_command("load_cri", verbosity=0)
        cls.user = get_user_model().objects.create_user("o", "o@example.org", "pw-123456!")
        cls.p = Project.objects.create(code="UGA1072", title="t", country_iso3="UGA", country_name="Uganda",
                                       owner=cls.user, sector="education", stage="PPRR")
        box = Polygon.from_bbox((W, S, E, N))
        ProjectArea.objects.create(project=cls.p, method="draw", geom=MultiPolygon(box, srid=4326), area_km2=3090)
        Indicator.objects.create(project=cls.p, statement="Students", cri_id="9.1", tier="project_cri", geo_role="estimate")

    def setUp(self):
        self.client.force_login(self.user)

    def start(self, module, params):
        # Eager Celery: the task runs when the request's transaction commits.
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post("/api/analysis/runs/", json.dumps(
                {"project": "UGA1072", "module": module, "phase": "preparation", "params": params}),
                content_type="application/json")
        self.assertEqual(r.status_code, 201, r.content)
        run = ModuleRun.objects.get(pk=r.json()["run"]["id"])
        self.assertEqual(run.status, "done", run.error + run.log)
        return run

    def metric(self, run, name):
        return next(o for o in run.outputs if o["name"] == name)["value"]

    def test_modules_listed_with_availability(self):
        d = self.client.get("/api/analysis/modules/?project=UGA1072").json()
        ids = {m["id"]: m for m in d["modules"]}
        self.assertEqual(ids["school_access"]["availability"]["status"], "ready")
        self.assertEqual(ids["school_access"]["cri_in_project"], ["9.1"])
        self.assertEqual(d["modules"][0]["id"], "school_access")  # CRI match first

    def test_area_baseline_slope_and_totals(self):
        run = self.start("area_baseline", {"slope_threshold_deg": 15, "zone_level": 2})
        self.assertAlmostEqual(self.metric(run, "mean_slope"), math.degrees(math.atan(0.1)), delta=0.2)
        self.assertEqual(self.metric(run, "steep_share"), 0)
        lc = next(o for o in run.outputs if o["name"] == "landcover")["rows"]
        self.assertEqual({r["class"] for r in lc}, {"Cropland", "Grassland"})
        self.assertAlmostEqual(self.metric(run, "population"), 500 * 500, delta=2000)

    def test_school_access_distance_and_evidence(self):
        run = self.start("school_access", {"threshold_m": 5000, "zone_level": 3})
        # One school in the middle of a 500x500-cell box of 1 person per cell:
        # people within 5 km ≈ cells inside a circle of radius 5 km.
        cell = (RES * raster.EARTH_M_PER_DEG) ** 2 * math.cos(math.radians(2.25))
        expected_within = math.pi * 5000 ** 2 / cell
        within = 250_000 - self.metric(run, "beyond")
        self.assertAlmostEqual(within, expected_within, delta=expected_within * 0.03)
        ev = Evidence.objects.filter(run=run).order_by("cri_code")
        self.assertEqual([e.cri_code for e in ev], ["9.1", "9.3"])
        self.assertIsNotNone(ev[0].indicator)
        self.assertEqual(ev[0].status, "proposed")
        r = self.client.post(f"/api/analysis/evidence/{ev[0].id}/accept/")
        self.assertEqual(r.json()["evidence"]["status"], "accepted")
        f = next(o for o in run.outputs if o["type"] == "image")["file"]
        self.assertEqual(self.client.get(f"/api/analysis/runs/{run.id}/files/{f}").status_code, 200)
        self.assertEqual(self.client.get(f"/api/analysis/runs/{run.id}/files/../../x").status_code, 404)

    def test_terrain(self):
        run = self.start("terrain", {"slope_threshold_deg": 15, "zone_level": 2})
        self.assertAlmostEqual(self.metric(run, "mean_slope"), math.degrees(math.atan(0.1)), delta=0.2)
        classes = {r["class"]: r["share"] for r in next(o for o in run.outputs if o["name"] == "slope_classes")["rows"]}
        self.assertGreater(classes["Moderate"], 95)  # ~5.7° everywhere
        bands = next(o for o in run.outputs if o["name"] == "elevation_bands")["rows"]
        self.assertAlmostEqual(sum(r["share"] for r in bands), 100, delta=0.5)
        self.assertEqual({o["name"] for o in run.outputs if o["type"] == "image"}, {"elevation", "slope", "steep"})
