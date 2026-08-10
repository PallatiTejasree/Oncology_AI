import unittest
from pathlib import Path

from Query.query_encoder import BiomedCLIPQueryEncoder


class ImageQueryInputTests(unittest.TestCase):
    def test_missing_image_is_rejected_before_inference(self):
        encoder = object.__new__(BiomedCLIPQueryEncoder)
        with self.assertRaises(FileNotFoundError):
            encoder.encode_image(Path("does-not-exist.jpg"))


if __name__ == "__main__":
    unittest.main()
