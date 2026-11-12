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

from apps.analysis.ops import raster
from apps.analysis.models import ModuleRun
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
    (ds / "osm_schools").mkdir(parents=True, exist_ok=True)
    (ds / "osm_schools" / "UGA.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [34.25, 2.25]}, "properties": {"name": "A"}}]}))
    (ds / "osm_buildings_points").mkdir(parents=True, exist_ok=True)
    pts = [[34.1 + i * 0.001, 2.1] for i in range(30)] + [[34.4, 2.4], [35.0, 3.0]]  # last one is outside
    (ds / "osm_buildings_points" / "UGA.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": c}, "properties": {}} for c in pts]}))


@unittest.skipIf(rasterio is None, "rasterio is not installed")
@override_settings(DATA_DIR=TMP, MEDIA_ROOT=TMP / "media", CELERY_TASK_ALWAYS_EAGER=True,
                   ANALYSES_DIR=Path(settings.ANALYSES_DIR) / "_parked")
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

    def test_terrain(self):
        run = self.start("terrain", {"slope_threshold_deg": 15, "zone_level": 2})
        self.assertAlmostEqual(self.metric(run, "mean_slope"), math.degrees(math.atan(0.1)), delta=0.2)
        classes = {r["class"]: r["share"] for r in next(o for o in run.outputs if o["name"] == "slope_classes")["rows"]}
        self.assertGreater(classes["Moderate"], 95)  # ~5.7° everywhere
        bands = next(o for o in run.outputs if o["name"] == "elevation_bands")["rows"]
        self.assertAlmostEqual(sum(r["share"] for r in bands), 100, delta=0.5)
        self.assertEqual({o["name"] for o in run.outputs if o["type"] == "image"}, {"elevation", "slope", "steep"})
