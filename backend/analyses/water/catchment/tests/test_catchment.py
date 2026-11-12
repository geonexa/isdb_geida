"""Catchment from a point on synthetic DEMs with a known catchment (needs WhiteboxTools)."""
import json
import unittest

import numpy as np

from apps.analysis.core.testing import AnalysisTestCase
from apps.analysis.engines import whitebox
from analyses.water.stream_network.tests.test_stream_network import DEM_BBOX, DEM_SIZE, M_PER_DEG, seg_distance

D_DEG = 0.04          # ridge distance from the upper valley


def basin(top, outlet_lat=2.22, slope_side=0.05, slope_down=0.01, tilt=0.002):
    """
    A closed valley from (34.25, top) down to (34.25, outlet_lat), walled by a ridge D_DEG from it, then an open valley
    continuing south. Land within D_DEG of the upper valley drains to the outlet; land beyond the ridge drains away.
    Expected catchment: about the 'stadium' of radius D_DEG around the upper valley, without its southern half-disc.
    """
    up, down = ((34.25, outlet_lat), (34.25, top)), ((34.25, 1.8), (34.25, outlet_lat))
    d_m = D_DEG * M_PER_DEG

    def z(lon, lat):
        du = seg_distance(lon, lat, *up) * M_PER_DEG
        dd = seg_distance(lon, lat, *down) * M_PER_DEG
        tent = slope_side * np.clip(np.minimum(du, 2 * d_m - du), 0, None)
        return 500 + (lat - 2.0) * M_PER_DEG * slope_down + (lon - 34.0) * M_PER_DEG * tilt + np.minimum(tent, slope_side * dd)
    return z


def expected_km2(top, outlet_lat=2.22):
    length = (top - outlet_lat) * M_PER_DEG / 1000
    r = D_DEG * M_PER_DEG / 1000
    return length * 2 * r + np.pi * r * r / 2


@unittest.skipUnless(whitebox.available(), "WhiteboxTools is not installed")
class TestCatchment(AnalysisTestCase):
    analysis_id = "catchment"
    area_bbox = (34.1, 2.1, 34.4, 2.4)

    def test_closed_valley(self):
        self.synthetic_dataset("elevation", basin(top=2.36), bbox=DEM_BBOX, size=DEM_SIZE)
        run = self.run_analysis({"outlet": [34.252, 2.223], "snap_m": 300})     # about 220 m east of the stream
        area = self.metric(run, "area_km2")
        self.assertAlmostEqual(area, expected_km2(2.36), delta=0.2 * expected_km2(2.36))
        profile = {r["measure"]: r for r in self.table(run, "profile")}
        lon, lat = (float(v) for v in profile["Outlet on the stream"]["value"].split(","))
        self.assertAlmostEqual(lon, 34.25, delta=0.001)                          # moved onto the valley floor
        self.assertIn("moved", profile["Outlet on the stream"]["note"])
        self.assertGreater(self.metric(run, "in_area_share"), 95)
        self.assertEqual({o["name"] for o in run.outputs},             # catchment only: no rainfall, ETa, land cover or people
                         {"area_km2", "in_area_share", "mean_slope", "profile", "catchment", "streams", "outlet_point"})
        self.assertGreater(profile["Longest flow path"]["value"], 15)            # the valley is 15.5 km long
        self.assertIn("Time of concentration (Kirpich)", profile)
        poly = json.loads((run.workdir / self.output(run, "catchment")["file"]).read_text())
        self.assertEqual(len(poly["features"]), 1)
        self.assertNotIn("larger", run.summary)

    def test_clip_grows_to_fit_the_catchment(self):
        # The valley runs to 2.62, beyond the first clip (area + 5 km reaches 2.445): the clip must grow northwards.
        self.synthetic_dataset("elevation", basin(top=2.62), bbox=(33.95, 1.95, 34.75, 2.75), size=2700)
        run = self.run_analysis({"outlet": [34.25, 2.222]})
        self.assertIn("reaches the clip edge (n)", run.log)
        self.assertAlmostEqual(self.metric(run, "area_km2"), expected_km2(2.62), delta=0.2 * expected_km2(2.62))
        self.assertLess(self.metric(run, "in_area_share"), 60)
        self.assertNotIn("larger", run.summary)

    def test_needs_an_outlet(self):
        run = self.run_analysis({}, expect="failed")
        self.assertIn("pick a point on the map", run.error)

    def test_point_off_the_stream(self):
        # About 900 m east of the valley floor, on the slope.
        self.synthetic_dataset("elevation", basin(top=2.36), bbox=DEM_BBOX, size=DEM_SIZE)
        run = self.run_analysis({"outlet": [34.258, 2.25]})                     # nearest stream within 300 m: none
        self.assertIn("isn't on a stream", run.summary)
        self.assertLess(self.metric(run, "area_km2"), 1)
        warning = self.table(run, "profile")[0]
        self.assertEqual(warning["measure"], "Warning")
        self.assertIn("west", warning["note"])                                   # the valley is to the west
        # Snapping to the largest stream within 1.5 km lands in the valley and finds the catchment above it.
        run = self.run_analysis({"outlet": [34.258, 2.25], "snap_to": "largest", "snap_m": 1500})
        self.assertNotIn("isn't on a stream", run.summary)
        self.assertGreater(self.metric(run, "area_km2"), 50)
