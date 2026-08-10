"""Safe query-time extraction of useful raster images embedded in PDFs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExtractedPdfImage:
    path: Path
    page: int
    width: int
    height: int
    sha256: str


def extract_pdf_images(
    pdf_path: Path,
    output_dir: Path,
    *,
    max_images: int = 8,
    min_width: int = 160,
    min_height: int = 120,
) -> list[ExtractedPdfImage]:
    """Extract bounded, deduplicated embedded images without rendering pages."""
    import fitz
    from PIL import Image
    from io import BytesIO

    output_dir.mkdir(parents=True, exist_ok=True)
    accepted: list[ExtractedPdfImage] = []
    seen_hashes: set[str] = set()

    with fitz.open(pdf_path) as document:
        for page_number, page in enumerate(document, start=1):
            for image_info in page.get_images(full=True):
                if len(accepted) >= max_images:
                    return accepted
                extracted = document.extract_image(image_info[0])
                content = extracted.get("image") or b""
                if not content:
                    continue
                digest = hashlib.sha256(content).hexdigest()
                if digest in seen_hashes:
                    continue
                try:
                    with Image.open(BytesIO(content)) as image:
                        width, height = image.size
                        image_format = (image.format or "PNG").lower()
                except Exception:
                    continue
                if width < min_width or height < min_height:
                    continue
                seen_hashes.add(digest)
                extension = "jpg" if image_format in {"jpeg", "jpg"} else "png"
                target = output_dir / f"page-{page_number:03d}-{digest[:12]}.{extension}"
                if not target.exists():
                    target.write_bytes(content)
                accepted.append(ExtractedPdfImage(target, page_number, width, height, digest))
    return accepted
