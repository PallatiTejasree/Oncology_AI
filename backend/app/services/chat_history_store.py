"""User-isolated, rehydratable JSON conversation persistence."""

from __future__ import annotations

import fcntl
import json
import os
import re
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError


BACKEND_ROOT = Path(__file__).resolve().parents[2]
CHAT_CACHE_DIR = Path(os.getenv("CHAT_CACHE_DIR", BACKEND_ROOT / "storage" / "chat_cache"))
LEGACY_CHAT_HISTORY_FILE = BACKEND_ROOT / "data" / "chat_history.json"
_SAFE_ID = re.compile(r"^[1-9]\d*$")


class ConversationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: str
    role: Literal["user", "assistant"]
    content: str
    timestamp: str
    citations: list[str] = Field(default_factory=list)
    intent: str | None = None
    reliability: dict[str, Any] | None = None
    response_payload: dict[str, Any] | None = None


class CaseContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    uploaded_file_references: list[str] = Field(default_factory=list)
    patient_summary: str = ""
    documented_facts: list[dict[str, Any]] = Field(default_factory=list)
    important_findings: list[dict[str, Any]] = Field(default_factory=list)
    procedures: list[str] = Field(default_factory=list)
    treatments: list[str] = Field(default_factory=list)
    pathology: list[str] = Field(default_factory=list)
    biomarkers: list[str] = Field(default_factory=list)


class AnalysisState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    last_intent: str | None = None
    last_evidence_ids: list[str] = Field(default_factory=list)
    last_reliability: dict[str, Any] | None = None


class PersistedConversation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    session_id: int
    user_id: int
    created_at: str
    updated_at: str
    last_accessed_at: str
    conversation: list[ConversationMessage] = Field(default_factory=list)
    case_context: CaseContext = Field(default_factory=CaseContext)
    analysis_state: AnalysisState = Field(default_factory=AnalysisState)


