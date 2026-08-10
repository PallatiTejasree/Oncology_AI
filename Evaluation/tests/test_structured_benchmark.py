import unittest

from Evaluation.run_structured_benchmark import DEFAULT_CASES, load_cases, validate_result
from app.langchain.pipeline import _clean_structured_citations


class StructuredBenchmarkTests(unittest.TestCase):
    def test_default_manifest_is_balanced_and_complete(self):
        cases = load_cases(DEFAULT_CASES)
        self.assertEqual(len(cases), 20)
        self.assertEqual(sum(case["kind"] == "pdf" for case in cases), 2)
        self.assertEqual(sum(case["kind"] == "image" for case in cases), 5)
        self.assertEqual(sum(case["kind"] == "hybrid" for case in cases), 5)

    def test_result_validation_requires_structured_llm_evidence(self):
        errors = validate_result({
            "structured_answer": None,
            "model_name": "retrieval-only",
            "evidence": [],
            "citation_validation": {"status": "none"},
            "generation_diagnostics": {"error": "test generation error"},
        })
        self.assertIn("missing structured_answer (Gemini may have fallen back)", errors)
        self.assertIn("LLM fallback used: test generation error", errors)

    def test_invalid_citations_are_removed_from_structured_narrative_and_arrays(self):
        cleaned = _clean_structured_citations({
            "plain_language_summary": "User question [U1]; evidence [R1].",
            "findings": [{"citations": ["U1", "R1"]}],
        }, ["U1"])
        self.assertEqual(cleaned["plain_language_summary"], "User question ; evidence [R1].")
        self.assertEqual(cleaned["findings"][0]["citations"], ["R1"])


if __name__ == "__main__":
    unittest.main()
