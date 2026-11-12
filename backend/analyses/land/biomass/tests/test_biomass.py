"""Biomass production on synthetic WaPOR and land cover rasters."""
import numpy as np

from apps.analysis.core.testing import AnalysisTestCase


class TestBiomass(AnalysisTestCase):
    analysis_id = "biomass"

    def setUp(self):
        self.synthetic_dataset("landcover", lambda lon, lat: np.where(lon < 34.25, 40, 20), year=2021)

    def test_totals_cropland_and_change(self):
        # 2024: 12,000 kg/ha on cropland (west), 4,000 on shrubland (east). 2020: 10,000 everywhere.
        self.synthetic_dataset("biomass-global", lambda lon, lat: np.where(lon < 34.25, 12000, 4000), year=2024)
        self.synthetic_dataset("biomass-global", lambda lon, lat: np.full_like(lon, 10000), year=2020)
        run = self.run_analysis({"year": 2024, "compare_year": 2020})
        self.assertAlmostEqual(self.metric(run, "mean_biomass"), 8000, delta=200)
        self.assertAlmostEqual(self.metric(run, "cropland_mean"), 12000, delta=150)
        self.assertAlmostEqual(self.metric(run, "change_pct"), -20, delta=2)
        # total = mean kg/ha x area ha / 1000; area about 3,060 km² = 306,000 ha
        area_ha = sum(r["area_km2"] for r in self.table(run, "per_zone")) * 100
        self.assertAlmostEqual(self.metric(run, "total_biomass"), 8000 * area_ha / 1000, delta=0.03 * 8000 * area_ha / 1000)
        by_lc = {r["label"]: r["mean"] for r in self.table(run, "by_landcover")}
        self.assertAlmostEqual(by_lc["Shrubland"], 4000, delta=100)
        self.assertEqual(self.output(run, "change")["unit"], "%")

    def test_single_year_without_comparison(self):
        self.synthetic_dataset("biomass-global", lambda lon, lat: np.full_like(lon, 5000), year=2024)
        run = self.run_analysis({"year": 2024})
        names = [o["name"] for o in run.outputs]
        self.assertNotIn("change", names)
        self.assertNotIn("change_pct", names)
