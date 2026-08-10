"""Build 50 deterministic known-item evaluation cases from project artifacts."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from Evaluation.config import CASES_FILE, PROJECT_ROOT, QRELS_FILE


TEXT_CHUNKS = PROJECT_ROOT / "Ingestion" / "datasets" / "processed" / "chunk_metadata.csv"
IMAGE_METADATA = (
    PROJECT_ROOT / "Ingestion" / "datasets" / "embeddings" / "image_embedding_metadata.csv"
)

CASE_FIELDS = [
    "case_id",
    "query_type",
    "query_text",
    "image_path",
    "expected_cancer_types",
    "expected_sources",
    "notes",
    "enabled",
]
QREL_FIELDS = ["case_id", "item_type", "item_id", "relevance", "reviewer", "notes"]


def concise_query(text: str, maximum_words: int = 28) -> str:
    """Create a deterministic known-item query without changing medical terms."""
    text = re.sub(r"\s+", " ", text).strip()
    words = text.split()
    return " ".join(words[:maximum_words]).strip(" ,;:")


def cancer_key(value: str) -> str:
    return (value or "unknown").split("|")[0].strip() or "unknown"


def stratified_rows(rows: list[dict[str, str]], count: int) -> list[dict[str, str]]:
    """Prefer distinct cancer labels, then deterministically fill remaining slots."""
    selected = []
    selected_ids = set()
    seen_cancers = set()
    for row in rows:
        cancer = cancer_key(row.get("cancer_type", ""))
        identifier = row.get("chunk_id") or row.get("image_id")
        if cancer == "unknown" or cancer in seen_cancers:
            continue
        selected.append(row)
        selected_ids.add(identifier)
        seen_cancers.add(cancer)
        if len(selected) == count:
            return selected
    for row in rows:
        identifier = row.get("chunk_id") or row.get("image_id")
        if identifier in selected_ids:
            continue
        selected.append(row)
        selected_ids.add(identifier)
        if len(selected) == count:
            return selected
    raise ValueError(f"Only {len(selected)} usable rows found; {count} required")


def load_text_candidates() -> list[dict[str, str]]:
    with TEXT_CHUNKS.open(newline="", encoding="utf-8") as handle:
        return [
            row
            for row in csv.DictReader(handle)
            if len((row.get("text") or "").split()) >= 20
            and row.get("source_dataset") in {"tcga_reports", "pmc_articles"}
        ]


def load_image_candidates() -> list[dict[str, str]]:
    with IMAGE_METADATA.open(newline="", encoding="utf-8") as handle:
        return [
            row
            for row in csv.DictReader(handle)
            if row.get("source_dataset") == "pmc_medical_images"
            and len((row.get("caption") or "").split()) >= 8
            and Path(row.get("image_path") or "").is_file()
        ]


def build_cases() -> tuple[list[dict], list[dict]]:
    text_rows = stratified_rows(load_text_candidates(), 20)
    image_rows = stratified_rows(load_image_candidates(), 30)
    cases: list[dict] = []
    qrels: list[dict] = []

    for index, row in enumerate(text_rows, start=1):
        case_id = f"TXT{index:03d}"
        cases.append(
            {
                "case_id": case_id,
                "query_type": "text",
                "query_text": concise_query(row["text"]),
                "image_path": "",
                "expected_cancer_types": row["cancer_type"],
                "expected_sources": row["source_dataset"],
                "notes": "Known-item seed from a real text chunk; requires human benchmark expansion",
                "enabled": "true",
            }
        )
        qrels.append(
            {
                "case_id": case_id,
                "item_type": "text",
                "item_id": row["chunk_id"],
                "relevance": 3,
                "reviewer": "project_seed",
                "notes": "Source item used to construct this known-item smoke query",
            }
        )

    # 15 caption-to-image, 10 image self-retrieval, and 5 report+image cases.
    groups = (("CTI", "text_to_image", image_rows[:15]), ("IMG", "image", image_rows[15:25]), ("HYB", "hybrid", image_rows[25:30]))
    for prefix, query_type, rows in groups:
        for index, row in enumerate(rows, start=1):
            case_id = f"{prefix}{index:03d}"
            image_path = Path(row["image_path"])
            cases.append(
                {
                    "case_id": case_id,
                    "query_type": query_type,
                    "query_text": concise_query(row["caption"]) if query_type != "image" else "",
                    "image_path": (
                        str(image_path.relative_to(PROJECT_ROOT))
                        if image_path.is_relative_to(PROJECT_ROOT)
                        else str(image_path)
                    ),
                    "expected_cancer_types": row["cancer_type"],
                    "expected_sources": row["source_dataset"],
                    "notes": "Known-item seed from an accepted PMC image; requires human benchmark expansion",
                    "enabled": "true",
                }
            )
            qrels.append(
                {
                    "case_id": case_id,
                    "item_type": "image",
                    "item_id": row["image_id"],
                    "relevance": 3,
                    "reviewer": "project_seed",
                    "notes": "Source image used to construct this known-item smoke query",
                }
            )
    if len(cases) != 50 or len(qrels) != 50:
        raise AssertionError("Seed builder must produce exactly 50 cases and 50 qrels")
    return cases, qrels


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    cases, qrels = build_cases()
    write_csv(CASES_FILE, CASE_FIELDS, cases)
    write_csv(QRELS_FILE, QREL_FIELDS, qrels)
    print(f"Wrote {len(cases)} cases to {CASES_FILE}")
    print(f"Wrote {len(qrels)} qrels to {QRELS_FILE}")


if __name__ == "__main__":
    main()
