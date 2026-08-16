import os
import unittest
from unittest.mock import patch

from app.langchain.service import LangChainAnalysisService


class LangChainServiceTests(unittest.TestCase):
    def test_fastapi_service_invokes_pipeline_through_runnable(self):
        service = LangChainAnalysisService()
        expected = {"summary": "connected"}
        with patch("app.langchain.service.get_analysis_pipeline") as factory:
            factory.return_value.analyze.return_value = expected
            result = service.analyze(text="oncology question", top_k=5)
        self.assertEqual(result, expected)
        factory.return_value.analyze.assert_called_once_with(text="oncology question", top_k=5)

    def test_status_never_exposes_api_key(self):
        service = LangChainAnalysisService()
        with patch.dict(os.environ, {"GEMINI_API_KEY": "secret-test-key", "GEMINI_MODEL": "gemini-test"}):
            status = service.status()
        self.assertTrue(status["connected"])
        self.assertTrue(status["gemini_configured"])
        self.assertEqual(status["gemini_model"], "gemini-test")
        self.assertNotIn("api_key", status)
        self.assertNotIn("secret-test-key", str(status))


if __name__ == "__main__":
    unittest.main()
