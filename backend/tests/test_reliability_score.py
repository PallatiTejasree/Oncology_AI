import unittest

from app.services.reliability_score import calculate_reliability


class ReliabilityScoreTests(unittest.TestCase):
    def test_supported_answer_returns_transparent_uncalibrated_score(self):
        result = calculate_reliability({
            "summary": "The report documents the finding [U1], supported by [R1].",
            "uploaded_sources": [{"file_name": "report.pdf"}],
            "evidence": [{"modality": "text"}, {"modality": "text"}],
            "citation_validation": {"status": "valid", "used": ["U1", "R1"], "invalid": []},
            "diagnostics": {"upload_consistency": {"status": "consistent", "consistent": True}},
            "structured_answer": {"limitations": []},
        })
        self.assertGreaterEqual(result["score"], 70)
        self.assertEqual(result["components"]["patient_document_support"], 100)
        self.assertFalse(result["calibrated"])
        self.assertIn("not diagnostic accuracy", result["explanation"])

    def test_non_analysis_response_has_no_score(self):
        self.assertIsNone(calculate_reliability({"response_type": "conversation"}))

    def test_uncertainty_does_not_reduce_report_coverage(self):
        base = {
            "uploaded_sources": [{"file_name": "report.pdf"}],
            "evidence": [{"modality": "text"}],
            "citation_validation": {"status": "valid", "used": ["U1"], "invalid": []},
        }
        clear = calculate_reliability({**base, "summary": "Confirmed finding [U1]."})
        uncertain = calculate_reliability({**base, "summary": "Possible finding; cannot exclude disease [U1].", "structured_answer": {"limitations": ["Test pending"]}})
        self.assertEqual(uncertain["components"]["completeness"], clear["components"]["completeness"])
        self.assertLess(uncertain["components"]["clinical_certainty"], clear["components"]["clinical_certainty"])


if __name__ == "__main__":
    unittest.main()
