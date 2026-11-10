"""Analysis platform and the OpenStreetMap module catalogue (vector, no network, no rasterio).

Fixture: a 0.5° box split into two admin units (West, East); OSM layers are local
GeoJSON files under DATA_DIR/datasets/osm_<layer>/UGA.geojson, and every other
layer is "unavailable" (fetch_layer patched), as when no extract can be reached.
"""
import json
import math
import tempfile
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.analysis import osm
from apps.analysis.models import Evidence, ModuleRun
from apps.analysis.registry import read_categories, read_manifests
from apps.boundaries.models import AdminUnit
from apps.projects.models import Indicator, Project, ProjectArea

TMP = Path(tempfile.mkdtemp(prefix="geida-test-"))
W, S, E, N = 34.0, 2.0, 34.5, 2.5
MID = 34.25
KM_PER_DEG = 2 * math.pi * 6_371_008.8 / 360 / 1000


def fc(features):
    return {"type": "FeatureCollection", "features": features}


def pt(lon, lat, **props):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": props}


def line(coords, **props):
    return {"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords}, "properties": props}


def square(lon, lat, size=0.0002, **props):
    ring = [[lon, lat], [lon + size, lat], [lon + size, lat + size], [lon, lat + size], [lon, lat]]
    return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]}, "properties": props}


def write(layer, data):
    d = TMP / "datasets" / layer
    d.mkdir(parents=True, exist_ok=True)
    (d / "UGA.geojson").write_text(json.dumps(data))


def make_data():
    write("osm_schools", fc([
        pt(34.1, 2.1, name="A Primary", amenity="school", **{"isced:level": "1", "osm_id": "node/1"}),
        pt(34.4, 2.4, name="B Nursery", amenity="kindergarten", osm_id="node/2"),
        pt(35.0, 3.0, name="Outside", amenity="school", osm_id="node/3")]))
    write("osm_health", fc([
        pt(34.2, 2.2, name="District Hospital", amenity="hospital", osm_id="node/10"),
        pt(34.3, 2.3, name="", healthcare="health_post", osm_id="node/11")]))
    houses = [square(34.1 + i * 0.001, 2.1, building="house", osm_id=f"way/{100 + i}") for i in range(30)]
    write("osm_buildings", fc(houses + [square(34.4, 2.4, building="yes", osm_id="way/200"),
                                        square(35.0, 3.0, building="house", osm_id="way/201")]))
    write("osm_roads", fc([
        line([[34.15, 2.25], [34.35, 2.25]], highway="primary", surface="asphalt", name="Main road", osm_id="way/300"),
        line([[34.1, 2.1], [34.1, 2.2]], highway="track", surface="dirt", osm_id="way/301"),
        line([[35.0, 3.0], [35.1, 3.0]], highway="primary", osm_id="way/302")]))
    write("osm_places", fc([pt(34.1, 2.1, name="Westville", place="village", osm_id="node/20"),
                            pt(34.4, 2.4, name="Easttown", place="town", population="12000", osm_id="node/21")]))


def unit(gid, name, level, w, e):
    AdminUnit.objects.create(gid=gid, level=level, iso3="UGA", country="Uganda", name=name,
                             geom=MultiPolygon(Polygon.from_bbox((w, S, e, N)), srid=4326))


