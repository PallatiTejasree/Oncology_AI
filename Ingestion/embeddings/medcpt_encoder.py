"""Generate MedCPT document embeddings for the unified chunk dataset."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from tqdm import tqdm
from transformers import AutoModel, AutoTokenizer


INGESTION_DIR = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = INGESTION_DIR / "datasets" / "processed" / "chunk_metadata.csv"
DEFAULT_OUTPUT_DIR = INGESTION_DIR / "datasets" / "embeddings"
MODEL_NAME = "ncbi/MedCPT-Article-Encoder"
REQUIRED_COLUMNS = {"chunk_id", "text"}


def select_device(requested: str = "auto") -> torch.device:
    """Select CUDA, Apple Silicon MPS, or CPU."""
    if requested != "auto":
        return torch.device(requested)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def load_chunks(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Chunk file not found: {path}")

    # Keep identifiers such as patient IDs as strings and avoid accidental NaN
    # values in tokenizer input or saved metadata.
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(f"Chunk file is missing columns: {sorted(missing)}")
    if frame.empty:
        raise ValueError("Chunk file contains no rows")
    if frame["chunk_id"].duplicated().any():
        raise ValueError("chunk_id values must be unique")
    if frame["text"].str.strip().eq("").any():
        raise ValueError("Chunk file contains empty text")
    return frame


def build_titles(frame: pd.DataFrame) -> list[str]:
    """Build the title side of MedCPT's title/text document input pair."""
    titles: list[str] = []
    for row in frame.to_dict("records"):
        section = row.get("section") or row.get("source_type") or "medical document"
        cancer_type = row.get("cancer_type")
        title = section.replace("_", " ").strip()
        if cancer_type and cancer_type.lower() != "unknown":
            title = f"{cancer_type.replace('|', ', ')} — {title}"
        titles.append(title)
    return titles


def encode_chunks(
    input_csv: Path = DEFAULT_INPUT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    batch_size: int = 32,
    max_length: int = 512,
    device_name: str = "auto",
    normalize: bool = False,
) -> tuple[Path, Path, Path]:
    """Encode every chunk and save aligned embeddings, metadata, and manifest."""
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")
    if max_length <= 0:
        raise ValueError("max_length must be greater than zero")

    frame = load_chunks(input_csv)
    titles = build_titles(frame)
    texts = frame["text"].tolist()
    device = select_device(device_name)

    print(f"Loading {MODEL_NAME}")
    print(f"Device: {device}")
    print(f"Chunks: {len(frame):,}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModel.from_pretrained(MODEL_NAME).to(device)
    model.eval()

    hidden_size = int(model.config.hidden_size)
    output_dir.mkdir(parents=True, exist_ok=True)
    embeddings_file = output_dir / "text_embeddings.npy"
    metadata_file = output_dir / "text_metadata.csv"
    manifest_file = output_dir / "text_embeddings_manifest.json"
    temporary_file = output_dir / "text_embeddings.tmp.npy"

    # A memory-mapped array avoids retaining every batch in RAM and then making
    # a second full copy with np.vstack().
    embeddings = np.lib.format.open_memmap(
        temporary_file,
        mode="w+",
        dtype=np.float32,
        shape=(len(frame), hidden_size),
    )

    try:
        with torch.inference_mode():
            for start in tqdm(range(0, len(frame), batch_size), desc="MedCPT"):
                end = min(start + batch_size, len(frame))
                encoded = tokenizer(
                    titles[start:end],
                    texts[start:end],
                    padding=True,
                    truncation=True,
                    max_length=max_length,
                    return_tensors="pt",
                )
                encoded = {name: tensor.to(device) for name, tensor in encoded.items()}
                batch_embeddings = model(**encoded).last_hidden_state[:, 0, :]
                if normalize:
                    batch_embeddings = torch.nn.functional.normalize(
                        batch_embeddings, p=2, dim=1
                    )
                embeddings[start:end] = batch_embeddings.float().cpu().numpy()

        embeddings.flush()
        del embeddings
        os.replace(temporary_file, embeddings_file)
    except BaseException:
        # Do not leave an apparently complete embedding file after interruption.
        del embeddings
        temporary_file.unlink(missing_ok=True)
        raise

    metadata_columns = [column for column in frame.columns if column != "text"]
    frame[metadata_columns].to_csv(metadata_file, index=False)
    manifest = {
        "model": MODEL_NAME,
        "input_file": str(input_csv.resolve()),
        "embeddings_file": str(embeddings_file.resolve()),
        "metadata_file": str(metadata_file.resolve()),
        "rows": len(frame),
        "dimensions": hidden_size,
        "batch_size": batch_size,
        "max_length": max_length,
        "normalized": normalize,
        "similarity": "cosine" if normalize else "dot_product",
        "document_input": "title_text_pair",
    }
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Embedding shape: ({len(frame)}, {hidden_size})")
    print(f"Embeddings: {embeddings_file}")
    print(f"Metadata: {metadata_file}")
    print(f"Manifest: {manifest_file}")
    return embeddings_file, metadata_file, manifest_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--device", default="auto", help="auto, cpu, cuda, or mps")
    parser.add_argument(
        "--normalize",
        action="store_true",
        help="L2-normalize embeddings for cosine retrieval; queries must match",
    )
    args = parser.parse_args()
    encode_chunks(
        input_csv=args.input,
        output_dir=args.output_dir,
        batch_size=args.batch_size,
        max_length=args.max_length,
        device_name=args.device,
        normalize=args.normalize,
    )


if __name__ == "__main__":
    main()
