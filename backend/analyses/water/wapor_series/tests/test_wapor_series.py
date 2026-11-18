"""Tests for wapor_series: synthetic WaPOR windows (no network), point and polygon places, trend and outputs."""
from unittest import mock

import numpy as np
import rasterio
from django.test import SimpleTestCase

from apps.analysis.core.testing import AnalysisTestCase
from apps.analysis.ops.timeseries import sens_slope

from .. import run as R


def fake_periods(mapset):
    step = mapset[-1]
    if step == "A":
        return [str(y) for y in range(2018, 2026)]
    if step == "M":
        return [f"{y}-{m:02d}" for y in range(2018, 2026) for m in range(1, 13)]
    return [f"{y}-{m:02d}-D{d}" for y in range(2018, 2026) for m in range(1, 13) for d in (1, 2, 3)]


def fake_window(mapset, period, bbox):
    """A 300 m grid over the bbox: value = 10 × (year − 2018) + 1 (a steady rise), NaN in the first column of wider windows."""
    w, s, e, n = bbox
    res = 0.0029296875
    cols, rows = max(1, int(np.ceil((e - w) / res))), max(1, int(np.ceil((n - s) / res)))
    data = np.full((rows, cols), 10.0 * (int(period[:4]) - 2018) + 1, "float32")
    if cols > 2:
        data[:, 0] = np.nan          # some no-data at the edge of polygon windows
    return data, rasterio.Affine(res, 0, w, 0, -res, n), "EPSG:4326"


@mock.patch("apps.analysis.data.wapor.periods", fake_periods)
@mock.patch("apps.analysis.data.wapor.read_window", fake_window)
class WaporSeriesTests(AnalysisTestCase):
    analysis_id = "wapor_series"

    def test_area_annual_series_rises(self):
        run = self.run_analysis({"variable": "AETI", "step": "A", "start_year": 2018, "end_year": 2025, "aoi": "area"})
        self.assertAlmostEqual(self.metric(run, "mean"), 36, places=0)        # mean of 1, 11, …, 71
        self.assertAlmostEqual(self.metric(run, "trend"), 10, places=1)       # +10 per year
        self.assertEqual(self.metric(run, "highest"), 71)
        chart = self.output(run, "series")
        self.assertEqual(len(chart["series"]), 1)
        self.assertEqual(len(chart["series"][0]["points"]), 8)
        self.assertEqual(len(self.table(run, "values")), 8)
        self.assertIsNotNone(self.output(run, "mean_map"))

    def test_point_monthly(self):
        lon, lat = self.area_bbox[0] + 0.05, self.area_bbox[1] + 0.05
        run = self.run_analysis({"variable": "PCP", "step": "M", "start_year": 2020, "end_year": 2021, "aoi": "point",
                                 "point": [lon, lat]})
        self.assertEqual(len(self.table(run, "values")), 24)
        self.assertEqual(self.table(run, "by_zone")[0]["zone"], "Point")

    def test_unavailable_step_is_explained(self):
        run = self.run_analysis({"variable": "TBP", "step": "M", "aoi": "area"}, expect="failed")
        self.assertIn("no monthly total biomass production", run.error)

    def test_too_many_periods(self):
        run = self.run_analysis({"variable": "AETI", "step": "D", "start_year": 2018, "end_year": 2025, "aoi": "area"},
                                expect="failed")
        self.assertIn("more than 220", run.error)


class TrendTests(SimpleTestCase):
    def test_sens_slope_and_mann_kendall(self):
        slope, p = sens_slope([2018, 2019, 2020, 2021, 2022], [1, 3, 5, 7, 9])
        self.assertEqual(slope, 2)
        self.assertLess(p, 0.05)
        self.assertEqual(sens_slope([1, 2], [1, 2]), (None, None))

    def test_period_helpers(self):
        self.assertEqual(R.period_label("2024-06-D1", "D"), "2024-06 D1")
        self.assertAlmostEqual(R.period_time("2024", "A"), 2024.5)
        self.assertAlmostEqual(R.period_time("2024-01", "M"), 2024 + 0.5 / 12)
