"""Thirty-minute in-memory cache backed by persisted conversation JSON."""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.services.chat_history_store import chat_history_store


logger = logging.getLogger(__name__)
ACTIVE_CACHE_TTL_SECONDS = max(
    60, int(os.getenv("CHAT_CACHE_TTL_SECONDS", os.getenv("CONVERSATION_CACHE_TTL_SECONDS", "1800")))
)


@dataclass
class _Entry:
    expires_at: float
    turns: list[dict[str, str]]


class ConversationCache:
    """Keep hydrated session state warm without owning durable history."""

    def __init__(self, history_store=None) -> None:
        self.history_store = history_store or chat_history_store
        self._entries: dict[tuple[int, int], _Entry] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _key(user_id: int, session_id: int) -> tuple[int, int]:
        return user_id, session_id

    def get(self, db: Session | None, *, user_id: int, session_id: int) -> list[dict[str, str]]:
        del db  # Ownership is checked by the route and persisted store.
        key = self._key(user_id, session_id)
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry and entry.expires_at > now:
                logger.debug("conversation cache HIT user=%s session=%s", user_id, session_id)
                entry.expires_at = now + ACTIVE_CACHE_TTL_SECONDS
                return [turn.copy() for turn in entry.turns]
            if entry:
                logger.info("runtime session expired; persisted JSON retained user=%s session=%s", user_id, session_id)
                self._entries.pop(key, None)

        logger.info("conversation cache MISS; loading persisted session user=%s session=%s", user_id, session_id)
        rows = self.history_store.list(user_id=user_id, session_id=session_id)
        turns = [{"user": row["question"], "assistant": row["answer"]} for row in rows]
        with self._lock:
            self._entries[key] = _Entry(now + ACTIVE_CACHE_TTL_SECONDS, turns)
        logger.info("conversation rehydrated user=%s session=%s turns=%s", user_id, session_id, len(turns))
        return [turn.copy() for turn in turns]

    def append(self, *, user_id: int, session_id: int, question: str, answer: str) -> None:
        key = self._key(user_id, session_id)
        now = time.monotonic()
        turn = {"user": question, "assistant": answer}
        with self._lock:
            entry = self._entries.get(key)
            turns = list(entry.turns) if entry and entry.expires_at > now else []
            if not turns or turns[-1] != turn:
                turns.append(turn)
            self._entries[key] = _Entry(now + ACTIVE_CACHE_TTL_SECONDS, turns)

    def clear(self, *, user_id: int, session_id: int) -> None:
        with self._lock:
            self._entries[self._key(user_id, session_id)] = _Entry(
                time.monotonic() + ACTIVE_CACHE_TTL_SECONDS, []
            )

    def delete(self, *, user_id: int, session_id: int) -> None:
        with self._lock:
            self._entries.pop(self._key(user_id, session_id), None)


conversation_cache = ConversationCache()
