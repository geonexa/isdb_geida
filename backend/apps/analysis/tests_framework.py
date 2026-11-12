"""The analysis framework: manifest schema, output check, limits, scaffolding and developer commands."""
import io
import shutil
import tempfile
from pathlib import Path

import yaml
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.analysis.core.manifest import validate_manifest
from apps.analysis.core.registry import availability, read_manifests
from apps.analysis.core.testing import AnalysisTestCase

GOOD = {"id": "demo", "version": "1.0.0", "title": "Demo", "category": "terrain", "phases": ["preparation"]}


def analyses_copy():
    """A temporary analyses/ with the real categories, planned list and template, but no analyses."""
    tmp = Path(tempfile.mkdtemp(prefix="geida-analyses-"))
    src = Path(settings.ANALYSES_DIR)
    for name in ("categories.yaml", "planned.yaml"):
        shutil.copy(src / name, tmp / name)
    shutil.copytree(src / "_template", tmp / "_template", ignore=shutil.ignore_patterns("__pycache__"))
    return tmp


class ManifestSchemaTests(AnalysisTestCase):
    def check(self, extra, message):
        with self.assertRaisesMessage(ValueError, message):
            validate_manifest({**GOOD, **extra}, "x/manifest.yaml")

    def test_valid_and_invalid_manifests(self):
        self.assertEqual(validate_manifest(dict(GOOD)), GOOD)
        self.check({"version": "1.0"}, "version:")
        self.check({"phases": []}, "phases:")
        self.check({"phases": ["later"]}, "phases.0:")
        self.check({"id": "Bad-Id"}, "id:")
        self.check({"unknown": 1}, "unknown: Extra inputs are not permitted")
        self.check({"parameters": [{"name": "k", "type": "choice", "label": "K", "default": 3,
                                    "choices": [{"value": 1, "label": "One"}]}]}, "default 3 isn't one of the choices")
        self.check({"parameters": [{"name": "n", "type": "number", "label": "N", "default": 9, "min": 0, "max": 5}]},
                   "outside")
        self.check({"outputs": [{"type": "table", "name": "a"}, {"type": "metric", "name": "a"}]},
                   "output names must be unique")
        self.check({"requires": ["arcgis"]}, "requires.0:")
        self.check({"queue": "fast"}, "queue:")

    def test_point_parameter(self):
        from django.contrib.gis.geos import MultiPolygon, Polygon
        from apps.analysis.core.manifest import parse_point
        from apps.analysis.views import _clean_params

        point = {"name": "outlet", "type": "point", "label": "Outlet"}
        validate_manifest({**GOOD, "parameters": [point]})
        validate_manifest({**GOOD, "parameters": [{**point, "default": [34.2, 2.3]}]})
        self.check({"parameters": [{**point, "default": [200, 2]}]}, "default is [lon, lat] or null")
        self.check({"parameters": [{**point, "default": "34, 2"}]}, "default is [lon, lat] or null")

        self.assertEqual(parse_point("34.25, 2.31"), [34.25, 2.31])
        self.assertEqual(parse_point("34.25 2.31"), [34.25, 2.31])
        self.assertEqual(parse_point([34.1234567, 2]), [34.123457, 2.0])
        for bad in (None, "", "34", "a, b", [1, 2, 3], "34, 95"):
            self.assertIsNone(parse_point(bad), bad)

        area = MultiPolygon(Polygon.from_bbox((34.0, 2.0, 34.5, 2.5)), srid=4326)
        m = {"parameters": [point]}
        self.assertEqual(_clean_params(m, {"outlet": "34.2, 2.3"}, area), ({"outlet": [34.2, 2.3]}, {}))
        self.assertEqual(_clean_params(m, {"outlet": [34.55, 2.3]}, area)[0], {"outlet": [34.55, 2.3]})  # ~5.5 km outside
        self.assertIn("Pick a point on the map", _clean_params(m, {}, area)[1]["outlet"])
        self.assertIn("type longitude, latitude", _clean_params(m, {"outlet": "north"}, area)[1]["outlet"])
        self.assertIn("more than 10 km", _clean_params(m, {"outlet": "35, 2.3"}, area)[1]["outlet"])

    def test_every_analysis_in_the_repository_is_valid(self):
        errors = []
        read_manifests(errors)
        self.assertEqual(errors, [])

    def test_analysis_docs_are_up_to_date(self):
        # docs/analyses/ is generated from the manifests and METHOD.md files.
        out = io.StringIO()
        call_command("document_analyses", "--check", stdout=out)
        self.assertIn("up to date", out.getvalue())


