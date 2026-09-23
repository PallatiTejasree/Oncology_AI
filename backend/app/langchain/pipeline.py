"""Application-facing retrieval and grounded-summary pipeline.

This module deliberately reuses the validated top-level ``Query`` package so
the API cannot silently use a different embedding model from the Chroma index.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.langchain.prompt_store import prompt_metadata, prompt_template

logger = logging.getLogger(__name__)


def _analysis_timing(stage: str, started: float) -> None:
    """Log duration only; prompts and clinical inputs must never enter logs."""
    logger.info("[analysis] %s: %.2fs", stage, time.perf_counter() - started)


def _classify_provider_error(error: Exception | str) -> dict[str, Any]:
    """Normalize Gemini failures without exposing provider payloads to clients."""
    message = str(error)
    upper = message.upper()
    code_match = re.search(r"(?:CODE['\"\s:]+|HTTP\s+)(\d{3})", upper)
    code = int(code_match.group(1)) if code_match else next(
        (candidate for candidate in (429, 503, 504) if str(candidate) in upper), None
    )
    retry_match = re.search(r"retryDelay['\"\s:]+['\"]?(\d+(?:\.\d+)?)s", message, re.I)
    if not retry_match:
        retry_match = re.search(r"retry\s+in\s+(\d+(?:\.\d+)?)s", message, re.I)
    retry_after = float(retry_match.group(1)) if retry_match else None
    daily_quota = code == 429 and any(token in upper for token in (
        "PERDAY", "PER DAY", "FREE_TIER_REQUESTS", "GENERATEREQUESTSPERDAY",
    ))
    if daily_quota:
        status, reason = "quota_exhausted", "daily_quota_exhausted"
    elif code == 429 or "RATE LIMIT" in upper:
        status, reason = "rate_limited", "temporary_rate_limit"
    elif code == 504 or "DEADLINE_EXCEEDED" in upper:
        status, reason = "network_error", "provider_deadline_exceeded"
    elif code == 503 or "UNAVAILABLE" in upper:
        status, reason = "provider_unavailable", "provider_outage"
    elif any(token in upper for token in ("TIMEOUT", "TIMED OUT", "CONNECTION", "NETWORK")):
        status, reason = "network_error", "network_or_timeout"
    else:
        status, reason = "provider_error", "provider_error"
    return {
        "provider_status": status,
        "provider_error_code": code,
        "quota_exhausted": daily_quota,
        "retry_after": retry_after,
        "fallback_reason": reason,
        "retryable": status in {"rate_limited", "provider_unavailable", "network_error"},
    }

_CERTAINTIES = {
    "confirmed", "favored", "suspicious", "indeterminate", "negative",
    "pending", "insufficient_information",
}
_INVENTORY_CATEGORIES = (
    "clinical_context", "diagnoses", "imaging_findings", "pathology_findings",
    "lymph_node_findings", "possible_spread_findings", "immunohistochemistry",
    "biomarkers", "molecular_results", "important_negative_findings",
    "staging_evidence", "staging_uncertainties", "pending_or_recommended_evaluation",
    "limitations",
)
_EVIDENCE_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "fact": {"type": "string"},
        "certainty": {"type": "string", "enum": sorted(_CERTAINTIES)},
        "citations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["fact", "certainty", "citations"],
}
_INVENTORY_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "document": {"type": "object"},
        **{key: {"type": "array", "items": _EVIDENCE_ITEM_SCHEMA} for key in _INVENTORY_CATEGORIES},
    },
    "required": list(_INVENTORY_CATEGORIES),
}

_GENERAL_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"}, "limitations": {"type": "array"},
        "reference_citations": {"type": "array"},
    },
    "required": ["answer", "limitations", "reference_citations"],
}
_FOCUSED_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "certainty": {"type": "string", "enum": sorted(_CERTAINTIES)},
        "citations": {"type": "array"},
    },
    "required": ["answer", "certainty", "citations"],
}
_ANSWER_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "plain_language_summary": {"type": "string"},
        "case_complexity": {
            "type": "object",
            "properties": {
                "level": {"type": "string", "enum": ["low", "moderate", "high", "insufficient_information"]},
                "reason": {"type": "string"},
                "citations": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["level", "reason", "citations"],
        },
        "evidence_support": {
            "type": "object",
            "properties": {
                "level": {"type": "string", "enum": ["Moderate", "Limited", "Insufficient"]},
                "explanation": {"type": "string"},
            },
            "required": ["level", "explanation"],
        },
        "documented_facts": {"type": "array", "items": {"type": "object"}},
        "ai_interpretation": {"type": "array", "items": {"type": "object"}},
        "missing_information": {"type": "array", "items": {"type": "string"}},
        "clinician_questions": {"type": "array", "items": {"type": "string"}},
        "key_findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"}, "result": {"type": "string"},
                    "meaning": {"type": "string"},
                    "certainty": {"type": "string", "enum": sorted(_CERTAINTIES)},
                    "importance": {"type": "string", "enum": ["critical", "high", "supporting"]},
                    "citations": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "result", "meaning", "certainty", "importance", "citations"],
            },
        },
        "limitations": {"type": "array", "items": {"type": "string"}},
        "medical_terms": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"term": {"type": "string"}, "definition": {"type": "string"}},
                "required": ["term", "definition"],
            },
        },
        "staging": {
            "type": "object",
            "properties": {
                "documented_components": {"type": "array", "items": {"type": "string"}},
                "unresolved_components": {"type": "array", "items": {"type": "string"}},
                "final_stage": {"type": ["string", "null"]},
                "can_assign_final_stage": {"type": "boolean"},
                "explanation": {"type": "string"},
                "citations": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["documented_components", "unresolved_components", "final_stage", "can_assign_final_stage", "explanation", "citations"],
        },
        "safety_notice": {"type": "string"},
    },
    "required": ["headline", "plain_language_summary", "case_complexity", "evidence_support", "documented_facts", "ai_interpretation", "missing_information", "clinician_questions", "key_findings", "staging", "limitations", "medical_terms", "safety_notice"],
}


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Query.pipeline import QueryPipeline  # noqa: E402
from app.schemas.analysis import FullReportAnswer  # noqa: E402


DISCLAIMER = (
    "AI-generated clinical decision support only. Results may be incomplete or "
    "incorrect and must not replace professional medical judgment, diagnosis, "
    "or treatment."
)

_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "for", "from", "how",
    "in", "is", "it", "of", "on", "or", "the", "this", "to", "what",
    "with", "my", "me", "does", "key",
}

_GENERIC_QUESTION_TERMS = _STOP_WORDS | {
    "about", "answer", "answers", "can", "could", "describe", "detail",
    "explain", "give", "help", "information", "please", "report", "show",
    "summarize", "summary", "tell", "these", "those", "understand", "oncology",
}

_QUESTION_TERM_ALIASES = {
    "liver": {"hepatic"},
    "hepatic": {"liver"},
    "lymph": {"nodal", "axillary", "node", "lymphadenopathy"},
    "node": {"nodal", "lymph", "axillary"},
    "metastasis": {"metastatic", "metastases", "spread", "metasta", "distant"},
    "metastatic": {"metastasis", "metastases", "spread", "metasta", "distant"},
    "spread": {"metastasis", "metastatic", "metasta"},
    "bone": {"osseous"},
    "lung": {"pulmonary"},
    "egfr": {"epidermal", "growth", "factor", "receptor"},
    "pdl1": {"pd-l1", "programmed", "death", "ligand"},
    "pd-l1": {"pdl1", "programmed", "death", "ligand"},
    "pathology": {"pathologic", "histology", "histologic", "biopsy"},
    "histology": {"pathology", "histologic", "biopsy"},
    "nodes": {"node", "nodal", "lymphadenopathy"},
    "metastases": {"metastasis", "metastatic", "spread", "distant"},
    "lesions": {"lesion", "mass", "nodule"},
    "imaging": {"radiology", "ct", "mri", "pet", "scan"},
}

# Pathology reports often contain laboratory sign-off, regulatory, and testing
# method statements. They describe how a report was produced, not the patient's
# result, so they must not be shown as a clinical finding.
_NONCLINICAL_REPORT_PATTERNS = (
    r"\b(?:personally )?examined the specimen\b",
    r"\b(?:reviewed (?:the )?report|signed (?:it )?electronically)\b",
    r"\banalyte[- ]specific reagents?\b",
    r"\bimmunohistochemical test results?\b",
    r"\b(?:gross and microscopic|microscopic and gross) portions?\b",
    r"\b(?:regulatory|disclaimer|declaration)\b.{0,80}\b(?:report|test|reagent)\b",
    r"\b(?:synthetic|constructed)\b.{0,80}\b(?:case|scenario|evidence|narrative)\b",
    r"\b(?:synthetic|constructed)\b",
    r"\btest case\b|\btesting (?:a )?(?:medical )?ai\b|\bevaluation (?:target|metadata)\b",
)


def _is_nonclinical_report_text(text: str) -> bool:
    """Return whether text is lab process/disclaimer language, not a finding."""
    return any(re.search(pattern, text, re.I) for pattern in _NONCLINICAL_REPORT_PATTERNS)


_FULL_REPORT_REQUEST = re.compile(
    r"\b(?:explain|summari[sz]e|review|analy[sz]e)\b.{0,40}\b(?:complete|whole|entire|full|all)?\s*(?:case|report|file|findings?)\b"
    r"|\b(?:all|every)\b.{0,30}\b(?:important|key|report)?\s*findings?\b",
    re.I,
)
_SYMPTOM_REQUEST = re.compile(
    r"\b(?:chest pain|shortness of breath|difficulty breathing|cannot breathe|can't breathe|fever|dizz(?:y|iness)|headache|nausea|vomiting|bleeding|swelling|weakness|faint(?:ed|ing)?|confusion|one-sided weakness|symptom|pain)\b",
    re.I,
)
_GENERAL_ONCOLOGY_REQUEST = re.compile(
    r"\b(?:what is|what are|what does|explain|define|how does)\b.{0,80}\b(?:mean|work)\b"
    r"|^\s*(?:what is|what are|explain|define)\s+(?!my\b|the\s+(?:report|scan|biopsy|pathology)\b)",
    re.I,
)


def _request_contract(question: str, *, has_uploaded_sources: bool, has_images: bool = False) -> str:
    """Select a task-level contract without keyword-specific medical prompts."""
    if not question.strip() and (has_uploaded_sources or has_images):
        return "full_report"
    if _FULL_REPORT_REQUEST.search(question):
        return "full_report"
    if _SYMPTOM_REQUEST.search(question):
        return "general"
    if _GENERAL_ONCOLOGY_REQUEST.search(question) and not re.search(
        r"\b(?:my|mine|me|patient|report|biopsy|scan|result|documented|found|finding|showed|positive|negative|stage)\b",
        question,
        re.I,
    ):
        return "general"
    if has_uploaded_sources or has_images:
        return "focused"
    return "general"


_QUESTION_INTENTS = {
    "PATHOLOGY": ("diagnosis", "biopsy", "pathology", "histopathology", "histology"),
    "BIOMARKERS": ("biomarker", "molecular", "mutation", "egfr", "alk", "ros1", "kras", "braf", "her2", "pd-l1", "pdl1", "ihc"),
    "MEDICATIONS": ("medication", "medicine", "medications", "medicines", "drug", "drugs", "prescription"),
    "PRIOR_SURGERY": ("cabg", "bypass", "heart operation", "heart surgery", "prior surgery", "previous surgery", "status post", "procedure", "operation"),
    "PAST_HISTORY": ("past medical history", "medical history", "comorbidity", "history of"),
    "IMAGING": ("ct", "pet", "mri", "ultrasound", "scan", "imaging", "radiology"),
    "TREATMENT": ("chemotherapy", "radiotherapy", "radiation", "immunotherapy", "treatment", "therapy", "resection"),
    "STAGING_EVIDENCE": ("tnm", "metasta", "spread", "stage", "staging", "lymph node", "nodes"),
    "MISSING_INFORMATION": ("missing", "not documented", "unknown", "what else", "pending information"),
}


def _question_intent(question: str) -> str:
    normalized = question.lower()
    for intent, terms in _QUESTION_INTENTS.items():
        if any(term in normalized for term in terms):
            return intent
    return "GENERAL_ANSWER"


def _deterministic_prompt_id(question: str, *, full_report: bool = False) -> str:
    """Return the task-level prompt ID; never route by medical keyword."""
    if full_report or _FULL_REPORT_REQUEST.search(question):
        return "FULL_REPORT_CONTRACT"
    return "FOCUSED_CONTRACT"


def _uploaded_evidence_chunks(
    uploaded_sources: list[dict[str, Any]], question: str, limit: int = 32,
) -> list[dict[str, Any]]:
    """Rank direct report excerpts for Gemini without generating an answer."""
    intent = _question_intent(question)
    category_patterns = (
        ("pathology-confirmed", 100, r"\b(?:pathologic|histologic|final) diagnosis\b|\b(?:biopsy|core needle).{0,100}\b(?:carcinoma|malignan|adenocarcinoma|squamous)\b"),
        ("lymph-node-pathology", 95, r"\b(?:lymph node|nodal).{0,80}\b(?:positive|metastatic carcinoma|metastasis|involvement confirmed)\b"),
        ("immunohistochemistry", 85, r"\b(?:immunohistochemistry|IHC|HER2|TTF-1|p40|CK5/6|PD-L1)\b"),
        ("imaging", 75, r"\b(?:CT|PET/?CT|PET scan|MRI|ultrasound|radiologic impression)\b"),
        ("molecular", 65, r"\b(?:molecular|mutation|EGFR|ALK|ROS1|KRAS|BRAF|NGS)\b"),
        ("indeterminate", 55, r"\b(?:indeterminate|uncertain|not confirmed|further staging|further characterization)\b"),
        ("documented-finding", 40, r"\b(?:suspicious|concerning|mass|lesion|abnormal)\b"),
    )
    preferred = {
        "PATHOLOGY": {"pathology-confirmed", "lymph-node-pathology", "immunohistochemistry"},
        "BIOMARKERS": {"immunohistochemistry", "molecular"},
        "IMAGING": {"imaging"},
        "STAGING_EVIDENCE": {"lymph-node-pathology", "imaging", "indeterminate", "pathology-confirmed"},
    }.get(intent, set())
    question_terms = _question_terms(question)
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source_index, source in enumerate(uploaded_sources, start=1):
        segments = source.get("evidence_segments") or [{"origin": "original_extraction", "content": source.get("content")}]
        for segment in segments:
            content = re.split(
                r"\b(?:AI TESTING TARGETS|EXPECTED AI SAFETY BEHAVIOR|GROUND-TRUTH RISK LABEL|SYNTHETIC DATA DISCLAIMER)\b",
                str(segment.get("content") or ""), maxsplit=1, flags=re.I,
            )[0]
            for order, sentence in enumerate(re.split(r"(?<=[.!?])\s+|(?=\d+\.\s+[A-Z])", " ".join(content.split()))):
                sentence = sentence.strip(" -•")
                key = sentence.lower()
                if len(sentence) < 25 or key in seen or _is_nonclinical_report_text(sentence):
                    continue
                category, strength = next(
                    ((name, score) for name, score, pattern in category_patterns if re.search(pattern, sentence, re.I)),
                    ("other", 15),
                )
                if category == "other":
                    continue
                seen.add(key)
                candidates.append({
                    "citation_id": f"U{source_index}", "category": category,
                    "strength": strength, "text": sentence, "order": order,
                    "origin": segment.get("origin") or "original_extraction",
                    "chunk_id": segment.get("chunk_id"),
                    "relevance": sum(term in key for term in question_terms),
                })
    category_priority = {
        "pathology-confirmed": 5, "lymph-node-pathology": 4,
        "immunohistochemistry": 3, "molecular": 2, "imaging": 1,
    }
    candidates.sort(key=lambda item: (
        item["relevance"], item["category"] in preferred,
        category_priority.get(item["category"], 0), item["strength"], -item["order"],
    ), reverse=True)
    selected: list[dict[str, Any]] = []
    signatures: list[set[str]] = []
    for item in candidates:
        signature = set(re.findall(r"[a-z0-9]+", item["text"].lower())) - _STOP_WORDS
        if any(signature and len(signature & prior) / len(signature | prior) >= 0.72 for prior in signatures):
            continue
        selected.append(item)
        signatures.append(signature)
        if len(selected) == limit:
            break
    return selected


def _uploaded_source_context(uploaded_sources: list[dict[str, Any]], question: str) -> str:
    """Use complete uploaded content when practical; otherwise retain each ranked clinical section."""
    documents = [
        {"citation_id": f"U{index}", "file_name": source.get("file_name"), "content": source.get("content")}
        for index, source in enumerate(uploaded_sources, start=1)
    ]
    # Approximate a conservative 4 characters/token budget without truncating
    # individual facts by character count.
    full_text = json.dumps(documents, ensure_ascii=False)
    token_budget = int(os.getenv("GEMINI_UPLOAD_CONTEXT_TOKENS", "24000"))
    if len(full_text.split()) <= token_budget * 0.75:
        return full_text
    chunks = _uploaded_evidence_chunks(uploaded_sources, question, limit=64)
    return json.dumps({"ranked_clinical_sections": chunks}, ensure_ascii=False)


def _valid_citations(value: Any, uploaded_count: int, reference_count: int) -> bool:
    citations = re.findall(r"[UR]\d+", json.dumps(value, ensure_ascii=False))
    return all(
        1 <= int(token[1:]) <= (uploaded_count if token.startswith("U") else reference_count)
        for token in citations
    )


def _normalize_inventory(value: Any, uploaded_count: int) -> dict[str, Any]:
    """Validate Gemini's evidence inventory without generating clinical content."""
    if not isinstance(value, dict):
        raise ValueError("inventory_schema_failed")
    normalized = {"document": value.get("document") if isinstance(value.get("document"), dict) else {}}
    for category in _INVENTORY_CATEGORIES:
        items = value.get(category)
        if not isinstance(items, list):
            raise ValueError("inventory_schema_failed")
        normalized[category] = []
        for item in items:
            if not isinstance(item, dict) or not str(item.get("fact") or "").strip():
                raise ValueError("inventory_schema_failed")
            certainty = str(item.get("certainty") or "")
            if certainty not in _CERTAINTIES:
                raise ValueError("inventory_invalid_certainty")
            citations = item.get("citations")
            if not isinstance(citations, list) or not citations:
                raise ValueError("inventory_missing_citation")
            if any(not re.fullmatch(r"U\d+", str(citation)) for citation in citations):
                raise ValueError("inventory_invalid_citation")
            if not _valid_citations({"citations": citations}, uploaded_count, 0):
                raise ValueError("inventory_invalid_citation")
            normalized[category].append({
                "fact": str(item["fact"]).strip(), "certainty": certainty,
                "citations": list(dict.fromkeys(str(citation) for citation in citations)),
            })
    return normalized


