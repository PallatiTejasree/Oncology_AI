import unittest
from types import SimpleNamespace

from app.api.routes.analysis import _uploaded_source_payload


class UploadedSourcePayloadTests(unittest.TestCase):
    def test_one_citation_source_per_physical_file(self):
        report = SimpleNamespace(
            file_name="case.pdf", mime_type="application/pdf", extracted_text="report"
        )
        image = SimpleNamespace(
            file_name="markers.png", mime_type="image/png", extracted_text="ER positive"
        )
        private = {
            "text": [
                {"file_name": "case.pdf", "content": "Relevant liver finding"},
                {"file_name": "case.pdf", "content": "Relevant liver finding"},
                {"file_name": "markers.png", "content": "PR positive"},
            ],
            "images": [{"file_name": "markers.png", "content": "markers.png"}],
        }

        result = _uploaded_source_payload([report], [image], private)

        self.assertEqual(len(result), 2)
        self.assertEqual([item["file_name"] for item in result], ["case.pdf", "markers.png"])
        self.assertNotIn("Relevant liver finding", result[0]["content"])
        self.assertEqual(result[0]["evidence_segments"][0]["origin"], "original_extraction")
        self.assertEqual(result[0]["evidence_segments"][1]["origin"], "private_retrieved_chunk")
        self.assertEqual(result[0]["evidence_segments"][1]["content"], "Relevant liver finding")
        self.assertIn("ER positive", result[1]["content"])
        self.assertIn("PR positive", [segment["content"] for segment in result[1]["evidence_segments"]])


if __name__ == "__main__":
    unittest.main()