class ScaffoldAndRunTests(AnalysisTestCase):
    analysis_id = "slope"  # scaffolded from the template in each test

    def setUp(self):
        self.root = analyses_copy()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.enterContext(self.settings(ANALYSES_DIR=self.root))

    def test_new_analysis_from_the_planned_list_runs(self):
        call_command("new_analysis", "terrain", "slope", stdout=io.StringIO())
        folder = self.root / "terrain" / "slope"
        for name in ("manifest.yaml", "run.py", "METHOD.md", "__init__.py", "tests/__init__.py", "tests/test_slope.py"):
            self.assertTrue((folder / name).exists(), name)
        self.assertTrue((self.root / "terrain" / "__init__.py").exists())
        m = yaml.safe_load((folder / "manifest.yaml").read_text())
        self.assertEqual((m["title"], m["category"], m["phases"]), ("Slope and slope classes", "terrain", ["preparation"]))
        self.assertIn("class TestSlope(AnalysisTestCase)", (folder / "tests" / "test_slope.py").read_text())
        self.assertEqual(list(read_manifests()), ["slope"])

        out = io.StringIO()
        call_command("check_analyses", stdout=out)
        self.assertIn("All analyses are valid.", out.getvalue())

        run = self.run_analysis()
        self.assertGreater(self.metric(run, "area_km2"), 2500)
        self.assertEqual(len(self.table(run, "per_zone")), 1)

        out = io.StringIO()
        call_command("run_analysis", "slope", "--project", "TEST01", "--param", "zone_level=1", stdout=out)
        self.assertIn("Done: The area of influence covers", out.getvalue())

    def test_new_analysis_refuses_bad_input(self):
        with self.assertRaisesMessage(CommandError, "Unknown category"):
            call_command("new_analysis", "nope", "x_y")
        with self.assertRaisesMessage(CommandError, "The id must start with a letter"):
            call_command("new_analysis", "terrain", "Bad-Id")
        call_command("new_analysis", "terrain", "demo", stdout=io.StringIO())
        with self.assertRaisesMessage(CommandError, "already exists"):
            call_command("new_analysis", "water", "demo")

    def test_run_analysis_checks_phase_and_parameters(self):
        call_command("new_analysis", "terrain", "slope", stdout=io.StringIO())
        with self.assertRaisesMessage(CommandError, "isn't offered in completion"):
            call_command("run_analysis", "slope", "--project", "TEST01", "--phase", "completion")
        with self.assertRaisesMessage(CommandError, "Bad --param"):
            call_command("run_analysis", "slope", "--project", "TEST01", "--param", "nope=1")
        with self.assertRaisesMessage(CommandError, "No project"):
            call_command("run_analysis", "slope", "--project", "NOPE")

    def test_missing_declared_output_fails_the_run(self):
        call_command("new_analysis", "terrain", "slope", stdout=io.StringIO())
        run_py = self.root / "terrain" / "slope" / "run.py"
        run_py.write_text(run_py.read_text().replace('ctx.add_metric("area_km2"', 'ctx.add_metric("area_total"'))
        run = self.run_analysis(expect="failed")
        self.assertIn("didn't produce the outputs its manifest declares (area_km2)", run.error)

    def test_area_limit_makes_the_analysis_unavailable(self):
        call_command("new_analysis", "terrain", "slope", stdout=io.StringIO())
        m = read_manifests()["slope"]
        self.assertEqual(availability(m, self.project)["status"], "ready")
        m["limits"] = {"max_area_km2": 100}
        av = availability(m, self.project)
        self.assertEqual(av["status"], "not_available")
        self.assertIn("larger than this analysis handles", av["reasons"][0])

    def test_broken_analysis_is_left_out_not_fatal(self):
        call_command("new_analysis", "terrain", "slope", stdout=io.StringIO())
        call_command("new_analysis", "water", "catchment", stdout=io.StringIO())
        (self.root / "water" / "catchment" / "manifest.yaml").write_text("id: catchment\nversion: one\n")
        errors = []
        self.assertEqual(list(read_manifests(errors)), ["slope"])
        self.assertIn("catchment/manifest.yaml", errors[0])
        with self.assertRaisesMessage(CommandError, "1 error(s)"):
            call_command("check_analyses", stdout=io.StringIO())


