"""Settlements on synthetic GHSL layers and OSM places."""
import json

import numpy as np

from apps.analysis.core.testing import AnalysisTestCase


class TestSettlements(AnalysisTestCase):
    analysis_id = "settlements"

    def setUp(self):
        # A town (urban centre, 30 people per cell) in the north-west quarter; low-density rural elsewhere (1 per cell).
        town = lambda lon, lat: (lon < 34.25) & (lat > 2.25)   # noqa: E731
        self.synthetic_dataset("ghsl_pop", lambda lon, lat: np.where(town(lon, lat), 30.0, 1.0), year=2020)
        self.synthetic_dataset("ghsl_smod", lambda lon, lat: np.where(town(lon, lat), 30, 12), year=2020)
        feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": c}, "properties": {"name": n, "place": p}}
                 for c, n, p in (([34.12, 2.38], "Big Town", "town"), ([34.4, 2.1], "Small Village", "village"),
                                 ([35.5, 2.1], "Far Away", "village"))]
        path = self._tmp / "places.geojson"
        path.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
        self.use_dataset("osm_places", path)

    def test_shares_and_places(self):
        run = self.run_analysis()
        # people: town 1/4 of the area at 30, rest 3/4 at 1 -> urban share 30 / (30 + 3) = 91%
        self.assertAlmostEqual(self.metric(run, "urban_share"), 100 * 30 / 33, delta=1.5)
        self.assertAlmostEqual(self.metric(run, "rural_share"), 100 * 3 / 33, delta=1.5)
        self.assertEqual(self.metric(run, "places_count"), 2)   # "Far Away" is outside the area
        places = self.table(run, "places")
        self.assertEqual(places[0]["name"], "Big Town")
        self.assertEqual(places[0]["class"], "Urban centre")
        self.assertGreater(places[0]["people_1km"], places[1]["people_1km"])
        self.assertEqual({i["label"] for i in self.output(run, "smod")["legend"]}, {"Urban centre", "Low density rural"})
