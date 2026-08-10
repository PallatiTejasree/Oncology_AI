"""Filter article figures and build a traceable medical-image manifest."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path

from PIL import Image

from Ingestion.config import (
    DOWNLOADS_DIR,
    IMAGE_METADATA_CSV,
    MEDICAL_IMAGES_DIR,
    PARSED_JSON_DIR,
)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".gif", ".webp"}
EXTENSION_PRIORITY = {".tif": 0, ".tiff": 0, ".png": 1, ".jpg": 2, ".jpeg": 2, ".webp": 3, ".gif": 4, ".bmp": 5}

KEEP_PATTERNS = {
    "ct": r"\b(?:ct|computed tomography)\b",
    "mri": r"\b(?:mri|magnetic resonance)\b",
    "pet": r"\b(?:pet(?:/ct)?|positron emission tomography)\b",
    "ultrasound": r"\b(?:ultrasound|sonograph(?:y|ic))\b",
    "xray": r"\b(?:x[- ]?ray|radiograph(?:y|ic)?)\b",
    "pathology": r"\b(?:histopathology|histology|h\s*&\s*e|hematoxylin|eosin)\b",
    "microscopy": r"\b(?:microscopy|microscopic|micrograph)\b",
    "clinical_image": r"\b(?:clinical photograph|clinical image|gross specimen|gross pathology)\b",
    "lesion": r"\b(?:tumou?r|lesion|mass|biopsy)\b",
    "ihc": r"\b(?:immunohistochemistry|ihc)\b",
    "other_modality": r"\b(?:fluorescence|endoscopy|dermoscopy)\b",
}

REJECT_PATTERNS = {
    "chart_or_plot": r"\b(?:bar chart|pie chart|line (?:graph|chart)|scatter plot|box plot|heatmap|volcano plot|forest plot|roc curve|kaplan[- ]meier)\b",
    "workflow": r"\b(?:flowchart|workflow|study design|algorithm|prisma|consort)\b",
    "molecular_diagram": r"\b(?:pathway|network|chemical structure|western blot|schematic illustration)\b",
    "table": r"\btable\b",
}

COMPILED_KEEP = {name: re.compile(pattern, re.IGNORECASE) for name, pattern in KEEP_PATTERNS.items()}
COMPILED_REJECT = {name: re.compile(pattern, re.IGNORECASE) for name, pattern in REJECT_PATTERNS.items()}


def classify_caption(caption: str | None) -> tuple[bool, str]:
    text = (caption or "").strip()
    if not text:
        return False, "missing_caption"
    for name, pattern in COMPILED_REJECT.items():
        if pattern.search(text):
            return False, f"non_medical:{name}"
    for name, pattern in COMPILED_KEEP.items():
        if pattern.search(text):
            return True, f"medical:{name}"
    return False, "no_medical_modality_or_pathology_term"


def is_medical_caption(caption: str | None) -> bool:
    return classify_caption(caption)[0]


def load_json_files(json_folder: Path = PARSED_JSON_DIR) -> list[Path]:
    return sorted(Path(json_folder).rglob("*.json"))


def build_image_index(download_folder: Path = DOWNLOADS_DIR) -> dict:
    """Index once instead of walking the entire dataset for every figure."""
    by_pmcid_and_stem = defaultdict(list)
    by_stem = defaultdict(list)
    for path in Path(download_folder).rglob("*"):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        pmcid = next((part for part in path.parts if re.fullmatch(r"PMC\d+", part)), "")
        by_pmcid_and_stem[(pmcid, path.stem)].append(path)
        by_stem[path.stem].append(path)
    return {"pmcid_stem": by_pmcid_and_stem, "stem": by_stem}


def find_image(image_name: str, pmcid: str, image_index: dict) -> Path | None:
    stem = Path(image_name).stem
    candidates = image_index["pmcid_stem"].get((pmcid, stem), [])
    if not candidates:
        candidates = image_index["stem"].get(stem, [])
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: (EXTENSION_PRIORITY.get(path.suffix.lower(), 99), -path.stat().st_size))[0]


def inspect_image(image_path: Path, minimum_dimension: int = 150) -> dict:
    try:
        with Image.open(image_path) as image:
            width, height = image.size
            image_format = image.format or image_path.suffix.lstrip(".").upper()
            image.verify()
        if width < minimum_dimension or height < minimum_dimension:
            return {"valid": False, "reason": "image_too_small", "width": width, "height": height, "format": image_format}
        ratio = width / height
        if ratio > 6 or ratio < 0.15:
            return {"valid": False, "reason": "extreme_aspect_ratio", "width": width, "height": height, "format": image_format}
        return {"valid": True, "reason": "valid", "width": width, "height": height, "format": image_format}
    except Exception as exc:
        return {"valid": False, "reason": f"invalid_image:{type(exc).__name__}", "width": "", "height": "", "format": ""}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def process_dataset(
    json_folder: Path = PARSED_JSON_DIR,
    download_folder: Path = DOWNLOADS_DIR,
    output_folder: Path = MEDICAL_IMAGES_DIR,
    manifest_path: Path = IMAGE_METADATA_CSV,
    copy_files: bool = True,
) -> dict:
    json_files = load_json_files(json_folder)
    image_index = build_image_index(download_folder)
    output_folder = Path(output_folder)
    manifest_path = Path(manifest_path)
    output_folder.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    records = []

    for json_file in json_files:
        article = json.loads(json_file.read_text(encoding="utf-8"))
        pmcid = article.get("pmcid") or json_file.stem
        cancer_types = article.get("cancer_types") or [article.get("cancer_type", "unknown")]
        for figure in article.get("figures") or []:
            image_name = figure.get("image") or ""
            caption = figure.get("caption") or ""
            accepted, reason = classify_caption(caption)
            source = find_image(image_name, pmcid, image_index) if image_name else None
            inspection = {"valid": False, "reason": "image_not_found", "width": "", "height": "", "format": ""}
            if not source:
                accepted, reason = False, "image_not_found"
            else:
                inspection = inspect_image(source)
                if accepted and not inspection["valid"]:
                    accepted, reason = False, inspection["reason"]

            destination = ""
            file_hash = ""
            if source:
                file_hash = sha256_file(source)
            if accepted and source and copy_files:
                destination_path = output_folder / pmcid / source.name
                destination_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination_path)
                destination = str(destination_path.resolve())

            records.append(
                {
                    "image_id": f"{pmcid}:{figure.get('figure_id') or image_name}",
                    "pmcid": pmcid,
                    "cancer_types": "|".join(sorted(set(filter(None, cancer_types)))),
                    "figure_id": figure.get("figure_id", ""),
                    "caption": caption,
                    "source_path": str(source.resolve()) if source else "",
                    "image_path": destination,
                    "width": inspection["width"],
                    "height": inspection["height"],
                    "format": inspection["format"],
                    "sha256": file_hash,
                    "accepted": accepted,
                    "reason": reason,
                }
            )

    fieldnames = list(records[0]) if records else ["image_id", "pmcid", "cancer_types", "accepted", "reason"]
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    return {
        "json_files": len(json_files),
        "figures": len(records),
        "accepted": sum(record["accepted"] for record in records),
        "rejected": sum(not record["accepted"] for record in records),
        "manifest": str(manifest_path),
    }


if __name__ == "__main__":
    print(json.dumps(process_dataset(), indent=2))
