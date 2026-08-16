"""Seed PostgreSQL-managed quick responses.

Revision ID: 20260811_0002
Revises: 20260811_0001
Create Date: 2026-08-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from migrations.add_quick_responses import RESPONSES


revision: str = "20260811_0002"
down_revision: Union[str, None] = "20260811_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    statement = sa.text(
        """
        INSERT INTO quick_responses
            (intent, trigger_phrase, response_text, active)
        VALUES
            (:intent, :trigger_phrase, :response_text, TRUE)
        ON CONFLICT (trigger_phrase) DO UPDATE SET
            intent = EXCLUDED.intent,
            response_text = EXCLUDED.response_text,
            active = TRUE,
            updated_at = NOW()
        """
    )
    rows = [
        {
            "intent": intent,
            "trigger_phrase": trigger_phrase,
            "response_text": response_text,
        }
        for intent, entries in RESPONSES.items()
        for trigger_phrase, response_text in entries.items()
    ]
    connection.execute(statement, rows)


def downgrade() -> None:
    connection = op.get_bind()
    statement = sa.text(
        "DELETE FROM quick_responses WHERE trigger_phrase = :trigger_phrase"
    )
    for entries in RESPONSES.values():
        for trigger_phrase in entries:
            connection.execute(statement, {"trigger_phrase": trigger_phrase})
