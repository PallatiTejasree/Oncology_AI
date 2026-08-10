from ingestion.file_validator import FileValidator
from ingestion.metadata_extractor import PDFMetadataExtractor
from ingestion.pdf_processor import PDFProcessor
from ingestion.image_filter import ImageFilter


class IngestionPipeline:

    def __init__(self):
        print("\nMedical AI Ingestion Pipeline Initialized\n")

    def process(self, file_path):

        print("=" * 80)
        print("STEP 1 : FILE VALIDATION")
        print("=" * 80)

        validation = FileValidator.validate(file_path)

        if not validation["accepted"]:
            print("Validation Failed")
            print(validation["reason"])

            return validation

        print("Validation Successful\n")

        print("=" * 80)
        print("STEP 2 : METADATA EXTRACTION")
        print("=" * 80)

        metadata = PDFMetadataExtractor.extract(file_path)

        print(metadata)

        print()

        print("=" * 80)
        print("STEP 3 : PDF PROCESSING")
        print("=" * 80)

        pdf = PDFProcessor.extract(file_path)

        print(f"Pages : {pdf['total_pages']}")
        print(f"Characters : {len(pdf['text'])}")
        print(f"Images : {len(pdf['images'])}")

        print()

        print("=" * 80)
        print("STEP 4 : IMAGE FILTER")
        print("=" * 80)

        filtered = ImageFilter.filter_images(pdf["images"])

        print(f"Accepted : {len(filtered['accepted'])}")
        print(f"Rejected : {len(filtered['rejected'])}")

        print()

        print("=" * 80)
        print("INGESTION COMPLETED")
        print("=" * 80)

        return {

            "validation": validation,

            "metadata": metadata,

            "pdf": pdf,

            "accepted_images": filtered["accepted"],

            "rejected_images": filtered["rejected"]

        }


if __name__ == "__main__":

    pipeline = IngestionPipeline()

    result = pipeline.process(
        "sample_files/Reports/report_1.pdf"
    )

    print("\nPipeline Finished Successfully")