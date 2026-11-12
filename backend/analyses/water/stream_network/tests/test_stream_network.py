"""Stream network on synthetic DEMs (needs WhiteboxTools)."""
import json
import unittest

import numpy as np

from apps.analysis.core.testing import AnalysisTestCase
from apps.analysis.engines import whitebox

M_PER_DEG = 111_000
# The DEM clip is the area plus 5 km; the synthetic DEM covers it at ~30 m, like Copernicus (no upsampling,
# which would make flat valley floors several cells wide and split one stream into parallel twins).
DEM_BBOX, DEM_SIZE = (34.03, 2.03, 34.47, 2.47), 1600


def seg_distance(lon, lat, a, b):
    """Distance in degrees from points to the segment a-b."""
    (x1, y1), (x2, y2) = a, b
    dx, dy = x2 - x1, y2 - y1
    t = np.clip(((lon - x1) * dx + (lat - y1) * dy) / (dx * dx + dy * dy), 0, 1)
    return np.hypot(lon - (x1 + t * dx), lat - (y1 + t * dy))


def valley(segments, slope_side=0.05, slope_down=0.01, tilt=0.002):
    """Elevation rising away from the valley segments and towards the north (water drains south).
    A slight eastward tilt keeps a perfectly symmetric valley floor one cell wide (no tie between two columns)."""
    def z(lon, lat):
        d = np.min([seg_distance(lon, lat, a, b) for a, b in segments], axis=0) * M_PER_DEG
        return 500 + d * slope_side + (lat - 2.0) * M_PER_DEG * slope_down + (lon - 34.0) * M_PER_DEG * tilt
    return z


@unittest.skipUnless(whitebox.available(), "WhiteboxTools is not installed")
class TestStreamNetwork(AnalysisTestCase):
    analysis_id = "stream_network"
    area_bbox = (34.1, 2.1, 34.4, 2.4)

    def setUp(self):
        # OSM waterways for the comparison: one 10 km river inside the area (and no network access in tests).
        path = self._tmp / "waterways.geojson"
        path.write_text(json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"waterway": "river"},
                                    "geometry": {"type": "LineString", "coordinates": [[34.25, 2.30], [34.25, 2.39]]}}]}))
        self.use_dataset("osm_waterways", path)

    def test_single_valley(self):
        self.synthetic_dataset("elevation", valley([((34.25, 1.9), (34.25, 2.6))]), bbox=DEM_BBOX, size=DEM_SIZE)
        run = self.run_analysis({"threshold_km2": 5})
        # A perfectly straight V-valley crosses the (slightly rotated) UTM grid columns, so where two floor cells
        # tie, D8 may run a short twin channel beside the main one (order 2 after they meet). Check the length.
        self.assertLessEqual(self.metric(run, "max_order"), 2)
        km = self.metric(run, "stream_km")
        self.assertGreater(km, 25)          # the area is 33 km tall; the stream starts once 5 km² drain to it
        self.assertLess(km, 45)
        by_order = {r["order"]: r["km"] for r in self.table(run, "by_order")}
        self.assertGreater(by_order[1], 20)  # the main stem
        self.assertTrue((run.workdir / self.output(run, "streams")["file"]).exists())

    def test_two_valleys_join(self):
        # Two valleys from the north-west and north-east join at (34.25, 2.25) and continue south.
        self.synthetic_dataset("elevation", valley([((34.0, 2.6), (34.25, 2.25)), ((34.5, 2.6), (34.25, 2.25)),
                                                    ((34.25, 2.25), (34.25, 1.9))]), bbox=DEM_BBOX, size=DEM_SIZE)
        run = self.run_analysis({"threshold_km2": 5})
        self.assertEqual(self.metric(run, "max_order"), 2)
        orders = {r["order"]: r["km"] for r in self.table(run, "by_order")}
        self.assertGreater(orders[1], orders[2])     # two tributaries, one shorter trunk inside the area
        self.assertGreater(self.metric(run, "drainage_density"), 0)
        self.assertAlmostEqual(self.metric(run, "osm_km"), 10, delta=0.3)
