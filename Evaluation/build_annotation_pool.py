"""Retrieve candidate results for human relevance annotation."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from Evaluation.config import CASES_FILE, OUTPUT_DIR, QRELS_FILE
from Evaluation.runner import RetrievalRunner, canonical_result_id
from Evaluation.schema import load_cases, load_qrels


FIELDS = [
    "case_id",
    "query_type",
    "rank",
    "item_type",
    "item_id",
    "current_relevance",
    "reviewed_relevance",
    "reviewer",
    "cancer_type",
    "source_dataset",
    "document_preview",
    "notes",
]


def build_pool(cases_file: Path, qrels_file: Path, output: Path, top_k: int, device: str) -> None:
    cases = load_cases(cases_file)
    qrels = load_qrels(qrels_file, {case.case_id for case in cases})
    runner = RetrievalRunner(device=device)
    rows = []
    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] {case.case_id}")
        for rank, result in enumerate(runner.run(case, top_k), start=1):
            canonical = canonical_result_id(result)
            item_type, item_id = canonical.split(":", 1)
            metadata = result.get("metadata") or {}
            rows.append(
                {
                    "case_id": case.case_id,
                    "query_type": case.query_type,
                    "rank": rank,
                    "item_type": item_type,
                    "item_id": item_id,
                    "current_relevance": qrels[case.case_id].get(canonical, ""),
                    "reviewed_relevance": "",
                    "reviewer": "",
                    "cancer_type": metadata.get("cancer_type", ""),
                    "source_dataset": metadata.get("source_dataset", ""),
                    "document_preview": (result.get("document") or "")[:500].replace("\n", " "),
                    "notes": "",
                }
            )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Annotation pool: {output}")
    print("Fill reviewed_relevance (0-3) and reviewer, then transfer reviewed judgments to data/qrels.csv.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=CASES_FILE)
    parser.add_argument("--qrels", type=Path, default=QRELS_FILE)
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR / "annotation_pool.csv")
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()
    if args.top_k < 1:
        raise ValueError("top-k must be positive")
    build_pool(args.cases, args.qrels, args.output, args.top_k, args.device)


if __name__ == "__main__":
    main()
