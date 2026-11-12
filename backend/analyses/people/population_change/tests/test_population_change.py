"""Population change on synthetic years, with the WorldPop API mocked."""
from unittest import mock

import numpy as np

from apps.analysis.core.testing import AnalysisTestCase
from apps.analysis.data import people as WP


def fake_api(path, body, raw=False, timeout=120):
    years = range(body["from_year"], body["to_year"] + 1)
    return {"years": [{"data_year": y, "total_population": 1000.0 + y - body["from_year"], "population_density": 1.0} for y in years]}


@mock.patch.object(WP, "worldpop_post", side_effect=fake_api)
class TestPopulationChange(AnalysisTestCase):
    analysis_id = "population_change"

    def test_worldpop_doubling_in_the_west(self, api):
        self.synthetic_dataset("worldpop", lambda lon, lat: np.full_like(lon, 4.0), year=2015)
        self.synthetic_dataset("worldpop", lambda lon, lat: np.where(lon < 34.25, 8.0, 4.0), year=2025)
        run = self.run_analysis()
        self.assertAlmostEqual(self.metric(run, "change_pct"), 50, delta=1)
        self.assertAlmostEqual(self.metric(run, "growth_rate"), 100 * (1.5 ** (1 / 10) - 1), delta=0.05)
        self.assertEqual(len(self.table(run, "by_year")), 11)
        self.assertEqual(self.output(run, "change")["unit"], "people per cell")

    def test_ghsl_before_2015_and_order(self, api):
        self.synthetic_dataset("ghsl_pop", lambda lon, lat: np.full_like(lon, 2.0), year=2000)
        self.synthetic_dataset("ghsl_pop", lambda lon, lat: np.full_like(lon, 3.0), year=2020)
        run = self.run_analysis({"year_from": 2000, "year_to": 2020})
        self.assertAlmostEqual(self.metric(run, "change_pct"), 50, delta=1)
        self.assertIn("GHSL", self.output(run, "population_from")["note"])
        self.assertNotIn("by_year", [o["name"] for o in run.outputs])
        run = self.run_analysis({"year_from": 2020, "year_to": 2000}, expect="failed")
        self.assertIn("later", run.error)
