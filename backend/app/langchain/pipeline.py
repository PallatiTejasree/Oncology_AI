"""Application-facing retrieval and grounded-summary pipeline.

This module deliberately reuses the validated top-level ``Query`` package so
the API cannot silently use a different embedding model from the Chroma index.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Query.pipeline import QueryPipeline  # noqa: E402


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


def _extractive_points(user_text: str, evidence: list[dict[str, Any]]) -> list[str]:
    """Select concise evidence sentences relevant to the question."""
    query_terms = {
        token for token in re.findall(r"[a-z0-9]+", user_text.lower())
        if len(token) > 2 and token not in _STOP_WORDS
    }
    candidates: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for rank, item in enumerate(evidence):
        text_value = " ".join(str(item.get("text") or "").split())
        for sentence in re.split(r"(?<=[.!?])\s+", text_value):
            sentence = sentence.strip(" -•")
            if len(sentence) < 25:
                continue
            normalized = sentence.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            sentence_terms = set(re.findall(r"[a-z0-9]+", normalized))
            overlap = len(query_terms & sentence_terms)
            candidates.append((overlap, -rank, sentence[:320]))
    candidates.sort(reverse=True)
    relevant = [text for overlap, _, text in candidates if overlap > 0][:4]
    if not relevant:
        relevant = [text for _, _, text in candidates[:3]]
    return relevant


def _evidence_item(result: dict[str, Any]) -> dict[str, Any]:
    metadata = result.get("metadata") or {}
    return {
        "id": result.get("id"),
        "rank": result.get("fused_rank") or result.get("rank"),
        "modality": result.get("modality"),
        "text": result.get("document") or "",
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


def _risk_review(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe retrieval limitations without inventing a clinical probability."""
    labels = [
        str(item.get("cancer_type")).replace("_", " ").title()
        for item in evidence
        if item.get("cancer_type")
        and str(item.get("cancer_type")).lower() not in {"unknown", "unlabelled"}
    ]
    unique_labels = list(dict.fromkeys(labels))
    if not evidence:
        agreement = "No retrieved evidence"
        agreement_note = "The system did not retrieve enough evidence for comparison."
    elif len(unique_labels) == 1:
        agreement = "One label represented"
        agreement_note = "Similar results share one label, but similarity is not a diagnosis."
    else:
        agreement = "Mixed labels"
        agreement_note = "Similar results include different labels and cannot support one conclusion."

    return {
        "level": "Not determined",
        "explanation": (
            "This system retrieves similar cases; it has not been clinically validated "
            "to calculate an individual's probability of cancer."
        ),
        "rows": [
            {
                "factor": "Estimated cancer risk",
                "status": "Not calculated",
                "meaning": "Retrieval similarity scores are not cancer-risk percentages.",
            },
            {
                "factor": "Labels in similar evidence",
                "status": ", ".join(unique_labels[:4]) if unique_labels else "Unavailable",
                "meaning": "These labels describe retrieved references, not the uploaded case.",
            },
            {
                "factor": "Evidence agreement",
                "status": agreement,
                "meaning": agreement_note,
            },
            {
                "factor": "Required next step",
                "status": "Professional review",
                "meaning": "A qualified clinician must interpret the original report or image in context.",
            },
        ],
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


def _normalize_structured_answer(value: Any) -> dict[str, Any]:
    """Normalize external LLM JSON and apply conservative evidence labeling."""
    if not isinstance(value, dict):
        raise ValueError("Gemini structured answer must be a JSON object")
    normalized = dict(value)
    for key in ("findings", "reasoning", "supports", "limitations"):
        normalized[key] = _as_list(normalized.get(key))
    terms = normalized.get("medical_terms")
    if isinstance(terms, dict):
        terms = ([terms] if "term" in terms or "definition" in terms else [
            {"term": str(term), "definition": str(definition)}
            for term, definition in terms.items()
        ])
    normalized["medical_terms"] = _as_list(terms)
    for section in ("findings", "reasoning"):
        for item in normalized[section]:
            if isinstance(item, dict):
                citations = item.get("citations")
                item["citations"] = (
                    re.findall(r"[UR]\d+", citations)
                    if isinstance(citations, str) else _as_list(citations)
                )
    support = normalized.get("evidence_support")
    if not isinstance(support, dict):
        support = {"level": "Limited", "explanation": str(support or "Evidence quality requires review.")}
    if str(support.get("level") or "").lower() == "strong":
        support["level"] = "Moderate"
        explanation = str(support.get("explanation") or "").strip()
        support["explanation"] = (
            f"{explanation} Automatic source matching has not been clinician-validated."
        ).strip()
    normalized["evidence_support"] = support
    return normalized


def _structured_citation_text(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    citations = []
    for section in ("findings", "reasoning"):
        for item in value.get(section) or []:
            citations.extend(item.get("citations") or [])
    return " ".join(f"[{citation}]" for citation in citations)


class ClinicalAnalysisPipeline:
    def __init__(self, device: str = "auto") -> None:
        self.retrieval = QueryPipeline(device=device)
        self.last_generation_error: str | None = None

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
    ) -> dict[str, Any]:
        analysis_started = time.perf_counter()
        clean_text = (text or "").strip()
        all_image_paths = [str(path) for path in (image_paths or [])]
        if image_path:
            all_image_paths.insert(0, str(image_path))
        all_image_paths = list(dict.fromkeys(all_image_paths))
        retrieval_started = time.perf_counter()
        if all_image_paths:
            retrieval = self.retrieval.query_images(
                all_image_paths, ocr_text=clean_text or None, top_k=top_k
            )
        elif clean_text:
            retrieval = self.retrieval.query_text(clean_text, top_k=top_k)
        else:
            raise ValueError("Analysis requires report text, an image, or both")
        retrieval_ms = round((time.perf_counter() - retrieval_started) * 1000, 2)

        selected_results = retrieval["fused_results"]
        if retrieval["query_type"] in {"image", "multi_image"}:
            # User-facing image explanations should be concise and based on the
            # strongest captioned image references, not a long mixed ranking.
            selected_results = retrieval.get("image_results", selected_results)[:3]
        evidence = [_evidence_item(item) for item in selected_results]
        supporting_images = [
            _evidence_item(item)
            for item in retrieval.get("supporting_image_results", [])
        ]
        summary_context = evidence + supporting_images
        generation_started = time.perf_counter()
        summary, model_name, structured_answer = self._summarize(
            clean_text, summary_context, conversation_history or [], uploaded_sources or []
        )
        generation_ms = round((time.perf_counter() - generation_started) * 1000, 2)
        citation_validation = _validate_citations(
            summary + _structured_citation_text(structured_answer),
            len(uploaded_sources or []), len(summary_context)
        )
        if citation_validation["invalid"]:
            summary = _remove_invalid_citations(summary, citation_validation["invalid"])
            structured_answer = _clean_structured_citations(
                structured_answer, citation_validation["invalid"]
            )
            citation_validation = _validate_citations(
                summary + _structured_citation_text(structured_answer),
                len(uploaded_sources or []), len(summary_context)
            ) | {"repaired": True}
        return {
            "query_type": retrieval["query_type"],
            "summary": summary,
            "structured_answer": structured_answer,
            "model_name": model_name,
            "generation_diagnostics": {
                "status": "generated" if structured_answer else "fallback",
                "error": getattr(self, "last_generation_error", None),
            },
            "evidence": evidence,
            "supporting_image_evidence": supporting_images,
            "diagnostics": {
                **retrieval["diagnostics"],
                "performance": {
                    "retrieval_ms": retrieval_ms,
                    "generation_ms": generation_ms,
                    "pipeline_total_ms": round(
                        (time.perf_counter() - analysis_started) * 1000, 2
                    ),
                },
            },
            "citation_validation": citation_validation,
            "uploaded_sources": uploaded_sources or [],
            "research_summary": _research_summary(summary_context),
            "risk_review": _risk_review(summary_context) if include_risk_review else None,
            "disclaimer": DISCLAIMER,
        }

    def _summarize(
        self,
        user_text: str,
        evidence: list[dict[str, Any]],
        conversation_history: list[dict[str, str]] | None = None,
        uploaded_sources: list[dict[str, Any]] | None = None,
    ) -> tuple[str, str, dict[str, Any] | None]:
        self.last_generation_error = None
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            self.last_generation_error = "GEMINI_API_KEY is not configured"
        else:
            try:
                from google import genai

                client = genai.Client(api_key=api_key)
                numbered_evidence = [
                    {"citation_number": index, **item}
                    for index, item in enumerate(evidence, start=1)
                ]
                context = json.dumps(numbered_evidence, ensure_ascii=False)[:24000]
                history = json.dumps(conversation_history or [], ensure_ascii=False)[:8000]
                upload_context = json.dumps([
                    {"citation_id": f"U{index}", **item}
                    for index, item in enumerate(uploaded_sources or [], start=1)
                ], ensure_ascii=False)[:4000]
                prompt = (
                    "You are an oncology clinical decision-support assistant. "
                    "Use only the supplied retrieval evidence. Distinguish the user's "
                    "content from retrieved similar cases. Do not make a definitive "
                    "diagnosis or prescribe treatment. State when evidence is insufficient.\n\n"
                    f"USER CONTENT:\n{user_text[:12000]}\n\n"
                    f"UPLOADED SOURCES (USER CONTENT PROVENANCE):\n{upload_context}\n\n"
                    f"RECENT CONVERSATION (context only; never treat it as evidence):\n{history}\n\n"
                    f"RETRIEVED EVIDENCE:\n{context}\n\n"
                    "Return valid JSON only, with no Markdown fence. Use this exact object shape: "
                    "{\"headline\":string,\"subheadline\":string,"
                    "\"evidence_support\":{\"level\":\"Strong|Moderate|Limited|Insufficient\",\"explanation\":string},"
                    "\"plain_language_summary\":string,"
                    "\"findings\":[{\"finding\":string,\"result\":string,\"meaning\":string,\"citations\":[string]}],"
                    "\"reasoning\":[{\"title\":string,\"explanation\":string,\"citations\":[string]}],"
                    "\"supports\":[string],\"limitations\":[string],"
                    "\"medical_terms\":[{\"term\":string,\"definition\":string}],"
                    "\"safety_notice\":string}. "
                    "Use cautious wording such as 'findings support' or 'most consistent with', not a definitive diagnosis. "
                    "Evidence support is a qualitative description, never a probability. Do not use Strong because semantic support has not been clinician-validated; use Moderate, Limited, or Insufficient. Keep the plain-language summary to two short paragraphs. "
                    "Include only findings actually present in user content or retrieved evidence. Put source IDs like U1 and R1 in citations arrays without brackets. "
                    "Claims about user content use uploaded IDs such as U1. Retrieved claims use R IDs matching citation_number. "
                    "Never invent citations, never use ranges, and never cite conversation history. "
                    "Clearly separate uploaded case findings from retrieved supporting similarity and state the most important limitation."
                )
                model = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
                response = client.models.generate_content(model=model, contents=prompt)
                if response.text and response.text.strip():
                    raw = response.text.strip().removeprefix("```json").removesuffix("```").strip()
                    structured = _normalize_structured_answer(json.loads(raw))
                    summary = structured.get("plain_language_summary") or structured.get("headline")
                    if summary:
                        return str(summary).strip(), model, structured
                self.last_generation_error = "Gemini returned an empty response"
            except Exception as error:
                # Retrieval remains usable when the optional external LLM is unavailable.
                self.last_generation_error = f"{type(error).__name__}: {str(error)[:1000]}"

        points = _extractive_points(user_text, evidence)
        if evidence and all(item.get("modality") == "image" for item in evidence):
            labels = [
                item.get("cancer_type")
                for item in evidence
                if item.get("cancer_type") and item.get("cancer_type") != "unknown"
            ]
            readable = [label.replace("_", " ").title() for label in dict.fromkeys(labels)]
            label_text = ", ".join(readable) if readable else "different conditions"
            overview = (
                "The uploaded image was compared with similar indexed reference images. "
                f"The related references include {label_text}, but visual similarity alone cannot identify the uploaded image or diagnose cancer. "
                "A qualified radiologist or pathologist should review the original image together with its modality, specimen site, and clinical history."
            )
        else:
            overview = "Based on the related indexed oncology records"
        if evidence and all(item.get("modality") == "image" for item in evidence):
            return overview, "retrieval-only", None
        return (
            (f"{overview}, the relevant findings are: " + "; ".join(point.rstrip(".") for point in points) + ". "
             if points else "The indexed records did not provide a sufficiently clear answer to this question. ")
            + "These related findings are not a diagnosis and should be checked against the original clinical material by a qualified clinician."
        ), "retrieval-only", None


@lru_cache(maxsize=1)
def get_analysis_pipeline() -> ClinicalAnalysisPipeline:
    """Load both large encoders once per backend process."""
    return ClinicalAnalysisPipeline(device=os.getenv("MODEL_DEVICE", "auto"))
