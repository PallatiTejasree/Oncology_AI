from pathlib import Path
from collections import Counter

from ingestion.pdf_processor import PDFProcessor
from ingestion.image_filter import ImageFilter

reports = sorted(Path("sample_files/Reports").glob("*.pdf"))

for pdf in reports:

    print("=" * 80)
    print(pdf.name)
    print("=" * 80)

    result = PDFProcessor.extract(str(pdf))

    filtered = ImageFilter.filter_images(result["images"])

    print(f"Original Images : {len(result['images'])}")
    print(f"Accepted Images : {len(filtered['accepted'])}")
    print(f"Rejected Images : {len(filtered['rejected'])}")

    reasons = Counter()

    for item in filtered["rejected"]:
        reasons[item["reason"]] += 1

    print("\nRejection Summary")

    for reason, count in reasons.items():
        print(f"{reason}: {count}")

    print()