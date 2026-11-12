"""Travel time weighted by population, on synthetic rasters."""
import numpy as np

from apps.analysis.core.testing import AnalysisTestCase


class TestTravelTime(AnalysisTestCase):
    analysis_id = "travel_time"

    def test_weighted_by_people(self):
        # West half: 30 min and 9 people per cell; east half: 300 min and 1 person per cell.
        self.synthetic_dataset("worldpop", lambda lon, lat: np.where(lon < 34.25, 9.0, 1.0), year=2025)
        self.synthetic_dataset("map_tt_cities", lambda lon, lat: np.where(lon < 34.25, 30.0, 300.0))
        run = self.run_analysis()
        self.assertAlmostEqual(self.metric(run, "mean_minutes"), 0.9 * 30 + 0.1 * 300, delta=6)
        self.assertAlmostEqual(self.metric(run, "median_minutes"), 30, delta=2)
        self.assertAlmostEqual(self.metric(run, "within_share"), 90, delta=2)
        bands = {r["label"]: r["share"] for r in self.table(run, "bands")}
        self.assertAlmostEqual(bands["3–6 h"], 10, delta=2)

    def test_health_walking(self):
        self.synthetic_dataset("worldpop_women_15_49", lambda lon, lat: np.full_like(lon, 1.0), year=2025)
        self.synthetic_dataset("map_tt_health_walk", lambda lon, lat: np.full_like(lon, 90.0))
        run = self.run_analysis({"travel_dataset": "map_tt_health_walk", "threshold_min": 120, "population_dataset": "worldpop_women_15_49"})
        self.assertEqual(self.metric(run, "within_share"), 100)
        self.assertIn("on foot", self.output(run, "mean_minutes")["title"])
        self.assertIn("Women aged 15–49", self.output(run, "within_share")["title"])
