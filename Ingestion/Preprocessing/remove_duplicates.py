"""Identify exact duplicate accepted images without deleting source data."""

from __future__ import annotations

import csv
import json
import os
import shutil
from collections import defaultdict
from pathlib import Path

from Ingestion.config import DEDUPLICATION_CSV, IMAGE_METADATA_CSV, UNIQUE_IMAGES_DIR


def deduplicate_manifest(
    manifest_path: Path = IMAGE_METADATA_CSV,
    duplicate_report: Path = DEDUPLICATION_CSV,
    unique_folder: Path = UNIQUE_IMAGES_DIR,
    materialize: bool = False,
) -> dict:
    manifest_path = Path(manifest_path)
    if not manifest_path.exists():
        raise FileNotFoundError(f"Image manifest not found: {manifest_path}")

    with manifest_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    accepted = [
        row for row in rows
        if row.get("accepted", "").lower() in {"true", "1", "yes"} and row.get("sha256")
    ]
    groups = defaultdict(list)
    for row in accepted:
        groups[row["sha256"]].append(row)

    duplicate_rows = []
    canonical_rows = []
    for file_hash, group in sorted(groups.items()):
        canonical = group[0]
        canonical_rows.append(canonical)
        for duplicate in group[1:]:
            duplicate_rows.append(
                {
                    "sha256": file_hash,
                    "canonical_image_id": canonical["image_id"],
                    "canonical_path": canonical.get("source_path", ""),
                    "duplicate_image_id": duplicate["image_id"],
                    "duplicate_path": duplicate.get("source_path", ""),
                }
            )

    duplicate_report = Path(duplicate_report)
    duplicate_report.parent.mkdir(parents=True, exist_ok=True)
    fields = ["sha256", "canonical_image_id", "canonical_path", "duplicate_image_id", "duplicate_path"]
    with duplicate_report.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(duplicate_rows)

    materialized = 0
    if materialize:
        unique_folder = Path(unique_folder)
        unique_folder.mkdir(parents=True, exist_ok=True)
        for row in canonical_rows:
            source_value = row.get("image_path") or row.get("source_path")
            if not source_value:
                continue
            source = Path(source_value)
            destination = unique_folder / row["pmcid"] / source.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                continue
            try:
                os.link(source, destination)
            except OSError:
                shutil.copy2(source, destination)
            materialized += 1

    return {
        "accepted_records": len(accepted),
        "unique_hashes": len(groups),
        "duplicate_records": len(duplicate_rows),
        "duplicate_report": str(duplicate_report),
        "materialized": materialized,
    }


if __name__ == "__main__":
    print(json.dumps(deduplicate_manifest(), indent=2))
