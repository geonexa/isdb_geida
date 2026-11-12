"""Tests for aspect on synthetic DEMs."""
import math

import numpy as np

from apps.analysis.core.testing import AnalysisTestCase

M_PER_DEG_LON = 111_320 * math.cos(math.radians(2.25))


class TestAspect(AnalysisTestCase):
    analysis_id = "aspect"

    def test_land_rising_east_faces_west(self):
        self.synthetic_dataset("elevation", lambda lon, lat: 1000 + (lon - 34.0) * M_PER_DEG_LON * 0.1)
        run = self.run_analysis()
        self.assertEqual(self.metric(run, "main_direction"), "West")
        shares = {r["label"]: r["share"] for r in self.table(run, "directions")}
        self.assertGreater(shares["West"], 99)
        self.assertEqual(self.metric(run, "flat_share"), 0)

    def test_land_rising_north_faces_south_and_flat_is_flat(self):
        # South half flat, north half rising northwards (faces south).
        self.synthetic_dataset("elevation", lambda lon, lat: np.where(lat < 2.25, 900, 900 + (lat - 2.25) * 110_600 * 0.2))
        run = self.run_analysis()
        self.assertEqual(self.metric(run, "main_direction"), "South")
        self.assertAlmostEqual(self.metric(run, "flat_share"), 50, delta=3)
        self.assertAlmostEqual(self.metric(run, "south_facing_share"), 50, delta=3)
        self.assertEqual(self.output(run, "aspect")["legend"][0]["label"], "Flat")
