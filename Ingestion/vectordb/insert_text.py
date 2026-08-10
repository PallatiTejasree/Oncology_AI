"""Insert validated MedCPT text vectors and chunk documents into ChromaDB."""

from __future__ import annotations

import argparse

from tqdm import tqdm

from Ingestion.vectordb.collections import get_or_create_collection
from Ingestion.vectordb.config import (
    BATCH_SIZE,
    TEXT_COLLECTION,
    TEXT_DOCUMENTS,
    TEXT_EMBEDDINGS,
    TEXT_MANIFEST,
    TEXT_METADATA,
)
from Ingestion.vectordb.ingestion_utils import (
    aligned_text_batches,
    checkpoint_start,
    clean_metadata,
    load_artifacts,
    write_checkpoint,
)


def insert_text(batch_size: int = BATCH_SIZE, reset: bool = False) -> int:
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")
    embeddings, manifest = load_artifacts(TEXT_EMBEDDINGS, TEXT_METADATA, TEXT_MANIFEST)
    collection = get_or_create_collection("text", reset=reset)
    checkpoint = TEXT_EMBEDDINGS.parent / "chroma_text_checkpoint.json"
    if reset:
        checkpoint.unlink(missing_ok=True)
    signature = {
        "collection": TEXT_COLLECTION,
        "rows": int(manifest["rows"]),
        "dimensions": int(manifest["dimensions"]),
        "model": manifest["model"],
    }
    start_index = checkpoint_start(checkpoint, signature)
    if collection.count() < start_index:
        print("Checkpoint is ahead of the collection; restarting safe upserts from row 0")
        start_index = 0
        checkpoint.unlink(missing_ok=True)
    if collection.count() == len(embeddings) and start_index == 0:
        print(f"Text collection already complete: {collection.count():,} vectors")
        return collection.count()
    print(f"Text vectors: {len(embeddings):,}; resuming at: {start_index:,}")

    offset = 0
    batches = aligned_text_batches(TEXT_METADATA, TEXT_DOCUMENTS, batch_size)
    for batch in tqdm(batches, total=(len(embeddings) + batch_size - 1) // batch_size, desc="Chroma text"):
        end = offset + len(batch)
        if end <= start_index:
            offset = end
            continue
        if offset < start_index:
            batch = batch[start_index - offset :]
            offset = start_index
            end = offset + len(batch)

        rows = [item[0] for item in batch]
        collection.upsert(
            ids=[row["chunk_id"] for row in rows],
            embeddings=embeddings[offset:end],
            metadatas=[clean_metadata(row, {"chunk_index"}) for row in rows],
            documents=[item[1] for item in batch],
        )
        offset = end
        write_checkpoint(checkpoint, signature, offset)

    if offset != len(embeddings):
        raise ValueError(f"Inserted input rows {offset:,}, expected {len(embeddings):,}")
    count = collection.count()
    if count != len(embeddings):
        raise ValueError(f"Collection contains {count:,}, expected {len(embeddings):,}")
    checkpoint.unlink(missing_ok=True)
    print(f"Text collection complete: {count:,} vectors")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--reset", action="store_true", help="Delete and rebuild text collection")
    args = parser.parse_args()
    insert_text(args.batch_size, args.reset)


if __name__ == "__main__":
    main()
