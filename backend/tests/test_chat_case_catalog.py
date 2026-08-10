import unittest

from run_chat_e2e import CASES


class ChatCaseCatalogTests(unittest.TestCase):
    def test_pdf_catalog_contains_exactly_41_unique_cases(self):
        self.assertEqual(len(CASES), 41)
        self.assertEqual({case.id for case in CASES}, set(range(1, 42)))

    def test_each_case_has_a_supported_expected_route(self):
        self.assertTrue(
            all(case.expected_route in {"conversation", "safety", "retrieval", "upload"} for case in CASES)
        )


if __name__ == "__main__":
    unittest.main()
