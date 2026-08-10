"""Export completed analysis responses from the application database for evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.db.database import SessionLocal

# Import every related mapper so SQLAlchemy can resolve class-name relationships.
from app.models.user import User  # noqa: F401
from app.models.upload_session import UploadSession  # noqa: F401
from app.models.report import Report  # noqa: F401
from app.models.medical_image import MedicalImage  # noqa: F401
from app.models.chat_history import ChatHistory  # noqa: F401
from app.models.chat import Chat  # noqa: F401
from app.models.message import Message  # noqa: F401
from app.models.summary import Summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "outputs" / "llm_analysis_results.json")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument(
        "--new-format-only",
        action="store_true",
        help="Export only responses produced with citation-validation metadata.",
    )
    args = parser.parse_args()
    if args.limit < 1:
        raise ValueError("--limit must be positive")

    db = SessionLocal()
    try:
        summaries = (
            db.query(Summary)
            .filter(Summary.processing_status == "Completed", Summary.ai_summary.is_not(None))
            .order_by(Summary.created_at.desc())
            .limit(args.limit)
            .all()
        )
        records = []
        for summary in summaries:
            try:
                result = json.loads(summary.ai_summary)
            except (TypeError, json.JSONDecodeError):
                continue
            if args.new_format_only and "citation_validation" not in result:
                continue
            records.append({
                "case_id": f"session-{summary.session_id}-summary-{summary.id}",
                "session_id": summary.session_id,
                "processing_time_ms": summary.processing_time_ms,
                **result,
            })
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Exported {len(records)} completed answers to {args.output}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
