"""Tests for contours on a synthetic DEM: a plane rising eastward from 1,000 m to 3,000 m."""
import json

from apps.analysis.core.testing import AnalysisTestCase


class TestContours(AnalysisTestCase):
    analysis_id = "contours"

    def setUp(self):
        self.synthetic_dataset("elevation", lambda lon, lat: 1000 + (lon - 34.0) / 0.5 * 2000)

    def test_lines_at_the_interval(self):
        run = self.run_analysis({"interval": 500, "smoothing": "none"})
        self.assertEqual(self.metric(run, "interval"), 500)
        geo = json.loads((run.workdir / self.output(run, "contours")["file"]).read_text())
        elevs = sorted({round(f["properties"]["elev"]) for f in geo["features"]})
        # Inside the area only. 1,000 m and 3,000 m are exactly its west and east edges: short slivers
        # may appear there; the three interior levels must be there as full N–S lines.
        self.assertTrue({1500, 2000, 2500} <= set(elevs) <= {1000, 1500, 2000, 2500, 3000}, elevs)
        interior = [f for f in geo["features"] if 1000 < round(f["properties"]["elev"]) < 3000]
        self.assertEqual(len(interior), 3)
        self.assertGreater(self.metric(run, "length_km"), 3 * 55.3 - 3)
        index = {round(f["properties"]["elev"]): f["properties"]["index"] for f in geo["features"]}
        self.assertEqual(index[2500], 1)                        # 2,500 = 5 × 500
        self.assertEqual(index[2000], 0)
        self.assertTrue((run.workdir / "contours.gpkg").exists())
        lon = geo["features"][0]["geometry"]["coordinates"][0][0]
        self.assertTrue(33.99 <= lon <= 34.51, lon)             # map layer in lon/lat (not UTM metres)

    def test_automatic_interval_and_limits(self):
        run = self.run_analysis()
        self.assertIn(self.metric(run, "interval"), (100, 200, 250))  # about 15 levels over 2,000 m
        run = self.run_analysis({"interval": 1}, expect="failed")
        self.assertIn("more than 400 contour levels", run.error)
