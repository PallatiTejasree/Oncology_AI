"""Database-backed fast replies for clearly non-clinical conversation."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.models.quick_response import QuickResponse


_SPACE = re.compile(r"\s+")
_PUNCTUATION = re.compile(r"[^a-z0-9'\s]")


def normalize_message(message: str) -> str:
    value = _PUNCTUATION.sub(" ", message.lower())
    return _SPACE.sub(" ", value).strip()


def conversational_response(db: Session, message: str | None) -> str | None:
    """Look up an exact conversational intent without intercepting medical text."""
    if not message:
        return None
    normalized = normalize_message(message)
    record = (
        db.query(QuickResponse)
        .filter(
            QuickResponse.trigger_phrase == normalized,
            QuickResponse.active.is_(True),
        )
        .first()
    )
    return record.response_text if record else None


def conversational_result(db: Session, message: str | None) -> dict | None:
    if not message:
        return None
    normalized = normalize_message(message)
    record = (
        db.query(QuickResponse)
        .filter(
            QuickResponse.trigger_phrase == normalized,
            QuickResponse.active.is_(True),
        )
        .first()
    )
    if record is None:
        return None
    return {
        "query_type": "conversation",
        "response_type": "conversation",
        "intent": record.intent,
        "summary": record.response_text,
        "evidence": [],
        "supporting_image_evidence": [],
        "diagnostics": {},
        "model_name": "postgres-quick-response-v1",
        "disclaimer": (
            "For clinical questions, retrieved information is decision support only "
            "and does not replace professional medical judgment."
        ),
    }
