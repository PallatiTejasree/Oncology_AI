"""
Configuration for ChromaDB ingestion.
"""

from pathlib import Path

# ----------------------------------------------------
# Project Paths
# ----------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATASET_DIR = PROJECT_ROOT / "Ingestion" / "datasets" / "embeddings"

TEXT_EMBEDDINGS = DATASET_DIR / "text_embeddings.npy"
TEXT_METADATA = DATASET_DIR / "text_metadata.csv"
TEXT_DOCUMENTS = PROJECT_ROOT / "Ingestion" / "datasets" / "processed" / "chunk_metadata.csv"
TEXT_MANIFEST = DATASET_DIR / "text_embeddings_manifest.json"

IMAGE_EMBEDDINGS = DATASET_DIR / "image_embeddings.npy"
IMAGE_METADATA = DATASET_DIR / "image_embedding_metadata.csv"
IMAGE_MANIFEST = DATASET_DIR / "image_embeddings_manifest.json"

# ----------------------------------------------------
# Collection Names
# ----------------------------------------------------

TEXT_COLLECTION = "oncology_text_embeddings"
IMAGE_COLLECTION = "oncology_image_embeddings"

TEXT_DISTANCE = "ip"
IMAGE_DISTANCE = "cosine"
IMAGE_EF_SEARCH = 1000

# ----------------------------------------------------
# Batch Size
# ----------------------------------------------------

BATCH_SIZE = 500
