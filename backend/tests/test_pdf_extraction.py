import tempfile
import unittest
from io import BytesIO
from pathlib import Path

import fitz
from PIL import Image

from app.services.pdf_extraction import extract_pdf_images


class PdfImageExtractionTests(unittest.TestCase):
    def test_extracts_large_images_and_ignores_small_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            large = BytesIO(); Image.new("RGB", (400, 300), "red").save(large, format="PNG")
            small = BytesIO(); Image.new("RGB", (40, 40), "blue").save(small, format="PNG")
            pdf = fitz.open(); page = pdf.new_page()
            page.insert_image(fitz.Rect(20, 20, 420, 320), stream=large.getvalue())
            page.insert_image(fitz.Rect(450, 20, 490, 60), stream=small.getvalue())
            pdf_path = root / "case.pdf"; pdf.save(pdf_path); pdf.close()

            images = extract_pdf_images(pdf_path, root / "images")
            self.assertEqual(len(images), 1)
            self.assertEqual((images[0].width, images[0].height), (400, 300))
            self.assertTrue(images[0].path.is_file())


if __name__ == "__main__":
    unittest.main()