@override_settings(DATA_DIR=TMP, MEDIA_ROOT=TMP / "media", CELERY_TASK_ALWAYS_EAGER=True)
class ModuleRunTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        make_data()
        call_command("load_cri", verbosity=0)
        cls.user = get_user_model().objects.create_user("o", "o@example.org", "pw-123456!")
        cls.p = Project.objects.create(code="UGA1072", title="t", country_iso3="UGA", country_name="Uganda",
                                       owner=cls.user, sector="education", stage="PPRR")
        box = Polygon.from_bbox((W, S, E, N))
        ProjectArea.objects.create(project=cls.p, method="draw", geom=MultiPolygon(box, srid=4326), area_km2=3090)
        Indicator.objects.create(project=cls.p, statement="Schools", cri_id="9.3", tier="project_cri", geo_role="verify")
        for level in (2, 3):
            unit(f"UGA.W.{level}", "West", level, W, MID)
            unit(f"UGA.E.{level}", "East", level, MID, E)

    def setUp(self):
        self.client.force_login(self.user)
        offline = mock.patch.object(osm, "fetch_layer", side_effect=osm.OSMUnavailable("offline (test)"))
        offline.start()
        self.addCleanup(offline.stop)

    def start(self, module, params=None):
        # Eager Celery: the task runs when the request's transaction commits.
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post("/api/analysis/runs/", json.dumps(
                {"project": "UGA1072", "module": module, "phase": "preparation", "params": params or {}}),
                content_type="application/json")
        self.assertEqual(r.status_code, 201, r.content)
        run = ModuleRun.objects.get(pk=r.json()["run"]["id"])
        self.assertEqual(run.status, "done", run.error + run.log)
        return run

    def out(self, run, name):
        return next(o for o in run.outputs if o["name"] == name)

    def metric(self, run, name):
        return self.out(run, name)["value"]

    # Catalogue ---------------------------------------------------------------------------
    def test_catalogue_has_categories_and_no_parked_modules(self):
        d = self.client.get("/api/analysis/modules/?project=UGA1072").json()
        ids = {m["id"]: m for m in d["modules"]}
        self.assertNotIn("area_baseline", ids)  # parked
        self.assertNotIn("terrain", ids)
        self.assertEqual([c["id"] for c in d["categories"]], [c["id"] for c in read_categories()])
        self.assertEqual(len(d["categories"]), 5)
        cats = {c["id"] for c in d["categories"]}
        self.assertTrue(all(m["category"] in cats for m in d["modules"]))
        self.assertEqual(sum(c["modules"] for c in d["categories"]), len(d["modules"]))
        self.assertEqual(ids["schools_inventory"]["availability"]["status"], "ready")
        self.assertEqual(ids["schools_inventory"]["cri_in_project"], ["9.3"])
        self.assertEqual(d["modules"][0]["id"], "schools_inventory")  # CRI match first

    def test_manifest_category_is_validated(self):
        bad = TMP / "bad_modules"
        (bad / "x").mkdir(parents=True, exist_ok=True)
        (bad / "categories.yaml").write_text("categories: [{id: social, title: Social}]")
        (bad / "x" / "run.py").write_text("def run(ctx): pass\n")
        (bad / "x" / "manifest.yaml").write_text("id: x\nversion: 1\ntitle: X\ncategory: nope\nphases: []\ninputs: {}\n")
        (bad / "_parked" / "y").mkdir(parents=True, exist_ok=True)
        with self.settings(MODULES_DIR=bad), self.assertRaisesMessage(ValueError, "category 'nope'"):
            read_manifests()
        (bad / "x" / "manifest.yaml").write_text("id: x\nversion: 1\ntitle: X\ncategory: social\nphases: []\ninputs: {}\n")
        with self.settings(MODULES_DIR=bad):
            self.assertEqual(list(read_manifests()), ["x"])

    def test_parked_module_runs_stay_viewable(self):
        from apps.analysis.models import Module
        m = Module.objects.create(id="terrain", version="0.1.0", title="Terrain", manifest={}, active=True)
        run = ModuleRun.objects.create(project=self.p, module=m, module_version="0.1.0", phase="preparation",
                                       status="done", created_by=self.user)
        self.client.get("/api/analysis/modules/")  # sync deactivates the parked module
        m.refresh_from_db()
        self.assertFalse(m.active)
        self.assertEqual(self.client.get(f"/api/analysis/runs/{run.id}/").status_code, 200)
        listed = self.client.get("/api/analysis/runs/?project=UGA1072").json()["runs"]
        self.assertIn(run.id, [r["id"] for r in listed])

    # Modules -----------------------------------------------------------------------------
    def test_schools_inventory(self):
        run = self.start("schools_inventory", {"zone_level": 3})
        self.assertEqual(self.metric(run, "count"), 2)
        self.assertEqual(self.metric(run, "zones_without"), 0)
        kinds = {r["kind"]: r["count"] for r in self.out(run, "by_kind")["rows"]}
        self.assertEqual(kinds, {"Primary": 1, "Pre-primary": 1})
        per_zone = self.out(run, "per_zone")["rows"]
        self.assertEqual(sum(r["count"] for r in per_zone), 2)
        rows = self.out(run, "list")["rows"]
        self.assertEqual({r["name"]: r["zone"] for r in rows}, {"A Primary": "West", "B Nursery": "East"})
        self.assertEqual(rows[0]["osm_id"][:5], "node/")
        ev = Evidence.objects.get(run=run)
        self.assertEqual((ev.cri_code, ev.value, ev.role, ev.status), ("9.3", 2, "verify", "proposed"))
        self.assertIsNotNone(ev.indicator)
        f = self.out(run, "points")["file"]
        self.assertEqual(self.client.get(f"/api/analysis/runs/{run.id}/files/{f}").status_code, 200)
        gj = json.loads((run.workdir / f).read_text())
        self.assertEqual(len(gj["features"]), 2)
        self.assertEqual(self.client.get(f"/api/analysis/runs/{run.id}/files/../../x").status_code, 404)

    def test_health_inventory(self):
        run = self.start("health_inventory")
        self.assertEqual(self.metric(run, "count"), 2)
        kinds = {r["kind"]: r["count"] for r in self.out(run, "by_kind")["rows"]}
        self.assertEqual(kinds, {"Hospital": 1, "Health post": 1})
        self.assertEqual(Evidence.objects.get(run=run).cri_code, "8.1")
        self.assertIn("1 is a hospital", run.summary)

    def test_buildings(self):
        run = self.start("buildings", {"cell_m": 500, "zone_level": 2})
        self.assertEqual(self.metric(run, "count"), 31)
        per_zone = {r["zone"]: r["buildings"] for r in self.out(run, "per_zone")["rows"]}
        self.assertEqual(per_zone, {"West": 30, "East": 1})
        kinds = {r["kind"]: r["count"] for r in self.out(run, "by_kind")["rows"]}
        self.assertEqual(kinds, {"Residential": 30, "Not specified": 1})
        side_m = 0.0002 * KM_PER_DEG * 1000
        expected = 31 * side_m * side_m * math.cos(math.radians(2.1))
        self.assertAlmostEqual(self.metric(run, "mean_m2"), expected / 31, delta=expected / 31 * 0.02)
        density = self.out(run, "density")
        self.assertEqual(density["style"]["property"], "buildings")
        cells = json.loads((run.workdir / density["file"]).read_text())["features"]
        self.assertEqual(sum(c["properties"]["buildings"] for c in cells), 31)
        self.assertEqual(self.out(run, "footprints")["title"], "Building footprints")
        self.assertFalse(Evidence.objects.filter(run=run).exists())

    def test_road_network(self):
        run = self.start("road_network", {"zone_level": 2})
        primary = 0.2 * KM_PER_DEG * math.cos(math.radians(2.25))
        track = 0.1 * KM_PER_DEG
        self.assertAlmostEqual(self.metric(run, "km"), primary + track, delta=0.2)
        self.assertAlmostEqual(self.metric(run, "major_km"), primary, delta=0.2)
        self.assertEqual(self.metric(run, "paved_share"), round(primary / (primary + track) * 100))
        per_zone = {r["zone"]: r for r in self.out(run, "per_zone")["rows"]}
        self.assertAlmostEqual(per_zone["East"]["km"], primary / 2, delta=0.1)
        self.assertAlmostEqual(per_zone["West"]["km"] + per_zone["East"]["km"], primary + track, delta=0.2)
        by_class = {r["class"]: r for r in self.out(run, "by_class")["rows"]}
        self.assertAlmostEqual(by_class["Track"]["unpaved_km"], track, delta=0.1)
        roads = json.loads((run.workdir / "roads.geojson").read_text())["features"]
        self.assertEqual(len(roads), 2)  # the one outside is dropped
        self.assertEqual(Evidence.objects.get(run=run).cri_code, "2.2")

    def test_area_profile(self):
        run = self.start("area_profile", {"zone_level": 2})
        inv = {r["layer"]: r["value"] for r in self.out(run, "inventory")["rows"]}
        self.assertEqual(inv["Schools"], 2)
        self.assertEqual(inv["Health facilities"], 2)
        self.assertEqual(inv["Named places"], 2)
        self.assertIn("Roads", inv)
        self.assertNotIn("Markets", inv)  # unavailable layers are skipped and named in the summary
        self.assertIn("Not available: ", run.summary)
        places = self.out(run, "place_list")["rows"]
        self.assertEqual([p["name"] for p in places], ["Easttown", "Westville"])  # towns before villages
        self.assertEqual(self.metric(run, "places"), 2)
        layers = {o["name"]: o for o in run.outputs if o["type"] == "vector"}
        self.assertEqual(layers["layer_roads"]["style"]["shape"], "line")
        self.assertEqual(layers["layer_schools"]["style"]["shape"], "point")
        self.assertNotEqual(layers["layer_schools"]["style"]["color"], layers["layer_health"]["style"]["color"])
        roads = json.loads((run.workdir / layers["layer_roads"]["file"]).read_text())["features"]
        self.assertEqual(len(roads), 2)  # the road outside the area is dropped
        self.assertEqual(roads[0]["properties"]["highway"], "primary")

    def test_rerun_is_identical(self):
        a, b = self.start("road_network"), self.start("road_network")
        self.assertEqual(self.out(a, "by_class")["rows"], self.out(b, "by_class")["rows"])

    def test_permissions(self):
        other = get_user_model().objects.create_user("x", "x@example.org", "pw-123456!")
        self.client.force_login(other)
        r = self.client.post("/api/analysis/runs/", json.dumps(
            {"project": "UGA1072", "module": "schools_inventory", "phase": "preparation", "params": {}}),
            content_type="application/json")
        self.assertEqual(r.status_code, 404)  # draft is invisible to others


