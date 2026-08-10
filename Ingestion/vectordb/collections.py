"""Create Chroma collections with model-compatible distance metrics."""

from __future__ import annotations

from Ingestion.vectordb.chroma_client import get_client
from Ingestion.vectordb.config import (
    IMAGE_COLLECTION,
    IMAGE_DISTANCE,
    IMAGE_EF_SEARCH,
    TEXT_COLLECTION,
    TEXT_DISTANCE,
)


COLLECTIONS = {
    "text": {
        "name": TEXT_COLLECTION,
        "space": TEXT_DISTANCE,
        "description": "MedCPT oncology clinical text embeddings",
        "model": "ncbi/MedCPT-Article-Encoder",
    },
    "image": {
        "name": IMAGE_COLLECTION,
        "space": IMAGE_DISTANCE,
        "ef_search": IMAGE_EF_SEARCH,
        "description": "BiomedCLIP mixed oncology image embeddings",
        "model": "microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224",
    },
}


def collection_space(collection) -> str | None:
    configuration = getattr(collection, "configuration", {}) or {}
    return (configuration.get("hnsw") or {}).get("space")


def get_or_create_collection(kind: str, reset: bool = False):
    """Return a correctly configured collection.

    An empty collection with an old/wrong metric is safely recreated. A
    populated incompatible collection is never deleted without ``reset``.
    """
    if kind not in COLLECTIONS:
        raise ValueError(f"Unknown collection kind: {kind}")
    config = COLLECTIONS[kind]
    client = get_client()

    try:
        existing = client.get_collection(config["name"], embedding_function=None)
    except Exception:
        existing = None

    if existing is not None:
        wrong_space = collection_space(existing) != config["space"]
        if reset or (wrong_space and existing.count() == 0):
            client.delete_collection(config["name"])
            existing = None
        elif wrong_space:
            raise RuntimeError(
                f"Collection {config['name']} uses {collection_space(existing)!r}, "
                f"but {config['space']!r} is required. Re-run with --reset to rebuild it."
            )

    if existing is not None:
        return existing
    return client.create_collection(
        name=config["name"],
        configuration={
            "hnsw": {
                "space": config["space"],
                **(
                    {"ef_search": config["ef_search"]}
                    if "ef_search" in config
                    else {}
                ),
            }
        },
        metadata={
            "description": config["description"],
            "model": config["model"],
            "distance": config["space"],
        },
        embedding_function=None,
    )


def create_collections(reset: bool = False):
    return (
        get_or_create_collection("text", reset=reset),
        get_or_create_collection("image", reset=reset),
    )


if __name__ == "__main__":
    text, image = create_collections()
    print(f"Text: {text.name} ({collection_space(text)})")
    print(f"Image: {image.name} ({collection_space(image)})")
