"""Create a unified text-chunk dataset from all supported ingestion outputs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Iterable, Iterator

try:
    from .splitter import split_text
except ImportError:  # Allows: python Ingestion/chunking/create_chunks.py
    from splitter import split_text


INGESTION_DIR = Path(__file__).resolve().parent.parent
TCGA_REPORTS = INGESTION_DIR / "datasets" / "processed" / "clean_reports.csv"
PMC_ARTICLES = INGESTION_DIR / "processed_dataset" / "parsed_json"
PMC_IMAGES = INGESTION_DIR / "processed_dataset" / "image_metadata.csv"
LEGACY_IMAGES = INGESTION_DIR / "datasets" / "images" / "oncology_metadata.csv"
OUTPUT_FILE = INGESTION_DIR / "datasets" / "processed" / "chunk_metadata.csv"

FIELDS = [
    "chunk_id", "source_dataset", "source_type", "document_id", "report_id",
    "patient_id", "pmcid", "image_id", "cancer_type", "section",
    "chunk_index", "text",
]


def _labels(value: object) -> str:
    if isinstance(value, list):
        return "|".join(str(item) for item in value if item)
    return str(value or "unknown")


def _tcga_documents() -> Iterator[dict[str, str]]:
    if not TCGA_REPORTS.exists():
        return
    with TCGA_REPORTS.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            yield {
                "source_dataset": "tcga_reports",
                "source_type": "clinical_report",
                "document_id": f"TCGA_REPORT_{row['report_id']}",
                "report_id": row["report_id"],
                "patient_id": row["patient_id"],
                "cancer_type": row["cancer_type"],
                "section": "report",
                "text": row["report"],
            }


def _pmc_documents() -> Iterator[dict[str, str]]:
    if not PMC_ARTICLES.exists():
        return
    for path in sorted(PMC_ARTICLES.glob("*.json")):
        article = json.loads(path.read_text(encoding="utf-8"))
        pmcid = str(article.get("pmcid") or path.stem)
        common = {
            "source_dataset": "pmc_articles",
            "source_type": "research_article",
            "pmcid": pmcid,
            "cancer_type": _labels(article.get("cancer_types") or article.get("cancer_type")),
        }

        seen: set[str] = set()
        front = "\n\n".join(
            value.strip()
            for value in (article.get("title", ""), article.get("abstract", ""))
            if isinstance(value, str) and value.strip()
        )
        if front:
            seen.add(" ".join(front.split()))
            yield {**common, "document_id": pmcid, "section": "title_and_abstract", "text": front}

        for index, section in enumerate(article.get("sections") or []):
            body = str(section.get("text") or "").strip()
            canonical = " ".join(body.split())
            if not body or canonical in seen:
                continue
            seen.add(canonical)
            title = str(section.get("title") or f"section_{index + 1}").strip()
            yield {
                **common,
                "document_id": pmcid,
                "section": title,
                "text": f"{title}. {body}" if title else body,
            }


def _image_caption_documents(path: Path, dataset: str, accepted_only: bool) -> Iterator[dict[str, str]]:
    if not path.exists():
        return
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        for row_number, row in enumerate(csv.DictReader(handle), start=1):
            if accepted_only and row.get("accepted", "").lower() != "true":
                continue
            caption = (row.get("caption") or "").strip()
            if not caption:
                continue
            image_id = row.get("image_id") or row.get("image") or f"image_{row_number}"
            yield {
                "source_dataset": dataset,
                "source_type": "image_caption",
                "document_id": image_id,
                "pmcid": row.get("pmcid", ""),
                "image_id": image_id,
                "cancer_type": row.get("cancer_types") or row.get("cancer_type") or "unknown",
                "section": "figure_caption",
                "text": caption,
            }


def iter_documents() -> Iterable[dict[str, str]]:
    yield from _tcga_documents()
    yield from _pmc_documents()
    yield from _image_caption_documents(PMC_IMAGES, "pmc_medical_images", accepted_only=True)
    # This legacy manifest currently has empty captions; usable captions will be
    # picked up automatically if they are populated later.
    yield from _image_caption_documents(LEGACY_IMAGES, "oncology_images", accepted_only=False)


def create_chunks(output_file: Path = OUTPUT_FILE, chunk_size: int = 800, overlap: int = 150) -> dict[str, int]:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    source_counts: dict[str, int] = {}
    document_count = 0
    chunk_count = 0

    with output_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for document in iter_documents():
            chunks = split_text(document.get("text", ""), chunk_size, overlap)
            if not chunks:
                continue
            document_count += 1
            source = document["source_dataset"]
            source_counts[source] = source_counts.get(source, 0) + len(chunks)
            for chunk_index, text in enumerate(chunks):
                chunk_count += 1
                record = {field: document.get(field, "") for field in FIELDS}
                record.update(
                    chunk_id=f"CHUNK_{chunk_count:07d}",
                    chunk_index=chunk_index,
                    text=text,
                )
                writer.writerow(record)

    return {"documents": document_count, "chunks": chunk_count, **source_counts}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE)
    parser.add_argument("--chunk-size", type=int, default=800)
    parser.add_argument("--overlap", type=int, default=150)
    args = parser.parse_args()
    counts = create_chunks(args.output, args.chunk_size, args.overlap)
    print(f"Documents processed: {counts.pop('documents')}")
    print(f"Chunks created: {counts.pop('chunks')}")
    for source, count in sorted(counts.items()):
        print(f"  {source}: {count}")
    print(f"Saved to: {args.output}")


if __name__ == "__main__":
    main()
