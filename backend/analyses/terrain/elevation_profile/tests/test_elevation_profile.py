"""Tests for elevation_profile on a synthetic DEM: a plane rising from 1,000 m (west) to 3,000 m (east)."""
import numpy as np
import rasterio
from rasterio.transform import from_bounds

from apps.analysis.core.testing import AnalysisTestCase


class TestElevationProfile(AnalysisTestCase):
    analysis_id = "elevation_profile"

    def setUp(self):
        # 0.001° pixels (about 110 m) over the test area plus a margin, in lon/lat like the real data.
        w, s, e, n = 33.9, 1.9, 34.6, 2.6
        cols, rows = 700, 700
        x = (np.arange(cols) + 0.5) / cols * (e - w) + w
        dem = np.tile(1000 + (x - 34.0) / 0.5 * 2000, (rows, 1)).astype("float32")  # 1,000 m at 34.0°E, 3,000 m at 34.5°E
        path = self._tmp / "dem.tif"
        with rasterio.open(path, "w", driver="GTiff", width=cols, height=rows, count=1, dtype="float32",
                           crs="EPSG:4326", transform=from_bounds(w, s, e, n, cols, rows), nodata=-9999) as dst:
            dst.write(dem, 1)
        self.use_dataset("elevation", path)

    def test_elevation_range_bands_and_map(self):
        run = self.run_analysis({"bands": 4})
        self.assertAlmostEqual(self.metric(run, "min_elevation"), 1000, delta=40)
        self.assertAlmostEqual(self.metric(run, "max_elevation"), 3000, delta=40)
        self.assertAlmostEqual(self.metric(run, "mean_elevation"), 2000, delta=40)
        bands = self.table(run, "bands")
        self.assertAlmostEqual(sum(b["share"] for b in bands), 100, delta=0.5)
        self.assertGreaterEqual(len(bands), 4, bands)
        self.assertEqual(len(self.table(run, "per_zone")), 1)  # no admin units in tests: the whole area

        out = self.output(run, "elevation")
        self.assertEqual(out["type"], "raster")
        self.assertTrue((run.workdir / out["file"]).exists())        # PNG preview
        self.assertTrue((run.workdir / out["data_file"]).exists())   # values as a COG
        self.assertEqual(out["crs"], "EPSG:32636")                    # local UTM zone
        w, s, e, n = out["bounds"]
        self.assertTrue(33.95 < w < 34.05 and 34.45 < e < 34.55 and 1.95 < s < 2.05 and 2.45 < n < 2.55)
        with rasterio.open(run.workdir / out["data_file"]) as src:
            self.assertEqual(src.crs.to_epsg(), 32636)
            self.assertTrue(src.overviews(1) or max(src.width, src.height) < 512)  # COG (overviews when large)
        labels = [i["label"] for i in out["legend"]]
        self.assertRegex(labels[0], r"^1,0\d\d–1,250 m$")       # value ranges (2,000 m over 7 colours: 250 m steps)
        self.assertNotIn("above", labels[-1])                    # the ramp ends at the highest value
        self.client.force_login(self.user)
        r = self.client.get(f"/api/analysis/runs/{run.pk}/files/{out['data_file']}?download=1")
        self.assertEqual((r.status_code, r["Content-Type"]), (200, "image/tiff"))
        self.assertIn("TEST01_elevation_profile_elevation.tif", r["Content-Disposition"])
        self.assertEqual(run.datasets[0]["id"], "elevation")
        self.assertEqual(run.datasets[0]["title"], "Elevation (Copernicus DEM GLO-30)")
        self.assertEqual(run.datasets[0]["reference_date"], "Static")

    def test_cache_reuses_the_clip(self):
        self.run_analysis()
        run = self.run_analysis()
        self.assertNotIn("clipping the local file", run.log)  # second run reads the cached clip


class TestElevationProfileFromCatalogueSources(AnalysisTestCase):
    """Without a local file the DEM tiles come from the catalogue's sources (a STAC search; mocked here)
    and are read at native resolution with GDAL."""
    analysis_id = "elevation_profile"

    def test_reads_the_sources_at_native_resolution(self):
        from unittest import mock

        import rasterio
        from rasterio.transform import from_bounds

        tile = self._tmp / "tile.tif"  # a 1 arc-second tile like Copernicus GLO-30, constant 1,500 m
        with rasterio.open(tile, "w", driver="GTiff", width=2520, height=2520, count=1, dtype="float32",
                           crs="EPSG:4326", transform=from_bounds(33.8, 1.8, 34.5 + 0.2, 2.5 + 0.2, 2520, 2520)) as dst:
            dst.write(np.full((2520, 2520), 1500, dtype="float32"), 1)
        seen = {}

        def fake_sources(layer, year, bbox):
            seen.update(layer=layer["id"], bbox=bbox)
            return [(str(tile), None, None)]

        with mock.patch("apps.geoportal.raster.sources", side_effect=fake_sources):
            run = self.run_analysis()
        self.assertEqual(seen["layer"], "elevation")
        self.assertAlmostEqual(seen["bbox"][0], 34.0 - 0.0023, delta=0.0005)  # area plus the 250 m DEM margin
        self.assertEqual(self.metric(run, "mean_elevation"), 1500)
        self.assertIn("at native resolution", run.log)
        self.assertIn("30 m pixels in EPSG:32636", run.log)
        self.assertEqual(self.output(run, "elevation")["resolution_m"], 30)
