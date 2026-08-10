
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

import numpy as np


DEFAULT_BASE = Path(__file__).resolve().parent.parent / "datasets" / "embeddings"
BLOCK_SIZE = 8192

DATASETS = {
    "text": {
        "title": "TEXT EMBEDDINGS (MedCPT)",
        "embeddings": "text_embeddings.npy",
        "metadata": "text_metadata.csv",
        "manifest": "text_embeddings_manifest.json",
        "id_column": "chunk_id",
        "required_columns": {"chunk_id", "source_dataset", "source_type", "document_id"},
        "expected_model": "ncbi/MedCPT-Article-Encoder",
    },
    "image": {
        "title": "IMAGE EMBEDDINGS (BiomedCLIP)",
        "embeddings": "image_embeddings.npy",
        "metadata": "image_embedding_metadata.csv",
        "manifest": "image_embeddings_manifest.json",
        "id_column": "image_id",
        "required_columns": {"image_id", "source_dataset", "image_path"},
        "expected_model": "hf-hub:microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224",
    },
}


def require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Missing file: {path}")
    print(f"✓ Found {path.name}")


def load_manifest(path: Path, expected_model: str) -> dict:
    require_file(path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    required = {"model", "rows", "dimensions", "normalized", "similarity"}
    missing = required.difference(manifest)
    if missing:
        raise ValueError(f"{path.name} is missing fields: {sorted(missing)}")
    if manifest["model"] != expected_model:
        raise ValueError(
            f"Unexpected model in {path.name}: {manifest['model']!r}; "
            f"expected {expected_model!r}"
        )
    if int(manifest["rows"]) <= 0 or int(manifest["dimensions"]) <= 0:
        raise ValueError(f"Invalid rows or dimensions in {path.name}")
    print(f"✓ Manifest model: {manifest['model']}")
    return manifest


def validate_metadata(
    path: Path,
    id_column: str,
    required_columns: set[str],
) -> tuple[int, Counter[str]]:
    """Stream metadata so the 47 MB image CSV is not loaded into a DataFrame."""
    require_file(path)
    identifiers: set[str] = set()
    sources: Counter[str] = Counter()
    rows = 0

    with path.open(newline="", encoding="utf-8", errors="strict") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = required_columns.difference(columns)
        if missing:
            raise ValueError(f"{path.name} is missing columns: {sorted(missing)}")

        for line_number, row in enumerate(reader, start=2):
            identifier = (row.get(id_column) or "").strip()
            if not identifier:
                raise ValueError(f"Empty {id_column} in {path.name} line {line_number}")
            if identifier in identifiers:
                raise ValueError(
                    f"Duplicate {id_column} {identifier!r} in {path.name} line {line_number}"
                )
            identifiers.add(identifier)
            source = (row.get("source_dataset") or "").strip()
            if not source:
                raise ValueError(f"Empty source_dataset in {path.name} line {line_number}")
            sources[source] += 1
            rows += 1

    if rows == 0:
        raise ValueError(f"{path.name} contains no metadata rows")
    print(f"✓ Metadata rows: {rows:,}")
    print(f"✓ Unique {id_column}: {len(identifiers):,}")
    print(f"✓ Sources: {dict(sources)}")
    return rows, sources


def validate_vectors(path: Path, manifest: dict) -> tuple[int, int]:
    """Memory-map vectors and validate them in bounded-size blocks."""
    require_file(path)
    vectors = np.load(path, mmap_mode="r", allow_pickle=False)
    if vectors.ndim != 2:
        raise ValueError(f"{path.name} must be 2D; received shape {vectors.shape}")

    rows, dimensions = map(int, vectors.shape)
    expected_shape = (int(manifest["rows"]), int(manifest["dimensions"]))
    if (rows, dimensions) != expected_shape:
        raise ValueError(
            f"{path.name} shape {(rows, dimensions)} does not match manifest {expected_shape}"
        )
    if not np.issubdtype(vectors.dtype, np.floating):
        raise ValueError(f"{path.name} must contain floating-point vectors, got {vectors.dtype}")

    normalized = bool(manifest["normalized"])
    minimum_norm = float("inf")
    maximum_norm = 0.0
    for start in range(0, rows, BLOCK_SIZE):
        block = np.asarray(vectors[start : start + BLOCK_SIZE])
        if not np.isfinite(block).all():
            bad = np.argwhere(~np.isfinite(block))[0]
            raise ValueError(
                f"Non-finite value in {path.name} at row {start + int(bad[0])}, "
                f"dimension {int(bad[1])}"
            )
        norms = np.linalg.norm(block, axis=1)
        if np.any(norms == 0):
            first = int(np.flatnonzero(norms == 0)[0])
            raise ValueError(f"Zero vector in {path.name} at row {start + first}")
        minimum_norm = min(minimum_norm, float(norms.min()))
        maximum_norm = max(maximum_norm, float(norms.max()))
        if normalized and not np.allclose(norms, 1.0, rtol=1e-4, atol=1e-4):
            first = int(np.flatnonzero(~np.isclose(norms, 1.0, rtol=1e-4, atol=1e-4))[0])
            raise ValueError(
                f"Expected normalized vectors in {path.name}; row {start + first} "
                f"has norm {float(norms[first]):.6f}"
            )

    print(f"✓ Shape: ({rows:,}, {dimensions})")
    print(f"✓ Floating dtype: {vectors.dtype}")
    print("✓ All values finite; no zero vectors")
    print(f"✓ Vector norm range: {minimum_norm:.6f}–{maximum_norm:.6f}")
    if normalized:
        print("✓ L2 normalization matches manifest")
    return rows, dimensions


def validate_source_counts(manifest: dict, sources: Counter[str]) -> None:
    expected = manifest.get("input_sources")
    if expected is None:
        return
    expected = {str(key): int(value) for key, value in expected.items()}
    if dict(sources) != expected:
        raise ValueError(
            f"Metadata source counts {dict(sources)} do not match manifest {expected}"
        )
    print("✓ Source counts match manifest")


def validate_dataset(base: Path, config: dict) -> None:
    print("\n" + "=" * 64)
    print(config["title"])
    print("=" * 64)
    manifest = load_manifest(base / config["manifest"], config["expected_model"])
    metadata_rows, sources = validate_metadata(
        base / config["metadata"], config["id_column"], config["required_columns"]
    )
    vector_rows, _ = validate_vectors(base / config["embeddings"], manifest)
    if vector_rows != metadata_rows:
        raise ValueError(
            f"Row mismatch: {vector_rows:,} embeddings vs {metadata_rows:,} metadata rows"
        )
    print("✓ Embedding and metadata rows align")
    validate_source_counts(manifest, sources)
    print(f"✓ {config['title']} PASSED")


def check_incomplete_artifacts(base: Path) -> None:
    incomplete = [
        base / "text_embeddings.tmp.npy",
        base / "image_embeddings.tmp.npy",
        base / "image_embeddings_checkpoint.json",
    ]
    present = [path.name for path in incomplete if path.exists()]
    if present:
        raise RuntimeError(
            "Incomplete embedding artifacts are present: " + ", ".join(present)
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--only", choices=["text", "image"], help="Validate one dataset")
    args = parser.parse_args()

    check_incomplete_artifacts(args.base)
    selected = [args.only] if args.only else ["text", "image"]
    for name in selected:
        validate_dataset(args.base, DATASETS[name])

    print("\n" + "=" * 64)
    print("ALL SELECTED EMBEDDINGS ARE VALID")
    print("=" * 64)


if __name__ == "__main__":
    main()
