from pathlib import Path

from ocr.extractor import OCRExtractor

ocr = OCRExtractor()

images = sorted(
    Path("sample_files/extracted_images").glob("*.png")
)

print(f"\nFound {len(images)} images\n")

for image in images[:3]:

    print("=" * 80)

    print(image.name)

    result = ocr.extract(str(image))

    print(f"Confidence : {result['ocr_confidence']}")

    print(f"Time : {result['processing_time']} sec")

    print("\nOCR TEXT:\n")

    print(result["ocr_text"][:500])

    print()