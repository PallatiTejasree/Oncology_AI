"""Run retrieval evaluation and write per-case and aggregate metrics."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

from Evaluation.config import CASES_FILE, DEFAULT_K_VALUES, OUTPUT_DIR, QRELS_FILE
from Evaluation.metrics import evaluate_ranking, label_diagnostics
from Evaluation.runner import RetrievalRunner, canonical_result_id
from Evaluation.schema import load_cases, load_qrels


def aggregate(rows: list[dict]) -> dict:
    values: dict[str, list[float]] = defaultdict(list)
    by_type: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        query_type = row["query_type"]
        for key, value in row.items():
            if isinstance(value, (int, float)) and key != "top_k":
                values[key].append(float(value))
                by_type[query_type][key].append(float(value))
    return {
        "macro_average": {key: mean(items) for key, items in sorted(values.items())},
        "by_query_type": {
            query_type: {key: mean(items) for key, items in sorted(metrics.items())}
            for query_type, metrics in sorted(by_type.items())
        },
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run_evaluation(
    cases_file: Path,
    qrels_file: Path,
    output_dir: Path,
    k_values: tuple[int, ...],
    device: str,
) -> dict:
    if not k_values or any(k < 1 for k in k_values):
        raise ValueError("All k values must be positive")
    cases = load_cases(cases_file)
    qrels = load_qrels(qrels_file, {case.case_id for case in cases})
    runner = RetrievalRunner(device=device)
    maximum_k = max(k_values)
    rows = []
    rankings = {}

    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] {case.case_id}: {case.query_type}")
        results = runner.run(case, maximum_k)
        ranked_ids = [canonical_result_id(result) for result in results]
        rankings[case.case_id] = [
            {
                "rank": rank,
                "id": identifier,
                "distance": result.get("distance"),
                "retrieval_score": result.get("retrieval_score"),
                "rrf_score": result.get("rrf_score"),
                "cancer_type": (result.get("metadata") or {}).get("cancer_type"),
                "source_dataset": (result.get("metadata") or {}).get("source_dataset"),
            }
            for rank, (identifier, result) in enumerate(zip(ranked_ids, results), start=1)
        ]
        for k in k_values:
            row = {"case_id": case.case_id, "query_type": case.query_type, "top_k": k}
            row.update(evaluate_ranking(ranked_ids, qrels[case.case_id], k))
            row.update(
                label_diagnostics(
                    results, case.expected_cancer_types, case.expected_sources, k
                )
            )
            rows.append(row)

    output_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "cases_file": str(cases_file.resolve()),
        "qrels_file": str(qrels_file.resolve()),
        "case_count": len(cases),
        "k_values": list(k_values),
        **aggregate(rows),
        "rankings": rankings,
    }
    judged_keys = [
        key for key in summary["macro_average"] if key.startswith("judged@")
    ]
    if judged_keys and min(summary["macro_average"][key] for key in judged_keys) < 0.8:
        summary["warning"] = (
            "Judgment coverage is below 80%; unjudged retrieved items are treated as "
            "non-relevant, so quality metrics are preliminary. Build and review an annotation pool."
        )
    (output_dir / "evaluation_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    write_csv(output_dir / "per_case_metrics.csv", rows)
    print(f"Summary: {output_dir / 'evaluation_summary.json'}")
    print(f"Per-case metrics: {output_dir / 'per_case_metrics.csv'}")
    if "warning" in summary:
        print(f"WARNING: {summary['warning']}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=CASES_FILE)
    parser.add_argument("--qrels", type=Path, default=QRELS_FILE)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--k", type=int, nargs="+", default=list(DEFAULT_K_VALUES))
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()
    run_evaluation(args.cases, args.qrels, args.output_dir, tuple(sorted(set(args.k))), args.device)


if __name__ == "__main__":
    main()
