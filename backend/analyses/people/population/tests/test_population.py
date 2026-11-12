"""Population and density on synthetic population grids, with the WorldPop API mocked."""
from unittest import mock

import numpy as np

from apps.analysis.core.testing import AnalysisTestCase
from apps.analysis.data import people as WP
from apps.analysis.data.base import DatasetUnavailable

PYRAMID = [{"class": c, "age": a, "male": 100.0, "female": 110.0} for c, a in (("00", "0"), ("01", "1 to 4"), ("05", "5 to 9"))]


def fake_api(path, body, raw=False, timeout=120):
    if path == "/groups":
        return {"total_population": 1000.0, "groups": [{"name": g, "population": 100.0 * (i + 1), "share": 0.1 * (i + 1)}
                                                        for i, g in enumerate(body["groups"])]}
    if path == "/agesex":
        return {"agesex_pyramid": PYRAMID}
    if path == "/batch":
        return {"features": [{"id": f["id"], "groups": [{"name": "under_5", "population": 42.0}]} for f in body["features"]["features"]]}
    raise DatasetUnavailable("WorldPop: no raster in tests")


@mock.patch.object(WP, "worldpop_post", side_effect=fake_api)
class TestPopulation(AnalysisTestCase):
    analysis_id = "population"

    def test_worldpop_totals_classes_and_age_sex(self, api):
        # 0.001° cells (~111 m): 10 people per cell in the west half (~800 per km²), none in the east.
        self.synthetic_dataset("worldpop", lambda lon, lat: np.where(lon < 34.25, 10.0, 0.0), year=2025)
        run = self.run_analysis()
        self.assertAlmostEqual(self.metric(run, "total_population"), 1_250_000, delta=0.02 * 1_250_000)
        self.assertAlmostEqual(self.metric(run, "dense_share"), 100, delta=1)
        classes = {r["label"].split(" (")[0]: r for r in self.table(run, "density_classes")}
        self.assertAlmostEqual(classes["Uninhabited"]["area_km2"] / classes["Clustered"]["area_km2"], 1, delta=0.05)
        self.assertEqual(self.metric(run, "under5"), 100)
        self.assertEqual(self.table(run, "age_groups")[0]["share"], 10)
        self.assertEqual(self.table(run, "age_pyramid")[0]["age"], "5 to 9")   # oldest first
        self.assertIn("WorldPop", self.output(run, "total_population")["note"])

    def test_ghsl_epoch_and_no_age_tables(self, api):
        self.synthetic_dataset("ghsl_pop", lambda lon, lat: np.full_like(lon, 1.0), year=2010)
        run = self.run_analysis({"population_dataset": "ghsl_pop", "year": 2012})
        self.assertIn("2010", self.output(run, "total_population")["title"])
        names = [o["name"] for o in run.outputs]
        self.assertNotIn("age_groups", names)

    def test_falls_back_to_ghsl(self, api):
        # No WorldPop file and the API "fails": GHSL 2020 is used for 2021.
        self.synthetic_dataset("ghsl_pop", lambda lon, lat: np.full_like(lon, 2.0), year=2020)
        run = self.run_analysis({"year": 2021})
        self.assertIn("unavailable", self.output(run, "total_population")["note"])
        self.assertIn("using GHSL 2020", run.log)
        # Before 2015 GHSL is used directly.
        self.synthetic_dataset("ghsl_pop", lambda lon, lat: np.full_like(lon, 1.0), year=2000)
        run = self.run_analysis({"year": 2000})
        self.assertIn("GHSL is used for 2000", run.log)
        self.assertIn("2000", self.output(run, "total_population")["title"])
