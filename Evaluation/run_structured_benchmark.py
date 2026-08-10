"""Generate the isolated 20-case structured-answer benchmark with checkpoints."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import fitz
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = Path(__file__).parent / "data" / "structured_answer_cases.json"
DEFAULT_OUTPUT = Path(__file__).parent / "outputs" / "structured_benchmark_results.json"
REQUIRED_STRUCTURED_KEYS = {
    "headline", "subheadline", "evidence_support", "plain_language_summary",
    "findings", "reasoning", "supports", "limitations", "medical_terms", "safety_notice",
}


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("Structured benchmark must contain a non-empty JSON list")
    ids = [str(case.get("case_id") or "") for case in cases]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("Every benchmark case requires a unique case_id")
    allowed = {"text", "image", "hybrid", "pdf"}
    if any(case.get("kind") not in allowed or not str(case.get("prompt") or "").strip() for case in cases):
        raise ValueError("Every case requires a supported kind and non-empty prompt")
    if path.resolve() == DEFAULT_CASES.resolve():
        distribution = Counter(case["kind"] for case in cases)
        expected = Counter({"text": 8, "image": 5, "hybrid": 5, "pdf": 2})
        if len(cases) != 20 or distribution != expected:
            raise ValueError(f"Default benchmark must be 20 balanced cases; received {dict(distribution)}")
    for case in cases:
        source = case.get("image_path") or case.get("pdf_path")
        if source and not (PROJECT_ROOT / source).is_file():
            raise FileNotFoundError(f"Missing fixture for {case['case_id']}: {source}")
    return cases


def pdf_text(path: Path) -> str:
    with fitz.open(path) as document:
        return "\n".join(page.get_text("text") for page in document).strip()


def validate_result(result: dict[str, Any]) -> list[str]:
    errors = []
    structured = result.get("structured_answer")
    if not isinstance(structured, dict):
        errors.append("missing structured_answer (Gemini may have fallen back)")
    else:
        missing = sorted(REQUIRED_STRUCTURED_KEYS - set(structured))
        if missing:
            errors.append(f"structured_answer missing keys: {', '.join(missing)}")
    if result.get("citation_validation", {}).get("status") == "invalid":
        errors.append("citation validation failed")
    if not result.get("evidence"):
        errors.append("no retrieved evidence")
    if result.get("model_name") == "retrieval-only":
        detail = (result.get("generation_diagnostics") or {}).get("error")
        errors.append(f"LLM fallback used: {detail}" if detail else "LLM fallback used")
    return errors


def save_checkpoint(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--case-id", action="append", help="Run only a selected case; repeatable")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit must be positive")

    load_dotenv(PROJECT_ROOT / "backend" / ".env")
    from app.langchain.pipeline import ClinicalAnalysisPipeline
    from app.services.pdf_extraction import extract_pdf_images

    cases = load_cases(args.cases)
    if args.case_id:
        selected = set(args.case_id)
        cases = [case for case in cases if case["case_id"] in selected]
        missing = selected - {case["case_id"] for case in cases}
        if missing:
            raise ValueError(f"Unknown case IDs: {sorted(missing)}")
    if args.limit:
        cases = cases[: args.limit]

    records = []
    # Always preserve unrelated checkpoint records. --no-resume means rerun
    # selected cases, not erase results from the rest of the benchmark.
    if args.output.is_file():
        records = json.loads(args.output.read_text(encoding="utf-8"))
    completed = (
        set()
        if args.no_resume
        else {record["case_id"] for record in records if record.get("status") == "PASS"}
    )
    pipeline = ClinicalAnalysisPipeline()
    attempted_records = []

    for index, case in enumerate(cases, start=1):
        if case["case_id"] in completed:
            print(f"[{index}/{len(cases)}] {case['case_id']}: RESUME-SKIP")
            continue
        started = time.perf_counter()
        try:
            kind = case["kind"]
            prompt = case["prompt"]
            image_paths: list[Path] = []
            uploaded_sources = []
            analysis_text = prompt
            extraction = None
            if kind in {"image", "hybrid"}:
                image_path = PROJECT_ROOT / case["image_path"]
                image_paths = [image_path]
                uploaded_sources = [{"file_name": image_path.name, "source_type": "uploaded_image"}]
            elif kind == "pdf":
                path = PROJECT_ROOT / case["pdf_path"]
                extracted = extract_pdf_images(
                    path, args.output.parent / "benchmark_extracted_images" / case["case_id"]
                )
                image_paths = [item.path for item in extracted]
                analysis_text = f"{prompt}\n\nUPLOADED REPORT TEXT:\n{pdf_text(path)}"
                uploaded_sources = [{"file_name": path.name, "source_type": "uploaded_report"}]
                extraction = {"images_extracted": len(extracted), "pages": sorted({item.page for item in extracted})}

            result = pipeline.analyze(
                text=analysis_text,
                image_paths=image_paths,
                top_k=args.top_k,
                include_risk_review=kind != "text",
                uploaded_sources=uploaded_sources,
            )
            errors = validate_result(result)
            record = {
                "case_id": case["case_id"], "kind": kind, "prompt": prompt,
                "expected_label": case.get("expected_label"),
                "status": "FAIL" if errors else "PASS", "errors": errors,
                "processing_time_ms": round((time.perf_counter() - started) * 1000),
                "pdf_extraction": extraction,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                **result,
            }
        except Exception as error:
            record = {
                "case_id": case["case_id"], "kind": case["kind"], "prompt": case["prompt"],
                "expected_label": case.get("expected_label"), "status": "ERROR",
                "errors": [f"{type(error).__name__}: {error}"],
                "processing_time_ms": round((time.perf_counter() - started) * 1000),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        attempted_records.append(record)
        previous = next(
            (item for item in records if item.get("case_id") == case["case_id"]), None
        )
        checkpoint_record = (
            previous
            if previous and previous.get("status") == "PASS" and record.get("status") != "PASS"
            else record
        )
        records = [
            item for item in records if item.get("case_id") != case["case_id"]
        ] + [checkpoint_record]
        save_checkpoint(args.output, records)
        print(f"[{index}/{len(cases)}] {case['case_id']}: {record['status']} ({record['processing_time_ms']} ms)")
        if record["status"] == "FAIL":
            for error in record.get("errors", []):
                print(f"  - {error}")
        if previous and checkpoint_record is previous and record.get("status") != "PASS":
            print("  - Previous PASS checkpoint preserved")
        if any("429 RESOURCE_EXHAUSTED" in error for error in record.get("errors", [])):
            print("Stopping early because the Gemini project quota is exhausted.")
            break

    counts = Counter(record.get("status") for record in attempted_records)
    print(f"Output: {args.output.resolve()}")
    print(" ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    return 1 if counts.get("FAIL") or counts.get("ERROR") else 0


if __name__ == "__main__":
    raise SystemExit(main())