def _budget_complete_records(
    records: list[Any], max_chars: int, *, prefer_latest: bool = False
) -> str:
    """Serialize complete records within a prompt budget."""
    selected: list[Any] = []
    candidates = list(reversed(records)) if prefer_latest else records
    for record in candidates:
        candidate_records = [record, *selected] if prefer_latest else [*selected, record]
        candidate = json.dumps(candidate_records, ensure_ascii=False)
        if len(candidate) > max_chars:
            break
        selected = candidate_records
    return json.dumps(selected, ensure_ascii=False)


def _relevant_conversation_turns(
    records: list[dict[str, Any]], question: str, recent_window: int = 8
) -> list[dict[str, Any]]:
    """Keep relevant older turns plus a bounded recent window in original order."""
    if not records:
        return []
    question_terms = {
        term for term in re.findall(r"[a-z0-9]+", (question or "").lower())
        if len(term) >= 3 and term not in _GENERIC_QUESTION_TERMS
    }
    recent_start = max(0, len(records) - recent_window)
    selected = []
    for index, record in enumerate(records):
        text = " ".join(str(record.get(key) or "") for key in ("user", "assistant")).lower()
        relevant = bool(question_terms and any(term in text for term in question_terms))
        if relevant or index >= recent_start:
            selected.append(record)
    return selected


