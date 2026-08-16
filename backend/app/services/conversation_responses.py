"""Database-backed fast replies for clearly non-clinical conversation."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.models.quick_response import QuickResponse


_SPACE = re.compile(r"\s+")
_PUNCTUATION = re.compile(r"[^a-z0-9'\s]")

_ONCOLOGY_TERMS = {
    "cancer", "oncology", "oncologist", "tumor", "tumour", "carcinoma",
    "malignant", "malignancy", "metastasis", "metastatic", "lesion",
    "lymphoma", "leukemia", "myeloma", "sarcoma", "melanoma", "biopsy",
    "chemotherapy", "chemo", "radiotherapy", "radiation", "immunotherapy",
    "pathology", "histopathology", "cytology", "staging", "grade", "pet",
    "ct", "mri", "scan", "nodule", "mass", "lymph", "node", "her2",
    "ki67", "ki-67", "egfr", "alk", "kras", "brca", "er", "pr", "ihc", "marker",
    "breast", "lung", "liver", "prostate", "colorectal", "colon", "rectal",
    "ovarian", "cervical", "pancreatic", "thyroid", "brain", "bone",
    "report", "clinical", "diagnosis", "prognosis", "remission", "recurrence",
}

_ONCOLOGY_SCOPE_PHRASES = (
    "test result", "test results",
)

_DOCUMENT_ONCOLOGY_PATTERNS = (
    "cancer", "oncology", "carcinoma", "malignant", "malignancy", "metastasis",
    "metastatic", "sarcoma", "lymphoma", "leukemia", "myeloma", "melanoma",
    "neoplasm", "tumor", "tumour", "chemotherapy", "radiotherapy",
    "immunotherapy", "core biopsy", "histopathology report", "staging work up",
    "staging workup", "known case of carcinoma", "her2/neu", "ki-67",
    "invasive ductal", "invasive lobular", "pet-ct", "pet/ct",
)


def is_oncology_scope(message: str | None, conversation_history: list[dict[str, str]] | None = None) -> bool:
    """Conservatively allow oncology questions and contextual follow-ups."""
    combined = " ".join(filter(None, [message or "", *[
        f"{turn.get('user', '')} {turn.get('assistant', '')}"
        for turn in (conversation_history or [])[-3:]
    ]]))
    words = set(normalize_message(combined).split())
    normalized = normalize_message(combined)
    return bool(words & _ONCOLOGY_TERMS) or any(
        phrase in normalized for phrase in _ONCOLOGY_SCOPE_PHRASES
    )


def is_oncology_document(text: str | None) -> bool:
    """Identify explicit oncology content in OCR/report text without treating any lab report as cancer evidence."""
    normalized = normalize_message(text or "")
    return any(normalize_message(pattern) in normalized for pattern in _DOCUMENT_ONCOLOGY_PATTERNS)


def out_of_scope_result(summary: str | None = None) -> dict:
    return {
        "query_type": "out_of_scope",
        "response_type": "out_of_scope",
        "intent": "scope_refusal",
        "summary": summary or (
            "Sorry, I can only help with oncology-related reports, medical images, "
            "cancer evidence, and questions about information in your uploaded files. "
            "I don’t have reliable information for that request. Please ask an "
            "oncology-related question or upload relevant clinical material."
        ),
        "evidence": [],
        "supporting_image_evidence": [],
        "diagnostics": {"scope_guard": "out_of_scope"},
        "model_name": "oncology-scope-guard-v1",
        "disclaimer": None,
    }


def managed_response(db: Session, key: str, fallback: str) -> str:
    """Fetch a reusable system message from PostgreSQL with a safe fallback."""
    record = (
        db.query(QuickResponse)
        .filter(
            QuickResponse.trigger_phrase == f"__{key}__",
            QuickResponse.active.is_(True),
        )
        .first()
    )
    return record.response_text if record else fallback


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
    response_type = "product_help" if record.intent == "product_help" else "conversation"
    return {
        "query_type": response_type,
        "response_type": response_type,
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
