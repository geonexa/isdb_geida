"""Site suitability on synthetic layers with a known answer."""
import json

import numpy as np

from apps.analysis.core.manifest import parse_criteria
from apps.analysis.core.testing import AnalysisTestCase

LAYERS = [{"id": "slope", "label": "Slope", "kind": "range", "unit": "°"},
          {"id": "landcover", "label": "Land cover", "kind": "classes",
           "classes": [{"value": 30, "label": "Grassland"}, {"value": 40, "label": "Cropland"}]}]


class TestSuitability(AnalysisTestCase):
    analysis_id = "suitability"

    def setUp(self):
        # Elevation rises from 50 m in the west to 550 m in the east (gentle slope); cropland in the north half.
        self.synthetic_dataset("elevation", lambda lon, lat: 50 + 1000 * (lon - 34.0), bbox=(33.9, 1.9, 34.6, 2.6), size=1400)
        self.synthetic_dataset("landcover", lambda lon, lat: np.where(lat > 2.25, 40.0, 30.0), bbox=(33.9, 1.9, 34.6, 2.6), size=700)

    def test_must_have_and_weights(self):
        run = self.run_analysis({"criteria": [
            {"layer": "elevation", "min": 300, "weight": 0, "must": True},     # the east half (lon >= 34.25)
            {"layer": "landcover", "classes": [40], "weight": 50, "must": False},
            {"layer": "slope", "max": 10, "weight": 50, "must": False}], "min_score": 100, "min_site_km2": 1})
        self.assertAlmostEqual(self.metric(run, "suitable_share"), 25, delta=3)    # east and north: a quarter
        self.assertAlmostEqual(self.metric(run, "excluded_share"), 50, delta=3)    # the west half fails the must-have
        classes = {r["class"]: r["share"] for r in self.table(run, "classes")}
        self.assertAlmostEqual(classes["All conditions met (100%)"], 25, delta=3)
        self.assertAlmostEqual(classes["Moderate (50–74%)"], 25, delta=3)          # east and south: slope only
        crit = {r["condition"]: r for r in self.table(run, "criteria")}
        self.assertAlmostEqual(crit["Land cover (ESA WorldCover): Cropland"]["met_share"], 50, delta=3)
        self.assertEqual(crit["Slope ≤ 10°"]["met_share"], 100.0)
        sites = self.table(run, "sites")
        self.assertEqual(len(sites), 1)                                             # one connected block
        self.assertAlmostEqual(sites[0]["lon"], 34.375, delta=0.02)
        self.assertAlmostEqual(sites[0]["lat"], 2.375, delta=0.02)
        polys = json.loads((run.workdir / self.output(run, "site_polygons")["file"]).read_text())
        self.assertEqual(len(polys["features"]), 1)

    def test_distance_to_roads(self):
        # One road along lon 34.25: within 2 km of it is a strip about 4 km wide in a ~55 km wide area.
        path = self._tmp / "roads.geojson"
        path.write_text(json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"highway": "primary"},
                                    "geometry": {"type": "LineString", "coordinates": [[34.25, 1.95], [34.25, 2.55]]}}]}))
        self.use_dataset("osm_roads", path)
        run = self.run_analysis({"criteria": [{"layer": "dist_roads", "max": 2, "weight": 1, "must": False}],
                                 "min_score": 100, "min_site_km2": 0})
        self.assertAlmostEqual(self.metric(run, "suitable_share"), 4 / 55.6 * 100, delta=1.5)

    def test_criteria_are_checked(self):
        ok, problem = parse_criteria([{"layer": "slope", "max": 10, "weight": 2}], LAYERS)
        self.assertIsNone(problem)
        self.assertEqual(ok[0], {"layer": "slope", "weight": 2.0, "must": False, "min": None, "max": 10.0})
        for rows, msg in (([], "at least one"), ([{"layer": "nope"}], "choose a layer"),
                          ([{"layer": "slope", "weight": 1}], "minimum, a maximum"),
                          ([{"layer": "slope", "min": 9, "max": 3, "weight": 1}], "above the maximum"),
                          ([{"layer": "landcover", "classes": [99], "weight": 1}], "at least one class"),
                          ([{"layer": "slope", "max": 5, "weight": 0}], "weight")):
            self.assertIsNone(parse_criteria(rows, LAYERS)[0])
            self.assertIn(msg, parse_criteria(rows, LAYERS)[1])
        # The run form sends JSON text; the API accepts it.
        self.assertIsNone(parse_criteria(json.dumps([{"layer": "slope", "max": 5, "must": True}]), LAYERS)[1])
