"""Conservative preprocessing shared by all text-query retrieval paths.

This module cleans formatting noise without lowercasing, stemming, removing
punctuation, or deleting stop words. Those aggressive operations can change
clinical meaning (especially negation, measurements, biomarkers, and units).
"""

from __future__ import annotations

import re
import unicodedata


MAX_QUERY_CHARACTERS = 12_000

_INVISIBLE = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff\u00ad]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HORIZONTAL_SPACE = re.compile(r"[^\S\r\n]+")
_NEWLINES = re.compile(r"\s*\n+\s*")
_WORD_LINE_BREAK = re.compile(r"(?<=[A-Za-z])-[ \t]*\n[ \t]*(?=[A-Za-z])")


def preprocess_query_text(value: str, *, max_characters: int = MAX_QUERY_CHARACTERS) -> str:
    """Return model-ready query text while preserving clinical semantics.

    Queries remain a single query and are not chunked. Very large pasted input
    is bounded before tokenization; normal uploaded documents should be queried
    through their already-chunked Chroma records.
    """
    if not isinstance(value, str):
        raise ValueError("query must be text")
    if max_characters < 256:
        raise ValueError("max_characters must be at least 256")

    clean = unicodedata.normalize("NFC", value)
    clean = clean.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    clean = _INVISIBLE.sub("", clean)
    clean = _CONTROL.sub(" ", clean)
    # Repair a common OCR/PDF copy artifact: "metasta-\ntic". A hyphen that
    # stays on one line (for example "HER2-positive") is preserved.
    clean = _WORD_LINE_BREAK.sub("", clean)
    clean = _HORIZONTAL_SPACE.sub(" ", clean)
    clean = _NEWLINES.sub(" ", clean)
    clean = clean.strip()
    if not clean:
        raise ValueError("query cannot be empty")

    if len(clean) > max_characters:
        clean = clean[:max_characters].rstrip()
        boundary = clean.rfind(" ")
        if boundary >= int(max_characters * 0.9):
            clean = clean[:boundary]
    return clean
