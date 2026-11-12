"""Sub-catchments on synthetic DEMs (needs WhiteboxTools)."""
import json
import unittest

from apps.analysis.core.testing import AnalysisTestCase
from apps.analysis.engines import whitebox
from analyses.water.stream_network.tests.test_stream_network import DEM_BBOX, DEM_SIZE, valley


@unittest.skipUnless(whitebox.available(), "WhiteboxTools is not installed")
class TestSubBasins(AnalysisTestCase):
    analysis_id = "sub_basins"
    area_bbox = (34.1, 2.1, 34.4, 2.4)

    def test_two_valleys_and_their_exit(self):
        # Two valleys from the north-west and north-east join at (34.25, 2.25) and leave the area southwards.
        self.synthetic_dataset("elevation", valley([((34.0, 2.6), (34.25, 2.25)), ((34.5, 2.6), (34.25, 2.25)),
                                                    ((34.25, 2.25), (34.25, 1.9))]), bbox=DEM_BBOX, size=DEM_SIZE)
        run = self.run_analysis({"min_area_km2": 20})
        units = self.table(run, "units")
        self.assertGreaterEqual(self.metric(run, "unit_count"), 3)          # two tributaries and the trunk at least
        self.assertAlmostEqual(sum(u["share"] for u in units), 100, delta=1)
        exits = self.table(run, "exits")
        self.assertTrue(exits)
        main = exits[0]
        self.assertAlmostEqual(main["lon"], 34.25, delta=0.01)          # the trunk leaves through the south edge
        self.assertAlmostEqual(main["lat"], 2.1, delta=0.01)
        self.assertGreater(main["drains_km2"], 500)                     # most of the clip drains through it
        polys = json.loads((run.workdir / self.output(run, "sub_basins")["file"]).read_text())
        self.assertEqual(len(polys["features"]), len(units))
