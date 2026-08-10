"""Small process-local TTL cache for recent conversation turns.

PostgreSQL is the source of truth. The cache only avoids repeatedly loading the
same recent turns and is safe to lose on restart.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.chat_history import ChatHistory


CACHE_TTL_SECONDS = max(60, int(os.getenv("CONVERSATION_CACHE_TTL_SECONDS", "1800")))
CACHE_MAX_TURNS = max(1, min(20, int(os.getenv("CONVERSATION_CACHE_MAX_TURNS", "6"))))


@dataclass
class _Entry:
    expires_at: float
    turns: list[dict[str, str]]


class ConversationCache:
    def __init__(self) -> None:
        self._entries: dict[tuple[int, int], _Entry] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _key(user_id: int, session_id: int) -> tuple[int, int]:
        return user_id, session_id

    def get(self, db: Session, *, user_id: int, session_id: int) -> list[dict[str, str]]:
        key = self._key(user_id, session_id)
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry and entry.expires_at > now:
                return [turn.copy() for turn in entry.turns]
            self._entries.pop(key, None)

        rows = (
            db.query(ChatHistory)
            .filter(
                ChatHistory.user_id == user_id,
                ChatHistory.session_id == session_id,
            )
            .order_by(ChatHistory.created_at.desc(), ChatHistory.id.desc())
            .limit(CACHE_MAX_TURNS)
            .all()
        )
        turns = [
            {"user": row.question, "assistant": row.answer}
            for row in reversed(rows)
        ]
        with self._lock:
            self._entries[key] = _Entry(now + CACHE_TTL_SECONDS, turns)
        return [turn.copy() for turn in turns]

    def append(
        self,
        *,
        user_id: int,
        session_id: int,
        question: str,
        answer: str,
    ) -> None:
        key = self._key(user_id, session_id)
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            turns = list(entry.turns) if entry and entry.expires_at > now else []
            turns.append({"user": question, "assistant": answer})
            self._entries[key] = _Entry(
                now + CACHE_TTL_SECONDS,
                turns[-CACHE_MAX_TURNS:],
            )

    def clear(self, *, user_id: int, session_id: int) -> None:
        with self._lock:
            # Keep an empty live entry so the immediately following request does
            # not repopulate the context from PostgreSQL. Permanent history is
            # deliberately retained and may be available again after TTL expiry.
            self._entries[self._key(user_id, session_id)] = _Entry(
                time.monotonic() + CACHE_TTL_SECONDS,
                [],
            )


conversation_cache = ConversationCache()
