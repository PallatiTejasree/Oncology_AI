"""Paths and defaults for retrieval evaluation."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVALUATION_DIR = PROJECT_ROOT / "Evaluation"
DATA_DIR = EVALUATION_DIR / "data"
OUTPUT_DIR = EVALUATION_DIR / "outputs"

CASES_FILE = DATA_DIR / "cases.csv"
QRELS_FILE = DATA_DIR / "qrels.csv"
DEFAULT_K_VALUES = (1, 3, 5, 10)
