"""Verify Chroma collection configuration, counts, metadata, and querying."""

from __future__ import annotations

import json

from Ingestion.vectordb.chroma_client import get_client
from Ingestion.vectordb.collections import COLLECTIONS, collection_space
from Ingestion.vectordb.config import IMAGE_EF_SEARCH, IMAGE_MANIFEST, TEXT_MANIFEST


MANIFESTS = {"text": TEXT_MANIFEST, "image": IMAGE_MANIFEST}
ID_FIELDS = {"text": "chunk_id", "image": "image_id"}


def verify_collection(kind: str) -> None:
    config = COLLECTIONS[kind]
    manifest = json.loads(MANIFESTS[kind].read_text(encoding="utf-8"))
    collection = get_client().get_collection(config["name"], embedding_function=None)
    expected_count = int(manifest["rows"])
    count = collection.count()

    print("=" * 70)
    print(f"{kind.upper()}: {collection.name}")
    print("=" * 70)
    if collection_space(collection) != config["space"]:
        raise ValueError(
            f"Wrong distance metric: {collection_space(collection)!r}; "
            f"expected {config['space']!r}"
        )
    print(f"✓ Distance metric: {config['space']}")
    if kind == "image":
        actual_ef = (collection.configuration.get("hnsw") or {}).get("ef_search")
        if actual_ef != IMAGE_EF_SEARCH:
            raise ValueError(
                f"Wrong image ef_search: {actual_ef}; expected {IMAGE_EF_SEARCH}"
            )
        print(f"✓ HNSW ef_search: {actual_ef}")
    if count != expected_count:
        raise ValueError(f"Wrong vector count: {count:,}; expected {expected_count:,}")
    print(f"✓ Vector count: {count:,}")

    sample = collection.peek(limit=1)
    if not sample["ids"]:
        raise ValueError("Collection unexpectedly returned no sample")
    identifier = sample["ids"][0]
    metadata = sample["metadatas"][0]
    if metadata.get(ID_FIELDS[kind]) != identifier:
        raise ValueError(
            f"Stored metadata {ID_FIELDS[kind]} does not match Chroma ID {identifier}"
        )
    if not sample["documents"][0]:
        raise ValueError(f"Stored document is empty for {identifier}")
    print(f"✓ Sample ID and metadata align: {identifier}")

    stored = collection.get(ids=[identifier], include=["embeddings"])
    result = collection.query(
        query_embeddings=[stored["embeddings"][0]],
        n_results=1,
        include=["distances"],
    )
    if not result["ids"] or not result["ids"][0]:
        raise ValueError("Vector query returned no results")
    print(f"✓ Vector query works; nearest ID: {result['ids'][0][0]}")


def main() -> None:
    for kind in ("text", "image"):
        verify_collection(kind)
    print("\nALL CHROMA COLLECTIONS ARE VALID")


if __name__ == "__main__":
    main()
