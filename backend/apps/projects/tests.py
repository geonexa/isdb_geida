import io
import json
import zipfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase

from .models import Project

KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
<Placemark><name>World</name><Polygon><outerBoundaryIs><LinearRing><coordinates>
-180,-85,0 180,-85,0 180,85,0 -180,85,0 -180,-85,0</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>
<Placemark><name>Site</name><Polygon><outerBoundaryIs><LinearRing><coordinates>
47.1,40.5,0 47.7,40.5,0 47.7,40.8,0 47.1,40.8,0 47.1,40.5,0</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>
</Document></kml>"""


class OnboardingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_cri", verbosity=0)
        U = get_user_model()
        cls.editor = U.objects.create_user("ed", "ed@example.org", "pw-123456!")
        cls.other = U.objects.create_user("ot", "ot@example.org", "pw-123456!")
        cls.reviewer = U.objects.create_user("rv", "rv@example.org", "pw-123456!", is_staff=True)

    def setUp(self):
        self.client.force_login(self.editor)

    def post(self, url, body, method="post"):
        return getattr(self.client, method)(url, json.dumps(body), content_type="application/json")

    def create(self, code="AZE1028"):
        r = self.post("/api/projects/", {"code": code, "title": "Karabakh canal", "country_iso3": "AZE"})
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()["project"]

    def test_create_and_duplicate(self):
        p = self.create()
        self.assertEqual(p["status"], "draft")
        self.assertEqual(p["country_name"], "Azerbaijan")
        self.assertEqual(set(p["missing_to_submit"]), {"sector", "stage", "area"})
        r = self.post("/api/projects/", {"code": "aze1028", "title": "x", "country_iso3": "AZE"})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["exists"]["code"], "AZE1028")

    def test_validation(self):
        r = self.post("/api/projects/", {"code": "12", "title": "", "country_iso3": "FRA"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.json()["errors"]), {"code", "title", "country_iso3"})

    def test_upload_ignores_world_placeholder(self):
        self.create()
        f = SimpleUploadedFile("site.kml", KML.encode())
        r = self.client.post("/api/projects/AZE1028/area/", {"file": f})
        self.assertEqual(r.status_code, 200, r.content)
        area = r.json()["project"]["area"]
        self.assertLess(area["area_km2"], 2000)
        self.assertTrue(any("whole world" in n for n in area["notes"]))

    def test_buffer_and_repair(self):
        r = self.post("/api/projects/area/preview/", {"method": "buffer", "lon": 6.39, "lat": 9.64, "km": 5})
        self.assertAlmostEqual(r.json()["area_km2"], 78.4, delta=1)
        bowtie = {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]}
        r = self.post("/api/projects/area/preview/", {"method": "draw", "geometry": bowtie})
        self.assertTrue(any("Repaired" in n for n in r.json()["notes"]))

    def test_indicators_defaults_and_warnings(self):
        self.create()
        r = self.post("/api/projects/AZE1028/indicators/", {"indicators": [
            {"cri": "3.2", "unit": "ha"}, {"cri": "17.4"}, {"statement": "Farmers trained"}]}, "put")
        ind = r.json()["project"]["indicators"]
        self.assertEqual([i["tier"] for i in ind], ["project_cri", "ta_cri", "project_specific"])
        self.assertEqual(ind[0]["geo_role"], "measure")
        self.assertTrue(any("km2" in w for w in ind[0]["warnings"]))

    def test_review_workflow_and_visibility(self):
        self.create()
        self.post("/api/projects/AZE1028/", {"sector": "agriculture", "stage": "PIASR"}, "patch")
        r = self.post("/api/projects/AZE1028/submit/", {})
        self.assertEqual(r.status_code, 400)  # no area yet
        self.post("/api/projects/area/preview/", {})
        self.post("/api/projects/AZE1028/area/", {"method": "buffer", "lon": 47.4, "lat": 40.6, "km": 3})
        self.assertEqual(self.post("/api/projects/AZE1028/submit/", {}).json()["project"]["status"], "review")
        self.assertEqual(self.post("/api/projects/AZE1028/", {"title": "x"}, "patch").status_code, 403)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get("/api/projects/AZE1028/").status_code, 404)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.post("/api/projects/AZE1028/return/", {}).status_code, 400)
        self.assertEqual(self.post("/api/projects/AZE1028/publish/", {}).json()["project"]["status"], "published")
        self.client.force_login(self.other)
        self.assertEqual(self.client.get("/api/projects/AZE1028/").status_code, 200)   # published: every signed-in user
        self.client.logout()
        # Projects are for signed-in users only, even published ones.
        self.assertEqual(self.client.get("/api/projects/AZE1028/").status_code, 401)
        self.assertEqual(self.client.get("/api/projects/").status_code, 401)
        self.assertEqual(self.client.get("/api/analysis/runs/?project=AZE1028").status_code, 404)

    def test_template_import_with_boundary_zip(self):
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "Projects"
        ws.append(["Project code", "Title", "Country (ISO3)", "Sector", "Cycle stage", "Themes"])
        ws.append(["AZE1028", "Karabakh canal", "AZE", "Agriculture", "PIASR", "water;agriculture;bogus"])
        ws.append(["UGA1072", "", "UGA", "", "", ""])
        buf = io.BytesIO()
        wb.save(buf)
        zb = io.BytesIO()
        with zipfile.ZipFile(zb, "w") as z:
            z.writestr("AZE1028.kml", KML)
        r = self.client.post("/api/projects/import/preview/", {
            "kind": "template", "file": SimpleUploadedFile("p.xlsx", buf.getvalue()),
            "boundaries": SimpleUploadedFile("b.zip", zb.getvalue())})
        d = r.json()
        self.assertEqual([x["action"] for x in d["rows"]], ["new", "error"])
        self.assertEqual(d["rows"][0]["boundary"], "file")
        r = self.post("/api/projects/import/commit/", {"token": d["token"], "rows": [{"row": 2}, {"row": 3}]})
        self.assertEqual(r.json()["created"], 1)
        p = Project.objects.get(code="AZE1028")
        self.assertEqual(p.source, "import")
        self.assertEqual(p.themes, ["water", "agriculture"])
        self.assertTrue(hasattr(p, "area"))


class MapLayoutTests(TestCase):
    """Map export layouts are kept per user in the database, so they follow the user to any computer."""
    LAYOUT = {"version": 2, "page": {"size": "A4", "orientation": "landscape"}, "items": [{"id": "t1", "type": "text"}]}

    @classmethod
    def setUpTestData(cls):
        U = get_user_model()
        cls.editor = U.objects.create_user("ed", "ed@example.org", "pw-123456!")
        cls.other = U.objects.create_user("ot", "ot@example.org", "pw-123456!")
        Project.objects.create(code="AZE1028", title="Karabakh canal", country_iso3="AZE", owner=cls.editor)

    def setUp(self):
        self.client.force_login(self.editor)

    def call(self, method, url, body=None):
        return getattr(self.client, method)(url, json.dumps(body) if body is not None else None, content_type="application/json")

    def test_layout_and_resolution_follow_the_user(self):
        r = self.call("get", "/api/projects/AZE1028/map-layout/").json()
        self.assertEqual((r["layout"], r["dpi"], r["templates"]), (None, 300, []))
        self.assertEqual(r["stored"], {"layout": False, "settings": False})
        self.assertEqual(self.call("put", "/api/projects/AZE1028/map-layout/", {"layout": self.LAYOUT, "dpi": 600}).status_code, 200)
        self.client.logout()
        self.client.force_login(self.editor)            # another session: another computer or browser
        r = self.call("get", "/api/projects/aze1028/map-layout/").json()
        self.assertEqual((r["layout"], r["dpi"], r["stored"]), (self.LAYOUT, 600, {"layout": True, "settings": True}))
        self.assertEqual(self.call("get", "/api/projects/AZE1028/map-layout/").status_code, 200)
        self.client.force_login(self.other)
        self.assertEqual(self.call("get", "/api/projects/AZE1028/map-layout/").status_code, 404)   # can't see the draft
        Project.objects.filter(code="AZE1028").update(status="published")
        self.assertIsNone(self.call("get", "/api/projects/AZE1028/map-layout/").json()["layout"])  # each user has their own

    def test_templates(self):
        r = self.call("post", "/api/projects/map-templates/", {"name": "IsDB A4", "layout": self.LAYOUT})
        self.assertEqual([t["name"] for t in r.json()["templates"]], ["IsDB A4"])
        r = self.call("post", "/api/projects/map-templates/", {"templates": [{"name": "Poster", "layout": self.LAYOUT},
                                                                             {"name": "IsDB A4", "layout": self.LAYOUT}]})
        self.assertEqual(sorted(t["name"] for t in r.json()["templates"]), ["IsDB A4", "Poster"])   # same name replaced
        r = self.call("delete", "/api/projects/map-templates/", {"name": "Poster"})
        self.assertEqual([t["name"] for t in r.json()["templates"]], ["IsDB A4"])
        for i in range(25):
            self.call("post", "/api/projects/map-templates/", {"name": f"T{i}", "layout": self.LAYOUT})
        self.assertEqual(len(self.call("get", "/api/projects/map-templates/").json()["templates"]), 20)

    def test_refuses_bad_input_and_anonymous_users(self):
        r = self.call("put", "/api/projects/AZE1028/map-layout/", {"layout": {"items": []}})
        self.assertIn("isn't a map layout", r.json()["error"])
        self.assertEqual(self.call("put", "/api/projects/AZE1028/map-layout/", {"dpi": 1234}).status_code, 400)
        self.assertEqual(self.call("post", "/api/projects/map-templates/", {"name": " ", "layout": self.LAYOUT}).status_code, 400)
        self.assertEqual(self.call("get", "/api/projects/NOPE01/map-layout/").status_code, 404)
        self.client.logout()
        self.assertEqual(self.call("get", "/api/projects/map-templates/").status_code, 401)


class ProjectLayersTests(TestCase):
    """The Analytics workspace lists a project's area, analysis outputs and Toolbox outputs as layers."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.gis.geos import MultiPolygon, Polygon

        from apps.analysis.models import Module, ModuleRun
        from apps.toolbox.models import ToolRun
        from .models import ProjectArea

        U = get_user_model()
        cls.editor = U.objects.create_user("ed", "ed@example.org", "pw-123456!")
        cls.other = U.objects.create_user("ot", "ot@example.org", "pw-123456!")
        p = Project.objects.create(code="AZE1028", title="Karabakh canal", country_iso3="AZE", owner=cls.editor)
        ProjectArea.objects.create(project=p, method="upload", area_km2=10.0,
                                   geom=MultiPolygon(Polygon.from_bbox((47.1, 40.5, 47.7, 40.8)), srid=4326))
        m = Module.objects.create(id="test_mod", version="1.0", title="Test analysis")
        ModuleRun.objects.create(project=p, module=m, module_version="1.0", status="done", outputs=[
            {"type": "raster", "name": "slope", "title": "Slope", "file": "slope.png", "data_file": "slope.tif"},
            {"type": "vector", "name": "sites", "title": "Sites", "file": "sites.geojson", "style": {"color": "#f00"}},
            {"type": "metric", "name": "m", "title": "Mean", "value": 1},
        ])
        ModuleRun.objects.create(project=p, module=m, module_version="1.0", status="failed", outputs=[
            {"type": "vector", "name": "x", "title": "Failed", "file": "x.geojson"}])
        ToolRun.objects.create(project=p, created_by=cls.editor, tool="buffer_vector", tool_title="Buffer",
                               engine="geolibre", name="Roads buffer", status="done", outputs=[
                                   {"name": "output", "title": "Output", "kind": "vector", "file": "output.gpkg",
                                    "geojson": "output.geojson"},
                                   {"name": "t", "title": "Table", "kind": "table", "file": "t.csv"}])

    def test_lists_layers_of_the_project(self):
        self.client.force_login(self.editor)
        r = self.client.get("/api/projects/AZE1028/layers/")
        self.assertEqual(r.status_code, 200, r.content)
        layers = r.json()["layers"]
        self.assertEqual([(l["group"], l["kind"], l["title"]) for l in layers], [
            ("Project", "vector", "Area of influence"), ("Analyses", "raster", "Slope"),
            ("Analyses", "vector", "Sites"), ("Toolbox", "vector", "Output")])
        self.assertEqual(layers[1]["url"], "/api/projects/AZE1028/layers/run-%d-slope/raster/" % layers[1]["run"])
        self.assertTrue(layers[3]["url"].endswith("/files/output.geojson"))
        area = self.client.get(layers[0]["url"])
        self.assertEqual(area["Content-Type"], "application/geo+json")
        self.assertEqual(json.loads(area.content)["features"][0]["properties"]["project"], "AZE1028")

    def test_sign_in_and_access(self):
        self.assertEqual(self.client.get("/api/projects/AZE1028/layers/").status_code, 401)
        self.assertEqual(self.client.get("/api/projects/AZE1028/layers/area/").status_code, 401)
        self.client.force_login(self.other)                  # a draft project: only its owner (and reviewers)
        self.assertEqual(self.client.get("/api/projects/AZE1028/layers/").status_code, 404)

    def test_raster_display_keeps_values_and_colours(self):
        """Classified rasters come as a one-byte GeoTIFF with a colour table; ramps unchanged, with their palette."""
        import tempfile
        from pathlib import Path

        import numpy as np
        import rasterio
        from django.test import override_settings
        from rasterio.transform import from_bounds

        from apps.analysis.models import Module, ModuleRun

        with tempfile.TemporaryDirectory() as tmp, override_settings(MEDIA_ROOT=Path(tmp)):
            p = Project.objects.get(code="AZE1028")
            r = ModuleRun.objects.create(project=p, module=Module.objects.get(pk="test_mod"), module_version="1.0",
                                         status="done", outputs=[
                {"type": "raster", "name": "cls", "title": "Classes", "data_file": "cls.tif", "legend_spec": {
                    "type": "classes", "items": [{"value": 1, "color": "#FF0000", "label": "One"},
                                                 {"value": 4, "color": "#00FF00", "label": "Four"}]}},
                {"type": "raster", "name": "ramp", "title": "Ramp", "data_file": "ramp.tif", "legend_spec": {
                    "type": "ramp", "palette": ["#FFFFCC", "#006837"], "min": 0, "max": 10, "unit": "m"}}])
            r.workdir.mkdir(parents=True, exist_ok=True)
            a = np.array([[1, 4], [4, np.nan]], dtype="float32")
            for name in ("cls", "ramp"):
                with rasterio.open(r.workdir / f"{name}.tif", "w", driver="GTiff", width=2, height=2, count=1,
                                   dtype="float32", crs="EPSG:4326", transform=from_bounds(47.1, 40.5, 47.2, 40.6, 2, 2),
                                   nodata=np.nan) as d:
                    d.write(a, 1)
            self.client.force_login(self.editor)
            res = self.client.get(f"/api/projects/AZE1028/layers/run-{r.pk}-cls/raster/")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(json.loads(res["X-GEIDA-Style"]), {"colormap": "palette", "nodata": 255})
            b"".join(res.streaming_content)
            with rasterio.open(Path(r.workdir) / "cls.display.tif") as d:
                self.assertEqual(d.read(1).tolist(), [[1, 4], [4, 255]])
                self.assertEqual(d.colormap(1)[4][:3], (0, 255, 0))
            res = self.client.get(f"/api/projects/AZE1028/layers/run-{r.pk}-ramp/raster/")
            self.assertEqual(json.loads(res["X-GEIDA-Style"])["palette"], ["#FFFFCC", "#006837"])
            self.assertEqual(self.client.get(f"/api/projects/AZE1028/layers/run-{r.pk}-nope/raster/").status_code, 404)
