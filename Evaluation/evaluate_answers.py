"""Evaluate generated answer structure/citations and prepare blinded human review."""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean


def _citation_ids(answer: str) -> list[str]:
    return re.findall(r"[UR]\d+", answer)


def score_record(record: dict) -> dict:
    answer = str(record.get("summary") or record.get("answer") or "").strip()
    structured = record.get("structured_answer") or {}
    evidence = record.get("evidence") or []
    supporting = record.get("supporting_image_evidence") or []
    uploads = record.get("uploaded_sources") or []
    allowed = {f"U{i}" for i in range(1, len(uploads) + 1)} | {
        f"R{i}" for i in range(1, len(evidence) + len(supporting) + 1)
    }
    structured_items = [*(structured.get("findings") or []), *(structured.get("reasoning") or [])]
    structured_citations = [citation for item in structured_items for citation in (item.get("citations") or [])]
    used = _citation_ids(answer) + structured_citations
    bullets = [line for line in answer.splitlines() if line.strip().startswith(("•", "-"))]
    cited_bullets = [line for line in bullets if _citation_ids(line)]
    citation_coverage = (
        sum(bool(item.get("citations")) for item in structured_items) / len(structured_items)
        if structured_items else len(cited_bullets) / len(bullets) if bullets else 0.0
    )
    limitation_text = " ".join(structured.get("limitations") or []) + " " + answer
    invalid = sorted(set(used) - allowed)
    return {
        "case_id": record.get("case_id") or record.get("session_id") or "unknown",
        "model_name": record.get("model_name") or "unknown",
        "query_type": record.get("query_type") or "unknown",
        "uploaded_sources": len(uploads),
        "retrieved_evidence": len(evidence) + len(supporting),
        "citation_count": len(used),
        "citation_validity": 1.0 if used and not invalid else 0.0,
        "citation_coverage": citation_coverage,
        "structured_sections": float(bool(structured) or ("Key findings" in answer and "Clinical note" in answer)),
        "limitation_present": float(bool(structured.get("limitations")) or bool(re.search(r"limit|insufficient|cannot|not establish", limitation_text, re.I))),
        "disclaimer_present": float(bool(record.get("disclaimer"))),
        "processing_time_ms": record.get("processing_time_ms"),
        "invalid_citations": "|".join(invalid),
    }


def evaluate(input_path: Path, output_dir: Path) -> dict:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    records = payload if isinstance(payload, list) else payload.get("records", [payload])
    rows = [score_record(record) for record in records]
    if not rows:
        raise ValueError("No answer records found")
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with (output_dir / "llm_per_case_metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)

    metric_names = ["citation_validity", "citation_coverage", "structured_sections", "limitation_present", "disclaimer_present"]
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(rows),
        "citation_schema_cases": sum(
            1 for record in records if "citation_validation" in record
        ),
        "automatic_metrics": {name: mean(float(row[name]) for row in rows) for name in metric_names},
        "warning": "Automatic checks validate structure, not clinical correctness. Complete clinician review before making quality claims.",
    }
    (output_dir / "llm_evaluation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    review_fields = ["case_id", "groundedness_0_3", "clinical_relevance_0_3", "safety_0_3", "completeness_0_3", "image_text_agreement_0_3", "reviewer", "notes"]
    with (output_dir / "llm_human_review.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=review_fields); writer.writeheader()
        for row in rows:
            writer.writerow({"case_id": row["case_id"]})
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON result or list of API result objects")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "outputs")
    args = parser.parse_args()
    summary = evaluate(args.input, args.output_dir)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
