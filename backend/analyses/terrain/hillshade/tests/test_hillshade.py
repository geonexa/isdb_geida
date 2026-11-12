"""Tests for hillshade on synthetic DEMs."""
import math

import numpy as np

from apps.analysis.core.testing import AnalysisTestCase

M_PER_DEG_LON = 111_320 * math.cos(math.radians(2.25))


class TestHillshade(AnalysisTestCase):
    analysis_id = "hillshade"

    def shade_mean(self, run):
        from apps.analysis.ops import grid as G
        r = G.read(run.workdir / self.output(run, "hillshade")["data_file"])
        return float(np.nanmean(r.data))

    def test_flat_land_and_relief(self):
        self.synthetic_dataset("elevation", lambda lon, lat: np.full(lon.shape, 1200.0))
        run = self.run_analysis()
        # Flat land lit from 45° above: cos(45°) × 255 = 180
        self.assertAlmostEqual(self.shade_mean(run), 255 * math.cos(math.radians(45)), delta=1)
        self.assertEqual(self.metric(run, "relief"), 0)

    def test_slope_facing_the_sun_is_brighter(self):
        # Land rising east faces west; a sun in the west lights it more than a sun in the east.
        self.synthetic_dataset("elevation", lambda lon, lat: 1000 + (lon - 34.0) * M_PER_DEG_LON * 0.3)
        west = self.shade_mean(self.run_analysis({"azimuth": 270}))
        east = self.shade_mean(self.run_analysis({"azimuth": 90}))
        self.assertGreater(west, east + 50)
        run = self.run_analysis({"z_factor": 2})
        self.assertAlmostEqual(self.metric(run, "relief"), 0.5 * M_PER_DEG_LON * 0.3, delta=0.5 * M_PER_DEG_LON * 0.3 * 0.03)
        self.assertEqual(self.output(run, "hillshade")["title"], "Hillshade (×2 vertical)")
