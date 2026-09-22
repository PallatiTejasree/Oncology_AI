"""Validated upload storage and upload-session lifecycle endpoints."""

from __future__ import annotations

import json
import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel

from app.db.database import get_db
from app.models.medical_image import MedicalImage
from app.models.report import Report
from app.models.upload_session import UploadSession
from app.models.user import User
from app.middleware.auth_middleware import get_current_user
from app.services.conversation_cache import conversation_cache
from app.services.chat_history_store import chat_history_store
from app.services.upload_ingestion import delete_private_session_vectors, ingest_session


router = APIRouter(prefix="/upload", tags=["Upload"])
PROJECT_ROOT = Path(__file__).resolve().parents[4]
UPLOAD_FOLDER = PROJECT_ROOT / "backend" / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

ALLOWED_REPORTS = {".pdf"}
ALLOWED_IMAGES = {".png", ".jpg", ".jpeg"}
ALLOWED_EXTENSIONS = ALLOWED_REPORTS | ALLOWED_IMAGES
MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_FILES = 3


class RenameSessionRequest(BaseModel):
    name: str


def _session_query(db: Session):
    return db.query(UploadSession).options(
        joinedload(UploadSession.reports),
        joinedload(UploadSession.medical_images),
        joinedload(UploadSession.summaries),
    )


def _summary_payload(summary: object | None, result: dict | None = None):
    if not summary:
        return None
    return {
        "id": summary.id,
        "model_name": summary.model_name,
        "processing_status": summary.processing_status,
        "created_at": summary.created_at,
        "query_type": summary.query_type,
        "retrieval_status": summary.retrieval_status,
        "calibrated": summary.calibrated,
        "processing_time_ms": summary.processing_time_ms,
        "confidence_score": summary.confidence_score,
        "result": result,
    }


def _display_title(session: UploadSession) -> str:
    if session.custom_title:
        return session.custom_title
    files = [item.file_name for item in session.reports] + [item.file_name for item in session.medical_images]
    stem = " ".join(Path(files[0]).stem.replace("_", " ").replace("-", " ").split()).title() if files else ""
    if session.session_name and not session.session_name.startswith("Analysis-") and session.session_name != session.original_query:
        return session.session_name
    if session.input_type == "image":
        return f"Pathology image review — {stem or 'Uploaded image'}"
    if session.input_type == "report":
        return f"Clinical report review — {stem or 'Uploaded report'}"
    if session.input_type == "both":
        return f"Multimodal case review — {stem or 'Uploaded case'}"
    query = " ".join((session.original_query or "").split())
    return f"Clinical question — {' '.join(query.split()[:7]) or 'Oncology review'}"


