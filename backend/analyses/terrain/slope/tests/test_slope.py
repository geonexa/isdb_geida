"""Tests for slope on synthetic DEMs with known slopes."""
import math

import numpy as np

from apps.analysis.core.testing import AnalysisTestCase

M_PER_DEG_LON = 111_320 * math.cos(math.radians(2.25))


class TestSlope(AnalysisTestCase):
    analysis_id = "slope"

    def test_tilted_plane(self):
        # Rises 10 m per 100 m eastward: slope atan(0.1) = 5.71°, everywhere "moderate".
        self.synthetic_dataset("elevation", lambda lon, lat: 1000 + (lon - 34.0) * M_PER_DEG_LON * 0.1)
        run = self.run_analysis()
        self.assertAlmostEqual(self.metric(run, "mean_slope"), math.degrees(math.atan(0.1)), delta=0.15)
        self.assertEqual(self.metric(run, "steep_share"), 0)
        classes = {r["label"].split(" (")[0]: r["share"] for r in self.table(run, "classes")}
        self.assertGreater(classes["Moderate"], 99)
        out = self.output(run, "slope")
        self.assertEqual(out["legend"][-1]["label"], "30 degrees and above")
        self.assertTrue((run.workdir / out["data_file"]).exists())

    def test_percent_and_threshold(self):
        # Rises 30 m per 100 m: 30 % rise, 16.7°, steeper than a 15° threshold.
        self.synthetic_dataset("elevation", lambda lon, lat: 500 + (lat - 2.0) * 110_600 * 0.3)
        run = self.run_analysis({"units": "percent", "steep_threshold": 15})
        self.assertAlmostEqual(self.metric(run, "mean_slope"), 30, delta=0.8)
        self.assertGreater(self.metric(run, "steep_share"), 99)
        self.assertEqual(self.output(run, "slope")["unit"], "%")

    def test_flat_with_a_steep_half(self):
        # Flat in the west, a 45° ramp in the east half.
        self.synthetic_dataset("elevation", lambda lon, lat: np.where(lon < 34.25, 800, 800 + (lon - 34.25) * M_PER_DEG_LON))
        run = self.run_analysis()
        self.assertAlmostEqual(self.metric(run, "steep_share"), 50, delta=3)
