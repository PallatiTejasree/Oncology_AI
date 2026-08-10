"""Boundary-aware text splitting for medical documents."""

from __future__ import annotations

import re
from typing import List


_SPACE_RE = re.compile(r"\s+")


def _normalise(text: str) -> str:
    return _SPACE_RE.sub(" ", text).strip()


def _end_boundary(text: str, start: int, proposed_end: int) -> int:
    """Return the best natural boundary at or before ``proposed_end``."""
    minimum = start + max(1, (proposed_end - start) // 2)
    window = text[minimum:proposed_end]

    # Prefer a sentence ending, then punctuation, and finally a word boundary.
    for pattern in (r"[.!?](?=\s)", r"[;:](?=\s)", r",(?=\s)", r"\s"):
        matches = list(re.finditer(pattern, window))
        if matches:
            match = matches[-1]
            return minimum + match.end()
    return proposed_end


def _overlap_start(text: str, start: int, end: int, overlap: int) -> int:
    """Choose a complete-word start close to the requested overlap."""
    target = max(start + 1, end - overlap)
    boundary = text.find(" ", target, end)
    return boundary + 1 if boundary != -1 else end


def split_text(text: str, chunk_size: int = 800, overlap: int = 150) -> List[str]:
    """Split text into overlapping chunks without cutting ordinary words.

    Sentence endings are preferred. If a sentence is longer than ``chunk_size``,
    punctuation or whitespace is used instead. The returned chunks contain at
    most ``chunk_size`` characters.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if overlap < 0:
        raise ValueError("overlap cannot be negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")
    if not isinstance(text, str) or not text.strip():
        return []

    text = _normalise(text)
    chunks: List[str] = []
    start = 0

    while start < len(text):
        proposed_end = min(start + chunk_size, len(text))
        end = (
            proposed_end
            if proposed_end == len(text)
            else _end_boundary(text, start, proposed_end)
        )
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break

        next_start = _overlap_start(text, start, end, overlap)
        if next_start <= start:  # Defensive guard against non-progress.
            next_start = end
        start = next_start

    return chunks
