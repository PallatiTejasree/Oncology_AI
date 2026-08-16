"""FastAPI endpoints that connect uploads to the validated retrieval pipeline."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.langchain.service import get_langchain_analysis_service
from app.models.summary import Summary
from app.models.chat_history import ChatHistory
from app.models.upload_session import UploadSession
from app.models.user import User
from app.middleware.auth_middleware import get_current_user
from app.schemas.analysis import AnalysisResponseContract, SessionAnalysisRequest, TextAnalysisRequest
from app.services.conversation_responses import conversational_result, is_oncology_document, is_oncology_scope, managed_response, out_of_scope_result
from app.services.conversation_cache import conversation_cache
from app.services.safety_responses import care_urgency, safety_result
from app.services.pdf_extraction import extract_pdf_images
from app.services.upload_ingestion import (
    ingest_session,
    inspect_image,
    retrieve_private_content,
)
from app.services.upload_consistency import assess_upload_consistency, consistency_diagnostics, mismatch_result


router = APIRouter(prefix="/analysis", tags=["Analysis"])


@router.get("/status")
def analysis_connection_status():
    """Report FastAPI → LangChain → Gemini wiring without exposing secrets."""
    return get_langchain_analysis_service().status()


def _session_quality_score(session: UploadSession) -> float | None:
    files = [*session.reports, *session.medical_images]
    accepted = [item.quality_score for item in files if item.quality_score is not None and item.processing_status in {"Indexed", "Processed"}]
    scores = accepted or [item.quality_score for item in files if item.quality_score is not None]
    return round(sum(scores) / len(scores), 1) if scores else None


def _humanize(value: str) -> str:
    return " ".join(value.replace("_", " ").replace("-", " ").split()).title()


def _meaningful_title(session: UploadSession, result: dict) -> str:
    files = [item.file_name for item in session.reports] + [item.file_name for item in session.medical_images]
    stem = _humanize(Path(files[0]).stem) if files else ""
    evidence = result.get("evidence") or []
    label = next((item.get("cancer_type") for item in evidence if item.get("cancer_type") and item.get("cancer_type") != "unknown"), None)
    if session.input_type == "image":
        return f"Pathology image review — {stem or _humanize(label or 'uploaded image')}"[:255]
    if session.input_type == "report":
        return f"Clinical report review — {stem or 'Uploaded report'}"[:255]
    if session.input_type == "both":
        return f"Multimodal case review — {stem or 'Uploaded case'}"[:255]
    if result.get("response_type") == "conversation" and result.get("intent") == "greeting":
        return "Greeting"
    words = (session.original_query or "Oncology question").split()[:8]
    return ("General enquiry — " + " ".join(words)).strip()[:255]


def _diagnostic_status(result: dict) -> str:
    if result.get("response_type") in {"conversation", "safety"}:
        return "not_applicable"
    diagnostics = result.get("diagnostics") or {}
    statuses = [
        item.get("status")
        for item in diagnostics.values()
        if isinstance(item, dict) and "status" in item
    ]
    return "retrieved" if "retrieved" in statuses else "no_results"


def _uploaded_source_payload(reports, images, private_evidence: dict) -> list[dict]:
    """Keep original extraction and private chunks distinct under one U source."""
    retrieved_by_name: dict[str, list[dict]] = {}
    for item in [*private_evidence.get("text", []), *private_evidence.get("images", [])]:
        file_name = item.get("file_name")
        content = " ".join(str(item.get("content") or "").split())
        if file_name and content:
            values = retrieved_by_name.setdefault(file_name, [])
            if content not in [value["content"] for value in values]:
                values.append({
                    "origin": "private_retrieved_chunk", "chunk_id": item.get("id"),
                    "content": content, "source_type": item.get("source_type"),
                })

    payload = []
    for report in reports:
        excerpts = retrieved_by_name.get(report.file_name) or []
        # The uploaded report itself is the primary evidence.  Semantic search
        # excerpts are supplemental only; a broad question must never replace
        # the report with an unrelated chunk from the same PDF.
        extracted_text = " ".join((report.extracted_text or "").split())
        payload.append({
            "file_name": report.file_name,
            "source_type": "uploaded_report",
            "mime_type": report.mime_type or "application/pdf",
            "content": extracted_text[:12000],
            "evidence_segments": [
                {"origin": "original_extraction", "content": extracted_text[:12000]},
                *excerpts,
            ],
        })
    for image in images:
        excerpts = retrieved_by_name.get(image.file_name) or []
        ocr_text = " ".join((image.extracted_text or "").split())
        payload.append({
            "file_name": image.file_name,
            "source_type": "uploaded_image",
            "mime_type": image.mime_type,
            "content": ocr_text[:6000],
            "evidence_segments": [
                {"origin": "original_extraction", "content": ocr_text[:6000]},
                *excerpts,
            ],
        })
    return payload


def _store_result(
    db: Session,
    session: UploadSession,
    result: dict,
    processing_time_ms: int,
    interaction_question: str | None = None,
) -> Summary:
    diagnostics = result.get("diagnostics") or {}
    if result.get("generation_diagnostics"):
        diagnostics = {**diagnostics, "generation": result["generation_diagnostics"]}
    evidence = {
        "uploaded_sources": result.get("uploaded_sources") or [],
        "private": result.get("private_evidence") or {"text": [], "images": []},
        "primary": result.get("evidence") or [],
        "supporting_images": result.get("supporting_image_evidence") or [],
        "citation_validation": result.get("citation_validation") or {},
    }
    stored = Summary(
        session_id=session.id,
        # Keep the complete response for backward-compatible result reopening.
        ai_summary=json.dumps(result, ensure_ascii=False),
        confidence_score=_session_quality_score(session),
        model_name=result["model_name"],
        processing_status="Completed",
        query_type=result.get("query_type"),
        retrieval_status=_diagnostic_status(result),
        diagnostics_json=json.dumps(diagnostics, ensure_ascii=False),
        evidence_json=json.dumps(evidence, ensure_ascii=False),
        disclaimer=result.get("disclaimer"),
        calibrated=False,
        processing_time_ms=processing_time_ms,
    )
    session.status = "Completed"
    session.session_name = _meaningful_title(session, result)
    session.failure_reason = None
    session.completed_at = datetime.now(timezone.utc)
    db.add(stored)
    question = interaction_question or session.original_query or ", ".join(
        [item.file_name for item in session.reports]
        + [item.file_name for item in session.medical_images]
    ) or "Uploaded clinical material"
    answer = result.get("summary") or "No summary was generated."
    db.add(ChatHistory(user_id=session.user_id, session_id=session.id, question=question, answer=answer))
    db.commit()
    db.refresh(stored)
    conversation_cache.append(
        user_id=session.user_id,
        session_id=session.id,
        question=question,
        answer=answer,
    )
    return stored


def _store_failure(
    db: Session,
    session: UploadSession,
    reason: str,
    processing_time_ms: int,
    interaction_question: str | None = None,
) -> None:
    clean_reason = reason[:2000]
    session.status = "Failed"
    session.failure_reason = clean_reason
    db.add(
        Summary(
            session_id=session.id,
            processing_status="Failed",
            query_type=session.input_type,
            retrieval_status="failed",
            calibrated=False,
            confidence_score=_session_quality_score(session),
            processing_time_ms=processing_time_ms,
            failure_reason=clean_reason,
        )
    )
    question = interaction_question or session.original_query or ", ".join(
        [item.file_name for item in session.reports]
        + [item.file_name for item in session.medical_images]
    ) or "Uploaded clinical material"
    db.add(ChatHistory(user_id=session.user_id, session_id=session.id, question=question, answer=clean_reason))
    db.commit()


def _extract_pdf(path: Path) -> str:
    try:
        import fitz

        with fitz.open(path) as document:
            return "\n".join(page.get_text("text") for page in document).strip()
    except Exception as error:
        raise HTTPException(422, f"Could not extract PDF text from {path.name}") from error


def _run_analysis(
    *,
    db: Session,
    text: str | None,
    image_path: Path | None,
    top_k: int,
    image_paths: list[Path] | None = None,
    conversation_history: list[dict[str, str]] | None = None,
    safety_text: str | None = None,
    has_uploaded_material: bool = False,
    uploaded_sources: list[dict] | None = None,
    private_evidence: dict[str, list[dict]] | None = None,
    intent_text: str | None = None,
) -> dict:
    safe_response = safety_result(safety_text if safety_text is not None else text)
    if safe_response is not None:
        return safe_response
    # Attached clinical material must always be analyzed. Text-only small talk
    # can bypass model loading, embeddings, and vector retrieval.
    all_image_paths = [*(image_paths or [])]
    if image_path is not None:
        all_image_paths.insert(0, image_path)
    if not all_image_paths:
        quick_response = conversational_result(db, text)
        if quick_response is not None:
            return quick_response
    if not has_uploaded_material and not all_image_paths and not is_oncology_scope(text, conversation_history):
        return out_of_scope_result()
    try:
        result = get_langchain_analysis_service().analyze(
            text=text,
            image_paths=all_image_paths,
            top_k=top_k,
            conversation_history=conversation_history,
            include_risk_review=has_uploaded_material,
            uploaded_sources=uploaded_sources,
            private_evidence=private_evidence,
            intent_text=intent_text,
        )
        # Newly generated analysis payloads are validated here rather than via
        # FastAPI response_model so legacy stored responses can still be read.
        AnalysisResponseContract.model_validate(result)
        # Safety refusals are based only on what the user asks, but the
        # attention indicator may also use explicit high-priority language in
        # uploaded clinical material. It remains an uncalibrated review signal,
        # never a cancer-risk probability.
        urgency_text = (
            "\n".join(filter(None, [safety_text, text]))
            if has_uploaded_material else
            (safety_text if safety_text is not None else text)
        )
        generated_complexity = (result.get("structured_answer") or {}).get("case_complexity")
        result["care_urgency"] = care_urgency(
            urgency_text,
            documented_evidence=result.get("structured_answer"),
            uploaded_document="\n\n".join(
                str(source.get("content") or "") for source in (uploaded_sources or [])
            ),
        )
        if has_uploaded_material and isinstance(generated_complexity, dict):
            level = str(generated_complexity.get("level") or "insufficient_information")
            result["case_complexity"] = {
                "level": "insufficient" if level == "insufficient_information" else level,
                "label": "Documented complexity",
                "message": str(generated_complexity.get("reason") or "Gemini did not provide a complexity reason."),
                "basis": "Gemini-generated from cited uploaded evidence",
                "citations": generated_complexity.get("citations") or [],
                "calibrated": False,
            }
        else:
            result["case_complexity"] = None
        return result
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(422, str(error)) from error
    except Exception as error:
        raise HTTPException(500, f"Retrieval pipeline failed: {error}") from error


@router.post("/text")
def analyze_text(
    request: TextAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clean_text = request.text.strip()
    session = UploadSession(
        user_id=current_user.id,
        session_name=clean_text[:80],
        status="Processing",
        input_type="text",
        original_query=clean_text,
        top_k=request.top_k,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    started = time.perf_counter()
    try:
        result = _run_analysis(db=db, text=clean_text, image_path=None, top_k=request.top_k)
        elapsed = round((time.perf_counter() - started) * 1000)
        stored = _store_result(
            db, session, result, elapsed, interaction_question=clean_text
        )
        return {"session_id": session.id, "summary_id": stored.id, **result}
    except HTTPException as error:
        elapsed = round((time.perf_counter() - started) * 1000)
        _store_failure(db, session, str(error.detail), elapsed, interaction_question=clean_text)
        raise


@router.post("/session/{session_id}")
def analyze_session(
    session_id: int,
    request: SessionAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = (
        db.query(UploadSession)
        .filter(UploadSession.id == session_id, UploadSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(404, "Upload session not found")

    session.status = "Processing"
    session.failure_reason = None
    question = (request.question or "").strip()
    if question and not session.original_query:
        session.original_query = question
    session.top_k = request.top_k
    db.commit()
    started = time.perf_counter()
    try:
        if session.input_type == "text" and not session.reports and not session.medical_images:
            recent_turns = conversation_cache.get(
                db, user_id=current_user.id, session_id=session.id
            )
            result = _run_analysis(
                db=db,
                text=question or session.original_query,
                image_path=None,
                top_k=request.top_k,
                conversation_history=recent_turns,
                safety_text=question,
                has_uploaded_material=False,
            )
            elapsed = round((time.perf_counter() - started) * 1000)
            stored = _store_result(
                db, session, result, elapsed, interaction_question=question or None
            )
            return {"session_id": session.id, "summary_id": stored.id, **result}

        ingestion = ingest_session(db, session)
        accepted_reports = [
            item for item in session.reports
            if item.processing_status in {"Indexed", "Processed"}
        ]
        accepted_images = [
            item for item in session.medical_images
            if item.processing_status in {"Indexed", "Processed"}
        ]
        if not accepted_reports and not accepted_images:
            reasons = "; ".join(
                f"{item['file_name']}: {item['reason']}" for item in ingestion["rejected"]
            ) or "No uploaded file passed validation"
            raise HTTPException(422, reasons)
        report_texts = []
        for report in accepted_reports:
            path = Path(report.file_path)
            if not report.extracted_text:
                report.extracted_text = _extract_pdf(path)
            report.processing_status = "Processed"
            if report.extracted_text:
                report_texts.append(report.extracted_text)
        image_ocr_texts = [
            image.extracted_text for image in accepted_images if image.extracted_text
        ]
        recent_turns = conversation_cache.get(
            db, user_id=current_user.id, session_id=session.id
        )
        consistency = assess_upload_consistency([
            *[
                {"file_name": report.file_name, "text": report.extracted_text}
                for report in accepted_reports
            ],
            *[
                {"file_name": image.file_name, "text": image.extracted_text}
                for image in accepted_images
            ],
        ])
        if not consistency.consistent:
            friendly_message = managed_response(
                db,
                "upload_mismatch",
                (
                    "Oops! It looks like the uploaded documents belong to different patients or cases. "
                    "Please check your files and upload the matching report and image together."
                ),
            )
            result = mismatch_result(consistency, friendly_message)
            elapsed = round((time.perf_counter() - started) * 1000)
            stored = _store_result(
                db, session, result, elapsed, interaction_question=question or None
            )
            return {"session_id": session.id, "summary_id": stored.id, **result}
        extracted_material = "\n\n".join([*report_texts, *image_ocr_texts]).strip()
        if (
            len(extracted_material) >= 100
            and not is_oncology_document(extracted_material)
            and not is_oncology_scope(question, recent_turns)
        ):
            result = out_of_scope_result(
                "Sorry, this appears to be a general medical or laboratory report rather than oncology-related material. "
                "I’m limited to oncology reports, cancer-related medical images, and evidence in that area, so I won’t "
                "compare this file with cancer cases or provide a potentially misleading interpretation. Please ask a "
                "qualified healthcare professional to review this report."
            )
            result.setdefault("diagnostics", {})["upload_consistency"] = consistency_diagnostics(consistency)
            elapsed = round((time.perf_counter() - started) * 1000)
            stored = _store_result(db, session, result, elapsed, interaction_question=question or None)
            return {"session_id": session.id, "summary_id": stored.id, **result}
        private_query = question or " ".join(report_texts)[:4000] or "uploaded clinical image"
        private_evidence = retrieve_private_content(
            user_id=current_user.id,
            session_id=session.id,
            question=private_query,
            top_k=request.top_k,
        )

        image_paths = [Path(image.file_path) for image in accepted_images]
        extracted_pdf_images = []
        uploaded_sources = _uploaded_source_payload(
            accepted_reports, accepted_images, private_evidence
        )
        for report in accepted_reports:
            report_path = Path(report.file_path)
            extracted = extract_pdf_images(
                report_path,
                report_path.parent / "extracted_images" / report_path.stem,
            )
            for item in extracted:
                quality = inspect_image(item.path)
                if quality.accepted:
                    extracted_pdf_images.append(item)
                    image_paths.append(item.path)
                else:
                    ingestion["rejected"].append({
                        "file_name": f"{report.file_name} page {item.page} image",
                        "reason": quality.rejection_reason,
                    })
        for image in accepted_images:
            image.processing_status = "Processed"
        result = _run_analysis(
            db=db,
            text="\n\n".join(filter(None, [question, *report_texts, *image_ocr_texts])) or None,
            image_path=None,
            image_paths=image_paths,
            top_k=request.top_k,
            conversation_history=recent_turns,
            safety_text=question,
            has_uploaded_material=bool(session.reports or session.medical_images),
            uploaded_sources=uploaded_sources,
            private_evidence=private_evidence,
            intent_text=question,
        )
        result.setdefault("diagnostics", {})["upload_consistency"] = consistency_diagnostics(consistency)
        result.setdefault("diagnostics", {})["pdf_image_extraction"] = {
            "reports_processed": len(session.reports),
            "images_extracted": len(extracted_pdf_images),
            "pages": sorted({item.page for item in extracted_pdf_images}),
            "max_images": 8,
            "status": "extracted" if extracted_pdf_images else "no_embedded_images",
        }
        result["diagnostics"]["upload_ingestion"] = ingestion
        result["diagnostics"]["private_upload_retrieval"] = {
            "text_chunks_retrieved": len(private_evidence["text"]),
            "images_retrieved": len(private_evidence["images"]),
            "ownership_filter": "user_id_and_session_id",
            "calibrated": False,
        }
        elapsed = round((time.perf_counter() - started) * 1000)
        stored = _store_result(
            db, session, result, elapsed, interaction_question=question or None
        )
        return {"session_id": session.id, "summary_id": stored.id, **result}
    except HTTPException as error:
        elapsed = round((time.perf_counter() - started) * 1000)
        for report in session.reports:
            if report.processing_status not in {"Processed", "Rejected"}:
                report.processing_status = "Failed"
                report.rejection_reason = str(error.detail)[:2000]
        for image in session.medical_images:
            if image.processing_status not in {"Processed", "Rejected"}:
                image.processing_status = "Failed"
                image.rejection_reason = str(error.detail)[:2000]
        _store_failure(db, session, str(error.detail), elapsed, interaction_question=question or None)
        raise
    except Exception as error:
        elapsed = round((time.perf_counter() - started) * 1000)
        _store_failure(db, session, str(error), elapsed, interaction_question=question or None)
        raise HTTPException(500, f"Analysis failed: {error}") from error


@router.delete("/session/{session_id}/cache")
def clear_session_cache(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = (
        db.query(UploadSession)
        .filter(UploadSession.id == session_id, UploadSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(404, "Upload session not found")
    conversation_cache.clear(user_id=current_user.id, session_id=session_id)
    return {
        "message": "Cached conversation context cleared. PostgreSQL history was retained.",
        "session_id": session_id,
    }
