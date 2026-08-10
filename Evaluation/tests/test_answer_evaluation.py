import unittest

from Evaluation.evaluate_answers import score_record


class AnswerEvaluationTests(unittest.TestCase):
    def test_scores_valid_grounded_structure(self):
        row = score_record({
            "case_id": "A1",
            "summary": "Key findings\n• Finding [U1]\n• Similar case [R1]\nClinical note\n• Limited biopsy cannot establish stage [U1]",
            "uploaded_sources": [{"file_name": "case.pdf"}],
            "evidence": [{"id": "one"}],
            "disclaimer": "Clinical support only",
        })
        self.assertEqual(row["citation_validity"], 1.0)
        self.assertEqual(row["citation_coverage"], 1.0)
        self.assertEqual(row["structured_sections"], 1.0)


if __name__ == "__main__":
    unittest.main()
