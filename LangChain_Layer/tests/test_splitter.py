from ingestion.metadata_extractor import PDFMetadataExtractor
from ingestion.pdf_processor import PDFProcessor
from ingestion.image_filter import ImageFilter
from ingestion.document_builder import MedicalDocumentBuilder
from ingestion.text_cleaner import MedicalTextCleaner
from ingestion.splitter import MedicalDocumentSplitter
from ocr.extractor import OCRExtractor

pdf_path = "sample_files/Reports/report_1.pdf"

# Metadata
metadata = PDFMetadataExtractor.extract(pdf_path)

# PDF
pdf = PDFProcessor.extract(pdf_path)

# Images
filtered = ImageFilter.filter_images(pdf["images"])

# OCR
ocr = OCRExtractor()

ocr_results = []

for image in filtered["accepted"]:
    ocr_results.append(
        ocr.extract(image["image_path"])
    )

# Build medical document
document = MedicalDocumentBuilder.build(
    metadata,
    pdf,
    ocr_results
)

# Clean text
clean_text = MedicalTextCleaner.clean(
    document["combined_text"]
)

# Split document
splitter = MedicalDocumentSplitter()

chunks = splitter.split(clean_text)

print("\n" + "=" * 80)
print("MEDICAL DOCUMENT SPLITTER")
print("=" * 80)

print(f"\nTotal Chunks : {len(chunks)}\n")

for chunk in chunks:

    print("-" * 80)

    print(f"Chunk ID   : {chunk['chunk_id']}")
    print(f"Characters : {chunk['characters']}")
    print(f"Words      : {chunk['words']}")

    print("\nPreview:\n")

    print(chunk["text"][:250])

    print()