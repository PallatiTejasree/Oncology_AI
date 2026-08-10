"""Validated upload storage and upload-session lifecycle endpoints."""

from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from app.db.database import get_db
from app.models.medical_image import MedicalImage
from app.models.report import Report
from app.models.upload_session import UploadSession
from app.models.user import User
from app.middleware.auth_middleware import get_current_user


router = APIRouter(prefix="/upload", tags=["Upload"])
PROJECT_ROOT = Path(__file__).resolve().parents[4]
UPLOAD_FOLDER = PROJECT_ROOT / "backend" / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

ALLOWED_REPORTS = {".pdf"}
ALLOWED_IMAGES = {".png", ".jpg", ".jpeg"}
ALLOWED_EXTENSIONS = ALLOWED_REPORTS | ALLOWED_IMAGES
MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_FILES = 5


def _session_query(db: Session):
    return db.query(UploadSession).options(
        joinedload(UploadSession.reports),
        joinedload(UploadSession.medical_images),
        joinedload(UploadSession.summaries),
    )


def _summary_payload(summary: object | None):
    if not summary:
        return None
    try:
        result = json.loads(summary.ai_summary) if summary.ai_summary else None
    except json.JSONDecodeError:
        result = {"summary": summary.ai_summary}
    return {
        "id": summary.id,
        "model_name": summary.model_name,
        "processing_status": summary.processing_status,
        "created_at": summary.created_at,
        "query_type": summary.query_type,
        "retrieval_status": summary.retrieval_status,
        "calibrated": summary.calibrated,
        "processing_time_ms": summary.processing_time_ms,
        "result": result,
    }


def _display_title(session: UploadSession) -> str:
    files = [item.file_name for item in session.reports] + [item.file_name for item in session.medical_images]
    stem = " ".join(Path(files[0]).stem.replace("_", " ").replace("-", " ").split()).title() if files else ""
    if session.input_type == "image":
        return f"Pathology image review — {stem or 'Uploaded image'}"
    if session.input_type == "report":
        return f"Clinical report review — {stem or 'Uploaded report'}"
    if session.input_type == "both":
        return f"Multimodal case review — {stem or 'Uploaded case'}"
    if session.session_name and not session.session_name.startswith("Analysis-") and session.session_name != session.original_query:
        return session.session_name
    query = " ".join((session.original_query or "").split())
    return f"Clinical question — {' '.join(query.split()[:7]) or 'Oncology review'}"


def _serialize(session: UploadSession, detailed: bool = False) -> dict:
    latest = max(session.summaries, key=lambda item: item.created_at) if session.summaries else None
    payload = {
        "session_id": session.id,
        "session_name": session.session_name,
        "display_title": _display_title(session),
        "status": session.status,
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
        payload["reports"] = [
            {
                "id": item.id,
                "file_name": item.file_name,
                "mime_type": item.mime_type,
                "file_size": item.file_size,
                "sha256": item.sha256,
                "processing_status": item.processing_status,
                "rejection_reason": item.rejection_reason,
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
            }
            for item in session.medical_images
        ]
        payload["latest_summary"] = _summary_payload(latest)
    return payload


@router.post("")
@router.post("/", include_in_schema=False)
async def upload_files(
    email: str = Form(...),
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if email.strip() != current_user.email:
        raise HTTPException(403, "Cannot upload files for another user")
    user = current_user
    if not files or len(files) > MAX_FILES:
        raise HTTPException(422, f"Upload between 1 and {MAX_FILES} files")

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
        return {
            "session_id": session.id,
            "uploaded_files": [item["original"] for item in prepared],
            "message": "Upload successful",
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
    db.delete(session)
    db.commit()
    for path in paths:
        path.unlink(missing_ok=True)
    folder = UPLOAD_FOLDER / str(session_id)
    try:
        folder.rmdir()
    except OSError:
        pass
    return {"message": "Upload session deleted", "session_id": session_id}
