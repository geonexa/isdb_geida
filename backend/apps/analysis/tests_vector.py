"""Vector helpers: projection, zone assignment, nearest, bands, lengths, grid, output."""
import json
import math
import tempfile
from pathlib import Path

import numpy as np
import shapely
from django.test import SimpleTestCase

from apps.analysis.ops import vector

TMP = Path(tempfile.mkdtemp(prefix="geida-vector-test-"))
M_PER_DEG = 2 * math.pi * vector.R / 360


def box(w, s, e, n):
    return {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}


# Two units side by side: west 34.0–34.25, east 34.25–34.5, latitude 2.0–2.5.
ZONES = [(1, "W", "West", box(34.0, 2.0, 34.25, 2.5)), (2, "E", "East", box(34.25, 2.0, 34.5, 2.5))]


class VectorTests(SimpleTestCase):
    def setUp(self):
        self.frame = vector.Frame(34.25, 2.25)
        self.zones = vector.Zones(ZONES, self.frame)

    def pts(self, coords):
        return shapely.points(self.frame.lonlat_to_m(coords))

    def test_projection_round_trip_and_scale(self):
        g = self.frame.to_m(np.array([shapely.Point(34.3, 2.4)], dtype=object))
        back = self.frame.to_deg(g)[0]
        self.assertAlmostEqual(back.x, 34.3, places=9)
        self.assertAlmostEqual(back.y, 2.4, places=9)
        # 0.1° of latitude ≈ 11.12 km
        a, b = self.pts([[34.25, 2.25], [34.25, 2.35]])
        self.assertAlmostEqual(shapely.distance(a, b), 0.1 * M_PER_DEG, delta=5)

    def test_zone_areas_equal_area(self):
        expected = 0.25 * 0.5 * M_PER_DEG ** 2 * math.cos(math.radians(2.25)) / 1e6
        for a in self.zones.area_km2:
            self.assertAlmostEqual(a, expected, delta=expected * 0.002)

    def test_assign_and_count(self):
        pts = self.pts([[34.1, 2.1], [34.2, 2.3], [34.4, 2.4], [35.0, 3.0]])
        z = self.zones.assign(pts)
        self.assertEqual(z.tolist(), [1, 1, 2, 0])
        counts = self.zones.count(z)
        self.assertEqual(counts[1], 2)
        self.assertEqual(counts[2], 1)
        self.assertEqual(counts[1:].sum() + counts[0], 4)

    def test_assign_polygons_by_surface_point(self):
        poly = self.frame.to_m(np.array([shapely.geometry.shape(box(34.3, 2.3, 34.31, 2.31))], dtype=object))
        self.assertEqual(self.zones.assign(poly).tolist(), [2])

    def test_border_point_counted_once(self):
        z = self.zones.assign(self.pts([[34.25, 2.25]]))
        self.assertIn(z[0], (1, 2))

    def test_nearest_and_bands(self):
        src = self.pts([[34.25, 2.25], [34.25, 2.27], [34.25, 2.30]])
        targets = self.pts([[34.25, 2.25]])
        idx, d = vector.nearest(src, targets)
        self.assertEqual(idx.tolist(), [0, 0, 0])
        self.assertAlmostEqual(d[1], 0.02 * M_PER_DEG, delta=3)
        bands = vector.band_index(d, [1000, 5000])
        self.assertEqual(bands.tolist(), [0, 1, 2])
        self.assertEqual(vector.band_labels([1000, 5000]), ["≤ 1 km", "1 km–5 km", "> 5 km"])
        none_idx, none_d = vector.nearest(src, np.empty(0, dtype=object))
        self.assertEqual(none_idx.tolist(), [-1, -1, -1])
        self.assertTrue(np.isinf(none_d).all())

    def test_within(self):
        src = self.pts([[34.25, 2.25], [34.25, 2.30]])
        self.assertEqual(vector.within(src, self.pts([[34.25, 2.255]]), 1000).tolist(), [True, False])

    def test_length_by_zone_and_class(self):
        # A 0.2° east-west line crossing the border at the middle.
        line = self.frame.to_m(np.array([shapely.LineString([(34.15, 2.25), (34.35, 2.25)])], dtype=object))
        m = self.zones.measure(line, classes=["primary"])
        half = 0.1 * M_PER_DEG * math.cos(math.radians(2.25)) / 1e3
        self.assertAlmostEqual(m[1]["primary"], half, delta=half * 0.002)
        self.assertAlmostEqual(m[2]["primary"], half, delta=half * 0.002)

    def test_clip_keeps_original_dimension(self):
        lines = self.frame.to_m(np.array([shapely.LineString([(33.9, 2.25), (34.1, 2.25)]),
                                          shapely.LineString([(35.0, 3.0), (35.1, 3.0)])], dtype=object))
        idx, cut = vector.clip(lines, self.zones.union)
        self.assertEqual(idx.tolist(), [0])
        self.assertEqual(shapely.get_type_id(cut[0]), 1)  # LineString

    def test_grid_counts(self):
        pts = self.pts([[34.25 + i * 0.0001, 2.25] for i in range(10)] + [[34.4, 2.4]])
        cells, counts = vector.grid_counts(pts, 1000, clip=self.zones.union)
        self.assertEqual(int(counts.sum()), 11)
        self.assertEqual(len(cells), len(counts))

    def test_read_and_write_geojson(self):
        src = TMP / "in.geojson"
        src.write_text(json.dumps({"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [34.1, 2.1]}, "properties": {"name": "A", "osm_id": "node/1"}},
            {"type": "Feature", "geometry": None, "properties": {}}]}))
        layer = vector.read(src, self.frame)
        self.assertEqual(len(layer), 1)
        out = vector.write_geojson(TMP / "out.geojson", self.frame, layer.geoms, [{"n": np.int64(3)}])
        f = json.loads(Path(out).read_text())["features"][0]
        self.assertEqual(f["geometry"]["coordinates"], [34.1, 2.1])
        self.assertEqual(f["properties"]["n"], 3)
        self.assertEqual(vector.osm_url("node/1"), "https://www.openstreetmap.org/node/1")
        lon, lat = vector.lonlat(self.frame, layer.geoms)
        self.assertAlmostEqual(lon[0], 34.1, places=6)
