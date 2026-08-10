import unittest

try:
    from .splitter import split_text
except ImportError:
    from splitter import split_text


class SplitTextTests(unittest.TestCase):
    def test_chunks_respect_size_and_do_not_cut_words(self):
        text = " ".join(f"medicalword{i}" for i in range(300))
        chunks = split_text(text, chunk_size=120, overlap=25)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(0 < len(chunk) <= 120 for chunk in chunks))
        self.assertTrue(all(chunk.split()[0].startswith("medicalword") for chunk in chunks))
        self.assertTrue(all(chunk.split()[-1].startswith("medicalword") for chunk in chunks))

    def test_prefers_sentence_boundaries(self):
        text = "First clinical sentence. Second clinical sentence. Third clinical sentence."
        chunks = split_text(text, chunk_size=55, overlap=10)
        self.assertTrue(chunks[0].endswith("."))

    def test_rejects_invalid_configuration(self):
        for chunk_size, overlap in ((0, 0), (10, -1), (10, 10), (10, 11)):
            with self.subTest(chunk_size=chunk_size, overlap=overlap):
                with self.assertRaises(ValueError):
                    split_text("medical text", chunk_size=chunk_size, overlap=overlap)

    def test_empty_input(self):
        self.assertEqual(split_text(""), [])
        self.assertEqual(split_text(None), [])


if __name__ == "__main__":
    unittest.main()
