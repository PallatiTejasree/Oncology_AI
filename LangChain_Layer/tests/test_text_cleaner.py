from ingestion.metadata_extractor import PDFMetadataExtractor
from ingestion.pdf_processor import PDFProcessor
from ingestion.image_filter import ImageFilter
from ingestion.document_builder import MedicalDocumentBuilder
from ingestion.text_cleaner import MedicalTextCleaner
from ocr.extractor import OCRExtractor

pdf_path = "sample_files/Reports/report_1.pdf"

metadata = PDFMetadataExtractor.extract(pdf_path)

pdf = PDFProcessor.extract(pdf_path)

filtered = ImageFilter.filter_images(pdf["images"])

ocr = OCRExtractor()

ocr_results = []

for image in filtered["accepted"]:

    ocr_results.append(
        ocr.extract(image["image_path"])
    )

document = MedicalDocumentBuilder.build(
    metadata,
    pdf,
    ocr_results
)

clean_text = MedicalTextCleaner.clean(
    document["combined_text"]
)

print("=" * 80)
print("CLEAN MEDICAL DOCUMENT")
print("=" * 80)

print()

print(clean_text[:1500])