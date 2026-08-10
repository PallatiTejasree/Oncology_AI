import os
import pandas as pd

# =====================================================
# Paths
# =====================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

METADATA_PATH = os.path.join(
    BASE_DIR,
    "datasets",
    "images",
    "oncology_metadata.csv",
)

IMAGE_FOLDER = os.path.join(
    BASE_DIR,
    "datasets",
    "images",
    "oncology_images",
)

OUTPUT_DIR = os.path.join(
    BASE_DIR,
    "datasets",
    "processed",
)

os.makedirs(OUTPUT_DIR, exist_ok=True)

OUTPUT_PATH = os.path.join(
    OUTPUT_DIR,
    "clean_image_metadata.csv",
)

# =====================================================
# Load Metadata
# =====================================================

print("=" * 60)
print("Loading Oncology Image Metadata...")
print("=" * 60)

metadata_df = pd.read_csv(METADATA_PATH)

print(f"Total Records : {len(metadata_df):,}")

print("\nColumns")

print(metadata_df.columns.tolist())

print("\nPreview")

print(metadata_df.head())