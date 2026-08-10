from datetime import datetime


class MedicalDocumentBuilder:

    @staticmethod
    def build(metadata, pdf_data, ocr_results):

        # ------------------------
        # Combine OCR text
        # ------------------------

        ocr_text = []

        for result in ocr_results:

            if result["status"] == "success":

                text = result["ocr_text"].strip()

                if text:

                    ocr_text.append(text)

        combined_ocr = "\n".join(ocr_text)

        # ------------------------
        # Final Medical Document
        # ------------------------

        combined_text = f"""
========== REPORT TEXT ==========

{pdf_data["text"]}

========== IMAGE OCR ==========

{combined_ocr}
"""

        return {

            "document_id": metadata["file_name"],

            "created_at": datetime.now().isoformat(),

            "metadata": metadata,

            "pdf_text": pdf_data["text"],

            "ocr_text": combined_ocr,

            "combined_text": combined_text,

            "statistics": {

                "pages": pdf_data["total_pages"],

                "images": len(pdf_data["images"]),

                "ocr_images": len(ocr_results),

                "pdf_characters": len(pdf_data["text"]),

                "ocr_characters": len(combined_ocr)

            }

        }