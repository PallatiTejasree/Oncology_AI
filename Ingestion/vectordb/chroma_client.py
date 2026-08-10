"""
chroma_client.py

Creates and returns a persistent ChromaDB client.
"""

import chromadb
from chromadb.config import Settings
from pathlib import Path


# --------------------------------------------------
# Project paths
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CHROMA_DB_PATH = PROJECT_ROOT / "Ingestion" / "chroma_db"

_client = None


def get_client():
    """Return a lazily-created persistent ChromaDB client."""
    global _client
    if _client is None:
        CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=str(CHROMA_DB_PATH),
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


if __name__ == "__main__":
    print("=" * 60)
    print("ChromaDB Client")
    print("=" * 60)
    print(f"Database Path : {CHROMA_DB_PATH}")
    print("Status        : Connected Successfully")
