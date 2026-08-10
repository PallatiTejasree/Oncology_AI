from pathlib import Path

# --------------------------------------------------
# Project Root
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------
# Dataset Locations
# --------------------------------------------------

DOWNLOADS_DIR = PROJECT_ROOT / "Dataset_Downloader" / "downloads"

PROCESSED_DATASET_DIR = PROJECT_ROOT / "Ingestion" / "processed_dataset"

PARSED_JSON_DIR = PROCESSED_DATASET_DIR / "parsed_json"

MEDICAL_IMAGES_DIR = PROCESSED_DATASET_DIR / "medical_images"

FILTERED_IMAGES_DIR = PROCESSED_DATASET_DIR / "filtered_images"

UNIQUE_IMAGES_DIR = PROCESSED_DATASET_DIR / "unique_images"

REJECTED_IMAGES_DIR = PROCESSED_DATASET_DIR / "rejected_images"

IMAGE_METADATA_CSV = PROCESSED_DATASET_DIR / "image_metadata.csv"

DEDUPLICATION_CSV = PROCESSED_DATASET_DIR / "duplicate_images.csv"

# --------------------------------------------------
# Create directories automatically
# --------------------------------------------------

for directory in [
    PROCESSED_DATASET_DIR,
    PARSED_JSON_DIR,
    MEDICAL_IMAGES_DIR,
    FILTERED_IMAGES_DIR,
    UNIQUE_IMAGES_DIR,
    REJECTED_IMAGES_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)
