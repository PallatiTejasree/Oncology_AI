import tempfile
import unittest
from pathlib import Path

import fitz
from PIL import Image

from app.services.upload_ingestion import (
    chunk_medical_text,
    clean_medical_text,
    extract_report,
    inspect_image,
)


class UploadIngestionTests(unittest.TestCase):
    def test_cleaning_preserves_clinical_negation_and_measurement(self):
        cleaned = clean_medical_text("Page 1 of 2\nNo mass. Lesion measures 2.4 cm.\x0c")
        self.assertNotIn("Page 1 of 2", cleaned)
        self.assertIn("No mass", cleaned)
        self.assertIn("2.4 cm", cleaned)

    def test_chunking_is_overlapping_and_bounded(self):
        chunks = chunk_medical_text("Finding sentence. " * 300, size=500, overlap=80)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(item) <= 500 for item in chunks))

    def test_rejects_blank_image(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "blank.png"
            Image.new("RGB", (300, 300), "white").save(path)
            result = inspect_image(path)
            self.assertFalse(result.accepted)
            self.assertIn("completely white", result.rejection_reason.lower())
            self.assertIn("too blurry", result.rejection_reason.lower())
            self.assertGreaterEqual(len(result.rejection_reasons), 2)
            self.assertLess(result.quality_score, 40)
            self.assertTrue(result.quality_reasons)

    def test_reports_all_detected_image_quality_problems(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "small-flat.png"
            Image.new("RGB", (100, 100), "gray").save(path)
            result = inspect_image(path)
            self.assertFalse(result.accepted)
            self.assertIn("too small", result.rejection_reason.lower())
            self.assertIn("too blurry", result.rejection_reason.lower())
            self.assertEqual(len(result.rejection_reasons), 2)
            self.assertLess(result.quality_score, 40)

    def test_extracts_and_chunks_pdf_text(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.pdf"
            document = fitz.open()
            page = document.new_page()
            page.insert_text((72, 72), "Pathology report: No distant metastasis identified. Tumor measures 2.4 cm.")
            document.save(path)
            document.close()
            result = extract_report(path)
            self.assertIn("No distant metastasis", result.text)
            self.assertEqual(len(result.chunks), 1)
            self.assertGreaterEqual(result.quality_score, 40)
            self.assertTrue(result.quality_reasons)


if __name__ == "__main__":
    unittest.main()