class RasterToolkitTests(AnalysisTestCase):
    """ops.grid, render.legend, data.cache and catalogue datasets."""

    def test_catalogue_layers_are_datasets(self):
        from apps.analysis.data import DATASETS
        from apps.analysis.data.cog import CatalogRaster
        for lid in ("elevation", "eta", "precipitation", "landcover", "surface-water"):
            self.assertIsInstance(DATASETS[lid], CatalogRaster, lid)
        self.assertNotIn("slope", DATASETS)  # computed on the fly by TiTiler: analyses compute it
        self.assertTrue(DATASETS["landcover"].categorical)
        self.assertEqual(DATASETS["eta"].periods[0], 2018)

    def test_legends(self):
        import numpy as np

        from apps.analysis.render import legend as L
        with self.assertRaisesMessage(ValueError, "A ramp legend needs"):
            L.load({"type": "ramp", "palette": ["#000000"]})
        with self.assertRaisesMessage(ValueError, "type: ramp"):
            L.load({"palette": []})
        ramp = L.load({"type": "ramp", "palette": ["#000000", "#FFFFFF"], "min": 0, "max": 10, "unit": "m"})
        rgba = L.colorize(np.array([[0, 5, 10, np.nan]], dtype="float32"), ramp)
        self.assertEqual(rgba[0, 0, :3].tolist(), [0, 0, 0])
        self.assertEqual(rgba[0, 2, :3].tolist(), [255, 255, 255])
        self.assertTrue(120 <= rgba[0, 1, 0] <= 135)
        self.assertEqual(rgba[0, 3, 3], 0)  # no data: transparent
        self.assertEqual([i["label"] for i in L.items(ramp)], ["0–5 m", "5–10 m"])  # ranges, not single values
        self.assertEqual(L.items({**ramp, "open_max": True})[-1]["label"], "10 m and above")
        elev = {"type": "ramp", "palette": ["#000000"] * 7, "min": 1196, "max": 4659, "unit": "m"}
        labels = [i["label"] for i in L.items(elev)]
        self.assertEqual((labels[0], labels[1], labels[-1]), ("1,196–1,500 m", "1,500–2,000 m", "4,500–4,659 m"))
        classes = {"type": "classes", "items": [{"value": 1, "color": "#FF0000", "label": "One"}]}
        self.assertEqual(L.colorize(np.array([[1, 2]], dtype="float32"), classes)[0, :, 3].tolist(), [220, 0])

    def test_grid_reproject_and_write(self):
        import numpy as np
        from rasterio.transform import from_origin

        from apps.analysis.ops import grid as G
        r = G.Raster(np.arange(16, dtype="float32").reshape(4, 4), from_origin(0, 400, 100, 100), "EPSG:32636")
        self.assertIs(G.reproject(r, r.grid), r)  # same grid: unchanged
        half = G.Grid("EPSG:32636", from_origin(0, 400, 200, 200), (2, 2))
        self.assertEqual(G.reproject(r, half, "average").data.shape, (2, 2))
        self.assertEqual(r.grid.pixel_area_m2, 10_000)
        path = G.write(r, self._tmp / "r.tif", cog=True)
        back = G.read(path)
        self.assertEqual(back.crs, "EPSG:32636")
        self.assertEqual(back.data.tolist(), r.data.tolist())
        self.assertEqual(r.stats()["mean"], 7.5)

    def test_cache_keys_follow_their_inputs(self):
        from apps.analysis.data import cache
        a = cache.path_for("flow", {"dem": "elevation", "v": 1})
        self.assertEqual(a, cache.path_for("flow", {"v": 1, "dem": "elevation"}))  # order doesn't matter
        self.assertNotEqual(a, cache.path_for("flow", {"dem": "elevation", "v": 2}))


