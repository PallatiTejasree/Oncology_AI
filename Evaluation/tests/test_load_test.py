import unittest

from Evaluation.load_test import summarize


class LoadTestSummaryTests(unittest.TestCase):
    def test_summary_reports_throughput_and_failures(self):
        result = summarize([
            {"http_status": 200, "latency_ms": 10},
            {"http_status": 200, "latency_ms": 20},
            {"http_status": 500, "latency_ms": 30},
        ], 1.5)
        self.assertEqual(result["successful"], 2)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["throughput_requests_per_second"], 2.0)
        self.assertEqual(result["latency_ms"]["median"], 20)


if __name__ == "__main__":
    unittest.main()
