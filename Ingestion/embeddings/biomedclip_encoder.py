"""Generate BiomedCLIP embeddings for the project's 2D oncology images."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Iterable

import numpy as np


INGESTION_DIR = Path(__file__).resolve().parent.parent
PMC_METADATA = INGESTION_DIR / "processed_dataset" / "image_metadata.csv"
LEGACY_METADATA = INGESTION_DIR / "datasets" / "images" / "oncology_metadata.csv"
DEFAULT_OUTPUT_DIR = INGESTION_DIR / "datasets" / "embeddings"
MODEL_ID = "hf-hub:microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224"

OUTPUT_FIELDS = [
    "image_id",
    "source_dataset",
    "pmcid",
    "cancer_type",
    "caption",
    "image_path",
    "width",
    "height",
    "format",
    "sha256",
]


def select_device(requested: str = "auto") -> str:
    import torch

    if requested != "auto":
        return requested
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _normalise_record(record: dict[str, str]) -> dict[str, str]:
    return {field: str(record.get(field) or "") for field in OUTPUT_FIELDS}


def _load_pmc_records() -> Iterable[dict[str, str]]:
    if not PMC_METADATA.exists():
        return
    with PMC_METADATA.open(newline="", encoding="utf-8", errors="replace") as handle:
        for row in csv.DictReader(handle):
            if (row.get("accepted") or "").lower() != "true":
                continue
            yield _normalise_record(
                {
                    **row,
                    "source_dataset": "pmc_medical_images",
                    "cancer_type": row.get("cancer_types") or "unknown",
                }
            )


def _load_legacy_records() -> Iterable[dict[str, str]]:
    if not LEGACY_METADATA.exists():
        return
    with LEGACY_METADATA.open(newline="", encoding="utf-8", errors="replace") as handle:
        for row_number, row in enumerate(csv.DictReader(handle), start=1):
            original_id = row.get("image") or f"image_{row_number}"
            yield _normalise_record(
                {
                    **row,
                    "image_id": f"oncology:{original_id}",
                    "source_dataset": "oncology_images",
                    "cancer_type": "unknown",
                }
            )


def load_image_records(include_legacy: bool = True, limit: int | None = None) -> list[dict[str, str]]:
    """Load PMC accepted images and, by default, the legacy oncology collection."""
    records = list(_load_pmc_records())
    if include_legacy:
        records.extend(_load_legacy_records())
    if limit is not None:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        records = records[:limit]
    if not records:
        raise ValueError("No image records were found")

    ids = [record["image_id"] for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("image_id values must be unique")
    missing = [record["image_id"] for record in records if not Path(record["image_path"]).is_file()]
    if missing:
        raise FileNotFoundError(
            f"{len(missing)} image files are missing; first IDs: {', '.join(missing[:5])}"
        )
    return records


def validate_image_records(
    records: list[dict[str, str]], failures_file: Path
) -> list[dict[str, str]]:
    """Remove corrupt/empty images before the expensive model run."""
    from PIL import Image
    from tqdm import tqdm

    valid: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    for record in tqdm(records, desc="Validating images"):
        path = Path(record["image_path"])
        try:
            if path.stat().st_size == 0:
                raise ValueError("empty file (0 bytes)")
            with Image.open(path) as image:
                image.verify()
            valid.append(record)
        except Exception as error:
            failures.append(
                {
                    "image_id": record["image_id"],
                    "image_path": record["image_path"],
                    "reason": f"{type(error).__name__}: {error}",
                }
            )

    temporary = failures_file.with_suffix(failures_file.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image_id", "image_path", "reason"])
        writer.writeheader()
        writer.writerows(failures)
    os.replace(temporary, failures_file)
    if not valid:
        raise ValueError("All selected images failed validation")
    print(f"Valid images: {len(valid):,}; rejected corrupt images: {len(failures):,}")
    return valid


def load_model(device: str):
    """Load BiomedCLIP and its model-specific image preprocessing."""
    try:
        import open_clip
    except ImportError as error:
        raise RuntimeError(
            "open_clip is not installed. Run `pip install -r requirements.txt`."
        ) from error

    model, preprocess = open_clip.create_model_from_pretrained(MODEL_ID)
    model = model.to(device)
    model.eval()
    return model, preprocess


def _load_batch(records: list[dict[str, str]], preprocess):
    import torch
    from PIL import Image

    tensors = []
    for record in records:
        try:
            with Image.open(record["image_path"]) as image:
                tensors.append(preprocess(image.convert("RGB")))
        except Exception as error:
            raise RuntimeError(
                f"Cannot preprocess {record['image_id']} at {record['image_path']}"
            ) from error
    return torch.stack(tensors)


def _write_metadata(path: Path, records: list[dict[str, str]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(records)
    os.replace(temporary, path)


def _write_json_atomic(path: Path, data: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def encode_images(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    batch_size: int = 32,
    device_name: str = "auto",
    normalize: bool = True,
    include_legacy: bool = True,
    limit: int | None = None,
) -> tuple[Path, Path, Path]:
    """Encode all selected images and save row-aligned vectors and metadata."""
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")

    import torch
    from tqdm import tqdm

    records = load_image_records(include_legacy=include_legacy, limit=limit)
    device = select_device(device_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    embeddings_file = output_dir / "image_embeddings.npy"
    metadata_file = output_dir / "image_embedding_metadata.csv"
    manifest_file = output_dir / "image_embeddings_manifest.json"
    temporary_embeddings = output_dir / "image_embeddings.tmp.npy"
    checkpoint_file = output_dir / "image_embeddings_checkpoint.json"
    failures_file = output_dir / "image_embedding_failures.csv"

    records = validate_image_records(records, failures_file)

    source_counts: dict[str, int] = {}
    for record in records:
        source = record["source_dataset"]
        source_counts[source] = source_counts.get(source, 0) + 1

    print(f"Loading {MODEL_ID}")
    print(f"Device: {device}")
    print(f"Images: {len(records):,} ({source_counts})")
    model, preprocess = load_model(device)

    embeddings = None
    dimensions = 0
    start_index = 0
    try:
        with torch.inference_mode():
            if temporary_embeddings.exists() and checkpoint_file.exists():
                checkpoint = json.loads(checkpoint_file.read_text(encoding="utf-8"))
                expected = {
                    "model": MODEL_ID,
                    "rows": len(records),
                    "normalized": normalize,
                    "first_image_id": records[0]["image_id"],
                    "last_image_id": records[-1]["image_id"],
                }
                if all(checkpoint.get(key) == value for key, value in expected.items()):
                    embeddings = np.load(temporary_embeddings, mmap_mode="r+")
                    dimensions = int(embeddings.shape[1])
                    start_index = int(checkpoint.get("next_index", 0))
                    print(f"Resuming from image {start_index:,}/{len(records):,}")
                else:
                    raise RuntimeError(
                        "An incompatible embedding checkpoint exists. Remove "
                        f"{temporary_embeddings.name} and {checkpoint_file.name}, then retry."
                    )

            for start in tqdm(
                range(start_index, len(records), batch_size),
                desc="BiomedCLIP",
                initial=start_index // batch_size,
                total=(len(records) + batch_size - 1) // batch_size,
            ):
                end = min(start + batch_size, len(records))
                images = _load_batch(records[start:end], preprocess).to(device)
                vectors = model.encode_image(images)
                if normalize:
                    vectors = torch.nn.functional.normalize(vectors, p=2, dim=1)
                vectors = vectors.float().cpu().numpy()

                if embeddings is None:
                    dimensions = int(vectors.shape[1])
                    embeddings = np.lib.format.open_memmap(
                        temporary_embeddings,
                        mode="w+",
                        dtype=np.float32,
                        shape=(len(records), dimensions),
                    )
                if vectors.ndim != 2 or vectors.shape[1] != dimensions:
                    raise ValueError(f"Unexpected embedding shape: {vectors.shape}")
                if not np.isfinite(vectors).all():
                    raise ValueError(f"Non-finite embedding in rows {start}:{end}")
                embeddings[start:end] = vectors

                embeddings.flush()
                _write_json_atomic(
                    checkpoint_file,
                    {
                        "model": MODEL_ID,
                        "rows": len(records),
                        "dimensions": dimensions,
                        "normalized": normalize,
                        "first_image_id": records[0]["image_id"],
                        "last_image_id": records[-1]["image_id"],
                        "next_index": end,
                    },
                )

        if embeddings is None:
            raise RuntimeError("No embeddings were generated")
        embeddings.flush()
        del embeddings
        embeddings = None
        os.replace(temporary_embeddings, embeddings_file)
    except BaseException:
        if embeddings is not None:
            embeddings.flush()
            del embeddings
        print(
            "Embedding stopped. The temporary embeddings and checkpoint were "
            "preserved; run the same command to resume."
        )
        raise

    _write_metadata(metadata_file, records)
    checkpoint_file.unlink(missing_ok=True)
    manifest = {
        "model": MODEL_ID,
        "input_sources": source_counts,
        "embeddings_file": str(embeddings_file.resolve()),
        "metadata_file": str(metadata_file.resolve()),
        "rows": len(records),
        "dimensions": dimensions,
        "batch_size": batch_size,
        "normalized": normalize,
        "similarity": "cosine" if normalize else "dot_product",
        "note": "Legacy oncology images have unknown labels because their source captions are empty.",
        "failures_file": str(failures_file.resolve()),
    }
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Embedding shape: ({len(records)}, {dimensions})")
    print(f"Embeddings: {embeddings_file}")
    print(f"Metadata: {metadata_file}")
    print(f"Manifest: {manifest_file}")
    return embeddings_file, metadata_file, manifest_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--device", default="auto", help="auto, cpu, cuda, or mps")
    parser.add_argument("--exclude-legacy", action="store_true")
    parser.add_argument("--limit", type=int, help="Encode only the first N images for a test run")
    parser.add_argument(
        "--no-normalize",
        action="store_true",
        help="Keep raw vectors instead of cosine-ready normalized vectors",
    )
    args = parser.parse_args()
    encode_images(
        output_dir=args.output_dir,
        batch_size=args.batch_size,
        device_name=args.device,
        normalize=not args.no_normalize,
        include_legacy=not args.exclude_legacy,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
