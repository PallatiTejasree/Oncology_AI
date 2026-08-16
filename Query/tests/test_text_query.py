import unittest

from Query.query_encoder import _validate_text
from Query.query_preprocessing import preprocess_query_text


class QueryInputTests(unittest.TestCase):
    def test_rejects_blank_query(self):
        with self.assertRaises(ValueError):
            _validate_text("   ")

    def test_trims_query(self):
        self.assertEqual(_validate_text("  breast cancer  "), "breast cancer")

    def test_normalizes_copied_whitespace_and_invisible_characters(self):
        raw = "\ufeff  No\u00a0mass\twas   detected.\nHER2/neu: negative (1+).  "
        self.assertEqual(
            preprocess_query_text(raw),
            "No mass was detected. HER2/neu: negative (1+).",
        )

    def test_preserves_negation_measurements_units_and_biomarkers(self):
        clinical = "No metastatic mass. Lesion: 2.4 × 1.8 cm; Ki-67 22%; 78 µg/mL."
        self.assertEqual(preprocess_query_text(clinical), clinical)

    def test_repairs_word_broken_across_copied_lines(self):
        self.assertEqual(
            preprocess_query_text("Possible metasta-\ntic lesion"),
            "Possible metastatic lesion",
        )

    def test_preserves_meaningful_hyphen(self):
        self.assertEqual(
            preprocess_query_text("HER2-positive breast cancer"),
            "HER2-positive breast cancer",
        )

    def test_bounds_very_large_pasted_query(self):
        result = preprocess_query_text("oncology " * 500, max_characters=300)
        self.assertLessEqual(len(result), 300)
        self.assertFalse(result.endswith(" "))


if __name__ == "__main__":
    unittest.main()
