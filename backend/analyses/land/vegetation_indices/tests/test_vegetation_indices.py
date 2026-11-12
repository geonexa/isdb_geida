"""Vegetation indices with the Sentinel-2 search and reads replaced by synthetic scenes."""
from unittest import mock

import numpy as np

from apps.analysis.core.testing import AnalysisTestCase
from apps.analysis.data import sentinel2 as S2


def fake_items(n=4):
    return [{"id": f"S2_T36NXH_2024060{k}", "date": f"2024-06-0{k}", "tile": "MGRS-36NXH", "cloud": 5.0 * k,
             "assets": {}} for k in range(1, n + 1)]


def fake_read(item, bands, grid):
    """Dense vegetation in the west half (NDVI 0.8), bare soil in the east (NDVI 0.1); scene 1 is cloudy in the north."""
    rows, cols = grid.shape
    west = np.zeros(grid.shape, bool)
    west[:, : cols // 2] = True
    nir = np.where(west, 0.45, 0.22).astype("float32")
    red = np.where(west, 0.05, 0.18).astype("float32")
    out = {"red": red, "nir": nir, "blue": np.full(grid.shape, 0.04, "float32"),
           "nir08": nir, "swir16": np.where(west, 0.15, 0.30).astype("float32")}
    clear = np.ones(grid.shape, bool)
    if item["id"].endswith("1"):
        clear[: rows // 2] = False
        out["nir"] = np.where(clear, nir, 0.9)   # a cloud value that must be ignored
    return {b: out[b] for b in bands}, clear


@mock.patch.object(S2, "read_item", side_effect=fake_read)
@mock.patch.object(S2, "search", return_value=fake_items())
class TestVegetationIndices(AnalysisTestCase):
    analysis_id = "vegetation_indices"
    area_bbox = (34.0, 2.0, 34.1, 2.1)

    def setUp(self):
        # Land cover for the per-class table: cropland in the west half, bare in the east.
        self.synthetic_dataset("landcover", lambda lon, lat: np.where(lon < 34.05, 40, 60), year=2021)

    def test_ndvi_halves(self, search, read):
        run = self.run_analysis({"year": 2024, "season": "apr_jun"})
        self.assertAlmostEqual(self.metric(run, "mean_index"), (0.8 + 0.1) / 2, delta=0.03)
        self.assertAlmostEqual(self.metric(run, "high_share"), 50, delta=3)
        self.assertEqual(self.metric(run, "scenes"), 4)
        classes = self.table(run, "classes")
        self.assertAlmostEqual(classes[0]["share"] + classes[1]["share"], 50, delta=3)  # 0.1 sits on the class edge
        obs = self.output(run, "observations")["stats"]
        self.assertEqual((obs["min"], obs["max"]), (3, 4))
        args = search.call_args[0]
        self.assertEqual((args[1], args[2]), ("2024-04-01", "2024-06-30"))
        self.assertEqual(len(self.table(run, "scene_list")), 4)
        by_lc = {r["label"]: r["mean"] for r in self.table(run, "by_landcover")}
        self.assertAlmostEqual(by_lc["Cropland"], 0.8, delta=0.02)
        self.assertAlmostEqual(by_lc["Bare / sparse vegetation"], 0.1, delta=0.02)

    def test_ndmi_and_cache(self, search, read):
        run = self.run_analysis({"year": 2024, "index": "ndmi"})
        west, east = (0.45 - 0.15) / 0.6, (0.22 - 0.30) / 0.52
        self.assertAlmostEqual(self.metric(run, "mean_index"), (west + east) / 2, delta=0.03)
        calls = read.call_count
        self.run_analysis({"year": 2024, "index": "ndmi"})
        self.assertEqual(read.call_count, calls)   # composite reused from the cache

    def test_no_scenes(self, search, read):
        search.return_value = []
        run = self.run_analysis({"year": 2024}, expect="failed")
        self.assertIn("No Sentinel-2 scenes", run.error)
        search.return_value = fake_items()
        run = self.run_analysis({"year": 2099}, expect="failed")
        self.assertIn("future", run.error)
