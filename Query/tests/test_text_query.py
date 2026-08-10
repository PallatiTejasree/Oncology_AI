import unittest

from Query.query_encoder import _validate_text


class QueryInputTests(unittest.TestCase):
    def test_rejects_blank_query(self):
        with self.assertRaises(ValueError):
            _validate_text("   ")

    def test_trims_query(self):
        self.assertEqual(_validate_text("  breast cancer  "), "breast cancer")


if __name__ == "__main__":
    unittest.main()
