import unittest

from Evaluation.performance_report import latency_summary, percentile


class PerformanceReportTests(unittest.TestCase):
    def test_latency_summary_reports_median_and_p95(self):
        result = latency_summary([10, 20, 30, 40, 50])
        self.assertEqual(result["count"], 5)
        self.assertEqual(result["median_ms"], 30)
        self.assertEqual(result["p95_ms"], 48)

    def test_percentile_rejects_empty_input(self):
        with self.assertRaises(ValueError):
            percentile([], 0.95)


if __name__ == "__main__":
    unittest.main()
