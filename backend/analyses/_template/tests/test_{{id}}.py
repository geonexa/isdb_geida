"""Tests for {{id}}: run it on a small project area and check the results."""
from apps.analysis.core.testing import AnalysisTestCase


class Test{{class}}(AnalysisTestCase):
    analysis_id = "{{id}}"

    def test_runs_and_reports_the_area(self):
        run = self.run_analysis()
        self.assertGreater(self.metric(run, "area_km2"), 0)
        self.assertEqual(len(self.table(run, "per_zone")), 1)  # no admin units in tests: the whole area
