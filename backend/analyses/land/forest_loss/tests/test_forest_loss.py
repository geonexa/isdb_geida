"""Forest cover and loss on synthetic Hansen layers."""
import numpy as np

from apps.analysis.core.testing import AnalysisTestCase


class TestForestLoss(AnalysisTestCase):
    analysis_id = "forest_loss"

    def setUp(self):
        # Forest (80% canopy) in the west half, 10% canopy in the east.
        self.synthetic_dataset("hansen_treecover2000", lambda lon, lat: np.where(lon < 34.25, 80, 10))
        # In the west half: the north fifth lost in 2005, the next fifth in 2019; loss marked in the east is not forest.
        self.synthetic_dataset("hansen_lossyear", lambda lon, lat: np.where(
            lat > 2.4, 5, np.where(lat > 2.3, 19, np.where(lon > 34.4, 12, 0))))

    def test_forest_and_loss_by_year(self):
        run = self.run_analysis()
        self.assertAlmostEqual(self.metric(run, "forest_share"), 50, delta=2)
        self.assertAlmostEqual(self.metric(run, "loss_share"), 40, delta=2)
        years = {r["year"]: r["loss_km2"] for r in self.table(run, "loss_by_year")}
        self.assertAlmostEqual(years[2005], years[2019], delta=0.05 * years[2005])
        self.assertEqual(years[2012], 0)   # not forest in 2000
        self.assertEqual(len(self.output(run, "loss")["legend"]), 5)

    def test_from_year_and_threshold(self):
        run = self.run_analysis({"from_year": 2010})
        self.assertAlmostEqual(self.metric(run, "loss_share"), 20, delta=2)
        self.assertEqual([i["label"] for i in self.output(run, "loss")["legend"]][0], "2010")
        run = self.run_analysis({"threshold": 90})
        self.assertEqual(self.metric(run, "forest_2000"), 0)
