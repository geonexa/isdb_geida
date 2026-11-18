"""Project reports: permissions, generating a version (web page and PDF), share links, deleting (needs WeasyPrint)."""
import json
import shutil
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.projects.models import Project

from . import charts
from .models import Report

try:
    import weasyprint  # noqa: F401
    HAVE_WEASYPRINT = True
except (ImportError, OSError):
    HAVE_WEASYPRINT = False


@unittest.skipUnless(HAVE_WEASYPRINT, "WeasyPrint is not installed")
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class ReportTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = Path(tempfile.mkdtemp(prefix="geida-report-test-"))
        cls._settings = override_settings(MEDIA_ROOT=cls._tmp / "media", DATA_DIR=cls._tmp / "data")
        cls._settings.enable()
        cls._tiles = mock.patch("apps.reports.maps._tile", return_value=None)     # no basemap downloads in tests
        cls._tiles.start()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._tiles.stop()
        cls._settings.disable()
        shutil.rmtree(cls._tmp, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        import numpy as np
        from django.contrib.gis.geos import MultiPolygon, Polygon
        from PIL import Image

        from apps.analysis.models import Module, ModuleRun
        from apps.projects.models import ProjectArea

        U = get_user_model()
        cls.owner = U.objects.create_user("ow", "ow@example.org", "pw-123456!")
        cls.other = U.objects.create_user("ot", "ot@example.org", "pw-123456!")
        cls.project = Project.objects.create(code="AZE1028", title="Karabakh canal", country_iso3="AZE",
                                             country_name="Azerbaijan", owner=cls.owner)
        ProjectArea.objects.create(project=cls.project, method="draw", area_km2=900.0,
                                   geom=MultiPolygon(Polygon.from_bbox((47.1, 40.5, 47.5, 40.8)), srid=4326))
        m = Module.objects.create(id="slope", version="1.0", title="Slope",
                                  manifest={"category": "terrain", "question": "How steep is the land?",
                                            "parameters": [{"name": "year", "label": "Year"}]})
        cls.mrun = ModuleRun.objects.create(project=cls.project, module=m, module_version="1.0", status="done",
                                           params={"year": 2024}, summary="Mostly gentle slopes.", outputs=[
            {"type": "metric", "name": "mean", "title": "Mean slope", "value": 4.2, "unit": "°"},
            {"type": "table", "name": "classes", "title": "Slope classes", "columns": [
                {"key": "class", "label": "Class"}, {"key": "share", "label": "Share", "unit": "%"}],
             "rows": [{"class": "Flat", "share": 60.0}, {"class": "Steep", "share": 40.0}]},
            {"type": "raster", "name": "slope", "title": "Slope", "file": "slope.png", "data_file": "slope.tif",
             "bounds": [47.1, 40.5, 47.5, 40.8], "legend": [{"label": "Flat", "color": "#1A9850"}], "unit": "°"},
            {"type": "vector", "name": "pts", "title": "Points", "file": "pts.geojson", "style": {"color": "#d62728"}},
        ])
        cls.mrun.workdir.mkdir(parents=True, exist_ok=True)
        Image.fromarray(np.full((40, 60, 4), (26, 152, 80, 220), dtype=np.uint8)).save(cls.mrun.workdir / "slope.png")
        (cls.mrun.workdir / "pts.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [47.3, 40.6]}, "properties": {}}]}))

    def post(self, url, body=None):
        return self.client.post(url, json.dumps(body or {}), content_type="application/json")

    def create(self, sections=None):
        r = self.post("/api/reports/AZE1028/", {"title": "Screening", "subtitle": "Test", "content": {
            "summary": "Our summary.", "sections": sections if sections is not None else [{"run": self.mrun.pk}]}})
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()["report"]

    def test_access(self):
        self.assertEqual(self.client.get("/api/reports/AZE1028/").status_code, 401)
        self.client.force_login(self.other)                      # a draft project: owner and reviewers only
        self.assertEqual(self.client.get("/api/reports/AZE1028/").status_code, 404)
        self.client.force_login(self.owner)
        rep = self.create(sections=[{"run": self.mrun.pk}, {"run": 999999}])
        self.assertEqual([s["run"] for s in rep["content"]["sections"]], [self.mrun.pk])   # unknown runs dropped
        runs = self.client.get("/api/reports/AZE1028/runs/").json()["runs"]
        self.assertEqual(runs[0]["category"], "terrain")
        self.assertEqual({o["kind"] for o in runs[0]["outputs"]}, {"Figures", "Table", "Map"})

    def test_generate_share_and_delete(self):
        self.client.force_login(self.owner)
        rep = self.create()
        res = self.post(f"/api/reports/{rep['id']}/generate/")
        self.assertEqual(res.status_code, 201, res.content)
        v = self.client.get(f"/api/reports/{rep['id']}/").json()["report"]["versions"][0]
        self.assertEqual(v["status"], "done", v["error"])
        self.assertGreaterEqual(v["pages"], 3)
        pdf = self.client.get(v["pdf_url"])
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertTrue(b"".join(pdf.streaming_content).startswith(b"%PDF"))
        html = self.client.get(v["html_url"]).content.decode()
        for text in ("Screening", "Our summary.", "Mostly gentle slopes.", "Slope classes", "<svg", "Figure"):
            self.assertIn(text, html)
        self.assertNotIn("__GEIDA_PDF_URL__", html)
        from .models import ReportVersion
        snap = ReportVersion.objects.get(pk=v["id"]).snapshot
        self.assertNotIn("<svg", json.dumps(snap))                 # pictures stay in the files, not the database
        self.assertEqual(snap["sections"][0]["metrics"][0]["value"], "4.2")

        # Share: a link opens the latest version without signing in, until revoked or expired.
        share = self.post(f"/api/reports/{rep['id']}/share/", {"expires_days": 7}).json()["report"]["share"]
        self.client.logout()
        self.assertEqual(self.client.get(share["url"]).status_code, 200)
        self.assertEqual(self.client.get(share["url"] + "pdf").status_code, 200)
        self.assertEqual(self.client.get(v["html_url"]).status_code, 401)
        Report.objects.filter(pk=rep["id"]).update(share_expires=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self.client.get(share["url"]).status_code, 404)

        self.client.force_login(self.other)
        self.assertEqual(self.client.delete(f"/api/reports/{rep['id']}/").status_code, 404)
        self.client.force_login(self.owner)
        folder = Report.objects.get(pk=rep["id"]).folder
        self.assertTrue(folder.exists())
        self.assertEqual(self.client.delete(f"/api/reports/{rep['id']}/").status_code, 200)
        self.assertFalse(folder.exists())

    def test_needs_content_to_generate(self):
        self.client.force_login(self.owner)
        r = self.post("/api/reports/AZE1028/", {"title": "Empty"}).json()["report"]
        self.assertEqual(self.post(f"/api/reports/{r['id']}/generate/").status_code, 400)


class ChartTests(unittest.TestCase):
    def test_bars_for_share_tables_only(self):
        t = {"columns": [{"key": "class", "label": "Class"}, {"key": "share", "label": "Share", "unit": "%"}],
             "rows": [{"class": "A", "share": 70}, {"class": "B", "share": 30}]}
        svg = charts.bar_chart(t, {"A": "#ff0000"})
        self.assertIn("<svg", svg)
        self.assertIn("#ff0000", svg)
        self.assertIsNone(charts.bar_chart({"columns": t["columns"], "rows": t["rows"][:1]}))
        self.assertIsNone(charts.pick({"columns": [{"key": "name"}, {"key": "lat"}], "rows": [{"name": "x", "lat": 1}] * 3}))