class NativeResolutionTests(AnalysisTestCase):
    def test_wapor_scale_factor_and_native_resolution(self):
        """WaPOR COGs store integers with a scale factor: the clip returns real values at 300 m."""
        from unittest import mock

        import numpy as np
        import rasterio
        from django.contrib.gis.geos import Polygon
        from rasterio.transform import from_bounds

        from apps.analysis.data import DATASETS
        from apps.analysis.ops import grid as G

        path = self._tmp / "wapor.tif"
        with rasterio.open(path, "w", driver="GTiff", width=300, height=300, count=1, dtype="int16", nodata=-9999,
                           crs="EPSG:4326", transform=from_bounds(33.5, 1.5, 35.0, 3.0, 300, 300)) as dst:
            dst.write(np.full((300, 300), 8000, dtype="int16"), 1)
            dst.scales, dst.offsets = (0.1,), (0.0,)
        geom = Polygon.from_bbox(self.area_bbox)
        geom.srid = 4326
        with mock.patch("apps.geoportal.raster.sources", return_value=[(str(path), None, None)]):
            out, year = DATASETS["eta"].clip(geom, "UGA", 2022, log=lambda m: None)
        r = G.read(out)
        self.assertEqual(year, 2022)
        self.assertAlmostEqual(float(np.nanmean(r.data)), 800.0, places=3)  # 8000 × 0.1 mm
        self.assertEqual(r.grid.res, 300)
        self.assertEqual(r.crs, "EPSG:32636")


class CountResamplingTests(AnalysisTestCase):
    """Population counts keep their total when read onto a finer run grid (e.g. one set by a 30 m DEM)."""
    analysis_id = "population"

    def ctx(self, extra_inputs=()):
        from apps.analysis.core.registry import sync_modules
        from apps.analysis.core.runner import RunContext
        from apps.analysis.models import Module, ModuleRun
        sync_modules()
        module = Module.objects.get(pk=self.analysis_id)
        run = ModuleRun.objects.create(project=self.project, module=module, module_version=module.version,
                                       phase="preparation", params={}, created_by=self.user)
        ctx = RunContext(run)
        inputs = dict(ctx.manifest["inputs"])
        inputs["required"] = [*inputs.get("required", []), *extra_inputs]
        ctx.manifest = {**ctx.manifest, "inputs": inputs}
        return ctx

    def test_counts_keep_their_total_on_a_finer_grid(self):
        import numpy as np
        self.synthetic_dataset("elevation", lambda lon, lat: np.full_like(lon, 500.0))
        self.synthetic_dataset("worldpop", lambda lon, lat: np.full_like(lon, 1.0), year=2025)
        own = self.ctx()
        pop = own.raster("population", year=2025)                     # its own ~100 m grid
        total = float(np.nansum(pop.data[own.area_mask(pop)]))
        fine = self.ctx([{"name": "dem", "type": "raster", "default": "elevation", "label": "DEM"}])
        dem = fine.raster("dem", res=30)                              # the DEM sets a 30 m grid first
        self.assertAlmostEqual(dem.grid.res, 30, delta=0.5)
        pop30 = fine.raster("population", year=2025)
        self.assertAlmostEqual(float(np.nansum(pop30.data[fine.area_mask(pop30)])) / total, 1, delta=0.03)

    def test_damaged_clip_is_read_again(self):
        # A clip left empty by an interrupted run is rebuilt, not reused.
        import numpy as np
        from pathlib import Path
        self.synthetic_dataset("elevation", lambda lon, lat: np.full_like(lon, 500.0))
        dem_input = [{"name": "dem", "type": "raster", "default": "elevation", "label": "DEM"}]
        first = self.ctx(dem_input).raster("dem")
        path = Path(first.info["source"])
        path.write_bytes(b"")
        again = self.ctx(dem_input).raster("dem")
        self.assertGreater(path.stat().st_size, 0)
        self.assertEqual(float(np.nanmax(again.data)), 500.0)
        self.assertFalse(list(path.parent.glob("*.part.tif")))
