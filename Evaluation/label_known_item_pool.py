"""Label top-K candidates under the deterministic known-item benchmark rule.

This does not create clinical relevance judgments. The seeded source item is
relevant; other retrieved items are non-relevant for exact-item recovery.
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

from Evaluation.config import OUTPUT_DIR, QRELS_FILE


def label_pool(pool_file: Path, qrels_file: Path, top_k: int = 5) -> int:
    with qrels_file.open(newline="", encoding="utf-8") as handle:
        known = {
            (row["case_id"], row["item_type"], row["item_id"]): int(row["relevance"])
            for row in csv.DictReader(handle)
            if int(row["relevance"]) > 0
        }
    with pool_file.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        rows = list(reader)

    labelled = 0
    for row in rows:
        if int(row["rank"]) > top_k:
            continue
        key = (row["case_id"], row["item_type"], row["item_id"])
        row["reviewed_relevance"] = str(known.get(key, 0))
        row["reviewer"] = "automated_known_item_rule"
        row["notes"] = (
            "Exact seeded source item"
            if key in known
            else "Not the seeded source item; not a clinical irrelevance judgment"
        )
        labelled += 1

    temporary = pool_file.with_suffix(pool_file.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, pool_file)
    print(f"Known-item labels written: {labelled}")
    print("WARNING: These are retrieval-integrity labels, not clinical relevance judgments.")
    return labelled


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", type=Path, default=OUTPUT_DIR / "annotation_pool.csv")
    parser.add_argument("--qrels", type=Path, default=QRELS_FILE)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    if args.top_k < 1:
        raise ValueError("top-k must be positive")
    label_pool(args.pool, args.qrels, args.top_k)


if __name__ == "__main__":
    main()
