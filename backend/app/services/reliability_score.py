"""Transparent, uncalibrated evidence-support scoring for generated answers."""

from __future__ import annotations

import json
import re
from typing import Any


_UNCERTAINTY = re.compile(
    r"\b(?:cannot exclude|indeterminate|insufficient|not documented|not available|"
    r"pending|possible|possibly|suspicious|uncertain|unknown|unclear)\b",
    re.I,
)


def _clamp(value: float) -> int:
    return round(max(0.0, min(100.0, value)))


def _label(score: int) -> str:
    if score >= 85:
        return "High evidence support"
    if score >= 70:
        return "Moderate evidence support"
    if score >= 50:
        return "Limited evidence support"
    return "Low evidence support"


def _document_support(result: dict[str, Any]) -> int:
    sources = result.get("uploaded_sources") or []
    if not sources:
        return 25
    validation = result.get("citation_validation") or {}
    uploaded_citations = {
        citation for citation in (validation.get("used") or [])
        if re.fullmatch(r"U\d+", str(citation))
    }
    invalid_uploaded = {
        citation for citation in (validation.get("invalid") or [])
        if re.fullmatch(r"U\d+", str(citation))
    }
    if uploaded_citations and not invalid_uploaded:
        # One uploaded patient document is sufficient to establish the source
        # for the answer. Citation count must not penalize a complete report.
        return 100
    content = json.dumps(
        [result.get("summary"), result.get("structured_answer")], ensure_ascii=False
    )
    inline_citations = set(re.findall(r"\bU\d+\b", content))
    return _clamp(55 + 15 * min(len(inline_citations), 3))


def _retrieval_support(result: dict[str, Any]) -> int:
    evidence = [
        *(result.get("evidence") or []),
        *(result.get("supporting_image_evidence") or []),
    ]
    if not evidence:
        return 20
    # Rank/count signals are comparable across modalities; raw MedCPT and
    # BiomedCLIP values deliberately are not combined as if on one scale.
    modalities = {str(item.get("modality") or "text") for item in evidence}
    count_score = min(70, 25 + len(evidence) * 10)
    modality_bonus = 15 if len(modalities) > 1 else 5
    return _clamp(count_score + modality_bonus)


def _citation_support(result: dict[str, Any]) -> int:
    validation = result.get("citation_validation") or {}
    used = validation.get("used") or []
    invalid = validation.get("invalid") or []
    if invalid:
        return _clamp(30 - 10 * len(invalid))
    if validation.get("status") == "valid":
        return _clamp(65 + 8 * min(len(used), 4))
    return 35


def _agreement(result: dict[str, Any]) -> int:
    consistency = (result.get("diagnostics") or {}).get("upload_consistency") or {}
    if consistency.get("status") == "mismatch":
        return 0
    if consistency.get("consistent") is False:
        return 35
    structured = result.get("structured_answer") or {}
    balance = structured.get("evidence_balance") or {}
    against = balance.get("against") or balance.get("does_not_support") or []
    return 60 if against else 90


def _completeness(result: dict[str, Any]) -> int:
    structured = result.get("structured_answer") or {}
    limitations = structured.get("limitations") or []
    if isinstance(limitations, str):
        limitations = [limitations]
    text = " ".join(filter(None, [result.get("summary") or "", json.dumps(limitations)]))
    uncertainty_count = len(_UNCERTAINTY.findall(text))
    return _clamp(90 - min(45, len(limitations) * 8 + uncertainty_count * 5))


def calculate_reliability(result: dict[str, Any]) -> dict[str, Any] | None:
    """Return an evidence-support heuristic, not a correctness probability."""
    if result.get("response_type") in {"conversation", "rejection", "out_of_scope", "safety"}:
        return None
    if not any((result.get("uploaded_sources"), result.get("evidence"), result.get("supporting_image_evidence"))):
        return None

    components = {
        "patient_document_support": _document_support(result),
        "retrieval_support": _retrieval_support(result),
        "citation_support": _citation_support(result),
        "evidence_agreement": _agreement(result),
        "completeness": _completeness(result),
    }
    score = _clamp(
        components["patient_document_support"] * 0.35
        + components["retrieval_support"] * 0.25
        + components["citation_support"] * 0.20
        + components["evidence_agreement"] * 0.10
        + components["completeness"] * 0.10
    )
    reasons = []
    reasons.append(
        "Uploaded patient material directly supports the response."
        if components["patient_document_support"] >= 70
        else "Direct support from uploaded patient material is limited."
    )
    reasons.append(
        "Supporting clinical evidence was retrieved."
        if components["retrieval_support"] >= 60
        else "Little supporting clinical evidence was retrieved."
    )
    reasons.append(
        "Citation identifiers passed structural validation."
        if components["citation_support"] >= 60
        else "Citation support is missing or limited."
    )
    if components["completeness"] < 70:
        reasons.append("Some information remains missing or uncertain.")
    return {
        "score": score,
        "label": _label(score),
        "calibrated": False,
        "components": components,
        "explanation": "This heuristic reflects evidence support, not diagnostic accuracy or the probability that the answer is correct.",
        "reasons": reasons,
    }
