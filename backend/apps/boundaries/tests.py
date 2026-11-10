from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.cache import cache
from django.test import TestCase

from .models import AdminUnit
from .views import WORLD_CACHE_KEY


def square(x, y, size):
    return Polygon.from_bbox((x, y, x + size, y + size))


class WorldOutlineTests(TestCase):
    """GET /api/boundaries/world/: every country, simplified for globe-scale maps."""

    @classmethod
    def setUpTestData(cls):
        # A country with a big mainland and a tiny island; a region (level 1) that must not appear.
        geom = MultiPolygon(square(30, 0, 4), square(40, 0, 0.1), srid=4326)
        AdminUnit.objects.create(gid="UGA", level=0, iso3="UGA", country="Uganda", name="Uganda", geom=geom, geom_display=geom)
        AdminUnit.objects.create(gid="UGA.1_1", level=1, iso3="UGA", country="Uganda", name="Central",
                                 geom=MultiPolygon(square(31, 0, 1), srid=4326))

    def setUp(self):
        cache.delete(WORLD_CACHE_KEY)

    def test_countries_only_with_tiny_islands_dropped(self):
        data = self.client.get("/api/boundaries/world/").json()
        self.assertEqual([f["id"] for f in data["features"]], ["UGA"])
        f = data["features"][0]
        self.assertEqual(f["properties"], {"gid": "UGA", "name": "Uganda"})
        self.assertEqual(f["geometry"]["type"], "MultiPolygon")
        self.assertEqual(len(f["geometry"]["coordinates"]), 1)  # the 0.01 deg² island is gone

    def test_coordinates_on_a_tenth_degree_grid(self):
        coords = self.client.get("/api/boundaries/world/").json()["features"][0]["geometry"]["coordinates"]
        for x, y in coords[0][0]:
            self.assertEqual(round(x, 1), x)
            self.assertEqual(round(y, 1), y)
