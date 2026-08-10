"""Shared utilities for reliable Chroma ingestion."""

from __future__ import annotations

import csv
import json
import os
from itertools import zip_longest
from pathlib import Path
from typing import Iterator

import numpy as np


def load_artifacts(embeddings_file: Path, metadata_file: Path, manifest_file: Path):
    for path in (embeddings_file, metadata_file, manifest_file):
        if not path.is_file():
            raise FileNotFoundError(f"Missing required artifact: {path}")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    embeddings = np.load(embeddings_file, mmap_mode="r", allow_pickle=False)
    if embeddings.ndim != 2:
        raise ValueError(f"Expected 2D embeddings, received {embeddings.shape}")
    expected = (int(manifest["rows"]), int(manifest["dimensions"]))
    if embeddings.shape != expected:
        raise ValueError(f"Embedding shape {embeddings.shape} does not match manifest {expected}")
    return embeddings, manifest


def clean_metadata(
    row: dict[str, str],
    integer_fields: set[str] | None = None,
    float_fields: set[str] | None = None,
    excluded_fields: set[str] | None = None,
) -> dict:
    """Return Chroma-compatible scalar metadata without empty values."""
    integer_fields = integer_fields or set()
    float_fields = float_fields or set()
    excluded_fields = excluded_fields or set()
    result = {}
    for key, value in row.items():
        if key in excluded_fields:
            continue
        value = (value or "").strip()
        if not value:
            continue
        if key in integer_fields:
            try:
                result[key] = int(value)
                continue
            except ValueError:
                pass
        if key in float_fields:
            try:
                result[key] = float(value)
                continue
            except ValueError:
                pass
        result[key] = value
    return result


def csv_batches(path: Path, batch_size: int) -> Iterator[list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8", errors="strict") as handle:
        reader = csv.DictReader(handle)
        batch = []
        for row in reader:
            batch.append(row)
            if len(batch) == batch_size:
                yield batch
                batch = []
        if batch:
            yield batch


def aligned_text_batches(metadata_file: Path, documents_file: Path, batch_size: int):
    """Stream aligned text metadata and chunk documents."""
    with metadata_file.open(newline="", encoding="utf-8") as metadata_handle, documents_file.open(
        newline="", encoding="utf-8"
    ) as documents_handle:
        metadata_reader = csv.DictReader(metadata_handle)
        documents_reader = csv.DictReader(documents_handle)
        batch = []
        for row_number, pair in enumerate(
            zip_longest(metadata_reader, documents_reader), start=1
        ):
            metadata, document = pair
            if metadata is None or document is None:
                raise ValueError("Text metadata and chunk document row counts differ")
            if metadata.get("chunk_id") != document.get("chunk_id"):
                raise ValueError(
                    f"Text alignment mismatch at row {row_number}: "
                    f"{metadata.get('chunk_id')} != {document.get('chunk_id')}"
                )
            text = (document.get("text") or "").strip()
            if not text:
                raise ValueError(f"Empty chunk text at row {row_number}")
            batch.append((metadata, text))
            if len(batch) == batch_size:
                yield batch
                batch = []
        if batch:
            yield batch


def checkpoint_start(path: Path, signature: dict) -> int:
    if not path.exists():
        return 0
    checkpoint = json.loads(path.read_text(encoding="utf-8"))
    if any(checkpoint.get(key) != value for key, value in signature.items()):
        raise RuntimeError(f"Incompatible ingestion checkpoint: {path}")
    return int(checkpoint.get("next_index", 0))


def write_checkpoint(path: Path, signature: dict, next_index: int) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps({**signature, "next_index": next_index}, indent=2), encoding="utf-8"
    )
    os.replace(temporary, path)
