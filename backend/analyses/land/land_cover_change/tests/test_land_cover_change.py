"""Land cover change on two synthetic years."""
import numpy as np

from apps.analysis.core.testing import AnalysisTestCase


class TestLandCoverChange(AnalysisTestCase):
    analysis_id = "land_cover_change"

    def test_trees_to_crops_and_crops_to_built(self):
        # 2017: trees west, crops east. 2023: the western quarter (34.0–34.125) became crops,
        # and the north of the east half became built area.
        self.synthetic_dataset("lulc_annual", lambda lon, lat: np.where(lon < 34.25, 2, 5), year=2017)
        self.synthetic_dataset("lulc_annual", lambda lon, lat: np.where(
            lon < 34.125, 5, np.where(lon < 34.25, 2, np.where(lat > 2.4, 7, 5))), year=2023)
        run = self.run_analysis()
        self.assertAlmostEqual(self.metric(run, "changed_share"), 35, delta=2)   # 25% trees->crops + 10% crops->built
        self.assertAlmostEqual(self.metric(run, "built_change") / self.metric(run, "cropland_change"), 10 / 15, delta=0.05)
        self.assertLess(self.metric(run, "tree_change"), 0)
        first = self.table(run, "transitions")[0]
        self.assertEqual((first["from"], first["to"]), ("Trees", "Crops"))
        self.assertEqual({i["label"] for i in self.output(run, "changes")["legend"]}, {"Crops", "Built area"})

    def test_clouds_left_out_and_order_checked(self):
        self.synthetic_dataset("lulc_annual", lambda lon, lat: np.where(lon < 34.25, 10, 5), year=2018)
        self.synthetic_dataset("lulc_annual", lambda lon, lat: np.full_like(lon, 5), year=2020)
        run = self.run_analysis({"year_from": 2018, "year_to": 2020})
        self.assertEqual(self.metric(run, "changed_share"), 0)
        run = self.run_analysis({"year_from": 2020, "year_to": 2018}, expect="failed")
        self.assertIn("later", run.error)
