from pathlib import Path
import mimetypes

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".docx"
}

MAX_FILE_SIZE_MB = 25


class FileValidator:

    @staticmethod
    def validate(file_path: str):

        path = Path(file_path)

        # File exists
        if not path.exists():
            return {
                "accepted": False,
                "reason": "File not found"
            }

        # Empty file
        if path.stat().st_size == 0:
            return {
                "accepted": False,
                "reason": "Uploaded file is empty"
            }

        # Extension
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return {
                "accepted": False,
                "reason": f"Unsupported file type: {path.suffix}"
            }

        # Size
        size_mb = path.stat().st_size / (1024 * 1024)

        if size_mb > MAX_FILE_SIZE_MB:
            return {
                "accepted": False,
                "reason": f"File exceeds {MAX_FILE_SIZE_MB} MB limit"
            }

        # MIME type
        mime_type, _ = mimetypes.guess_type(str(path))

        return {
            "accepted": True,
            "reason": "Validation successful",
            "file_name": path.name,
            "extension": path.suffix.lower(),
            "mime_type": mime_type,
            "size_mb": round(size_mb, 2)
        }