"""Add structured analysis-history columns to an existing PostgreSQL database."""

from sqlalchemy import text

from app.db.database import engine


STATEMENTS = (
    # Upgrade legacy tables created by the project's earlier schema.
    "ALTER TABLE upload_sessions ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
    "ALTER TABLE upload_sessions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()",
    "UPDATE upload_sessions SET created_at = upload_time WHERE upload_time IS NOT NULL",
    "UPDATE upload_sessions SET updated_at = COALESCE(created_at, NOW()) WHERE updated_at IS NULL",
    "ALTER TABLE reports ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
    "UPDATE reports SET created_at = uploaded_at WHERE uploaded_at IS NOT NULL",
    "ALTER TABLE medical_images ADD COLUMN IF NOT EXISTS file_name VARCHAR(255)",
    "ALTER TABLE medical_images ADD COLUMN IF NOT EXISTS file_path VARCHAR(500)",
    "ALTER TABLE medical_images ADD COLUMN IF NOT EXISTS image_type VARCHAR(100)",
    "ALTER TABLE medical_images ADD COLUMN IF NOT EXISTS extracted_text TEXT",
    "ALTER TABLE medical_images ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
    "UPDATE medical_images SET file_name = image_name WHERE file_name IS NULL",
    "UPDATE medical_images SET file_path = image_path WHERE file_path IS NULL",
    "UPDATE medical_images SET extracted_text = ocr_text WHERE extracted_text IS NULL",
    "UPDATE medical_images SET created_at = uploaded_at WHERE uploaded_at IS NOT NULL",
    "ALTER TABLE summaries ADD COLUMN IF NOT EXISTS ai_summary TEXT",
    "ALTER TABLE summaries ADD COLUMN IF NOT EXISTS confidence_score DOUBLE PRECISION",
    "ALTER TABLE summaries ADD COLUMN IF NOT EXISTS model_name VARCHAR(100)",
    "ALTER TABLE summaries ADD COLUMN IF NOT EXISTS processing_status VARCHAR(50) DEFAULT 'Completed'",
    "ALTER TABLE summaries ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
    "UPDATE summaries SET ai_summary = summary WHERE ai_summary IS NULL",
    "UPDATE summaries SET created_at = generated_at WHERE generated_at IS NOT NULL",
    "ALTER TABLE upload_sessions ADD COLUMN IF NOT EXISTS input_type VARCHAR(20) NOT NULL DEFAULT 'upload'",
    "ALTER TABLE upload_sessions ADD COLUMN IF NOT EXISTS original_query TEXT",
    "ALTER TABLE upload_sessions ADD COLUMN IF NOT EXISTS top_k INTEGER NOT NULL DEFAULT 5",
    "ALTER TABLE upload_sessions ADD COLUMN IF NOT EXISTS failure_reason TEXT",
    "ALTER TABLE upload_sessions ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ",
    "ALTER TABLE reports ADD COLUMN IF NOT EXISTS mime_type VARCHAR(100)",
    "ALTER TABLE reports ADD COLUMN IF NOT EXISTS file_size INTEGER",
    "ALTER TABLE reports ADD COLUMN IF NOT EXISTS sha256 VARCHAR(64)",
    "ALTER TABLE reports ADD COLUMN IF NOT EXISTS processing_status VARCHAR(50) NOT NULL DEFAULT 'Uploaded'",
    "ALTER TABLE reports ADD COLUMN IF NOT EXISTS rejection_reason TEXT",
    "ALTER TABLE medical_images ADD COLUMN IF NOT EXISTS mime_type VARCHAR(100)",
    "ALTER TABLE medical_images ADD COLUMN IF NOT EXISTS file_size INTEGER",
    "ALTER TABLE medical_images ADD COLUMN IF NOT EXISTS sha256 VARCHAR(64)",
    "ALTER TABLE medical_images ADD COLUMN IF NOT EXISTS width INTEGER",
    "ALTER TABLE medical_images ADD COLUMN IF NOT EXISTS height INTEGER",
    "ALTER TABLE medical_images ADD COLUMN IF NOT EXISTS processing_status VARCHAR(50) NOT NULL DEFAULT 'Uploaded'",
    "ALTER TABLE medical_images ADD COLUMN IF NOT EXISTS rejection_reason TEXT",
    "ALTER TABLE summaries ADD COLUMN IF NOT EXISTS query_type VARCHAR(50)",
    "ALTER TABLE summaries ADD COLUMN IF NOT EXISTS retrieval_status VARCHAR(50)",
    "ALTER TABLE summaries ADD COLUMN IF NOT EXISTS diagnostics_json TEXT",
    "ALTER TABLE summaries ADD COLUMN IF NOT EXISTS evidence_json TEXT",
    "ALTER TABLE summaries ADD COLUMN IF NOT EXISTS disclaimer TEXT",
    "ALTER TABLE summaries ADD COLUMN IF NOT EXISTS calibrated BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE summaries ADD COLUMN IF NOT EXISTS processing_time_ms INTEGER",
    "ALTER TABLE summaries ADD COLUMN IF NOT EXISTS failure_reason TEXT",
    "CREATE INDEX IF NOT EXISTS ix_upload_sessions_user_created ON upload_sessions (user_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS ix_summaries_session_created ON summaries (session_id, created_at DESC)",
)


def main() -> None:
    with engine.begin() as connection:
        for statement in STATEMENTS:
            connection.execute(text(statement))
    print(f"Applied {len(STATEMENTS)} idempotent analysis-history migration steps.")


if __name__ == "__main__":
    main()