class QueueTests(TestCase):
    def test_broker_down_marks_run_failed(self):
        from unittest import mock

        from apps.analysis import tasks
        from apps.analysis.models import Module

        user = get_user_model().objects.create_user("q", "q@example.org", "pw-123456!")
        p = Project.objects.create(code="UGA2000", title="t", country_iso3="UGA", country_name="Uganda", owner=user)
        m = Module.objects.create(id="area_baseline", version="0.1.0", title="x")
        run = ModuleRun.objects.create(project=p, module=m, module_version="0.1.0", phase="preparation")
        with mock.patch.object(tasks.run_module, "delay", side_effect=ConnectionError("refused")):
            self.assertIsNotNone(tasks.enqueue(run))
        run.refresh_from_db()
        self.assertEqual(run.status, "failed")
        self.assertIn("Redis", run.error)

    def test_claim_is_exclusive(self):
        from apps.analysis.models import Module
        from apps.analysis.tasks import claim

        user = get_user_model().objects.create_user("c", "c@example.org", "pw-123456!")
        p = Project.objects.create(code="UGA2001", title="t", country_iso3="UGA", country_name="Uganda", owner=user)
        m = Module.objects.create(id="area_baseline", version="0.1.0", title="x")
        run = ModuleRun.objects.create(project=p, module=m, module_version="0.1.0", phase="preparation")
        self.assertIsNotNone(claim(run.pk))
        self.assertIsNone(claim(run.pk))  # second worker gets nothing
        self.assertIsNotNone(claim(run.pk, redelivered=True))  # redelivery after a worker died
