"""Summarize latency from structured and API acceptance benchmark artifacts."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

from Evaluation.config import OUTPUT_DIR, PROJECT_ROOT


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        raise ValueError("Cannot calculate a percentile without values")
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def latency_summary(values: list[float]) -> dict[str, float | int]:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return {"count": 0}
    return {
        "count": len(clean), "min_ms": round(min(clean), 2),
        "mean_ms": round(mean(clean), 2), "median_ms": round(median(clean), 2),
        "p95_ms": round(percentile(clean, 0.95), 2), "max_ms": round(max(clean), 2),
    }


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest(pattern: str) -> Path | None:
    paths = sorted((PROJECT_ROOT / "tests/outputs").glob(pattern), key=lambda p: p.stat().st_mtime)
    return paths[-1] if paths else None


def build_report(structured_path: Path, api_paths: list[Path]) -> dict[str, Any]:
    structured = _load(structured_path)
    structured_records = structured if isinstance(structured, list) else structured.get("records", [])
    structured_groups: dict[str, list[float]] = defaultdict(list)
    stage_groups: dict[str, list[float]] = defaultdict(list)
    for record in structured_records:
        if record.get("status") != "PASS":
            continue
        structured_groups[str(record.get("kind") or "unknown")].append(record.get("processing_time_ms"))
        performance = ((record.get("diagnostics") or {}).get("performance") or {})
        for key in ("retrieval_ms", "generation_ms", "pipeline_total_ms"):
            if performance.get(key) is not None:
                stage_groups[key].append(performance[key])

    api_groups: dict[str, list[float]] = defaultdict(list)
    api_passed = api_failed = 0
    for path in api_paths:
        payload = _load(path)
        for record in payload.get("results", []):
            if record.get("status") == "PASS":
                api_passed += 1
                api_groups[str(record.get("expected_route") or "unknown")].append(record.get("elapsed_ms"))
            elif record.get("status") == "FAIL":
                api_failed += 1
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "structured_source": str(structured_path.resolve()),
        "api_sources": [str(path.resolve()) for path in api_paths],
        "structured_total": latency_summary([
            value for values in structured_groups.values() for value in values
        ]),
        "structured_by_kind": {
            key: latency_summary(values) for key, values in sorted(structured_groups.items())
        },
        "pipeline_stages": {
            key: latency_summary(values) for key, values in sorted(stage_groups.items())
        },
        "api": {
            "passed": api_passed, "failed": api_failed,
            "overall": latency_summary([value for values in api_groups.values() for value in values]),
            "by_route": {key: latency_summary(values) for key, values in sorted(api_groups.items())},
        },
        "limitations": [
            "Latency was measured on the current development machine, not production infrastructure.",
            "Gemini network latency and provider load can vary between runs.",
            "Concurrent-user throughput and resource utilization require a separate live load test.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--structured", type=Path,
        default=OUTPUT_DIR / "structured_benchmark_results.json",
    )
    parser.add_argument("--api", type=Path, action="append")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR / "performance_summary.json")
    args = parser.parse_args()
    api_paths = args.api or [
        path for path in (_latest("chat_e2e_full_*.json"), _latest("chat_e2e_uploads_*.json"))
        if path is not None
    ]
    report = build_report(args.structured, api_paths)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Output: {args.output.resolve()}")


if __name__ == "__main__":
    main()
