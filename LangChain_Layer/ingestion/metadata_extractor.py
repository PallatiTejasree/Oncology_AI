from pathlib import Path
from datetime import datetime

import fitz  # PyMuPDF
from PIL import Image


class PDFMetadataExtractor:

    @staticmethod
    def extract(file_path: str):

        path = Path(file_path)

        doc = fitz.open(file_path)

        metadata = doc.metadata

        return {
            "file_name": path.name,
            "file_size_mb": round(path.stat().st_size / (1024 * 1024), 2),
            "pages": len(doc),
            "title": metadata.get("title"),
            "author": metadata.get("author"),
            "subject": metadata.get("subject"),
            "creator": metadata.get("creator"),
            "producer": metadata.get("producer"),
            "created": metadata.get("creationDate"),
            "modified": metadata.get("modDate"),
            "uploaded_at": datetime.now().isoformat()
        }


class ImageMetadataExtractor:

    @staticmethod
    def extract(file_path: str):

        path = Path(file_path)

        image = Image.open(file_path)

        return {
            "file_name": path.name,
            "file_size_mb": round(path.stat().st_size / (1024 * 1024), 2),
            "width": image.width,
            "height": image.height,
            "mode": image.mode,
            "format": image.format,
            "dpi": image.info.get("dpi"),
            "uploaded_at": datetime.now().isoformat()
        }