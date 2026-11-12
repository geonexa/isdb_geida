"""Land cover composition on synthetic class maps."""
import numpy as np

from apps.analysis.core.testing import AnalysisTestCase


class TestLandCover(AnalysisTestCase):
    analysis_id = "land_cover"

    def test_worldcover_halves(self):
        # Cropland west of 34.25°, tree cover east of it; a strip of built-up in the north-east.
        self.synthetic_dataset("landcover", lambda lon, lat: np.where(lon < 34.25, 40, np.where(lat > 2.45, 50, 10)), year=2021)
        run = self.run_analysis()
        self.assertAlmostEqual(self.metric(run, "cropland_share"), 50, delta=2)
        self.assertAlmostEqual(self.metric(run, "tree_share"), 45, delta=2)
        self.assertAlmostEqual(self.metric(run, "built_share"), 5, delta=1)
        labels = [r["label"] for r in self.table(run, "classes")]
        self.assertEqual(labels[0], "Cropland")
        out = self.output(run, "land_cover")
        self.assertEqual({i["label"] for i in out["legend"]}, {"Cropland", "Tree cover", "Built-up"})
        self.assertTrue(self.table(run, "per_zone"))

    def test_esri_yearly_map(self):
        self.synthetic_dataset("lulc_annual", lambda lon, lat: np.where(lat < 2.25, 5, 11), year=2019)
        run = self.run_analysis({"landcover_dataset": "lulc_annual", "year": 2019})
        self.assertAlmostEqual(self.metric(run, "cropland_share"), 50, delta=2)
        self.assertIn("Rangeland", [r["label"] for r in self.table(run, "classes")])

    def test_worldcover_year_outside_range(self):
        run = self.run_analysis({"year": 2018}, expect="failed")
        self.assertIn("2020 and 2021", run.error)
