import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.api.routes.analysis import _store_result
from app.models.chat import Chat
from app.models.medical_image import MedicalImage
from app.models.message import Message
from app.models.report import Report
from app.models.summary import Summary
from app.models.upload_session import UploadSession
from app.models.user import User


class _FakeDb:
    def __init__(self):
        self.added = []

    def add(self, value):
        self.added.append(value)

    def commit(self):
        return None

    def refresh(self, value):
        value.id = 1


class GenerationDiagnosticsPersistenceTests(unittest.TestCase):
    def test_generation_mode_and_quota_diagnostics_are_persisted(self):
        db = _FakeDb()
        session = SimpleNamespace(
            id=9, user_id=4, reports=[], medical_images=[], input_type="text",
            original_query="Explain this report", session_name="Analysis-test",
            status="Processing", failure_reason=None, completed_at=None,
        )
        generation = {
            "generation_mode": "extractive_fallback",
            "provider_status": "quota_exhausted",
            "provider_error_code": 429,
            "quota_exhausted": True,
            "retry_after": 59.0,
            "fallback_reason": "daily_quota_exhausted",
            "gemini_calls_attempted": 1,
            "gemini_calls_skipped_due_to_quota": 1,
        }
        result = {
            "summary": "Grounded retrieval-only summary.",
            "model_name": "retrieval-only",
            "generation_mode": "extractive_fallback",
            "generation_diagnostics": generation,
            "diagnostics": {"text": {"status": "retrieved"}},
        }
        with (
            patch("app.api.routes.analysis.conversation_cache.append"),
            patch("app.api.routes.analysis.chat_history_store.append"),
        ):
            _store_result(db, session, result, 25)
        stored = next(item for item in db.added if isinstance(item, Summary))
        self.assertIsNone(stored.ai_summary)
        diagnostics = json.loads(stored.diagnostics_json)
        self.assertEqual(diagnostics["generation"]["generation_mode"], "extractive_fallback")
        self.assertEqual(diagnostics["generation"]["provider_error_code"], 429)
        self.assertTrue(diagnostics["generation"]["quota_exhausted"])


if __name__ == "__main__":
    unittest.main()
