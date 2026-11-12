"""
Test helpers for analyses (used by analyses/<category>/<id>/tests/).

    from apps.analysis.core.testing import AnalysisTestCase

    class SlopeTests(AnalysisTestCase):
        analysis_id = "slope"

        def test_mean_slope(self):
            run = self.run_analysis({"units": "degrees"})
            self.assertAlmostEqual(self.metric(run, "mean_slope"), 5.7, delta=0.2)

Each test class gets a project with a rectangular area of influence (area_bbox) in a
temporary data and media folder, so runs never touch the real data or cache. Put small
input files in the analysis' tests/fixtures/ and copy them into DATA_DIR with
use_dataset() (local dataset overrides are read from DATA_DIR/datasets/<id>/<ISO3>.*).
"""
import shutil
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import TestCase, override_settings

from ..models import ModuleRun
from .registry import sync_modules
from .runner import execute


class AnalysisTestCase(TestCase):
    analysis_id = ""
    area_bbox = (34.0, 2.0, 34.5, 2.5)   # lon/lat, a ~3,000 km² rectangle in Uganda
    iso3, country = "UGA", "Uganda"

    @classmethod
    def setUpClass(cls):
        cls._tmp = Path(tempfile.mkdtemp(prefix="geida-analysis-test-"))
        cls._settings = override_settings(DATA_DIR=cls._tmp / "data", MEDIA_ROOT=cls._tmp / "media")
        cls._settings.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._settings.disable()
        shutil.rmtree(cls._tmp, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        from apps.projects.models import Project, ProjectArea

        cls.user = get_user_model().objects.create_user("analyst", "analyst@example.org", "pw-123456!")
        cls.project = Project.objects.create(code="TEST01", title="Analysis test", country_iso3=cls.iso3,
                                             country_name=cls.country, owner=cls.user, stage="PPRR")
        geom = MultiPolygon(Polygon.from_bbox(cls.area_bbox), srid=4326)
        km2 = geom.transform(3857, clone=True).area / 1e6  # rough; analyses measure in their own frame
        ProjectArea.objects.create(project=cls.project, method="draw", geom=geom, area_km2=km2)

    # Inputs --------------------------------------------------------------------------------
    def fixture(self, name):
        """Path of a file in the calling analysis' tests/fixtures/ folder."""
        import inspect
        caller = Path(inspect.stack()[1].filename).parent
        return caller / "fixtures" / name

    def use_dataset(self, dataset_id, path, year=None):
        """Serve a fixture file as dataset `dataset_id` for this project's country (for one `year` only, when given)."""
        from django.conf import settings
        path = Path(path)
        dest = Path(settings.DATA_DIR) / "datasets" / dataset_id / f"{self.iso3}{f'_{year}' if year else ''}{path.suffix}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(path, dest)
        shutil.rmtree(Path(settings.DATA_DIR) / dataset_id, ignore_errors=True)  # clips of the old file
        return dest

    def synthetic_dataset(self, dataset_id, func, bbox=(33.9, 1.9, 34.6, 2.6), size=700, year=None):
        """
        Serve a lon/lat GeoTIFF computed from func(lon, lat) -> values as dataset `dataset_id`
        (default: the test area plus a margin, 0.001° pixels, like a real global dataset).
        """
        import numpy as np
        import rasterio
        from rasterio.transform import from_bounds

        w, s, e, n = bbox
        lon = (np.arange(size) + 0.5) / size * (e - w) + w
        lat = n - (np.arange(size) + 0.5) / size * (n - s)
        values = np.asarray(func(*np.meshgrid(lon, lat)), dtype="float32")
        path = self._tmp / f"{dataset_id}{f'_{year}' if year else ''}_synthetic.tif"
        with rasterio.open(path, "w", driver="GTiff", width=size, height=size, count=1, dtype="float32",
                           crs="EPSG:4326", transform=from_bounds(w, s, e, n, size, size), nodata=-9999) as dst:
            dst.write(values, 1)
        return self.use_dataset(dataset_id, path, year)

    # Running -------------------------------------------------------------------------------
    def run_analysis(self, params=None, phase="preparation", expect="done"):
        """Run the analysis synchronously (no queue) and return the ModuleRun."""
        from ..models import Module

        sync_modules()
        module = Module.objects.get(pk=self.analysis_id)
        run = ModuleRun.objects.create(project=self.project, module=module, module_version=module.version,
                                       phase=phase, params=params or {}, created_by=self.user)
        execute(run)
        run.refresh_from_db()
        if expect:
            self.assertEqual(run.status, expect, f"{run.error}\n{run.log}")
        return run

    # Reading results -----------------------------------------------------------------------
    def output(self, run, name):
        try:
            return next(o for o in run.outputs if o["name"] == name)
        except StopIteration:
            self.fail(f"No output '{name}'; outputs: {[o['name'] for o in run.outputs]}")

    def metric(self, run, name):
        return self.output(run, name)["value"]

    def table(self, run, name):
        return self.output(run, name)["rows"]
