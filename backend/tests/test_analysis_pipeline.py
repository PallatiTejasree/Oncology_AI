import os
import unittest
from unittest.mock import patch

from app.langchain.pipeline import (
    ClinicalAnalysisPipeline, DISCLAIMER, _normalize_structured_answer,
    _validate_citations,
)


class _FakeRetrieval:
    def query_text(self, query, top_k):
        return {
            "query_type": "text",
            "fused_results": [
                {
                    "id": "chunk-1",
                    "rank": 1,
                    "modality": "text",
                    "document": "Retrieved evidence excerpt",
                    "metadata": {"source_dataset": "test", "cancer_type": "LUAD"},
                    "retrieval_score": 0.8,
                    "metric": "ip",
                }
            ],
            "diagnostics": {"text": {"calibrated": False}, "images": {}},
        }


class ClinicalAnalysisPipelineTests(unittest.TestCase):
    def test_retrieval_fallback_is_grounded_and_uncalibrated(self):
        pipeline = ClinicalAnalysisPipeline.__new__(ClinicalAnalysisPipeline)
        pipeline.retrieval = _FakeRetrieval()
        with patch.dict(os.environ, {}, clear=True):
            result = pipeline.analyze(text="lung report", top_k=5)
        self.assertEqual(result["model_name"], "retrieval-only")
        self.assertEqual(result["evidence"][0]["cancer_type"], "LUAD")
        self.assertEqual(result["supporting_image_evidence"], [])
        self.assertIn("not a diagnosis", result["summary"])
        self.assertIn("Retrieved evidence excerpt", result["summary"])
        self.assertEqual(result["disclaimer"], DISCLAIMER)
        self.assertIsNone(result["risk_review"])
        self.assertEqual(result["research_summary"]["related_records"], 1)

    def test_empty_input_is_rejected(self):
        pipeline = ClinicalAnalysisPipeline.__new__(ClinicalAnalysisPipeline)
        pipeline.retrieval = _FakeRetrieval()
        with self.assertRaises(ValueError):
            pipeline.analyze(text="  ")

    def test_citation_validation_rejects_out_of_range_sources(self):
        result = _validate_citations("Finding [U1]. Comparison [R1, R4].", 1, 2)
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["invalid"], ["R4"])

    def test_structured_answer_normalizes_external_llm_shapes(self):
        result = _normalize_structured_answer({
            "limitations": "No patient file was provided.",
            "supports": "Retrieved evidence supports the definition.",
            "findings": {"finding": "HER2", "citations": "R1, R2"},
            "reasoning": [],
            "medical_terms": {"HER2": "A receptor protein."},
            "evidence_support": {"level": "Strong", "explanation": "Five records agree."},
        })
        self.assertEqual(result["limitations"], ["No patient file was provided."])
        self.assertEqual(result["findings"][0]["citations"], ["R1", "R2"])
        self.assertEqual(result["medical_terms"][0]["term"], "HER2")
        self.assertEqual(result["evidence_support"]["level"], "Moderate")


if __name__ == "__main__":
    unittest.main()
