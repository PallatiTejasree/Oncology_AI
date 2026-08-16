"""Small contract tests for the documented ingestion/query architecture."""

import unittest
from pathlib import Path

from app.models import medical_image, report, summary, upload_session, user
from app.services.upload_ingestion import (
    MIN_QUALITY_SCORE,
    USER_IMAGE_COLLECTION,
    USER_TEXT_COLLECTION,
)
from app.services.conversation_cache import conversation_cache


class ArchitectureContractTests(unittest.TestCase):
    def test_ingestion_quality_gate_and_private_collections_are_explicit(self):
        self.assertEqual(MIN_QUALITY_SCORE, 40.0)
        self.assertNotEqual(USER_TEXT_COLLECTION, USER_IMAGE_COLLECTION)
        self.assertIn("user_upload", USER_TEXT_COLLECTION)
        self.assertIn("user_upload", USER_IMAGE_COLLECTION)

    def test_postgres_models_cover_required_persistent_state(self):
        self.assertTrue({"email", "password_hash", "recovery_pin_hash"}.issubset(user.User.__table__.columns.keys()))
        self.assertTrue({"status", "failure_reason", "archived_at"}.issubset(upload_session.UploadSession.__table__.columns.keys()))
        required_file_fields = {"file_path", "processing_status", "rejection_reason", "quality_score", "quality_reasons_json"}
        self.assertTrue(required_file_fields.issubset(report.Report.__table__.columns.keys()))
        self.assertTrue(required_file_fields.issubset(medical_image.MedicalImage.__table__.columns.keys()))
        self.assertTrue({"diagnostics_json", "evidence_json", "confidence_score"}.issubset(summary.Summary.__table__.columns.keys()))

    def test_fastapi_does_not_mutate_schema_at_startup(self):
        main_source = Path(__file__).parents[1] / "app" / "main.py"
        self.assertNotIn("metadata.create_all", main_source.read_text())

    def test_postgres_is_the_conversation_context_source_of_truth(self):
        source = Path(__file__).parents[1] / "app" / "services" / "conversation_cache.py"
        text = source.read_text()
        self.assertIn("db.query(ChatHistory)", text)
        self.assertIsNotNone(conversation_cache)

    def test_analysis_route_passes_private_retrieval_into_orchestration(self):
        source = Path(__file__).parents[1] / "app" / "api" / "routes" / "analysis.py"
        text = source.read_text()
        self.assertIn("private_evidence=private_evidence", text)


if __name__ == "__main__":
    unittest.main()
