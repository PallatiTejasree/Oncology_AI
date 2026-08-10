from ingestion.metadata_extractor import PDFMetadataExtractor
from ingestion.pdf_processor import PDFProcessor
from ingestion.image_filter import ImageFilter
from ingestion.document_builder import MedicalDocumentBuilder
from ocr.extractor import OCRExtractor

pdf_path = "sample_files/Reports/report_1.pdf"

metadata = PDFMetadataExtractor.extract(pdf_path)

pdf = PDFProcessor.extract(pdf_path)

filtered = ImageFilter.filter_images(pdf["images"])

ocr = OCRExtractor()

ocr_results = []

for image in filtered["accepted"]:

    result = ocr.extract(image["image_path"])

    ocr_results.append(result)

document = MedicalDocumentBuilder.build(

    metadata,

    pdf,

    ocr_results

)

print("=" * 80)

print("DOCUMENT CREATED")

print("=" * 80)

print()

print(document["statistics"])

print()

print(document["combined_text"][:1200])