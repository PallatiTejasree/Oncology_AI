"""Optional PaddleOCR smoke test.

The active application ingestion path uses Tesseract. PaddleOCR is an optional
legacy experiment and should not make the normal unit suite fail when its large
native dependency stack is not installed.
"""

import os
import unittest


class PaddleOCRSmokeTest(unittest.TestCase):
    @unittest.skipUnless(
        os.getenv("RUN_PADDLEOCR_TEST") == "1",
        "set RUN_PADDLEOCR_TEST=1 to exercise the optional PaddleOCR stack",
    )
    def test_paddleocr_initializes(self):
        from paddleocr import PaddleOCR

        engine = PaddleOCR(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            lang="en",
        )
        self.assertIsNotNone(engine)


if __name__ == "__main__":
    unittest.main()
