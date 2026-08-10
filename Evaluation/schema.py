"""Load and validate evaluation cases and graded relevance judgments."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from Evaluation.config import PROJECT_ROOT


QUERY_TYPES = {"text", "text_to_image", "image", "hybrid"}
ITEM_TYPES = {"text", "image"}


def split_values(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in (value or "").split("|") if part.strip())


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    query_type: str
    query_text: str
    image_path: Path | None
    expected_cancer_types: tuple[str, ...]
    expected_sources: tuple[str, ...]
    notes: str


@dataclass(frozen=True)
class Qrel:
    case_id: str
    item_type: str
    item_id: str
    relevance: int
    reviewer: str
    notes: str

    @property
    def canonical_id(self) -> str:
        return f"{self.item_type}:{self.item_id}"


def _resolve_image_path(value: str) -> Path | None:
    if not value.strip():
        return None
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_cases(path: Path) -> list[EvaluationCase]:
    if not path.is_file():
        raise FileNotFoundError(f"Evaluation cases not found: {path}")
    cases = []
    seen = set()
    with path.open(newline="", encoding="utf-8") as handle:
        for line, row in enumerate(csv.DictReader(handle), start=2):
            if (row.get("enabled") or "true").strip().lower() not in {"true", "1", "yes"}:
                continue
            case_id = (row.get("case_id") or "").strip()
            query_type = (row.get("query_type") or "").strip()
            query_text = (row.get("query_text") or "").strip()
            image_path = _resolve_image_path(row.get("image_path") or "")
            if not case_id or case_id in seen:
                raise ValueError(f"Missing or duplicate case_id in {path.name} line {line}")
            if query_type not in QUERY_TYPES:
                raise ValueError(f"Invalid query_type {query_type!r} in case {case_id}")
            if query_type in {"text", "text_to_image", "hybrid"} and not query_text:
                raise ValueError(f"Case {case_id} requires query_text")
            if query_type in {"image", "hybrid"}:
                if image_path is None or not image_path.is_file():
                    raise FileNotFoundError(f"Case {case_id} image does not exist: {image_path}")
            seen.add(case_id)
            cases.append(
                EvaluationCase(
                    case_id=case_id,
                    query_type=query_type,
                    query_text=query_text,
                    image_path=image_path,
                    expected_cancer_types=split_values(row.get("expected_cancer_types") or ""),
                    expected_sources=split_values(row.get("expected_sources") or ""),
                    notes=(row.get("notes") or "").strip(),
                )
            )
    if not cases:
        raise ValueError("No enabled evaluation cases were found")
    return cases


def load_qrels(path: Path, case_ids: set[str]) -> dict[str, dict[str, int]]:
    if not path.is_file():
        raise FileNotFoundError(f"Qrels not found: {path}")
    judgments: dict[str, dict[str, int]] = {case_id: {} for case_id in case_ids}
    with path.open(newline="", encoding="utf-8") as handle:
        for line, row in enumerate(csv.DictReader(handle), start=2):
            case_id = (row.get("case_id") or "").strip()
            item_type = (row.get("item_type") or "").strip()
            item_id = (row.get("item_id") or "").strip()
            if case_id not in case_ids:
                raise ValueError(f"Unknown case_id {case_id!r} in {path.name} line {line}")
            if item_type not in ITEM_TYPES or not item_id:
                raise ValueError(f"Invalid qrel item in {path.name} line {line}")
            try:
                relevance = int(row.get("relevance") or "")
            except ValueError as error:
                raise ValueError(f"Invalid relevance in {path.name} line {line}") from error
            if relevance not in {0, 1, 2, 3}:
                raise ValueError("Relevance must be 0, 1, 2, or 3")
            canonical = f"{item_type}:{item_id}"
            if canonical in judgments[case_id]:
                raise ValueError(f"Duplicate qrel {case_id}/{canonical}")
            judgments[case_id][canonical] = relevance
    missing = [case_id for case_id, qrels in judgments.items() if not any(v > 0 for v in qrels.values())]
    if missing:
        raise ValueError(f"Enabled cases require at least one positive qrel: {missing}")
    return judgments
