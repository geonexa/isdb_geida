"""Field boundaries on a synthetic set of square fields."""
import json
import math

from apps.analysis.core.testing import AnalysisTestCase

M_PER_DEG = 111_320


def square(lon, lat, side_m):
    d_lon = side_m / (M_PER_DEG * math.cos(math.radians(lat)))
    d_lat = side_m / 110_574
    return {"type": "Polygon", "coordinates": [[[lon, lat], [lon + d_lon, lat], [lon + d_lon, lat + d_lat],
                                                [lon, lat + d_lat], [lon, lat]]]}


class TestFieldBoundaries(AnalysisTestCase):
    analysis_id = "field_boundaries"

    def write_fields(self, fields):
        feats = [{"type": "Feature", "geometry": square(lon, lat, side), "properties": {"score": score, "area_m2": side * side}}
                 for lon, lat, side, score in fields]
        path = self._tmp / "fields.geojson"
        path.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
        self.use_dataset("ftw_fields_2025", path)

    def test_counts_sizes_and_score(self):
        # 100 fields of 1 ha (100 m sides) and 10 of 25 ha (500 m sides) inside; 5 outside the area; 20 with low score.
        fields = [(34.01 + 0.004 * (i % 10), 2.01 + 0.004 * (i // 10), 100, 80) for i in range(100)]
        fields += [(34.3 + 0.01 * i, 2.3, 500, 90) for i in range(10)]
        fields += [(34.6 + 0.01 * i, 2.2, 100, 90) for i in range(5)]
        fields += [(34.2, 2.2 + 0.002 * i, 100, 5) for i in range(20)]
        self.write_fields(fields)
        run = self.run_analysis({"min_score": 10})
        self.assertEqual(self.metric(run, "field_count"), 110)
        self.assertAlmostEqual(self.metric(run, "field_area"), (100 * 1e4 + 10 * 25e4) / 1e6, delta=0.01)
        self.assertAlmostEqual(self.metric(run, "median_size"), 1.0, delta=0.01)
        sizes = {r["label"]: r["fields"] for r in self.table(run, "size_classes")}
        self.assertEqual(sizes["1–2 ha"], 100)
        self.assertEqual(sizes["10–50 ha"], 10)
        self.assertTrue((run.workdir / self.output(run, "fields")["file"]).exists())
        density = json.loads((run.workdir / self.output(run, "density")["file"]).read_text())
        self.assertGreater(len(density["features"]), 0)
        run = self.run_analysis({"min_score": 0})
        self.assertEqual(self.metric(run, "field_count"), 130)

    def test_no_fields(self):
        self.write_fields([(34.8, 2.8, 100, 90)])
        run = self.run_analysis()
        self.assertEqual(self.metric(run, "field_count"), 0)
        self.assertIn("doesn't prove", run.summary)