def _quality_reasons(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


def _rejected_file_payload(item, session: UploadSession, kind: str) -> dict:
    path = Path(item.file_path)
    return {
        "file_id": item.id,
        "session_id": session.id,
        "session_name": _display_title(session),
        "file_name": item.file_name,
        "file_type": kind,
        "mime_type": item.mime_type,
        "file_size": item.file_size,
        "processing_status": item.processing_status,
        "quality_score": item.quality_score,
        "quality_threshold": 40,
        "quality_reasons": _quality_reasons(item.quality_reasons_json),
        "rejection_reason": item.rejection_reason,
        "uploaded_at": item.created_at,
        "stored": path.is_file(),
    }
def _serialize(session: UploadSession, detailed: bool = False) -> dict:
    completed = [item for item in session.summaries if item.processing_status == "Completed"]
    latest = max(completed or session.summaries, key=lambda item: item.created_at) if session.summaries else None
    payload = {
        "session_id": session.id,
        "session_name": session.session_name,
        "custom_title": session.custom_title,
        "display_title": _display_title(session),
        "status": "Completed" if completed else session.status,
        "input_type": session.input_type,
        "original_query": session.original_query,
        "top_k": session.top_k,
        "failure_reason": session.failure_reason,
        "completed_at": session.completed_at,
        "archived_at": session.archived_at,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "files": [item.file_name for item in session.reports]
        + [item.file_name for item in session.medical_images],
    }
    if detailed:
        chat_messages = chat_history_store.list(
            user_id=session.user_id, session_id=session.id
        )
        payload["reports"] = [
            {
                "id": item.id,
                "file_name": item.file_name,
                "mime_type": item.mime_type,
                "file_size": item.file_size,
                "sha256": item.sha256,
                "processing_status": item.processing_status,
                "rejection_reason": item.rejection_reason,
                "quality_score": item.quality_score,
                "quality_reasons": _quality_reasons(item.quality_reasons_json),
                "has_text": bool(item.extracted_text),
            }
            for item in session.reports
        ]
        payload["images"] = [
            {
                "id": item.id,
                "file_name": item.file_name,
                "image_type": item.image_type,
                "mime_type": item.mime_type,
                "file_size": item.file_size,
                "sha256": item.sha256,
                "width": item.width,
                "height": item.height,
                "processing_status": item.processing_status,
                "rejection_reason": item.rejection_reason,
                "quality_score": item.quality_score,
                "quality_reasons": _quality_reasons(item.quality_reasons_json),
            }
            for item in session.medical_images
        ]
        ordered_summaries = sorted(session.summaries, key=lambda value: value.created_at)
        latest_index = ordered_summaries.index(latest) if latest in ordered_summaries else -1
        latest_message = (
            chat_messages[latest_index]
            if 0 <= latest_index < len(chat_messages)
            else None
        )
        latest_result = latest_message.get("result") if latest_message else None
        payload["latest_summary"] = _summary_payload(latest, latest_result)
        payload["messages"] = [
            {
                "id": item["id"],
                "question": item["question"],
                "answer": item["answer"],
                "created_at": item["created_at"],
            }
            for item in chat_messages
        ]
        ordered_messages = chat_messages
        all_files = sorted([*session.reports, *session.medical_images], key=lambda value: value.created_at)
        previous_summary_at = None
        payload["analyses"] = []
        for index, item in enumerate(ordered_summaries):
            message = ordered_messages[index] if index < len(ordered_messages) else None
            summary_payload = _summary_payload(item, message.get("result") if message else None)
            result = summary_payload.get("result") if summary_payload else None
            if not result and item.failure_reason:
                result = {
                    "response_type": "rejection",
                    "query_type": "validation",
                    "summary": item.failure_reason,
                }
            if not result:
                previous_summary_at = item.created_at
                continue
            turn_files = [
                value for value in all_files
                if value.created_at <= item.created_at
                and (previous_summary_at is None or value.created_at > previous_summary_at)
            ]
            payload["analyses"].append({
                "result": result,
                "question": message["question"] if message else session.original_query or "Analyze this uploaded file",
                "attachments": [{
                    "name": value.file_name,
                    "type": value.mime_type,
                    "kind": "report" if isinstance(value, Report) else "image",
                } for value in turn_files],
                "created_at": item.created_at,
            })
            previous_summary_at = item.created_at
    return payload


@router.post("")
@router.post("/", include_in_schema=False)
async def upload_files(
    email: str = Form(...),
    files: list[UploadFile] = File(...),
    session_id: int | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if email.strip() != current_user.email:
        raise HTTPException(403, "Cannot upload files for another user")
    user = current_user
    if not files:
        raise HTTPException(422, f"Upload between 1 and {MAX_FILES} files")

    ignored_files = files[MAX_FILES:]
    files = files[:MAX_FILES]

    prepared = []
    for upload in files:
        original = Path(upload.filename or "").name
        suffix = Path(original).suffix.lower()
        if not original or suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(415, f"Unsupported file type: {original or 'unnamed file'}")
        content = await upload.read(MAX_FILE_BYTES + 1)
        if not content:
            raise HTTPException(422, f"Empty file: {original}")
        if len(content) > MAX_FILE_BYTES:
            raise HTTPException(413, f"File exceeds 25 MB: {original}")
        if suffix == ".pdf" and not content.startswith(b"%PDF-"):
            raise HTTPException(422, f"Invalid PDF: {original}")
        width = height = None
        if suffix in ALLOWED_IMAGES:
            try:
                from io import BytesIO
                from PIL import Image

                with Image.open(BytesIO(content)) as image:
                    image.verify()
                with Image.open(BytesIO(content)) as image:
                    width, height = image.size
            except Exception as error:
                raise HTTPException(422, f"Invalid image: {original}") from error
        prepared.append(
            {
                "original": original,
                "suffix": suffix,
                "content": content,
                "mime_type": upload.content_type,
                "file_size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "width": width,
                "height": height,
            }
        )

    has_reports = any(item["suffix"] in ALLOWED_REPORTS for item in prepared)
    has_images = any(item["suffix"] in ALLOWED_IMAGES for item in prepared)
    input_type = "both" if has_reports and has_images else "report" if has_reports else "image"

    if session_id is not None:
        session = db.query(UploadSession).filter(
            UploadSession.id == session_id,
            UploadSession.user_id == user.id,
            UploadSession.archived_at.is_(None),
        ).first()
        if not session:
            raise HTTPException(404, "Conversation not found")
        existing_reports = bool(session.reports)
        existing_images = bool(session.medical_images)
        combined_reports = existing_reports or has_reports
        combined_images = existing_images or has_images
        session.input_type = "both" if combined_reports and combined_images else "report" if combined_reports else "image"
        session.status = "Uploaded"
        session.failure_reason = None
    else:
        session = UploadSession(
            user_id=user.id,
            session_name=f"Analysis-{uuid4().hex[:8]}",
            status="Uploaded",
            input_type=input_type,
            top_k=5,
        )
        db.add(session)
        db.flush()
    session_folder = UPLOAD_FOLDER / str(session.id)
    session_folder.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    try:
        for item in prepared:
            original = item["original"]
            suffix = item["suffix"]
            content = item["content"]
            path = session_folder / f"{uuid4().hex}{suffix}"
            path.write_bytes(content)
            written.append(path)
            if suffix in ALLOWED_REPORTS:
                db.add(
                    Report(
                        session_id=session.id,
                        file_name=original,
                        file_path=str(path),
                        mime_type=item["mime_type"],
                        file_size=item["file_size"],
                        sha256=item["sha256"],
                        processing_status="Uploaded",
                    )
                )
            else:
                db.add(
                    MedicalImage(
                        session_id=session.id,
                        file_name=original,
                        file_path=str(path),
                        image_type=suffix.lstrip("."),
                        mime_type=item["mime_type"],
                        file_size=item["file_size"],
                        sha256=item["sha256"],
                        width=item["width"],
                        height=item["height"],
                        processing_status="Uploaded",
                    )
                )
        db.commit()
        db.refresh(session)
        # The ingestion boundary belongs to the Upload API: validate quality,
        # extract/OCR, clean, chunk, embed and persist Chroma records now. The
        # Analysis API calls the same idempotent function as a recovery check,
        # but already-indexed files are not embedded a second time.
        ingestion = ingest_session(db, session)
        accepted_count = ingestion["reports"] + ingestion["images"]
        session.status = "Indexed" if accepted_count else "Rejected"
        if not accepted_count:
            session.failure_reason = "; ".join(
                f"{item['file_name']}: {item['reason']}"
                for item in ingestion["rejected"]
            )[:2000] or "No uploaded file passed validation"
        db.commit()
        message = (
            "Upload processed successfully"
            if accepted_count
            else "The uploaded files were retained but need attention"
        )
        if ignored_files:
            message += (
                f" Only the first {MAX_FILES} files were uploaded; "
                f"{len(ignored_files)} additional file(s) were not added."
            )
        return {
            "session_id": session.id,
            "uploaded_files": [item["original"] for item in prepared],
            "ignored_files": [Path(upload.filename or "").name for upload in ignored_files],
            "message": message,
            "ingestion": ingestion,
        }
    except Exception:
        db.rollback()
        for path in written:
            path.unlink(missing_ok=True)
        raise


@router.get("/history/{email}")
def upload_history(
    email: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if email.strip() != current_user.email:
        raise HTTPException(403, "Cannot view another user's upload history")
    user = current_user
    sessions = (
        _session_query(db)
        .filter(UploadSession.user_id == user.id)
        .filter(UploadSession.archived_at.is_(None))
        .order_by(UploadSession.created_at.desc())
        .all()
    )
    return [_serialize(session) for session in sessions]


@router.get("/archive")
def archived_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sessions = (
        _session_query(db)
        .filter(UploadSession.user_id == current_user.id, UploadSession.archived_at.is_not(None))
        .order_by(UploadSession.archived_at.desc())
        .all()
    )
    return [_serialize(session) for session in sessions]


@router.get("/rejected")
def rejected_uploads(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sessions = _session_query(db).filter(UploadSession.user_id == current_user.id).all()
    rejected = []
    for session in sessions:
        rejected.extend(
            _rejected_file_payload(item, session, "report")
            for item in session.reports if item.processing_status == "Rejected"
        )
        rejected.extend(
            _rejected_file_payload(item, session, "image")
            for item in session.medical_images if item.processing_status == "Rejected"
        )
    return sorted(rejected, key=lambda item: item["uploaded_at"], reverse=True)


@router.get("/rejected/{file_type}/{file_id}/download")
def download_rejected_upload(
    file_type: str,
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    model = Report if file_type == "report" else MedicalImage if file_type == "image" else None
    if model is None:
        raise HTTPException(422, "File type must be report or image")
    item = db.query(model).join(UploadSession).filter(
        model.id == file_id,
        model.processing_status == "Rejected",
        UploadSession.user_id == current_user.id,
    ).first()
    if not item:
        raise HTTPException(404, "Rejected file not found")
    path = Path(item.file_path)
    if not path.is_file():
        raise HTTPException(410, "The stored file is no longer available")
    return FileResponse(path, media_type=item.mime_type or "application/octet-stream", filename=item.file_name)


@router.post("/session/{session_id}/recheck-rejected")
def recheck_rejected_uploads(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _session_query(db).filter(
        UploadSession.id == session_id,
        UploadSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(404, "Analysis not found")
    rejected = [
        item for item in [*session.reports, *session.medical_images]
        if item.processing_status == "Rejected"
    ]
    if not rejected:
        raise HTTPException(409, "This analysis has no rejected files to recheck")
    missing = [item.file_name for item in rejected if not Path(item.file_path).is_file()]
    if missing:
        raise HTTPException(410, f"Stored file is unavailable: {', '.join(missing)}")
    for item in rejected:
        item.processing_status = "Uploaded"
    session.status = "Uploaded"
    session.failure_reason = None
    db.commit()
    return {
        "message": "Rejected files are ready for validation again",
        "session_id": session.id,
        "files": [item.file_name for item in rejected],
    }


@router.patch("/session/{session_id}/archive")
def archive_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(UploadSession).filter(UploadSession.id == session_id, UploadSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(404, "Upload session not found")
    session.archived_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Analysis archived", "session_id": session_id}


@router.patch("/session/{session_id}/restore")
def restore_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(UploadSession).filter(UploadSession.id == session_id, UploadSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(404, "Upload session not found")
    session.archived_at = None
    db.commit()
    return {"message": "Analysis restored", "session_id": session_id}


@router.patch("/session/{session_id}/name")
def rename_session(
    session_id: int,
    request: RenameSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(UploadSession).filter(
        UploadSession.id == session_id,
        UploadSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(404, "Analysis not found")
    clean_name = " ".join(request.name.split())
    if not clean_name:
        raise HTTPException(422, "Please enter a name for this analysis")
    if len(clean_name) > 80:
        raise HTTPException(422, "Analysis names can contain up to 80 characters")
    session.custom_title = clean_name
    db.commit()
    return {"message": "Analysis renamed", "session_id": session_id, "name": clean_name}


@router.get("/session/{session_id}")
def upload_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = (
        _session_query(db)
        .filter(UploadSession.id == session_id, UploadSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(404, "Upload session not found")
    return _serialize(session, detailed=True)


@router.delete("/session/{session_id}")
def delete_upload_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = (
        _session_query(db)
        .filter(UploadSession.id == session_id, UploadSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(404, "Upload session not found")
    paths = [Path(item.file_path) for item in [*session.reports, *session.medical_images]]
    vector_cleanup = delete_private_session_vectors(
        user_id=current_user.id, session_id=session_id
    )
    conversation_cache.delete(user_id=current_user.id, session_id=session_id)
    chat_history_store.delete_session(user_id=current_user.id, session_id=session_id)
    db.delete(session)
    db.commit()
    for path in paths:
        path.unlink(missing_ok=True)
    folder = UPLOAD_FOLDER / str(session_id)
    if folder.is_dir() and folder.parent == UPLOAD_FOLDER:
        shutil.rmtree(folder)
    return {
        "message": "Analysis, complete chat history, files, and private vectors deleted permanently",
        "session_id": session_id,
        "vectors_deleted": vector_cleanup,
    }
