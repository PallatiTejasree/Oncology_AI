import unittest

from Evaluation.config import CASES_FILE, QRELS_FILE
from Evaluation.schema import load_cases, load_qrels


class EvaluationSchemaTests(unittest.TestCase):
    def test_seed_files_are_valid(self):
        cases = load_cases(CASES_FILE)
        judgments = load_qrels(QRELS_FILE, {case.case_id for case in cases})
        self.assertEqual(len(cases), 50)
        self.assertTrue(all(any(value > 0 for value in judgments[c.case_id].values()) for c in cases))


if __name__ == "__main__":
    unittest.main()
