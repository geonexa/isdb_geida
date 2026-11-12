"""Access to services with synthetic population and facility points."""
import json

import numpy as np

from apps.analysis.core.testing import AnalysisTestCase


class TestServiceAccess(AnalysisTestCase):
    analysis_id = "service_access"
    area_bbox = (34.0, 2.0, 34.2, 2.2)

    def setUp(self):
        self.synthetic_dataset("worldpop", lambda lon, lat: np.full_like(lon, 2.0), year=2025)
        self.synthetic_dataset("worldpop_age_5_14", lambda lon, lat: np.full_like(lon, 0.6), year=2025)

    def write(self, dataset, coords):
        feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": c}, "properties": {"name": f"S{i}"}}
                 for i, c in enumerate(coords)]
        path = self._tmp / f"{dataset}.geojson"
        path.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
        self.use_dataset(dataset, path)

    def test_one_school_in_the_middle(self):
        self.write("osm_schools", [[34.1, 2.1]])
        run = self.run_analysis({"threshold_km": 5})
        # Area ~22 x 22 km, school in the centre: a 5 km disc covers pi*25 / 490 = 16% of people
        self.assertAlmostEqual(self.metric(run, "within_share"), 100 * np.pi * 25 / (22.2 * 22.1), delta=1.5)
        self.assertEqual(self.metric(run, "facilities"), 1)
        self.assertGreater(self.metric(run, "mean_distance"), 5)
        bands = self.table(run, "bands")
        self.assertEqual(bands[-1]["cumulative"], 100)
        # School-age children: same share, a third of the people beyond
        kids = self.run_analysis({"threshold_km": 5, "population_dataset": "worldpop_age_5_14"})
        self.assertAlmostEqual(self.metric(kids, "within_share"), self.metric(run, "within_share"), delta=0.5)
        self.assertAlmostEqual(self.metric(kids, "people_beyond") / self.metric(run, "people_beyond"), 0.3, delta=0.01)
        self.assertIn("School-age children", self.output(kids, "within_share")["title"])

    def test_service_outside_the_area_and_none(self):
        self.write("osm_health", [[34.25, 2.1]])          # 5.5 km east of the area's edge
        run = self.run_analysis({"facilities_dataset": "osm_health", "threshold_km": 2})
        self.assertEqual(self.metric(run, "within_share"), 0)
        self.assertEqual(self.metric(run, "facilities"), 0)
        self.write("osm_markets", [[35.5, 2.1]])          # far away, outside the 10 km search box
        run = self.run_analysis({"facilities_dataset": "osm_markets"}, expect="failed")
        self.assertIn("within 10 km", run.error)
