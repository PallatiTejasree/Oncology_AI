"""Backward-compatible entry point; text ingestion now lives in insert_text."""

from Ingestion.vectordb.insert_text import main


if __name__ == "__main__":
    main()
