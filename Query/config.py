"""Configuration shared by the oncology retrieval pipeline."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHROMA_DB_PATH = PROJECT_ROOT / "Ingestion" / "chroma_db"

TEXT_COLLECTION = "oncology_text_embeddings"
IMAGE_COLLECTION = "oncology_image_embeddings"

TEXT_QUERY_MODEL = "ncbi/MedCPT-Query-Encoder"
IMAGE_QUERY_MODEL = "hf-hub:microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224"

TEXT_EMBEDDING_DIM = 768
IMAGE_EMBEDDING_DIM = 512

DEFAULT_TOP_K = 5
MAX_TOP_K = 50
DEFAULT_FUSION_K = 60
HYBRID_TEXT_WEIGHT = 1.0
HYBRID_IMAGE_WEIGHT = 1.25
TEXT_LEXICAL_WEIGHT = 1.5
TEXT_SEMANTIC_WEIGHT = 1.0
TEXT_TO_IMAGE_MIN_COSINE_SCORE = 0.30


def select_device(requested: str = "auto") -> str:
    import torch

    if requested != "auto":
        return requested
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"