class ChatHistoryStore:
    """Persist one validated conversation file per authenticated user/session."""

    def __init__(self, root: Path = CHAT_CACHE_DIR, legacy_path: Path = LEGACY_CHAT_HISTORY_FILE) -> None:
        self.root = Path(root)
        self.legacy_path = Path(legacy_path)
        self._locks: dict[tuple[int, int], threading.RLock] = {}
        self._locks_guard = threading.Lock()

    @staticmethod
    def _validated_id(value: int, label: str) -> int:
        text = str(value)
        if isinstance(value, bool) or not _SAFE_ID.fullmatch(text):
            raise ValueError(f"Invalid {label}")
        return int(text)

    def _path(self, user_id: int, session_id: int) -> Path:
        user = self._validated_id(user_id, "user_id")
        session = self._validated_id(session_id, "session_id")
        return self.root / str(user) / f"{session}.json"

    def _thread_lock(self, user_id: int, session_id: int) -> threading.RLock:
        key = (user_id, session_id)
        with self._locks_guard:
            return self._locks.setdefault(key, threading.RLock())

    @contextmanager
    def _session_lock(self, user_id: int, session_id: int):
        path = self._path(user_id, session_id)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock_path = path.with_suffix(".lock")
        with self._thread_lock(user_id, session_id):
            with lock_path.open("a+", encoding="utf-8") as lock_file:
                os.chmod(lock_path, 0o600)
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield path
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _read(self, path: Path, *, user_id: int, session_id: int) -> PersistedConversation | None:
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            document = PersistedConversation.model_validate(value)
        except (OSError, json.JSONDecodeError, ValidationError) as error:
            raise RuntimeError(f"Conversation JSON is malformed or unsupported: {path.name}") from error
        if document.user_id != user_id or document.session_id != session_id:
            raise PermissionError("Conversation ownership mismatch")
        return document

    @staticmethod
    def _write(path: Path, document: PersistedConversation) -> None:
        temporary_name = None
        try:
            with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temporary:
                temporary_name = temporary.name
                json.dump(document.model_dump(mode="json"), temporary, ensure_ascii=False, indent=2)
                temporary.write("\n")
                temporary.flush()
                os.fsync(temporary.fileno())
            os.chmod(temporary_name, 0o600)
            os.replace(temporary_name, path)
            os.chmod(path, 0o600)
        finally:
            if temporary_name:
                Path(temporary_name).unlink(missing_ok=True)

    def _new(self, user_id: int, session_id: int) -> PersistedConversation:
        now = self._now()
        return PersistedConversation(
            session_id=session_id, user_id=user_id,
            created_at=now, updated_at=now, last_accessed_at=now,
        )

    def _legacy_rows(self, user_id: int, session_id: int) -> list[dict]:
        if not self.legacy_path.exists():
            return []
        try:
            value = json.loads(self.legacy_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return [
            row for row in value if isinstance(row, dict)
            and row.get("user_id") == user_id and row.get("session_id") == session_id
        ] if isinstance(value, list) else []

    @staticmethod
    def _case_context(result: dict[str, Any] | None) -> CaseContext:
        result = result or {}
        structured = result.get("structured_answer") or {}
        sources = result.get("uploaded_sources") or []
        return CaseContext(
            uploaded_file_references=[str(item.get("file_name")) for item in sources if item.get("file_name")],
            patient_summary=str(structured.get("plain_language_summary") or result.get("summary") or ""),
            documented_facts=list(structured.get("documented_facts") or []),
            important_findings=list(structured.get("key_findings") or structured.get("findings") or []),
            procedures=list(structured.get("procedures") or []),
            treatments=list(structured.get("treatments") or []),
            pathology=list(structured.get("pathology") or []),
            biomarkers=list(structured.get("biomarkers") or []),
        )

    @staticmethod
    def _analysis_state(result: dict[str, Any] | None) -> AnalysisState:
        result = result or {}
        evidence = [*(result.get("evidence") or []), *(result.get("supporting_image_evidence") or [])]
        return AnalysisState(
            last_intent=result.get("intent") or result.get("query_type"),
            last_evidence_ids=[str(item.get("id")) for item in evidence if item.get("id")],
            last_reliability=result.get("reliability"),
        )

    @staticmethod
    def _merge_case_context(current: CaseContext, incoming: CaseContext) -> CaseContext:
        def unique(values):
            seen = set()
            merged = []
            for value in values:
                marker = json.dumps(value, sort_keys=True, ensure_ascii=False)
                if marker not in seen:
                    seen.add(marker)
                    merged.append(value)
            return merged

        return CaseContext(
            uploaded_file_references=unique([*current.uploaded_file_references, *incoming.uploaded_file_references]),
            patient_summary=incoming.patient_summary or current.patient_summary,
            documented_facts=unique([*current.documented_facts, *incoming.documented_facts]),
            important_findings=unique([*current.important_findings, *incoming.important_findings]),
            procedures=unique([*current.procedures, *incoming.procedures]),
            treatments=unique([*current.treatments, *incoming.treatments]),
            pathology=unique([*current.pathology, *incoming.pathology]),
            biomarkers=unique([*current.biomarkers, *incoming.biomarkers]),
        )

    def append(self, *, user_id: int, session_id: int, question: str, answer: str, result: dict | None = None) -> dict:
        user_id = self._validated_id(user_id, "user_id")
        session_id = self._validated_id(session_id, "session_id")
        with self._session_lock(user_id, session_id) as path:
            document = self._read(path, user_id=user_id, session_id=session_id) or self._new(user_id, session_id)
            now = self._now()
            document.conversation.extend([
                ConversationMessage(message_id=str(uuid4()), role="user", content=question, timestamp=now),
                ConversationMessage(
                    message_id=str(uuid4()), role="assistant", content=answer, timestamp=now,
                    citations=list((result or {}).get("citation_validation", {}).get("used") or []),
                    intent=(result or {}).get("intent") or (result or {}).get("query_type"),
                    reliability=(result or {}).get("reliability"), response_payload=result,
                ),
            ])
            document.updated_at = now
            document.last_accessed_at = now
            document.case_context = self._merge_case_context(
                document.case_context, self._case_context(result)
            )
            document.analysis_state = self._analysis_state(result)
            self._write(path, document)
            return {"id": len(document.conversation) // 2, "user_id": user_id, "session_id": session_id, "question": question, "answer": answer, "result": result, "created_at": now}

    def _migrate_legacy(self, user_id: int, session_id: int) -> None:
        if self._path(user_id, session_id).exists():
            return
        for row in self._legacy_rows(user_id, session_id):
            self.append(
                user_id=user_id, session_id=session_id,
                question=str(row.get("question") or ""), answer=str(row.get("answer") or ""),
                result=row.get("result") if isinstance(row.get("result"), dict) else None,
            )

    def list(self, *, user_id: int, session_id: int, limit: int | None = None) -> list[dict]:
        user_id = self._validated_id(user_id, "user_id")
        session_id = self._validated_id(session_id, "session_id")
        self._migrate_legacy(user_id, session_id)
        with self._session_lock(user_id, session_id) as path:
            document = self._read(path, user_id=user_id, session_id=session_id)
            if document is None:
                return []
            document.last_accessed_at = self._now()
            self._write(path, document)
            rows = []
            pending_user = None
            for message in document.conversation:
                if message.role == "user":
                    pending_user = message
                elif pending_user is not None:
                    rows.append({
                        "id": len(rows) + 1, "user_id": user_id, "session_id": session_id,
                        "question": pending_user.content, "answer": message.content,
                        "result": message.response_payload, "created_at": message.timestamp,
                    })
                    pending_user = None
            return rows[-limit:] if limit is not None else rows

    def delete_session(self, *, user_id: int, session_id: int) -> int:
        user_id = self._validated_id(user_id, "user_id")
        session_id = self._validated_id(session_id, "session_id")
        with self._session_lock(user_id, session_id) as path:
            existed = path.exists()
            path.unlink(missing_ok=True)
            path.with_suffix(".lock").unlink(missing_ok=True)
            return int(existed)


chat_history_store = ChatHistoryStore()
