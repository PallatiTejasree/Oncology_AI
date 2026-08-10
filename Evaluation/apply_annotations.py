"""Merge completed annotation-pool judgments into qrels.csv safely."""

from __future__ import annotations

import argparse
import csv
import os
import shutil
from datetime import datetime
from pathlib import Path

from Evaluation.config import OUTPUT_DIR, QRELS_FILE


QREL_FIELDS = ["case_id", "item_type", "item_id", "relevance", "reviewer", "notes"]


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def apply_annotations(pool_file: Path, qrels_file: Path) -> tuple[int, int]:
    pool = read_rows(pool_file)
    existing = read_rows(qrels_file)
    merged = {
        (row["case_id"], row["item_type"], row["item_id"]): {
            field: row.get(field, "") for field in QREL_FIELDS
        }
        for row in existing
    }

    reviewed = 0
    for line, row in enumerate(pool, start=2):
        value = (row.get("reviewed_relevance") or "").strip()
        if not value:
            continue
        try:
            relevance = int(value)
        except ValueError as error:
            raise ValueError(f"Invalid reviewed_relevance {value!r} on line {line}") from error
        if relevance not in {0, 1, 2, 3}:
            raise ValueError(f"reviewed_relevance must be 0-3 on line {line}")
        reviewer = (row.get("reviewer") or "").strip()
        if not reviewer:
            raise ValueError(f"Reviewer is required for reviewed row on line {line}")
        key = (
            (row.get("case_id") or "").strip(),
            (row.get("item_type") or "").strip(),
            (row.get("item_id") or "").strip(),
        )
        if not all(key):
            raise ValueError(f"Missing case/item identity on line {line}")
        merged[key] = {
            "case_id": key[0],
            "item_type": key[1],
            "item_id": key[2],
            "relevance": relevance,
            "reviewer": reviewer,
            "notes": (row.get("notes") or "Human-reviewed annotation").strip(),
        }
        reviewed += 1

    if reviewed == 0:
        raise ValueError(
            "No completed annotations found. Fill reviewed_relevance and reviewer "
            "in annotation_pool.csv, save it, then rerun this command."
        )

    backup = qrels_file.with_suffix(qrels_file.suffix + ".backup")
    if backup.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = qrels_file.with_suffix(qrels_file.suffix + f".{stamp}.backup")
    shutil.copy2(qrels_file, backup)
    temporary = qrels_file.with_suffix(qrels_file.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=QREL_FIELDS)
        writer.writeheader()
        writer.writerows(merged.values())
    os.replace(temporary, qrels_file)
    print(f"Backup: {backup}")
    print(f"Imported reviewed rows: {reviewed}")
    print(f"Total qrels: {len(merged)}")
    return reviewed, len(merged)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", type=Path, default=OUTPUT_DIR / "annotation_pool.csv")
    parser.add_argument("--qrels", type=Path, default=QRELS_FILE)
    args = parser.parse_args()
    apply_annotations(args.pool, args.qrels)


if __name__ == "__main__":
    main()