def _json_response_text(response: Any) -> str:
    """Return a JSON object from a Gemini response, rejecting prose responses."""
    raw = str(getattr(response, "text", "") or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
        raw = re.sub(r"\s*```$", "", raw).strip()
    if not raw:
        raise ValueError("Gemini returned an empty response")
    # Gemini occasionally prefixes a valid object with one short sentence.
    # Parse only the complete JSON object; anything else is a parsing failure.
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Gemini response did not contain a JSON object")
    return raw[start : end + 1]


_UPLOAD_FINDING_PATTERNS = (
    # Clinical evidence hierarchy: confirmed pathology before imaging and
    # uncertainty. This affects both offline summaries and source context.
    (100, re.compile(r"\b(?:histologic|pathologic|final) diagnosis\b|\b(?:biopsy|core needle).{0,80}\b(?:carcinoma|malignan|adenocarcinoma|squamous)\b", re.I)),
    (95, re.compile(r"\b(?:lymph node|nodal).{0,80}\b(?:positive|metastatic carcinoma|metastasis|involvement confirmed)\b", re.I)),
    (85, re.compile(r"\b(?:immunohistochemistry|IHC|HER2|estrogen receptor|progesterone receptor|TTF-1|p40|CK7|CK20|PD-L1)\b", re.I)),
    (75, re.compile(r"\b(?:CT|PET/?CT|PET scan|MRI|ultrasound|radiologic impression)\b", re.I)),
    (65, re.compile(r"\b(?:molecular|mutation|EGFR|ALK|ROS1|KRAS|BRAF|NGS)\b", re.I)),
    (55, re.compile(r"\bindeterminate\b|\buncertain\b|\bfurther (?:staging|characterization|evaluation)\b", re.I)),
    (50, re.compile(r"\bsuspicious\b|\bconcerning\b|\bimpression\b|\bassessment\b", re.I)),
    (45, re.compile(r"\bgrade\s*(?:3|III)\b|\bhigh histologic grade\b|\blymphovascular invasion\b|\bperineural invasion\b", re.I)),
)


def _uploaded_reference_profile(uploaded_sources: list[dict[str, Any]]) -> set[str]:
    """Extract pathology-specific terms to reject discordant reference cases.

    This is not a diagnosis classifier. It uses only distinctive words already
    written in the uploaded pathology text so reference retrieval cannot force
    an unrelated cancer label into the answer.
    """
    generic = {
        "pathologic", "pathology", "histologic", "diagnosis", "final", "biopsy",
        "needle", "core", "tumor", "tumour", "non", "small", "cell", "cells",
        "carcinoma", "malignancy", "malignant", "invasive", "favor", "favored",
        "consistent", "with", "right", "left", "upper", "lower", "lobe", "lung",
    }
    preferences: set[str] = set()
    for source in uploaded_sources:
        content = str(source.get("content") or "")
        for sentence in re.split(r"(?<=[.!?])\s+", content):
            if not re.search(r"\b(?:patholog|histolog|biopsy|carcinoma|malignan)\b", sentence, re.I):
                continue
            preferences.update(
                token for token in re.findall(r"[a-z0-9]+", sentence.lower())
                if len(token) >= 4 and token not in generic
            )
    return preferences


def _reference_match_priority(
    result: dict[str, Any], preferences: set[str], query_terms: set[str] | None = None,
) -> int:
    """Favor pathology-consistent reference labels without claiming diagnosis."""
    query_terms = query_terms or set()
    metadata = result.get("metadata") or {}
    searchable = " ".join(
        str(metadata.get(field) or "")
        for field in ("cancer_type", "anatomy", "site", "histology", "biomarker", "modality", "section")
    ) + " " + str(result.get("document") or "")
    searchable_terms = set(re.findall(r"[a-z0-9-]+", searchable.lower()))
    preference_hits = len(preferences & searchable_terms)
    question_hits = len(query_terms & searchable_terms)
    has_reliable_label = any(
        str(metadata.get(field) or "").strip()
        for field in ("cancer_type", "anatomy", "site", "histology")
    )
    if preferences and preference_hits == 0 and has_reliable_label:
        return -1
    # Metadata and exact clinical-term overlap are soft boosts. Missing metadata
    # never removes a candidate; only an explicit mismatch with documented U
    # pathology terms is penalized.
    return min(2, preference_hits) + min(3, question_hits)


def _reference_signature(result: dict[str, Any]) -> set[str]:
    text = str(result.get("document") or "").lower()
    # Normalize common repeated wording so nearly identical RAG chunks do not
    # consume multiple evidence slots.
    return {
        token for token in re.findall(r"[a-z0-9]+", text)
        if len(token) > 2 and token not in _STOP_WORDS
    }


def _rank_and_deduplicate_references(
    results: list[dict[str, Any]], preferences: set[str], limit: int,
    query_terms: set[str] | None = None,
) -> list[dict[str, Any]]:
    ranked = sorted(
        results,
        key=lambda item: (
            _reference_match_priority(item, preferences, query_terms),
            float(item.get("rrf_score") or item.get("retrieval_score") or 0),
        ),
        reverse=True,
    )
    selected: list[dict[str, Any]] = []
    signatures: list[set[str]] = []
    for item in ranked:
        # When pathology explicitly indicates lung squamous/LUSC, a
        # mesothelioma reference is discordant rather than useful context.
        if preferences and _reference_match_priority(item, preferences, query_terms) < 0:
            continue
        signature = _reference_signature(item)
        duplicate = any(
            signature and existing and len(signature & existing) / len(signature | existing) >= 0.72
            for existing in signatures
        )
        metadata = item.get("metadata") or {}
        identity = tuple(metadata.get(field) for field in ("document_id", "pmcid", "image_id"))
        duplicate = duplicate or (any(identity) and any(
            identity == tuple((existing_item.get("metadata") or {}).get(field) for field in ("document_id", "pmcid", "image_id"))
            for existing_item in selected
        ))
        if duplicate:
            continue
        selected.append(item)
        signatures.append(signature)
        if len(selected) >= limit:
            break
    return [{**item, "fused_rank": index} for index, item in enumerate(selected, start=1)]


def _question_terms(text: str) -> set[str]:
    """Return meaningful terms so uploaded findings can follow the question."""
    terms = {
        token for token in re.findall(r"[a-z0-9-]+", text.lower())
        if len(token) > 2 and token not in _GENERIC_QUESTION_TERMS
    }
    expanded = set(terms)
    for term in terms:
        expanded.update(_QUESTION_TERM_ALIASES.get(term, set()))
        if len(term) >= 6:
            expanded.add(term[:6])
    return expanded


def _reference_query(question: str, uploaded_sources: list[dict[str, Any]]) -> tuple[str, set[str]]:
    """Build a bounded reference query from the question and documented U text.

    Only verbatim excerpts already present in uploaded evidence are added. This
    prevents a vague question from losing the case's site/pathology context,
    without asking an LLM to invent a diagnosis or turning uncertainty into a
    fact.
    """
    question = str(question or "").strip()
    terms = _question_terms(question)
    if not uploaded_sources:
        return question, terms
    excerpts: list[str] = []
    for source in uploaded_sources:
        content = " ".join(str(source.get("content") or "").split())
        if not content:
            continue
        sentences = re.split(r"(?<=[.!?;])\s+", content)
        scored = []
        for sentence in sentences:
            sentence_terms = set(re.findall(r"[a-z0-9-]+", sentence.lower()))
            clinical = bool(re.search(
                r"\b(?:carcinoma|adenocarcinoma|squamous|sarcoma|lymph|node|metasta|lesion|mass|nodule|biopsy|patholog|histolog|egfr|pd-l1|her2|mutation|ct|mri|pet)\b",
                sentence, re.I,
            ))
            overlap = len(terms & sentence_terms)
            if clinical or overlap:
                scored.append((overlap + (1 if clinical else 0), sentence.strip()))
        for _, sentence in sorted(scored, key=lambda item: item[0], reverse=True)[:6]:
            if sentence and sentence not in excerpts:
                excerpts.append(sentence[:500])
        if len(excerpts) >= 12:
            break
    context = " ".join(excerpts[:12])[:4000]
    query = " ".join(part for part in (question, context) if part).strip()
    return query, _question_terms(query)


def _extract_uploaded_points(
    uploaded_sources: list[dict[str, Any]],
    limit: int = 6,
    question: str | None = None,
) -> list[str]:
    """Extract report-first fallback facts without treating test instructions as findings."""
    candidates: list[tuple[int, int, str]] = []
    secondary: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for source_index, source in enumerate(uploaded_sources, start=1):
        content = str(source.get("content") or "")
        # Synthetic fixtures may contain expected-output instructions after the
        # clinical report. Those instructions are evaluation metadata, not
        # patient evidence, and must never be summarized as findings.
        content = re.split(
            r"\b(?:AI TESTING TARGETS|EXPECTED AI SAFETY BEHAVIOR|GROUND-TRUTH RISK LABEL|SYNTHETIC DATA DISCLAIMER)\b",
            content,
            maxsplit=1,
            flags=re.I,
        )[0]
        normalized_content = " ".join(content.split())
        for order, sentence in enumerate(re.split(r"(?<=[.!?])\s+|(?=\d+\.\s+[A-Z])", normalized_content)):
            sentence = sentence.strip(" -•")
            if len(sentence) < 30 or _is_nonclinical_report_text(sentence):
                continue
            normalized = sentence.lower()
            if normalized in seen:
                continue
            score = sum(weight for weight, pattern in _UPLOAD_FINDING_PATTERNS if pattern.search(sentence))
            if score == 0:
                # Secondary selection remains extractive: retain clearly
                # clinical sentences but never infer a finding from them.
                if re.search(
                    r"\b(?:patient|clinical|symptom|diagnos|patholog|biopsy|imaging|scan|"
                    r"lesion|mass|nodule|node|tumou?r|cancer|carcinoma|metasta|marker|"
                    r"positive|negative|treatment|follow[- ]?up|recommended|pending)\b",
                    sentence,
                    re.I,
                ):
                    seen.add(normalized)
                    secondary.append((1, -order, f"{sentence[:420]} [U{source_index}]"))
                continue
            seen.add(normalized)
            candidates.append((score, -order, f"{sentence[:420]} [U{source_index}]"))
    question_terms = _question_terms(question or "")
    if question_terms:
        # For a specific question, prioritize report sentences that mention its
        # subject (for example, "liver" also matches "hepatic").
        candidates.sort(
            key=lambda item: (
                sum(term in item[2].lower() for term in question_terms),
                item[0],
                item[1],
            ),
            reverse=True,
        )
    else:
        candidates.sort(reverse=True)
    pool = candidates or secondary
    if question_terms and not candidates:
        secondary.sort(
            key=lambda item: (
                sum(term in item[2].lower() for term in question_terms), item[1]
            ),
            reverse=True,
        )
    selected = [text for _, _, text in pool[:limit]]
    # Preserve at least one explicit uncertainty statement so suspicious or
    # indeterminate distant findings are not accidentally presented as
    # confirmed disease by an otherwise concise fallback summary.
    uncertainty = next(
        (
            text for _, _, text in candidates
            if re.search(r"\b(?:indeterminate|unconfirmed|requires further|exclude)\b", text, re.I)
        ),
        None,
    )
    if uncertainty and uncertainty not in selected:
        if len(selected) >= limit:
            selected[-1] = uncertainty
        else:
            selected.append(uncertainty)
    return selected


def _evidence_item(result: dict[str, Any]) -> dict[str, Any]:
    metadata = result.get("metadata") or {}
    return {
        "id": result.get("id"),
        "rank": result.get("fused_rank") or result.get("rank"),
        "modality": result.get("modality"),
        "text": result.get("document") or "",
        "source_preview": " ".join(str(result.get("document") or "").split())[:600],
        "section_name": metadata.get("section_name") or metadata.get("section"),
        "page_start": metadata.get("page_start") or metadata.get("page_number"),
        "page_end": metadata.get("page_end") or metadata.get("page_number"),
        "source_dataset": metadata.get("source_dataset"),
        "cancer_type": metadata.get("cancer_type"),
        "file_name": metadata.get("file_name") or metadata.get("image_name"),
        "pmcid": metadata.get("pmcid"),
        "document_id": metadata.get("document_id"),
        "image_id": metadata.get("image_id"),
        "retrieval_score": result.get("retrieval_score"),
        "rrf_score": result.get("rrf_score"),
        "metric": result.get("metric"),
    }


def _research_summary(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    sources = sorted({
        str(item.get("source_dataset"))
        for item in evidence
        if item.get("source_dataset")
    })
    count = len(evidence)
    source_count = len(sources)
    record_word = "record" if count == 1 else "records"
    source_word = "source collection" if source_count == 1 else "source collections"
    if count:
        message = f"Reviewed {count} related indexed {record_word} from {source_count or 1} {source_word}."
    else:
        message = "No closely related indexed records were available for this response."
    return {"related_records": count, "source_count": source_count, "sources": sources, "message": message}


def _validate_citations(summary: str, uploaded_count: int, retrieved_count: int) -> dict[str, Any]:
    """Validate citation identifiers structurally without claiming semantic support."""
    citations = re.findall(r"\[((?:[UR]\d+)(?:\s*,\s*[UR]\d+)*)\]", summary)
    used = [token for group in citations for token in re.findall(r"[UR]\d+", group)]
    invalid = []
    for token in used:
        limit = uploaded_count if token.startswith("U") else retrieved_count
        if int(token[1:]) < 1 or int(token[1:]) > limit:
            invalid.append(token)
    return {
        "status": "valid" if used and not invalid else "invalid" if invalid else "none",
        "used": list(dict.fromkeys(used)),
        "invalid": list(dict.fromkeys(invalid)),
        "uploaded_source_count": uploaded_count,
        "retrieved_source_count": retrieved_count,
        "note": "Citation identifiers were range-checked; semantic support still requires review.",
    }


def _remove_invalid_citations(summary: str, invalid: list[str]) -> str:
    invalid_set = set(invalid)
    if not invalid_set:
        return summary

    def replace(match: re.Match[str]) -> str:
        tokens = re.findall(r"[UR]\d+", match.group(1))
        valid = [token for token in tokens if token not in invalid_set]
        return f"[{', '.join(valid)}]" if valid else ""

    return re.sub(r"\[((?:[UR]\d+)(?:\s*,\s*[UR]\d+)*)\]", replace, summary)


def _semantic_grounding_review(
    answer: str, citation_validation: dict[str, Any], uploaded_sources: list[dict[str, Any]],
) -> dict[str, Any]:
    """Conservative support screen kept separate from citation-ID validation."""
    used_u = [item for item in citation_validation.get("used", []) if str(item).startswith("U")]
    if not used_u:
        return {"status": "not_applicable", "method": "lexical_support_screen", "unsupported_citations": []}
    answer_terms = set(re.findall(r"[a-z0-9-]{4,}", answer.lower())) - _GENERIC_QUESTION_TERMS
    unsupported: list[str] = []
    indeterminate = False
    for citation in used_u:
        index = int(citation[1:]) - 1
        source = str(uploaded_sources[index].get("content") or "") if 0 <= index < len(uploaded_sources) else ""
        source_terms = set(re.findall(r"[a-z0-9-]{4,}", source.lower()))
        if not source:
            unsupported.append(citation)
        elif len(answer_terms & source_terms) < 2:
            indeterminate = True
    return {
        "status": "unsupported" if unsupported else "indeterminate" if indeterminate else "supported",
        "method": "lexical_support_screen",
        "unsupported_citations": unsupported,
        "note": "Distinct from structural citation validation; this is not clinician validation.",
    }


def _clean_structured_citations(value: Any, invalid: list[str]) -> Any:
    """Remove invalid IDs from structured citation arrays and narrative fields."""
    invalid_set = set(invalid)
    if isinstance(value, dict):
        return {
            key: ([item for item in child if item not in invalid_set] if key == "citations" and isinstance(child, list)
                  else _clean_structured_citations(child, invalid))
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_clean_structured_citations(item, invalid) for item in value]
    if isinstance(value, str):
        return _remove_invalid_citations(value, invalid)
    return value


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return [] if value is None or value == "" else [value]


def _clarification_options(uploaded_sources: list[dict[str, Any]] | None, summary: str = "") -> list[str]:
    """Return stable core options plus options relevant to uploaded material."""
    source_text = " ".join(
        f"{source.get('file_name', '')} {source.get('source_type', '')} {source.get('content', '')}"
        for source in (uploaded_sources or [])
    ).lower()
    source_text = f"{source_text} {summary.lower()}"
    options = ["Diagnosis", "Pathology", "Treatment", "Staging"]
    conditional = (
        ("Biomarkers", r"biomarker|molecular|egfr|alk|ros1|pd-l1|ihc|immunohistochem|mutation"),
        ("Imaging findings", r"imaging|radiology|radiologic|mri|ct scan|pet|scan|lesion|nodule"),
        ("Lymph nodes", r"lymph node|lymph nodes|nodal|adenopathy"),
        ("Treatment response", r"treatment response|therapy response|chemotherapy|immunotherapy|radiation|targeted therapy|response"),
    )
    for label, pattern in conditional:
        if re.search(pattern, source_text, re.I):
            options.append(label)
    return options


def _normalize_structured_answer(
    value: Any, uploaded_count: int | None = None, reference_count: int | None = None,
) -> dict[str, Any]:
    """Normalize the canonical full-report answer and drop only invalid items."""
    if not isinstance(value, dict):
        raise ValueError("Gemini structured answer must be a JSON object")
    normalized = dict(value)
    normalized["limitations"] = [str(item) for item in _as_list(normalized.get("limitations")) if str(item).strip()]
    terms = normalized.get("medical_terms")
    if isinstance(terms, dict):
        terms = ([terms] if "term" in terms or "definition" in terms else [
            {"term": str(term), "definition": str(definition)}
            for term, definition in terms.items()
        ])
    normalized["medical_terms"] = _as_list(terms)
    findings = normalized.get("key_findings", normalized.get("findings", []))
    valid_findings = []
    for item in _as_list(findings):
        if not isinstance(item, dict) or not str(item.get("title") or item.get("finding") or "").strip():
            continue
        citations = item.get("citations")
        citations = re.findall(r"[UR]\d+", citations) if isinstance(citations, str) else _as_list(citations)
        citations = [str(citation) for citation in citations if re.fullmatch(r"U\d+", str(citation))]
        if uploaded_count is not None:
            citations = [c for c in citations if int(c[1:]) <= uploaded_count]
        if uploaded_count and not citations:
            continue
        certainty = str(item.get("certainty") or "insufficient_information")
        if certainty not in _CERTAINTIES:
            certainty = "insufficient_information"
        valid_findings.append({
            "title": str(item.get("title") or item.get("finding")).strip(),
            "result": str(item.get("result") or "").strip(),
            "meaning": str(item.get("meaning") or "").strip(),
            "certainty": certainty,
            "importance": str(item.get("importance") or "supporting") if str(item.get("importance") or "supporting") in {"critical", "high", "supporting"} else "supporting",
            "citations": citations,
        })
    normalized["key_findings"] = valid_findings
    def normalize_claims(raw: Any) -> list[dict[str, Any]]:
        claims = []
        for item in _as_list(raw):
            if not isinstance(item, dict) or not str(item.get("title") or item.get("finding") or "").strip():
                continue
            citations = item.get("citations")
            citations = re.findall(r"U\d+", citations) if isinstance(citations, str) else _as_list(citations)
            citations = [str(c) for c in citations if re.fullmatch(r"U\d+", str(c))]
            if uploaded_count is not None:
                citations = [c for c in citations if int(c[1:]) <= uploaded_count]
            # Patient-specific documented claims must be traceable to uploaded evidence.
            if uploaded_count and not citations:
                continue
            claims.append({
                "title": str(item.get("title") or item.get("finding")).strip(),
                "result": str(item.get("result") or "").strip(),
                "meaning": str(item.get("meaning") or "").strip(),
                "certainty": str(item.get("certainty") or "insufficient_information") if str(item.get("certainty") or "insufficient_information") in _CERTAINTIES else "insufficient_information",
                "importance": str(item.get("importance") or "supporting") if str(item.get("importance") or "supporting") in {"critical", "high", "supporting"} else "supporting",
                "citations": citations,
            })
        return claims
    normalized["documented_facts"] = normalize_claims(normalized.get("documented_facts"))
    normalized["ai_interpretation"] = normalize_claims(normalized.get("ai_interpretation"))
    normalized["missing_information"] = [str(item) for item in _as_list(normalized.get("missing_information")) if str(item).strip()]
    normalized["clinician_questions"] = [str(item) for item in _as_list(normalized.get("clinician_questions")) if str(item).strip()]
    for obsolete in ("findings", "reasoning", "supports", "primary_interpretation", "confirmed_findings", "favored_findings", "suspicious_findings", "indeterminate_findings", "important_negative_findings", "biomarkers_and_molecular_results", "subheadline"):
        normalized.pop(obsolete, None)
    support = normalized.get("evidence_support")
    if not isinstance(support, dict):
        support = {"level": "Limited", "explanation": str(support or "Evidence quality requires review.")}
    if str(support.get("level") or "").lower() == "strong":
        support["level"] = "Moderate"
        explanation = str(support.get("explanation") or "").strip()
        support["explanation"] = (
            f"{explanation} Automatic source matching has not been clinician-validated."
        ).strip()
    if support.get("level") not in {"Moderate", "Limited", "Insufficient"}:
        support["level"] = "Limited"
    support["explanation"] = str(support.get("explanation") or "Evidence quality requires review.")
    normalized["evidence_support"] = support
    complexity = normalized.get("case_complexity")
    if not isinstance(complexity, dict):
        complexity = {}
    allowed_levels = {"low", "moderate", "high", "insufficient_information"}
    if complexity.get("level") not in allowed_levels:
        complexity["level"] = "insufficient_information"
    complexity_citations = [
        str(citation) for citation in _as_list(complexity.get("citations"))
        if re.fullmatch(r"U\d+", str(citation))
        and (uploaded_count is None or int(str(citation)[1:]) <= uploaded_count)
    ]
    if uploaded_count and complexity["level"] != "insufficient_information" and not complexity_citations:
        complexity["level"] = "insufficient_information"
        complexity["reason"] = "Case complexity could not be supported by a valid uploaded-source citation."
    complexity["reason"] = str(complexity.get("reason") or "There is not enough validated information to characterize case complexity.")
    complexity["citations"] = complexity_citations
    normalized["case_complexity"] = complexity
    staging = normalized.get("staging")
    if not isinstance(staging, dict):
        staging = {}
    staging["documented_components"] = [str(item) for item in _as_list(staging.get("documented_components"))]
    staging["unresolved_components"] = [str(item) for item in _as_list(staging.get("unresolved_components"))]
    staging["citations"] = [
        str(citation) for citation in _as_list(staging.get("citations"))
        if re.fullmatch(r"U\d+", str(citation))
        and (uploaded_count is None or int(str(citation)[1:]) <= uploaded_count)
    ]
    staging["can_assign_final_stage"] = bool(staging.get("can_assign_final_stage"))
    if not staging["can_assign_final_stage"] or (uploaded_count and not staging["citations"]):
        staging["can_assign_final_stage"] = False
        staging["final_stage"] = None
    staging["explanation"] = str(staging.get("explanation") or "Structured staging details were not available.")
    normalized["staging"] = staging
    if not str(normalized.get("plain_language_summary") or normalized.get("headline") or "").strip():
        if normalized["key_findings"]:
            normalized["headline"] = normalized["key_findings"][0]["title"]
            normalized["plain_language_summary"] = normalized["key_findings"][0]["result"]
        else:
            raise ValueError("answer_schema_failed")
    normalized["headline"] = str(normalized.get("headline") or "Clinical evidence summary")
    normalized["plain_language_summary"] = str(normalized.get("plain_language_summary") or "")
    normalized["safety_notice"] = str(normalized.get("safety_notice") or DISCLAIMER)
    try:
        return FullReportAnswer.model_validate(normalized).model_dump()
    except Exception as error:
        raise ValueError("answer_schema_failed") from error


def _enforce_stage_authorization(
    structured: dict[str, Any], uploaded_sources: list[dict[str, Any]], *, authorized: bool = False,
) -> dict[str, Any]:
    """Prevent an LLM from calculating a formal stage without explicit authority."""
    staging = structured.get("staging")
    if not isinstance(staging, dict):
        return structured
    source_text = "\n".join(str(source.get("content") or "") for source in uploaded_sources)
    explicitly_documented = bool(re.search(
        r"\b(?:overall|clinical|pathologic|pathological|final)?\s*stage\s+(?:0|[ivx]+|[1-4])(?:[abc])?\b",
        source_text, re.I,
    ))
    if not (authorized or explicitly_documented):
        staging["can_assign_final_stage"] = False
        staging["final_stage"] = None
        staging["explanation"] = (
            "A formal stage was not explicitly documented and deterministic stage calculation was not authorized. "
            + str(staging.get("explanation") or "Staging evidence only is reported.")
        )
    return structured


def _structured_citation_text(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    citations = []
    for section in ("key_findings",):
        for item in value.get(section) or []:
            citations.extend(item.get("citations") or [])
    return " ".join(f"[{citation}]" for citation in citations)


class ClinicalAnalysisPipeline:
    def __init__(self, device: str = "auto") -> None:
        self.retrieval = QueryPipeline(device=device)
        self.last_generation_error: str | None = None
        self.last_generation_metadata: dict[str, Any] = {}

    def analyze(
        self,
        *,
        text: str | None = None,
        image_path: str | Path | None = None,
        image_paths: list[str | Path] | None = None,
        top_k: int = 5,
        conversation_history: list[dict[str, str]] | None = None,
        include_risk_review: bool = False,
        uploaded_sources: list[dict[str, Any]] | None = None,
        private_evidence: dict[str, list[dict[str, Any]]] | None = None,
        intent_text: str | None = None,
    ) -> dict[str, Any]:
        analysis_started = time.perf_counter()
        logger.info("[analysis] pipeline started")
        clean_text = (text or "").strip()
        all_image_paths = [str(path) for path in (image_paths or [])]
        if image_path:
            all_image_paths.insert(0, str(image_path))
        all_image_paths = list(dict.fromkeys(all_image_paths))
        # Retrieve extra candidates so clinically matched references can be
        # deduplicated before the user-facing top-k is selected.
        candidate_top_k = max(top_k * 3, 12)
        retrieval_query, query_terms = _reference_query(
            intent_text if intent_text is not None else clean_text,
            uploaded_sources or [],
        )
        retrieval_started = time.perf_counter()
        if all_image_paths:
            retrieval = self.retrieval.query_images(
                all_image_paths, ocr_text=retrieval_query or None, top_k=candidate_top_k
            )
        elif clean_text:
            retrieval = self.retrieval.query_text(retrieval_query, top_k=candidate_top_k)
        else:
            raise ValueError("Analysis requires report text, an image, or both")
        retrieval_ms = round((time.perf_counter() - retrieval_started) * 1000, 2)
        _analysis_timing("retrieval", retrieval_started)

        intent_started = time.perf_counter()
        reference_preferences = _uploaded_reference_profile(uploaded_sources or [])
        selected_results = retrieval["fused_results"]
        supporting_override = None
        # A screenshot/photo of a report can produce both OCR text and an image
        # vector. When substantial text was recovered, report evidence is more
        # interpretable than visual similarity to unrelated figures. Preserve
        # image-primary behaviour for genuine scans with little/no OCR text.
        if retrieval["query_type"] == "multimodal" and len(clean_text) >= 200:
            selected_results = retrieval.get("text_results", [])[:top_k]
            supporting_override = []
        if retrieval["query_type"] in {"image", "multi_image"}:
            # User-facing image explanations should be concise and based on the
            # strongest captioned image references, not a long mixed ranking.
            selected_results = retrieval.get("image_results", selected_results)[:3]
        selected_results = _rank_and_deduplicate_references(
            selected_results, reference_preferences, top_k, query_terms
        )
        evidence = [_evidence_item(item) for item in selected_results]
        supporting_images = [
            _evidence_item(item)
            for item in (
                supporting_override
                if supporting_override is not None
                else retrieval.get("supporting_image_results", [])
            )
        ]
        summary_context = evidence + supporting_images
        private_evidence = private_evidence or {"text": [], "images": []}
        private_text = list(private_evidence.get("text") or [])
        private_images = list(private_evidence.get("images") or [])
        # Uploaded report text is included in ``clean_text`` for retrieval, but
        # only the user's actual question may control the answer format.
        question_text = clean_text if intent_text is None else intent_text.strip()
        # A question without an uploaded report or image should be answered like
        # a conversation, not rendered as a full clinical-report review.
        request_contract = _request_contract(
            question_text,
            has_uploaded_sources=bool(uploaded_sources),
            has_images=bool(all_image_paths),
        )
        brief_response = request_contract == "general"
        focused_response = request_contract == "focused"
        logger.info(
            "[analysis] intent routing: %.2fs (contract=%s)",
            time.perf_counter() - intent_started,
            "general" if brief_response else "focused" if focused_response else "full_report",
        )
        generation_started = time.perf_counter()
        summary, model_name, structured_answer = self._summarize(
            question_text,
            summary_context,
            conversation_history or [],
            uploaded_sources or [],
            image_paths=all_image_paths,
            brief_response=brief_response,
            focused_response=focused_response,
        )
        generation_ms = round((time.perf_counter() - generation_started) * 1000, 2)
        citation_started = time.perf_counter()
        structured_citations = " ".join(
            f"[{citation}]" for citation in re.findall(
                r"[UR]\d+", json.dumps(structured_answer or {}, ensure_ascii=False)
            )
        )
        citation_validation = _validate_citations(
            summary + structured_citations,
            len(uploaded_sources or []), len(summary_context)
        )
        if citation_validation["invalid"]:
            summary = _remove_invalid_citations(summary, citation_validation["invalid"])
            structured_answer = _clean_structured_citations(
                structured_answer, citation_validation["invalid"]
            )
            citation_validation = _validate_citations(
                summary + " ".join(f"[{citation}]" for citation in re.findall(r"[UR]\d+", json.dumps(structured_answer or {}))),
                len(uploaded_sources or []), len(summary_context)
            ) | {"repaired": True}
        semantic_grounding = _semantic_grounding_review(
            summary, citation_validation, uploaded_sources or []
        )
        _analysis_timing("citation validation", citation_started)
        generation_metadata = self.last_generation_metadata
        public_generation_diagnostics = {
            key: generation_metadata.get(key)
            for key in (
                "generation_mode", "generation_status", "provider_status",
                "provider_error_code", "quota_exhausted", "retry_after",
                "fallback_reason", "gemini_calls_attempted",
                "gemini_calls_skipped_due_to_quota", "transient_retry_attempted",
                "inventory_started", "inventory_available", "answer_started",
                "answer_validation_passed", "answer_repair_attempted",
                "answer_repair_succeeded", "raw_response_present",
                "prompt_selection",
            )
        }
        public_generation_diagnostics["status"] = generation_metadata.get("generation_status")
        clarification_required = bool(
            focused_response
            and structured_answer
            and (
                str(structured_answer.get("certainty") or "") == "insufficient_information"
                or "not documented" in summary.lower()
            )
        )
        development_diagnostic = None
        if os.getenv("APP_ENV", "development").lower() != "production" and generation_metadata.get("generation_status") == "extractive_fallback":
            development_diagnostic = {
                "status": generation_metadata.get("provider_status"),
                "code": generation_metadata.get("provider_error_code"),
                "reason": generation_metadata.get("fallback_reason"),
            }
        response = {
            "query_type": retrieval["query_type"],
            "summary": summary,
            "brief_response": brief_response or focused_response,
            "response_contract": "general" if brief_response else "focused" if focused_response else "full_report",
            "structured_answer": structured_answer,
            "model_name": model_name,
            "generation_mode": generation_metadata.get("generation_mode"),
            "generation_status": generation_metadata.get("generation_status"),
            "provider_status": generation_metadata.get("provider_status"),
            "provider_error_code": generation_metadata.get("provider_error_code"),
            "quota_exhausted": bool(generation_metadata.get("quota_exhausted")),
            "retry_after": generation_metadata.get("retry_after"),
            "fallback_reason": generation_metadata.get("fallback_reason"),
            "gemini_calls_attempted": generation_metadata.get("gemini_calls_attempted", 0),
            "gemini_calls_skipped_due_to_quota": generation_metadata.get("gemini_calls_skipped_due_to_quota", 0),
            "raw_response_present": bool(generation_metadata.get("raw_response_present")),
            "json_parse_passed": not bool(
                self.last_generation_metadata.get("answer_json_parse_failed")
                or self.last_generation_metadata.get("answer_empty_response")
            ),
            "schema_validation_passed": bool(self.last_generation_metadata.get("answer_validation_passed")),
            "repair_attempted": bool(self.last_generation_metadata.get("answer_repair_attempted")),
            "repair_succeeded": self.last_generation_metadata.get("answer_repair_succeeded"),
            "structured_answer_present": structured_answer is not None,
            "generation_diagnostics": public_generation_diagnostics,
            "clarification_required": clarification_required,
            "clarification_question": "What would you like to know about this document?" if clarification_required else None,
            "clarification_options": _clarification_options(uploaded_sources, summary) if clarification_required else [],
            "development_diagnostic": development_diagnostic,
            "evidence": evidence,
            "supporting_image_evidence": supporting_images,
            "diagnostics": {
                **retrieval["diagnostics"],
                "retrieval_sources": {
                    "private_text": {
                        "status": "retrieved" if private_text else "no_results",
                        "count": len(private_text),
                        "ownership_filter": "user_id_and_session_id",
                        "collection_scope": "private_user_uploads",
                        "calibrated": False,
                    },
                    "private_images": {
                        "status": "retrieved" if private_images else "no_results",
                        "count": len(private_images),
                        "ownership_filter": "user_id_and_session_id",
                        "collection_scope": "private_user_uploads",
                        "calibrated": False,
                    },
                    "reference": {
                        "status": "retrieved" if summary_context else "no_results",
                        "count": len(summary_context),
                        "collection_scope": "shared_reference_evidence",
                        "calibrated": False,
                    },
                },
                "clinical_evidence_policy": {
                    "uploaded_hierarchy": [
                        "pathology", "positive lymph-node pathology", "immunohistochemistry",
                        "CT/PET and other imaging", "molecular findings", "indeterminate findings",
                        "external reference evidence",
                    ],
                    "reference_preference": "pathology-derived terms" if reference_preferences else None,
                    "query_enrichment": {
                        "applied": bool(uploaded_sources),
                        "question_terms": sorted(query_terms),
                        "documented_context_characters": max(0, len(retrieval_query) - len(intent_text or clean_text)),
                    },
                    "deduplicated_reference_count": len(selected_results),
                },
                "performance": {
                    "retrieval_ms": retrieval_ms,
                    "generation_ms": generation_ms,
                    "pipeline_total_ms": round(
                        (time.perf_counter() - analysis_started) * 1000, 2
                    ),
                },
            },
            "citation_validation": citation_validation,
            "semantic_grounding": semantic_grounding,
            "uploaded_sources": uploaded_sources or [],
            # Keep private retrieval distinct from shared reference evidence.
            # Its excerpts are consolidated into uploaded_sources for U-citations,
            # while this payload makes the two-source architecture observable.
            "private_evidence": {
                "text": private_text,
                "images": private_images,
            },
            "research_summary": _research_summary(summary_context),
            # Retrieval labels describe reference records, not this patient.
            # Keep them in the advanced evidence payload and never promote them
            # into a patient-facing cancer-risk review.
            "risk_review": None,
            "disclaimer": DISCLAIMER,
        }
        _analysis_timing("pipeline total", analysis_started)
        return response

    def _summarize(
        self,
        user_text: str,
        evidence: list[dict[str, Any]],
        conversation_history: list[dict[str, str]] | None = None,
        uploaded_sources: list[dict[str, Any]] | None = None,
        image_paths: list[str] | None = None,
        brief_response: bool = False,
        focused_response: bool = False,
    ) -> tuple[str, str, dict[str, Any] | None]:
        """Generate one of three explicit contracts with non-blocking repairs."""
        uploaded_sources = uploaded_sources or []
        image_paths = image_paths or []
        request_type = "general" if brief_response else "focused" if focused_response else "full_report"
        model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        diagnostics: dict[str, Any] = {
            "request_type": request_type, "generation_mode": "extractive_fallback",
            "generation_status": "extractive_fallback", "status": "extractive_fallback",
            "fallback_reason": None, "gemini_model": model,
            "inventory_started": False, "inventory_available": False,
            "inventory_provider_failed": False, "inventory_empty_response": False,
            "inventory_json_parse_failed": False, "inventory_schema_failed": False,
            "inventory_invalid_citation": False, "inventory_missing_citation": False,
            "inventory_repair_attempted": False, "inventory_repair_succeeded": False,
            "inventory_repair_failed": False,
            "answer_started": False, "answer_repair_attempted": False,
            "answer_repair_succeeded": False, "answer_validation_passed": False,
            "answer_provider_failed": False, "answer_empty_response": False,
            "answer_json_parse_failed": False, "answer_schema_failed": False,
            "answer_invalid_citation": False, "answer_repair_failed": False,
            "transient_retry_attempted": False, "raw_response_present": False,
            "provider_status": "available", "provider_error_code": None,
            "quota_exhausted": False, "retry_after": None,
            "gemini_calls_attempted": 0, "gemini_calls_skipped_due_to_quota": 0,
        }
        self.last_generation_error = None
        self.last_generation_metadata = diagnostics

        def mark_failure(stage: str, error: Exception | str) -> None:
            message = str(error)
            classification = _classify_provider_error(error)
            diagnostics.update({key: value for key, value in classification.items() if key != "retryable"})
            diagnostics[stage] = True
            diagnostics["failure_stage"] = stage
            diagnostics["gemini_error"] = f"{type(error).__name__}: {message}" if isinstance(error, Exception) else message
            self.last_generation_error = diagnostics["gemini_error"]

        def parse_response(response: Any, prefix: str) -> tuple[dict[str, Any] | None, str]:
            raw = str(getattr(response, "text", "") or "").strip()
            diagnostics["raw_response_present"] = diagnostics["raw_response_present"] or bool(raw)
            if os.getenv("CLINICAL_DEBUG_PROVIDER_OUTPUT", "").lower() in {"1", "true", "yes"}:
                logger.debug("Provider output received stage=%s characters=%s", prefix, len(raw))
            if not raw:
                diagnostics[f"{prefix}_empty_response"] = True
                return None, raw
            try:
                return json.loads(_json_response_text(response)), raw
            except Exception as error:
                diagnostics[f"{prefix}_json_parse_failed"] = True
                diagnostics[f"{prefix}_parsing_error"] = f"{type(error).__name__}: {error}"
                return None, raw

        api_key = os.getenv("GEMINI_API_KEY")
        gemini_timeout_seconds = min(
            60.0, max(45.0, float(os.getenv("GEMINI_REQUEST_TIMEOUT_SECONDS", "55")))
        )
        client = None
        types_module = None
        if api_key:
            try:
                from google import genai
                try:
                    from google.genai import types as types_module
                except ImportError:
                    types_module = None
                client_options: dict[str, Any] = {"api_key": api_key}
                http_options_type = getattr(types_module, "HttpOptions", None)
                if http_options_type is not None:
                    # google-genai expects this timeout in milliseconds.
                    client_options["http_options"] = http_options_type(
                        timeout=int(gemini_timeout_seconds * 1000)
                    )
                client = genai.Client(**client_options)
            except Exception as error:
                mark_failure("answer_provider_failed", error)
        else:
            mark_failure("answer_provider_failed", "GEMINI_API_KEY is not configured")

        def generate(stage: str, prompt: str, schema: dict[str, Any]) -> Any:
            if client is None:
                raise RuntimeError(self.last_generation_error or "Gemini provider unavailable")
            if diagnostics["quota_exhausted"]:
                diagnostics["gemini_calls_skipped_due_to_quota"] += 1
                raise RuntimeError("Gemini daily quota is exhausted")
            for attempt in range(2):
                gemini_started = time.perf_counter()
                try:
                    request: dict[str, Any] = {"model": model, "contents": prompt}
                    if types_module is not None:
                        request["config"] = types_module.GenerateContentConfig(
                            response_mime_type="application/json", response_json_schema=schema,
                        )
                    diagnostics["gemini_calls_attempted"] += 1
                    logger.info(
                        "[analysis] Gemini request started (stage=%s attempt=%s timeout=%.0fs)",
                        stage, attempt + 1, gemini_timeout_seconds,
                    )
                    response = client.models.generate_content(**request)
                    _analysis_timing(f"Gemini completed (stage={stage})", gemini_started)
                    return response
                except Exception as error:
                    _analysis_timing(f"Gemini failed (stage={stage})", gemini_started)
                    classification = _classify_provider_error(error)
                    diagnostics.update({key: value for key, value in classification.items() if key != "retryable"})
                    if classification["quota_exhausted"]:
                        raise
                    if attempt == 0 and classification["retryable"]:
                        diagnostics["transient_retry_attempted"] = True
                        wait_seconds = classification["retry_after"] if classification["retry_after"] is not None else 0.25
                        time.sleep(min(max(wait_seconds, 0.0), 2.0))
                        continue
                    raise

        prompt_started = time.perf_counter()
        reference_context = _budget_complete_records(evidence, 24000)
        # The cache supplies the complete session. Use all turns when they fit;
        # if an unusually long chat exceeds the model prompt budget, retain the
        # newest complete turns instead of silently keeping only the oldest.
        selected_history = _relevant_conversation_turns(
            conversation_history or [], user_text
        )
        history_context = _budget_complete_records(
            selected_history, 24000, prefer_latest=True
        )
        upload_context = _uploaded_source_context(uploaded_sources, user_text) if uploaded_sources else "[]"
        uploaded_chunks = _uploaded_evidence_chunks(uploaded_sources, user_text)
        ranked_upload_context = _budget_complete_records(uploaded_chunks, 18000)
        _analysis_timing("prompt context preparation", prompt_started)
        inventory: dict[str, Any] | None = None

        if request_type == "full_report" and client is not None:
            diagnostics["inventory_started"] = True
            prompt_loading_started = time.perf_counter()
            inventory_prompt = prompt_template(
                "INVENTORY",
                certainties=", ".join(sorted(_CERTAINTIES)),
                inventory_categories=", ".join(_INVENTORY_CATEGORIES),
                upload_context=upload_context,
            )
            _analysis_timing("prompt loading (inventory)", prompt_loading_started)
            raw_inventory = ""
            try:
                response = generate("inventory_generation", inventory_prompt, _INVENTORY_RESPONSE_SCHEMA)
                parsed, raw_inventory = parse_response(response, "inventory")
                if parsed is not None:
                    try:
                        inventory = _normalize_inventory(parsed, len(uploaded_sources))
                    except ValueError as error:
                        diagnostics[str(error)] = True
                if inventory is None:
                    diagnostics["inventory_repair_attempted"] = True
                    repair = generate(
                        "inventory_repair",
                        inventory_prompt + "\n" + prompt_template("INVENTORY_REPAIR", raw_inventory=raw_inventory),
                        _INVENTORY_RESPONSE_SCHEMA,
                    )
                    repaired, _ = parse_response(repair, "inventory_repair")
                    if repaired is not None:
                        inventory = _normalize_inventory(repaired, len(uploaded_sources))
                        diagnostics["inventory_repair_succeeded"] = True
            except Exception as error:
                if diagnostics["inventory_repair_attempted"]:
                    diagnostics["inventory_repair_failed"] = True
                else:
                    diagnostics["inventory_provider_failed"] = True
                diagnostics["inventory_error"] = f"{type(error).__name__}: {error}"
            diagnostics["inventory_available"] = inventory is not None
            if inventory is None and diagnostics["inventory_repair_attempted"]:
                diagnostics["inventory_repair_failed"] = True

        structured: dict[str, Any] | None = None
        usable_raw: dict[str, Any] | None = None
        if client is not None and not diagnostics["quota_exhausted"]:
            diagnostics["answer_started"] = True
            prompt_loading_started = time.perf_counter()
            selected_prompt_id = {
                "general": "GENERAL_CONTRACT",
                "focused": "FOCUSED_CONTRACT",
                "full_report": "FULL_REPORT_CONTRACT",
            }[request_type]
            routing_method = "deterministic"
            diagnostics["prompt_selection"] = {
                **prompt_metadata(selected_prompt_id), "routing_method": routing_method,
            }
            provenance = prompt_template("PROVENANCE")
            grounding = prompt_template("CLINICAL_GROUNDING")
            task_prompt = "Follow the selected task contract exactly."
            if request_type == "general":
                schema = _GENERAL_RESPONSE_SCHEMA
                contract = prompt_template("GENERAL_CONTRACT")
            elif request_type == "focused":
                schema = _FOCUSED_RESPONSE_SCHEMA
                image_only_request = bool(image_paths) and not any(
                    source.get("source_type") == "uploaded_report"
                    for source in uploaded_sources
                )
                contract = prompt_template(
                    "IMAGE_CONTRACT" if image_only_request else "FOCUSED_CONTRACT"
                )
            else:
                schema = _ANSWER_RESPONSE_SCHEMA
                contract = prompt_template("FULL_REPORT_CONTRACT")
            answer_prompt = prompt_template(
                "ANSWER",
                grounding=grounding,
                provenance=provenance,
                contract=contract,
                task_prompt=task_prompt,
                user_text=user_text,
                inventory=json.dumps(inventory, ensure_ascii=False),
                ranked_upload_context=ranked_upload_context,
                upload_context=upload_context,
                reference_context=reference_context,
                history_context=history_context,
            )
            _analysis_timing("prompt loading (answer)", prompt_loading_started)
            raw_answer = ""
            try:
                response = generate("answer_generation", answer_prompt, schema)
                parsed, raw_answer = parse_response(response, "answer")
                usable_raw = parsed

                def normalize_answer(candidate: Any) -> dict[str, Any]:
                    if not isinstance(candidate, dict):
                        raise ValueError("answer_schema_failed")
                    if request_type == "general":
                        if not str(candidate.get("answer") or "").strip():
                            raise ValueError("answer_schema_failed")
                        supplied = [str(c) for c in _as_list(candidate.get("reference_citations"))]
                        citations = [c for c in supplied if re.fullmatch(r"R\d+", c) and int(c[1:]) <= len(evidence)]
                        diagnostics["answer_invalid_citation"] = bool(supplied and len(citations) != len(supplied))
                        return {"answer": str(candidate["answer"]).strip(), "limitations": [str(x) for x in _as_list(candidate.get("limitations"))], "reference_citations": citations}
                    if request_type == "focused":
                        supplied = [str(c) for c in _as_list(candidate.get("citations"))]
                        citations = [c for c in supplied if re.fullmatch(r"U\d+", c) and int(c[1:]) <= len(uploaded_sources)]
                        diagnostics["answer_invalid_citation"] = bool(supplied and len(citations) != len(supplied))
                        certainty = str(candidate.get("certainty") or "insufficient_information")
                        if (
                            not str(candidate.get("answer") or "").strip()
                            or certainty not in _CERTAINTIES
                            or (certainty != "insufficient_information" and not citations)
                        ):
                            raise ValueError("answer_schema_failed")
                        return {"answer": str(candidate["answer"]).strip(), "certainty": certainty, "citations": citations}
                    patient_citations = [
                        str(citation)
                        for item in _as_list(candidate.get("key_findings"))
                        if isinstance(item, dict)
                        for citation in _as_list(item.get("citations"))
                    ]
                    diagnostics["answer_invalid_citation"] = any(
                        not re.fullmatch(r"U\d+", citation)
                        or int(citation[1:]) > len(uploaded_sources)
                        for citation in patient_citations
                    )
                    normalized = _normalize_structured_answer(candidate, len(uploaded_sources), len(evidence))
                    return _enforce_stage_authorization(normalized, uploaded_sources, authorized=False)

                try:
                    structured = normalize_answer(parsed)
                except Exception as error:
                    diagnostics["answer_schema_failed"] = True
                    diagnostics["answer_repair_attempted"] = True
                    repair = generate(
                        "answer_repair",
                        answer_prompt + "\n" + prompt_template("ANSWER_REPAIR", raw_answer=raw_answer),
                        schema,
                    )
                    repaired, _ = parse_response(repair, "answer_repair")
                    structured = normalize_answer(repaired)
                    diagnostics["answer_repair_succeeded"] = True
                diagnostics.update({
                    "answer_validation_passed": True, "generation_mode": "gemini_structured",
                    "generation_status": "gemini_structured", "status": "gemini_structured",
                    "failure_stage": None, "fallback_reason": None,
                })
            except Exception as error:
                diagnostics["answer_repair_failed"] = bool(diagnostics["answer_repair_attempted"])
                if not diagnostics.get("answer_schema_failed"):
                    diagnostics["answer_provider_failed"] = True
                diagnostics["answer_error"] = f"{type(error).__name__}: {error}"
                self.last_generation_error = diagnostics["answer_error"]
        elif client is not None and diagnostics["quota_exhausted"]:
            diagnostics["gemini_calls_skipped_due_to_quota"] += 1

        if structured is None and isinstance(usable_raw, dict):
            raw_text = str(usable_raw.get("answer") or usable_raw.get("plain_language_summary") or usable_raw.get("headline") or "").strip()
            raw_citations = list(dict.fromkeys(re.findall(r"[UR]\d+", json.dumps(usable_raw, ensure_ascii=False))))
            linked_patient_citations = (
                re.findall(r"U\d+", raw_text)
                if request_type == "full_report"
                else [str(citation) for citation in _as_list(usable_raw.get("citations"))]
            )
            valid_u = [
                citation for citation in linked_patient_citations
                if re.fullmatch(r"U\d+", citation)
                and 1 <= int(citation[1:]) <= len(uploaded_sources)
            ]
            degraded_grounded = request_type == "general" or bool(valid_u)
            if raw_text and degraded_grounded:
                limitation = "Some structured details could not be fully validated."
                if request_type == "full_report":
                    structured = FullReportAnswer(
                        headline="Clinical evidence summary",
                        plain_language_summary=raw_text,
                        case_complexity={
                            "level": "insufficient_information",
                            "reason": "Case complexity could not be fully validated from the degraded response.",
                            "citations": [],
                        },
                        evidence_support={"level": "Limited", "explanation": limitation},
                        key_findings=[],
                        staging={
                            "documented_components": [], "unresolved_components": [],
                            "final_stage": None, "can_assign_final_stage": False,
                            "explanation": "Structured staging details could not be fully validated.",
                            "citations": [],
                        },
                        limitations=[limitation], medical_terms=[], safety_notice=DISCLAIMER,
                    ).model_dump()
                elif request_type == "focused":
                    structured = {"answer": raw_text, "certainty": "insufficient_information", "citations": valid_u}
                else:
                    structured = {"answer": raw_text, "limitations": [limitation], "reference_citations": [c for c in raw_citations if c.startswith("R") and int(c[1:]) <= len(evidence)]}
                diagnostics.update({"generation_mode": "gemini_degraded", "generation_status": "gemini_degraded", "status": "gemini_degraded", "fallback_reason": "answer_structure_invalid"})
            elif raw_text and request_type != "general":
                diagnostics["fallback_reason"] = "degraded_answer_missing_valid_u_grounding"

        if structured is not None:
            summary = str(structured.get("answer") or structured.get("plain_language_summary") or structured.get("headline")).strip()
            self.last_generation_metadata = diagnostics
            return summary, model, structured

        points = _extract_uploaded_points(uploaded_sources, question=user_text)
        diagnostics.update({"generation_mode": "extractive_fallback", "generation_status": "extractive_fallback", "status": "extractive_fallback", "fallback_reason": diagnostics.get("fallback_reason") or ("provider_unavailable" if client is None else "answer_unusable")})
        if request_type == "general":
            asks_about_unshared_result = bool(re.search(r"\b(?:biopsy|pathology|report|findings?|results?)\b", user_text, re.I))
            if asks_about_unshared_result:
                result_name = "biopsy result" if re.search(r"\bbiopsy\b", user_text, re.I) else "report result"
                summary = f"I cannot tell what type of cancer is suggested without the actual {result_name}. Please upload the report or paste its Diagnosis or Impression section, and I can explain it in simple terms."
            else:
                summary = "I can provide general oncology information when the language model service is available. Please try again shortly."
            fallback = None
        elif request_type == "focused" and points:
            summary = "AI interpretation is currently unavailable. The uploaded report explicitly states: " + points[0] + " This extracted wording still requires professional clinical interpretation."
            fallback = {"answer": summary, "certainty": "insufficient_information", "citations": re.findall(r"U\d+", points[0])}
        elif points:
            summary = "AI interpretation is currently unavailable. The uploaded report explicitly documents:\n" + "\n".join(f"• {point}" for point in points) + "\nThese are extracted findings from the report and still require professional clinical interpretation."
            fallback = _normalize_structured_answer({
                "headline": "Extracted report findings", "plain_language_summary": summary,
                "case_complexity": {"level": "insufficient_information", "reason": "Automated interpretation is unavailable.", "citations": []},
                "evidence_support": {"level": "Limited", "explanation": "Only explicit uploaded report sentences are shown."},
                "key_findings": [{"title": f"Reported finding {i + 1}", "result": re.sub(r"\s*\[U\d+\]", "", point), "meaning": "This is extracted report wording.", "certainty": "insufficient_information", "importance": "supporting", "citations": re.findall(r"U\d+", point)} for i, point in enumerate(points)],
                "staging": {"documented_components": [], "unresolved_components": [], "final_stage": None, "can_assign_final_stage": False, "explanation": "No stage was inferred.", "citations": []},
                "limitations": ["Gemini interpretation is currently unavailable."], "medical_terms": [], "safety_notice": DISCLAIMER,
            }, len(uploaded_sources), len(evidence))
        else:
            summary = "The clinical explanation service is currently unavailable, and no readable uploaded finding was available to extract."
            fallback = None
        self.last_generation_metadata = diagnostics
        return summary, "retrieval-only", fallback

@lru_cache(maxsize=1)
def get_analysis_pipeline() -> ClinicalAnalysisPipeline:
    """Load both large encoders once per backend process."""
    return ClinicalAnalysisPipeline(device=os.getenv("MODEL_DEVICE", "auto"))
