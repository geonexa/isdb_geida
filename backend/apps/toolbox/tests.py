"""The Toolbox: curated GeoLibre tools run on the server, saved results, uploads, deleting (needs wasmtime)."""
import json
import unittest

import numpy as np
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from apps.analysis.core.testing import AnalysisTestCase

from . import engine, runner
from .models import ToolRun, ToolUpload

try:
    import wasmtime  # noqa: F401
    HAVE_WASMTIME = True
except ImportError:
    HAVE_WASMTIME = False


def tiff_bytes(bbox=(34.0, 2.0, 34.5, 2.5), size=100):
    """A small lon/lat GeoTIFF whose value is 1 in the west half and 3 in the east half."""
    import io
    import rasterio
    from rasterio.transform import from_bounds
    a = np.ones((size, size), dtype="float32")
    a[:, size // 2:] = 3
    buf = io.BytesIO()
    with rasterio.MemoryFile() as mem:
        with mem.open(driver="GTiff", width=size, height=size, count=1, dtype="float32", crs="EPSG:4326",
                      transform=from_bounds(*bbox, size, size), nodata=-9999) as d:
            d.write(a, 1)
        buf.write(mem.read())
    return buf.getvalue()


@unittest.skipUnless(HAVE_WASMTIME, "wasmtime is not installed")
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class ToolboxTests(AnalysisTestCase):
    def setUp(self):
        self.client.force_login(self.user)

    def post(self, url, body):
        return self.client.post(url, json.dumps(body), content_type="application/json")

    def start(self, tool, params=None, inputs=None, expect="done"):
        with self.captureOnCommitCallbacks(execute=True):
            r = self.post("/api/toolbox/TEST01/runs/", {"tool": tool, "params": params or {}, "inputs": inputs or {}})
        self.assertEqual(r.status_code, 201, r.content)
        t = ToolRun.objects.get(pk=r.json()["run"]["id"])
        self.assertEqual(t.status, expect, t.error + "\n" + t.log)
        return t

    def test_catalogue(self):
        c = self.client.get("/api/toolbox/tools/").json()
        self.assertGreaterEqual(c["count"], 150)
        self.assertLessEqual(c["count"], 200)
        tools = {t["id"]: t for cat in c["categories"] for t in cat["tools"]}
        for tid in ("buffer_vector", "clip", "intersect", "geida_dissolve", "geida_zonal_statistics", "reclass",
                    "raster_to_vector_polygons", "raster_summary_stats"):
            self.assertIn(tid, tools)
        self.assertNotIn("slope", tools)                       # terrain and hydrology are analyses
        buffer = {p["name"]: p for p in tools["buffer_vector"]["params"]}
        self.assertEqual((buffer["input"]["kind"], buffer["input"]["layer_kind"]), ("layer", "vector"))
        self.assertEqual(buffer["distance"]["kind"], "number")
        reclass = {p["name"]: p for p in tools["reclass"]["params"]}
        self.assertEqual(reclass["reclass_values"]["default"], "1,0,10;2,10,20")     # the engine's own format
        weights = {p["name"]: p for p in tools["weighted_overlay"]["params"]}["weights"]
        self.assertEqual(weights["kind"], "text")                                  # corrected manifest

    def test_buffer_rename_download_delete(self):
        t = self.start("buffer_vector", {"distance": 1000}, {"input": {"kind": "area"}})
        out = t.outputs[0]
        self.assertEqual((out["kind"], out["features"], out["geometry"]), ("vector", 1, "polygon"))
        self.assertTrue((t.workdir / out["file"]).exists() and (t.workdir / out["geojson"]).exists())
        # About 1 km wider than the area on each side (the area is ~55 km wide).
        gj = json.loads((t.workdir / out["geojson"]).read_text())
        xs = [c[0] for c in gj["features"][0]["geometry"]["coordinates"][0][0]] \
            if gj["features"][0]["geometry"]["type"] == "MultiPolygon" else [c[0] for c in gj["features"][0]["geometry"]["coordinates"][0]]
        self.assertAlmostEqual(min(xs), 34.0 - 1000 / 111_000, delta=0.002)
        listed = self.client.get("/api/toolbox/TEST01/runs/").json()["runs"]
        self.assertEqual([r["id"] for r in listed], [t.pk])
        self.assertTrue(listed[0]["can_delete"])
        r = self.client.patch(f"/api/toolbox/runs/{t.pk}/", json.dumps({"name": "Area plus 1 km"}), content_type="application/json")
        self.assertEqual(r.json()["run"]["name"], "Area plus 1 km")
        r = self.client.get(f"/api/toolbox/runs/{t.pk}/files/{out['file']}?download=1")
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r["Content-Disposition"])
        self.assertEqual(self.client.get(f"/api/toolbox/runs/{t.pk}/files/secret.txt").status_code, 404)
        # Someone else can't delete it; the owner can, and the folder and record go.
        other = get_user_model().objects.create_user("o2", "o2@example.org", "pw-123456!")
        self.project.status = "published"
        self.project.save()
        self.client.force_login(other)
        self.assertEqual(self.client.delete(f"/api/toolbox/runs/{t.pk}/").status_code, 403)
        self.client.force_login(self.user)
        folder = t.workdir
        self.assertEqual(self.client.delete(f"/api/toolbox/runs/{t.pk}/").status_code, 200)
        self.assertFalse(folder.exists())
        self.assertFalse(ToolRun.objects.filter(pk=t.pk).exists())
        self.assertTrue(self.project.log.filter(action="deleted toolbox run").exists())

    def test_upload_zonal_statistics_and_chaining(self):
        r = self.client.post("/api/toolbox/TEST01/uploads/", {"file": SimpleUploadedFile("values.tif", tiff_bytes())})
        self.assertEqual(r.status_code, 201, r.content)
        up = ToolUpload.objects.get()
        self.assertEqual(up.kind, "raster")
        # Statistics of the raster inside the area: half 1, half 3.
        z = self.start("geida_zonal_statistics", {}, {"input": {"kind": "upload", "id": up.pk}, "zones": {"kind": "area"}})
        table = next(o for o in z.outputs if o["kind"] == "table")
        row = dict(zip(table["columns"], table["rows"][0]))
        self.assertAlmostEqual(float(row["mean"]), 2.0, delta=0.15)
        self.assertEqual((float(row["min"]), float(row["max"])), (1.0, 3.0))
        # A result as input to another tool: reclassify the upload, then turn the classes into polygons.
        rc = self.start("reclass", {"reclass_values": "10,0,2;30,2,5"}, {"input": {"kind": "upload", "id": up.pk}})
        self.assertEqual(rc.outputs[0]["kind"], "raster")
        self.assertEqual(sorted(i["label"] for i in rc.outputs[0]["legend"]), ["10", "30"])
        poly = self.start("raster_to_vector_polygons", {}, {"input": {"kind": "tool", "run": rc.pk, "output": "output"}})
        self.assertGreaterEqual(poly.outputs[0]["features"], 2)
        # Raster statistics come back as the tool's report.
        st = self.start("raster_summary_stats", {}, {"input": {"kind": "upload", "id": up.pk}})
        self.assertAlmostEqual(st.report["mean"], 2.0, delta=0.05)
        # Deleting the upload keeps the results made from it.
        self.assertEqual(self.client.delete(f"/api/toolbox/uploads/{up.pk}/").status_code, 200)
        self.assertTrue(ToolRun.objects.filter(pk=z.pk).exists())

    def test_dissolve_and_errors(self):
        d = self.start("geida_dissolve", {}, {"input": {"kind": "area"}})
        self.assertEqual(d.outputs[0]["features"], 1)
        # A clear message when a required layer is missing, and for an unknown tool.
        r = self.post("/api/toolbox/TEST01/runs/", {"tool": "buffer_vector", "params": {"distance": 10}, "inputs": {}})
        self.assertIn("Choose a layer", r.json()["error"])
        self.assertEqual(self.post("/api/toolbox/TEST01/runs/", {"tool": "slope"}).status_code, 400)
        # The engine's own messages come through when a tool refuses its input.
        t = self.start("voronoi_diagram", {}, {"input_points": {"kind": "area"}}, expect="failed")
        self.assertIn("POINT", t.error.upper())
        r = self.client.post("/api/toolbox/TEST01/uploads/", {"file": SimpleUploadedFile("notes.docx", b"x")})
        self.assertEqual(r.status_code, 400)

    def test_time_limit(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            engine.run(["list"], tmp)   # warm up
            with self.assertRaises(engine.TimeLimit):
                # a buffer with an absurd number of segments takes far longer than 1 second
                from .inputs import write_vector
                write_vector(f"{tmp}/a.gpkg", [self.project.area.geom], 32636)
                engine.run(["buffer_vector", "--input=/work/a.gpkg", "--distance=10", "--quadrant_segments=5000000",
                            "--output=/work/b.geojson"], tmp, timeout_s=1)
