"""Compatibility entry point for the canonical medical-image filter."""

from Ingestion.Preprocessing.medical_image_filter import (
    classify_caption,
    is_medical_caption,
    process_dataset,
)

should_keep = is_medical_caption


if __name__ == "__main__":
    print(process_dataset())
