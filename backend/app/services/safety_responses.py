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
    r"severe shortness of breath", r"severe difficulty breathing",
    r"struggling to breathe", r"unable to catch (?:my |their |his |her )?breath",
    r"cannot speak normally.{0,50}(?:breath|breathing)|(?:breath|breathing).{0,50}cannot speak normally",
    r"coughing up blood", r"heavy bleeding", r"bleeding heavily", r"feel(?:ing)? faint", r"fainting", r"suicid",
)

_NEGATION = re.compile(
    r"\b(?:no|denies?|without|not present|not documented|no evidence of)\b", re.I
)
_HYPOTHETICAL = re.compile(
    r"\b(?:would require|could require|if (?:this occurs|the patient develops)|"
    r"if .{0,80}(?:develops?|occurs?|happens?)|go to (?:the )?emergency department if|call emergency services if|"
    r"seek emergency care if|warning signs include|return immediately for|"
    r"evaluation target|testing instruction|(?:a safe )?ai should|expected ai safety)\b", re.I
)
_HISTORICAL = re.compile(
    r"\b(?:history of|previously|in the past|last (?:week|month|year)|had|experienced)\b", re.I
)
_EXCLUDED_SECTION = re.compile(
    r"\b(?:recommendations?|report limitations?|synthetic(?:/test)? metadata|"
    r"ai evaluation targets?|testing instructions?|warning signs?)\b", re.I
)
_CURRENT_SECTION = re.compile(
    r"\b(?:current clinical history|clinical history|current presentation|presentation|"
    r"current examination|examination|history of present illness|chief complaint)\b", re.I
)


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|[\r\n]+", text) if part.strip()]


def _contextual_matches(text: str, *, require_current_section: bool = False) -> dict:
    """Classify warning-sign mentions without treating negated/instructional prose as symptoms."""
    active: list[str] = []
    negated: list[str] = []
    hypothetical: list[str] = []
    excluded_sections: list[str] = []
    current_section = not require_current_section
    for sentence in _sentences(text):
        heading = sentence.rstrip(":").strip()
        if _CURRENT_SECTION.search(heading):
            current_section = True
        elif _EXCLUDED_SECTION.search(heading):
            current_section = False
            excluded_sections.append(heading[:120])
        matches = [m.group(0) for pattern in EMERGENCY_PATTERNS for m in re.finditer(pattern, sentence, re.I)]
        if not matches:
            continue
        if _NEGATION.search(sentence):
            negated.extend(matches)
        elif _HYPOTHETICAL.search(sentence) or _HISTORICAL.search(sentence):
            hypothetical.extend(matches)
        elif current_section:
            active.extend(matches)
        else:
            hypothetical.extend(matches)
    return {
        "active_matches": list(dict.fromkeys(active)),
        "negated_matches": list(dict.fromkeys(negated)),
        "hypothetical_matches": list(dict.fromkeys(hypothetical)),
        "excluded_sections": list(dict.fromkeys(excluded_sections)),
    }

PROMPT_REVIEW_PATTERNS = (
    r"persistent fever", r"fever.*chemotherapy", r"fever.*chemo",
    r"new confusion", r"worsening pain", r"uncontrolled pain",
    r"unable to (eat|drink|keep.*down)", r"repeated vomiting",
    r"new weakness", r"rapidly worsening",
)

DOCUMENT_PROMPT_REVIEW_PATTERNS = (
    # Generic documented findings that warrant timely specialist review. These
    # are review signals, not diagnoses, stages, or risk estimates.
    r"priority clinician review", r"high[- ]risk oncology",
    r"(?:biopsy|pathology)[- ]?(?:proven|confirmed).{0,80}(?:invasive|carcinoma|malignan)",
    r"\b(?:carcinoma|malignan\w*|invasive cancer)\b",
    r"(?:invasive|malignan\w*|carcinoma).{0,80}(?:confirmed|documented|established)",
    r"(?:positive|confirmed).{0,80}(?:lymph[- ]node|nodal)",
    r"(?:lymph[- ]node|nodal).{0,80}(?:metasta|involvement)",
    r"(?:staging|stage).{0,80}(?:unresolved|uncertain|pending|indeterminate|incomplete)",
    r"(?:indeterminate|suspicious).{0,80}(?:distant|metasta|spread)",
)


def care_urgency(
    message: str | None,
    documented_evidence: object | None = None,
    uploaded_document: str | None = None,
) -> dict:
    """Return conservative triage guidance, never a diagnosis or risk score."""
    text = " ".join((message or "").split())
    user_matches = _contextual_matches(text)
    document_matches = _contextual_matches(uploaded_document or "", require_current_section=True)
    diagnostics = {
        "triggered": False,
        "trigger_source": "none",
        "active_matches": [],
        "negated_matches": list(dict.fromkeys(user_matches["negated_matches"] + document_matches["negated_matches"])),
        "hypothetical_matches": list(dict.fromkeys(user_matches["hypothetical_matches"] + document_matches["hypothetical_matches"])),
        "excluded_sections": document_matches["excluded_sections"],
        "reason": "No active emergency finding was identified.",
        "citations": [],
    }
    active = user_matches["active_matches"] or document_matches["active_matches"]
    if active:
        source = "user_message" if user_matches["active_matches"] else "uploaded_current_finding"
        diagnostics.update({
            "triggered": True, "trigger_source": source,
            "active_matches": active,
            "reason": "An active current emergency warning sign was explicitly reported.",
        })
        return {
            **diagnostics,
            "level": "emergency", "label": "Emergency",
            "message": "An active emergency warning sign was reported. Contact local emergency services or go to the nearest emergency department now.",
            "basis": f"Active warning-sign language in {source.replace('_', ' ')}",
            "calibrated": False,
        }
    if not text and not uploaded_document:
        return {
            **diagnostics,
            "level": "insufficient",
            "label": "Insufficient information",
            "message": "There is not enough symptom information to determine care urgency. A clinician should review the complete clinical context.",
            "basis": "No symptom description was available for urgency screening",
            "calibrated": False,
        }
    symptom_prompt = any(re.search(pattern, text, re.I) for pattern in PROMPT_REVIEW_PATTERNS)
    evidence_text = str(documented_evidence or "") + " " + (uploaded_document or "")
    document_prompt = any(
        re.search(pattern, candidate)
        for candidate in (text, evidence_text)
        for pattern in DOCUMENT_PROMPT_REVIEW_PATTERNS
    )
    if symptom_prompt or document_prompt:
        return {
            **diagnostics,
            "level": "prompt",
            "label": "Prompt review",
            "message": (
                "The uploaded report contains findings that warrant timely review by the treating oncology team. No immediate emergency warning was identified."
                if document_prompt and not symptom_prompt else
                "The reported symptoms should be discussed promptly with the treating clinical team or an urgent-care service."
            ),
            "basis": (
                "Explicit high-priority clinical language in uploaded material"
                if document_prompt and not symptom_prompt else
                "Explicit symptom language in the user's message"
            ),
            "calibrated": False,
        }
    return {
        **diagnostics,
        "level": "routine",
        "label": "Routine review",
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

    if care_urgency(message)["level"] == "emergency":
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
