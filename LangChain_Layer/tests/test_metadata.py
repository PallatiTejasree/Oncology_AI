from ingestion.metadata_extractor import PDFMetadataExtractor

pdf = PDFMetadataExtractor.extract("sample_files/Reports/report_1.pdf")

print(pdf)