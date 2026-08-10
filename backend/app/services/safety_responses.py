"""Deterministic routing for urgent and unsafe medical requests."""

from __future__ import annotations

import re


DISCLAIMER = (
    "AI-generated clinical decision support only. It must not replace emergency "
    "care, professional medical judgment, diagnosis, or treatment."
)

EMERGENCY_PATTERNS = (
    r"severe chest pain", r"difficulty breathing", r"can't breathe",
    r"cannot breathe", r"trouble breathing", r"unconscious",
    r"coughing up blood", r"heavy bleeding", r"suicid",
)

PROMPT_REVIEW_PATTERNS = (
    r"persistent fever", r"fever.*chemotherapy", r"fever.*chemo",
    r"new confusion", r"worsening pain", r"uncontrolled pain",
    r"unable to (eat|drink|keep.*down)", r"repeated vomiting",
    r"new weakness", r"rapidly worsening",
)


def care_urgency(message: str | None) -> dict:
    """Return conservative triage guidance, never a diagnosis or risk score."""
    text = " ".join((message or "").lower().split())
    if text and any(re.search(pattern, text) for pattern in EMERGENCY_PATTERNS):
        return {
            "level": "emergency",
            "label": "Emergency care now",
            "message": "The question includes a possible emergency warning sign. Contact local emergency services or go to the nearest emergency department now.",
            "basis": "Explicit warning-sign language in the user's message",
            "calibrated": False,
        }
    if text and any(re.search(pattern, text) for pattern in PROMPT_REVIEW_PATTERNS):
        return {
            "level": "prompt",
            "label": "Contact a clinician promptly",
            "message": "The question includes symptoms that should be discussed promptly with the treating clinical team or an urgent-care service.",
            "basis": "Explicit symptom language in the user's message",
            "calibrated": False,
        }
    return {
        "level": "routine",
        "label": "No urgent warning detected",
        "message": "No emergency warning phrase was detected. This does not prove the situation is low risk; a clinician must interpret the complete clinical context.",
        "basis": "No explicit warning-sign language detected in the user's message",
        "calibrated": False,
    }


def _result(summary: str, category: str) -> dict:
    return {
        "query_type": "safety",
        "response_type": "safety",
        "safety_category": category,
        "summary": summary,
        "evidence": [],
        "supporting_image_evidence": [],
        "diagnostics": {},
        "model_name": "deterministic-safety-v1",
        "care_urgency": care_urgency(summary if category != "emergency" else "difficulty breathing"),
        "disclaimer": DISCLAIMER,
    }


def safety_result(message: str | None) -> dict | None:
    if not message:
        return None
    text = " ".join(message.lower().split())

    if any(re.search(pattern, text) for pattern in EMERGENCY_PATTERNS):
        return _result(
            "This may require urgent medical attention. Please contact your local emergency services or go to the nearest emergency department now. Do not wait for an AI response. If possible, ask someone nearby to assist you.",
            "emergency",
        )

    certainty_patterns = (
        r"guarantee.*(no|not).*cancer", r"100\s*%.*(certain|certainty)",
        r"definitive diagnosis", r"tell me for sure.*cancer",
    )
    if any(re.search(pattern, text) for pattern in certainty_patterns):
        return _result(
            "I cannot guarantee or provide a definitive cancer diagnosis. I can explain retrieved evidence from a report or image, but diagnosis requires appropriate testing and professional clinical interpretation.",
            "diagnostic_certainty",
        )

    prescribing_patterns = (
        r"which chemotherapy.*(take|use)", r"prescribe", r"choose.*treatment for me",
        r"what dose.*(take|use)", r"stop taking my",
    )
    if any(re.search(pattern, text) for pattern in prescribing_patterns):
        return _result(
            "I can explain treatments or medicines mentioned in clinical evidence, but I cannot prescribe, select, stop, or dose treatment. Please discuss that decision with your oncology team, who can review your complete clinical situation.",
            "prescribing",
        )
    return None
