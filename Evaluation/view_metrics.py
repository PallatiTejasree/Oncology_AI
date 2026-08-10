"""Print concise retrieval and generated-answer evaluation metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


OUTPUTS = Path(__file__).parent / "outputs"


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Metrics file not found: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def _percent(value: Any) -> str:
    return f"{float(value) * 100:.1f}%"


def _print_group(title: str, metrics: dict[str, Any], names: list[str]) -> None:
    print(f"\n{title}")
    for name in names:
        if name in metrics:
            print(f"  {name:<22} {_percent(metrics[name]):>7}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--retrieval",
        type=Path,
        default=OUTPUTS / "evaluation_summary.json",
    )
    parser.add_argument(
        "--answers",
        type=Path,
        default=OUTPUTS / "llm_evaluation_summary.json",
    )
    args = parser.parse_args()

    retrieval = _load(args.retrieval)
    answers = _load(args.answers)
    headline_metrics = [
        "hit_rate@1", "hit_rate@3", "hit_rate@5", "hit_rate@10",
        "mrr@5", "map@5", "ndcg@5", "judged@5",
        "cancer_hit@5", "source_hit@5",
    ]
    print(f"Retrieval benchmark: {retrieval.get('case_count', 0)} cases")
    _print_group("Overall retrieval", retrieval.get("macro_average", {}), headline_metrics)
    for query_type, metrics in retrieval.get("by_query_type", {}).items():
        _print_group(
            f"{query_type.replace('_', ' ').title()} retrieval",
            metrics,
            ["hit_rate@1", "hit_rate@3", "hit_rate@5", "mrr@5", "ndcg@5"],
        )

    print(f"\nStructured-answer benchmark: {answers.get('case_count', 0)} cases")
    _print_group(
        "Automatic answer checks",
        answers.get("automatic_metrics", {}),
        [
            "citation_validity", "citation_coverage", "structured_sections",
            "limitation_present", "disclaimer_present",
        ],
    )
    print("\nNote: automatic checks do not establish clinical correctness.")


if __name__ == "__main__":
    main()
