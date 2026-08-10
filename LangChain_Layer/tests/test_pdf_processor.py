from pathlib import Path
from ingestion.pdf_processor import PDFProcessor

reports = sorted(Path("sample_files/Reports").glob("*.pdf"))

print(f"\nFound {len(reports)} PDF(s)\n")

for pdf in reports:

    print("=" * 80)
    print(pdf.name)
    print("=" * 80)

    result = PDFProcessor.extract(str(pdf))

    print(f"Pages      : {result['total_pages']}")
    print(f"Characters : {len(result['text'])}")
    print(f"Images     : {len(result['images'])}")

    print("\nFirst 5 Images:\n")

    for image in result["images"][:5]:
        print(image)

    print()