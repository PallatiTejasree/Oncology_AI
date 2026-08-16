"""Baseline Oncology AI PostgreSQL schema.

Revision ID: 20260811_0001
Revises: None
Create Date: 2026-08-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260811_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _id_index(table: str) -> None:
    op.create_index(f"ix_{table}_id", table, ["id"])


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("recovery_pin_hash", sa.String(64), nullable=True),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("gender", sa.String(), nullable=True),
        sa.Column("occupation", sa.String(), nullable=True),
        sa.Column("profile_completed", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
    )
    _id_index("users")
    op.create_index("ix_users_recovery_pin_hash", "users", ["recovery_pin_hash"], unique=True)

    op.create_table(
        "quick_responses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("intent", sa.String(50), nullable=False),
        sa.Column("trigger_phrase", sa.String(255), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    _id_index("quick_responses")
    op.create_index("ix_quick_responses_intent", "quick_responses", ["intent"])
    op.create_index("ix_quick_responses_trigger_phrase", "quick_responses", ["trigger_phrase"], unique=True)
    op.create_index("ix_quick_responses_active", "quick_responses", ["active"])

    op.create_table(
        "chats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    _id_index("chats")

    op.create_table(
        "upload_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_name", sa.String(255), nullable=False),
        sa.Column("custom_title", sa.String(80), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("input_type", sa.String(20), nullable=False),
        sa.Column("original_query", sa.Text(), nullable=True),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    _id_index("upload_sessions")
    op.create_index("ix_upload_sessions_user_created", "upload_sessions", ["user_id", "created_at"])
    op.create_index("ix_upload_sessions_user_archived", "upload_sessions", ["user_id", "archived_at"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chat_id", sa.Integer(), sa.ForeignKey("chats.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    _id_index("messages")

    for table_name in ("reports", "medical_images"):
        columns = [
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("session_id", sa.Integer(), sa.ForeignKey("upload_sessions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("file_name", sa.String(255), nullable=False),
            sa.Column("file_path", sa.String(500), nullable=False),
        ]
        if table_name == "medical_images":
            columns.append(sa.Column("image_type", sa.String(100), nullable=True))
        columns.extend([
            sa.Column("extracted_text", sa.Text(), nullable=True),
            sa.Column("mime_type", sa.String(100), nullable=True),
            sa.Column("file_size", sa.Integer(), nullable=True),
            sa.Column("sha256", sa.String(64), nullable=True),
        ])
        if table_name == "medical_images":
            columns.extend([
                sa.Column("width", sa.Integer(), nullable=True),
                sa.Column("height", sa.Integer(), nullable=True),
            ])
        columns.extend([
            sa.Column("processing_status", sa.String(50), nullable=False),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("quality_score", sa.Float(), nullable=True),
            sa.Column("quality_reasons_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        ])
        op.create_table(table_name, *columns)
        _id_index(table_name)

    op.create_table(
        "summaries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("upload_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column("processing_status", sa.String(50), nullable=True),
        sa.Column("query_type", sa.String(50), nullable=True),
        sa.Column("retrieval_status", sa.String(50), nullable=True),
        sa.Column("diagnostics_json", sa.Text(), nullable=True),
        sa.Column("evidence_json", sa.Text(), nullable=True),
        sa.Column("disclaimer", sa.Text(), nullable=True),
        sa.Column("calibrated", sa.Boolean(), nullable=False),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    _id_index("summaries")
    op.create_index("ix_summaries_session_created", "summaries", ["session_id", "created_at"])

    op.create_table(
        "chat_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("upload_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    _id_index("chat_history")


def downgrade() -> None:
    # Reverse dependency order prevents foreign-key violations.
    for table_name in (
        "chat_history",
        "summaries",
        "medical_images",
        "reports",
        "messages",
        "upload_sessions",
        "chats",
        "quick_responses",
        "users",
    ):
        op.drop_table(table_name)
