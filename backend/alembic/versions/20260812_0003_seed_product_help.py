"""Seed deterministic product-help responses.

Revision ID: 20260812_0003
Revises: 20260811_0002
Create Date: 2026-08-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from migrations.add_quick_responses import RESPONSES


revision: str = "20260812_0003"
down_revision: Union[str, None] = "20260811_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    statement = sa.text(
        """
        INSERT INTO quick_responses
            (intent, trigger_phrase, response_text, active)
        VALUES
            ('product_help', :trigger_phrase, :response_text, TRUE)
        ON CONFLICT (trigger_phrase) DO UPDATE SET
            intent = EXCLUDED.intent,
            response_text = EXCLUDED.response_text,
            active = TRUE,
            updated_at = NOW()
        """
    )
    connection.execute(
        statement,
        [
            {"trigger_phrase": trigger, "response_text": response}
            for trigger, response in RESPONSES["product_help"].items()
        ],
    )


def downgrade() -> None:
    connection = op.get_bind()
    statement = sa.text(
        "DELETE FROM quick_responses WHERE trigger_phrase = :trigger_phrase"
    )
    for trigger in RESPONSES["product_help"]:
        connection.execute(statement, {"trigger_phrase": trigger})
