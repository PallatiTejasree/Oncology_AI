import time
from paddleocr import PaddleOCR


class OCRExtractor:

    def __init__(self):

        self.ocr = PaddleOCR(
            lang="en"
        )

    def extract(self, image_path):

        start = time.time()

        result = self.ocr.predict(image_path)

        full_text = []

        confidences = []

        for page in result:

            if "rec_texts" in page:

                full_text.extend(page["rec_texts"])

            if "rec_scores" in page:

                confidences.extend(page["rec_scores"])

        processing_time = round(time.time() - start, 3)

        average_confidence = (
            round(sum(confidences) / len(confidences), 3)
            if confidences else 0
        )

        return {

            "image_path": image_path,

            "ocr_text": "\n".join(full_text),

            "ocr_confidence": average_confidence,

            "processing_time": processing_time,

            "status": "success" if full_text else "no_text"

        }