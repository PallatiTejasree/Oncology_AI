"""Session-scoped preprocessing and vector indexing for user uploads.

The reference Chroma collections are deliberately left untouched. User content
is stored in separate collections and tagged with user/session/file identifiers
so it can never be retrieved without an ownership filter.
"""

from __future__ import annotations

import os
import json
import re
import shutil
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np


USER_TEXT_COLLECTION = "user_upload_text_embeddings"
USER_IMAGE_COLLECTION = "user_upload_image_embeddings"
MIN_IMAGE_WIDTH = 200
MIN_IMAGE_HEIGHT = 200
BLUR_THRESHOLD = float(os.getenv("UPLOAD_BLUR_THRESHOLD", "80"))
MIN_QUALITY_SCORE = float(os.getenv("UPLOAD_MIN_QUALITY_SCORE", "40"))
MIN_PDF_PAGE_TEXT = 40
CHUNK_SIZE = 2400
CHUNK_OVERLAP = 300


@dataclass
class ProcessedReport:
    text: str
    chunks: list[dict] = field(default_factory=list)
    ocr_pages: list[int] = field(default_factory=list)
    quality_score: float = 0.0
    quality_reasons: list[str] = field(default_factory=list)


@dataclass
class ProcessedImage:
    accepted: bool
    rejection_reason: str | None = None
    rejection_reasons: list[str] = field(default_factory=list)
    ocr_text: str = ""
    blur_score: float | None = None
    quality_score: float = 0.0
    quality_reasons: list[str] = field(default_factory=list)


def clean_medical_text(text: str) -> str:
    """Normalize extraction noise without deleting clinical negation or units."""
    value = text.replace("\x00", " ").replace("\x0c", "\n")
    value = re.sub(r"(?im)^\s*page\s+\d+\s+of\s+\d+\s*$", " ", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def chunk_medical_text(text: str, *, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Create bounded, overlapping chunks while preferring paragraph boundaries."""
    clean = clean_medical_text(text)
    if not clean:
        return []
    if size < 200 or overlap < 0 or overlap >= size:
        raise ValueError("Invalid text chunk settings")
    chunks: list[str] = []
    start = 0
    while start < len(clean):
        end = min(start + size, len(clean))
        if end < len(clean):
            candidates = [clean.rfind(marker, start + size // 2, end) for marker in ("\n\n", ". ", "\n")]
            boundary = max(candidates)
            if boundary > start:
                end = boundary + 1
        chunk = clean[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(clean):
            break
        start = max(start + 1, end - overlap)
    return chunks


def _ocr_image(image) -> str:
    """Return OCR text when Tesseract is available; OCR failure is non-fatal."""
    if shutil.which("tesseract") is None:
        return ""
    try:
        import pytesseract
        from PIL import Image, ImageEnhance, ImageOps

        # Phone screenshots frequently place a relatively small report on a
        # large white canvas. Crop to non-white content and enlarge it before
        # OCR so clinically important measurements are not lost.
        gray = ImageOps.grayscale(image)
        ink_mask = gray.point(lambda pixel: 255 if pixel < 245 else 0)
        bounds = ink_mask.getbbox()
        prepared = image
        if bounds:
            left, top, right, bottom = bounds
            padding = max(8, round(min(image.size) * 0.01))
            prepared = image.crop((
                max(0, left - padding), max(0, top - padding),
                min(image.width, right + padding), min(image.height, bottom + padding),
            ))
        if prepared.width < 1600:
            scale = min(4.0, max(2.0, 1600 / max(1, prepared.width)))
            prepared = prepared.resize(
                (round(prepared.width * scale), round(prepared.height * scale)),
                resample=Image.Resampling.LANCZOS,
            )
        prepared = ImageEnhance.Contrast(ImageOps.grayscale(prepared)).enhance(1.6)
        prepared = ImageEnhance.Sharpness(prepared).enhance(1.5)

        return clean_medical_text(
            pytesseract.image_to_string(prepared, lang="eng", config="--oem 3 --psm 6")
        )
    except Exception:
        return ""


def inspect_image(path: Path) -> ProcessedImage:
    import cv2
    from PIL import Image, ImageStat

    try:
        with Image.open(path) as source:
            source.verify()
        with Image.open(path) as source:
            image = source.convert("RGB")
            width, height = image.size
            reasons: list[str] = []
            quality_reasons: list[str] = []
            resolution_ratio = min(width / MIN_IMAGE_WIDTH, height / MIN_IMAGE_HEIGHT, 1.0)
            quality_score = 10.0 + (20.0 * resolution_ratio)
            if width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT:
                reasons.append(
                    f"This image is too small to analyse reliably ({width} × {height} pixels). "
                    f"Please upload an image that is at least {MIN_IMAGE_WIDTH} × {MIN_IMAGE_HEIGHT} pixels."
                )
                quality_reasons.append(f"Resolution contributes {round(20 * resolution_ratio, 1)} of 20 points.")
            else:
                quality_reasons.append("Resolution is sufficient (20 of 20 points).")
            gray_pil = image.convert("L")
            mean = ImageStat.Stat(gray_pil).mean[0]
            if mean >= 250:
                reasons.append(
                    "This image appears almost completely white, so no usable clinical detail could be found. "
                    "Please check that you selected the correct image and upload the original file."
                )
                quality_reasons.append("The image is almost entirely white (0 of 30 content points).")
            elif mean <= 5:
                reasons.append(
                    "This image appears almost completely black, so no usable clinical detail could be found. "
                    "Please check that you selected the correct image and upload the original file."
                )
                quality_reasons.append("The image is almost entirely black (0 of 30 content points).")
            else:
                quality_score += 30.0
                quality_reasons.append("Visible content and contrast are present (30 of 30 points).")
            gray = np.asarray(gray_pil)
            blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            if blur_score < BLUR_THRESHOLD:
                reasons.append(
                    "This image is too blurry to analyse reliably. Please upload the original image or a clearer, "
                    "well-focused version without compression or motion blur."
                )
                sharpness_points = min(15.0, max(0.0, blur_score / BLUR_THRESHOLD * 15.0))
                quality_score += sharpness_points
                quality_reasons.append(f"Sharpness is below the required level ({round(sharpness_points, 1)} of 40 points).")
            else:
                quality_score += 40.0
                quality_reasons.append("Sharpness is sufficient (40 of 40 points).")
            if mean >= 250 or mean <= 5:
                quality_score = min(quality_score, 19.0)
            elif width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT or blur_score < BLUR_THRESHOLD:
                quality_score = min(quality_score, MIN_QUALITY_SCORE - 1)
            quality_score = round(max(0.0, min(100.0, quality_score)), 1)
            quality_reasons.append(f"Final ingestion-quality score: {quality_score} of 100; minimum required: {MIN_QUALITY_SCORE}.")
            if reasons:
                return ProcessedImage(
                    False,
                    rejection_reason=" ".join(reasons),
                    rejection_reasons=reasons,
                    blur_score=blur_score,
                    quality_score=quality_score,
                    quality_reasons=quality_reasons,
                )
            return ProcessedImage(True, ocr_text=_ocr_image(image), blur_score=blur_score, quality_score=quality_score, quality_reasons=quality_reasons)
    except Exception as error:
        reason = (
            "We could not open this image. The file may be damaged, incomplete, or saved in an unsupported image "
            "format. Please export it again as a valid PNG or JPEG and retry."
        )
        return ProcessedImage(False, rejection_reason=reason, rejection_reasons=[reason], quality_score=0.0, quality_reasons=["The file could not be opened, so its quality score is 0 of 100."])


def extract_report(path: Path) -> ProcessedReport:
    """Extract page text and OCR only pages that appear scanned."""
    import fitz
    from PIL import Image

    page_texts: list[str] = []
    ocr_pages: list[int] = []
    scanned_pages = 0
    try:
        with fitz.open(path) as document:
            for page_number, page in enumerate(document, start=1):
                text = clean_medical_text(page.get_text("text"))
                if len(text) < MIN_PDF_PAGE_TEXT:
                    scanned_pages += 1
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                    recovered = _ocr_image(image)
                    if recovered:
                        text = recovered
                        ocr_pages.append(page_number)
                if text:
                    page_texts.append(f"[Page {page_number}]\n{text}")
    except Exception as error:
        raise ValueError(f"PDF could not be processed: {error}") from error
    combined = clean_medical_text("\n\n".join(page_texts))
    if not combined:
        if scanned_pages and shutil.which("tesseract") is None:
            raise ValueError(
                "This PDF appears to contain scanned pages rather than selectable text, and text recognition is "
                "not available on the server right now. Please upload a searchable PDF or ask the administrator "
                "to enable OCR."
            )
        raise ValueError(
            "We could not find readable text in this PDF, even after text recognition. Please upload a clearer "
            "scan or a searchable PDF exported directly from the reporting system."
        )
    chunks = []
    for index, chunk in enumerate(chunk_medical_text(combined), start=1):
        pages = [int(value) for value in re.findall(r"\[Page\s+(\d+)\]", chunk, re.I)]
        sections = re.findall(
            r"(?im)^\s*(?:section\s*:\s*|#{1,3}\s*)?([A-Z][A-Za-z][A-Za-z /&-]{2,60})\s*:?\s*$",
            chunk,
        )
        chunks.append({
            "chunk_index": index,
            "text": chunk,
            "page_start": min(pages) if pages else None,
            "page_end": max(pages) if pages else None,
            "section_name": sections[0].strip() if sections else None,
        })
    text_points = min(25.0, len(combined) / 1000 * 25.0)
    quality_score = round(min(100.0, 65.0 + text_points + (10.0 if chunks else 0.0)), 1)
    quality_reasons = [
        "The PDF contains readable clinical text (65 base points).",
        f"Readable text volume contributes {round(text_points, 1)} of 25 points.",
        "Text was successfully divided into searchable chunks (10 of 10 points).",
        f"Final ingestion-quality score: {quality_score} of 100; minimum required: {MIN_QUALITY_SCORE}.",
    ]
    return ProcessedReport(combined, chunks, ocr_pages, quality_score, quality_reasons)


class _MedCPTArticleEncoder:
    def __init__(self, device: str = "auto") -> None:
        import torch
        from transformers import AutoModel, AutoTokenizer
        from Query.config import select_device

        self.torch = torch
        self.device = select_device(device)
        self.tokenizer = AutoTokenizer.from_pretrained("ncbi/MedCPT-Article-Encoder")
        self.model = AutoModel.from_pretrained("ncbi/MedCPT-Article-Encoder").to(self.device)
        self.model.eval()

    def encode(self, texts: list[str]) -> np.ndarray:
        encoded = self.tokenizer(
            ["uploaded clinical document"] * len(texts), texts,
            padding=True, truncation=True, max_length=512, return_tensors="pt",
        )
        encoded = {key: value.to(self.device) for key, value in encoded.items()}
        with self.torch.inference_mode():
            vectors = self.model(**encoded).last_hidden_state[:, 0, :]
        return vectors.float().cpu().numpy().astype(np.float32, copy=False)


@lru_cache(maxsize=1)
def _text_encoder() -> _MedCPTArticleEncoder:
    return _MedCPTArticleEncoder(os.getenv("MODEL_DEVICE", "auto"))


@lru_cache(maxsize=1)
def _image_encoder():
    from Query.query_encoder import BiomedCLIPQueryEncoder

    return BiomedCLIPQueryEncoder(os.getenv("MODEL_DEVICE", "auto"))


@lru_cache(maxsize=1)
def _text_query_encoder():
    from Query.query_encoder import MedCPTQueryEncoder

    return MedCPTQueryEncoder(os.getenv("MODEL_DEVICE", "auto"))


def _collection(name: str, space: str):
    from Ingestion.vectordb.chroma_client import get_client

    client = get_client()
    try:
        return client.get_collection(name, embedding_function=None)
    except Exception:
        return client.create_collection(
            name=name,
            configuration={"hnsw": {"space": space}},
            metadata={"scope": "private_user_uploads", "distance": space},
            embedding_function=None,
        )


def _existing_collection(name: str):
    """Return an existing private collection without creating it during query."""
    from Ingestion.vectordb.chroma_client import get_client

    try:
        return get_client().get_collection(name, embedding_function=None)
    except Exception:
        return None


def _private_filter(user_id: int, session_id: int) -> dict:
    return {
        "$and": [
            {"user_id": {"$eq": user_id}},
            {"session_id": {"$eq": session_id}},
        ]
    }


def _private_results(raw: dict, source_type: str) -> list[dict]:
    if not raw.get("ids") or not raw["ids"][0]:
        return []
    documents = (raw.get("documents") or [[]])[0]
    metadatas = (raw.get("metadatas") or [[]])[0]
    distances = (raw.get("distances") or [[]])[0]
    return [
        {
            "id": identifier,
            "source_type": source_type,
            "content": document or "",
            "retrieval_score": float(1.0 - distance),
            **(metadata or {}),
        }
        for identifier, document, metadata, distance in zip(
            raw["ids"][0], documents, metadatas, distances
        )
    ]


def retrieve_private_content(
    *, user_id: int, session_id: int, question: str, top_k: int = 5
) -> dict:
    """Retrieve only content owned by one user and upload session."""
    if not isinstance(question, str) or not question.strip():
        return {"text": [], "images": []}
    # Query cleaning is deliberately separate from document cleaning. The
    # question remains one bounded query (it is never chunked) and clinical
    # punctuation, negation, biomarkers and measurements are preserved.
    from Query.query_preprocessing import preprocess_query_text

    clean_question = preprocess_query_text(question)
    where = _private_filter(user_id, session_id)
    text_results: list[dict] = []
    image_results: list[dict] = []

    text_collection = _existing_collection(USER_TEXT_COLLECTION)
    if text_collection is not None and text_collection.count() > 0:
        vector = _text_query_encoder().encode(clean_question)
        raw = text_collection.query(
            query_embeddings=np.asarray([vector], dtype=np.float32),
            n_results=min(max(1, top_k), text_collection.count()),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        text_results = _private_results(raw, "uploaded_text")

    image_collection = _existing_collection(USER_IMAGE_COLLECTION)
    if image_collection is not None and image_collection.count() > 0:
        vector = _image_encoder().encode_text(clean_question)
        raw = image_collection.query(
            query_embeddings=np.asarray([vector], dtype=np.float32),
            n_results=min(max(1, min(2, top_k)), image_collection.count()),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        image_results = _private_results(raw, "uploaded_image")

    return {"text": text_results, "images": image_results}


def delete_private_session_vectors(*, user_id: int, session_id: int) -> dict:
    """Remove all private vectors belonging to one deleted upload session."""
    where = _private_filter(user_id, session_id)
    removed = {"text": 0, "images": 0}
    for key, name in (("text", USER_TEXT_COLLECTION), ("images", USER_IMAGE_COLLECTION)):
        collection = _existing_collection(name)
        if collection is None:
            continue
        before = collection.count()
        collection.delete(where=where)
        removed[key] = max(0, before - collection.count())
    return removed


def index_report(*, user_id: int, session_id: int, report_id: int, file_name: str, sha256: str, chunks: list[dict]) -> int:
    if not chunks:
        return 0
    texts = [item["text"] for item in chunks]
    vectors = _text_encoder().encode(texts)
    ids = [f"user:{user_id}:session:{session_id}:report:{report_id}:chunk:{item['chunk_index']}" for item in chunks]
    metadata = [{
        "source_dataset": "private_user_upload",
        "user_id": user_id,
        "session_id": session_id,
        "file_id": report_id,
        "file_name": file_name,
        "file_sha256": sha256 or "unknown",
        "chunk_index": item["chunk_index"],
        "page_start": item.get("page_start") or 0,
        "page_end": item.get("page_end") or item.get("page_start") or 0,
        "section_name": item.get("section_name") or "",
        "modality": "report_text",
    } for item in chunks]
    _collection(USER_TEXT_COLLECTION, "ip").upsert(
        ids=ids, embeddings=vectors, documents=texts, metadatas=metadata
    )
    return len(ids)


def index_image(*, user_id: int, session_id: int, image_id: int, file_name: str, sha256: str, path: Path, ocr_text: str) -> int:
    vector = _image_encoder().encode_image(path)
    identifier = f"user:{user_id}:session:{session_id}:image:{image_id}"
    _collection(USER_IMAGE_COLLECTION, "cosine").upsert(
        ids=[identifier], embeddings=[vector], documents=[ocr_text or file_name],
        metadatas=[{
            "source_dataset": "private_user_upload",
            "user_id": user_id,
            "session_id": session_id,
            "file_id": image_id,
            "file_name": file_name,
            "file_sha256": sha256 or "unknown",
            "modality": "uploaded_image",
        }],
    )
    return 1


def index_image_ocr(*, user_id: int, session_id: int, image_id: int, file_name: str, sha256: str, ocr_text: str) -> int:
    chunks = chunk_medical_text(ocr_text)
    if not chunks:
        return 0
    vectors = _text_encoder().encode(chunks)
    ids = [
        f"user:{user_id}:session:{session_id}:image:{image_id}:ocr:{index}"
        for index in range(1, len(chunks) + 1)
    ]
    _collection(USER_TEXT_COLLECTION, "ip").upsert(
        ids=ids,
        embeddings=vectors,
        documents=chunks,
        metadatas=[{
            "source_dataset": "private_user_upload",
            "user_id": user_id,
            "session_id": session_id,
            "file_id": image_id,
            "file_name": file_name,
            "file_sha256": sha256 or "unknown",
            "chunk_index": index,
            "modality": "image_ocr",
        } for index in range(1, len(chunks) + 1)],
    )
    return len(chunks)


def ingest_session(db, session) -> dict:
    """Preprocess and index every not-yet-indexed file in one upload session."""
    summary = {"reports": 0, "images": 0, "text_chunks": 0, "rejected": [], "quality": []}
    for report in session.reports:
        if report.processing_status in {"Indexed", "Processed"} and report.extracted_text:
            summary["reports"] += 1
            continue
        report.processing_status = "Processing"
        try:
            processed = extract_report(Path(report.file_path))
            if processed.quality_score < MIN_QUALITY_SCORE:
                raise ValueError(
                    f"This report's ingestion-quality score is {processed.quality_score} of 100, below the required {MIN_QUALITY_SCORE}. "
                    "Please upload a clearer or searchable PDF."
                )
            report.extracted_text = processed.text
            report.quality_score = processed.quality_score
            report.quality_reasons_json = json.dumps(processed.quality_reasons, ensure_ascii=False)
            summary["text_chunks"] += index_report(
                user_id=session.user_id, session_id=session.id, report_id=report.id,
                file_name=report.file_name, sha256=report.sha256, chunks=processed.chunks,
            )
            report.processing_status = "Indexed"
            report.rejection_reason = None
            summary["reports"] += 1
            summary["quality"].append({"file_name": report.file_name, "file_type": "report", "score": report.quality_score, "accepted": True, "reasons": processed.quality_reasons})
        except Exception as error:
            report.processing_status = "Rejected"
            report.rejection_reason = str(error)[:2000]
            report.quality_score = 0.0
            report.quality_reasons_json = json.dumps([report.rejection_reason], ensure_ascii=False)
            summary["rejected"].append({"file_name": report.file_name, "reason": report.rejection_reason})
            summary["quality"].append({"file_name": report.file_name, "file_type": "report", "score": 0.0, "accepted": False, "reasons": [report.rejection_reason]})

    for image in session.medical_images:
        if image.processing_status in {"Indexed", "Processed"}:
            summary["images"] += 1
            continue
        image.processing_status = "Processing"
        inspected = inspect_image(Path(image.file_path))
        image.extracted_text = inspected.ocr_text or None
        image.quality_score = inspected.quality_score
        image.quality_reasons_json = json.dumps(inspected.quality_reasons, ensure_ascii=False)
        summary["quality"].append({"file_name": image.file_name, "file_type": "image", "score": inspected.quality_score, "accepted": inspected.accepted, "reasons": inspected.quality_reasons})
        if not inspected.accepted:
            image.processing_status = "Rejected"
            image.rejection_reason = inspected.rejection_reason
            summary["rejected"].append({"file_name": image.file_name, "reason": image.rejection_reason})
            continue
        try:
            index_image(
                user_id=session.user_id, session_id=session.id, image_id=image.id,
                file_name=image.file_name, sha256=image.sha256,
                path=Path(image.file_path), ocr_text=inspected.ocr_text,
            )
            summary["text_chunks"] += index_image_ocr(
                user_id=session.user_id, session_id=session.id, image_id=image.id,
                file_name=image.file_name, sha256=image.sha256,
                ocr_text=inspected.ocr_text,
            )
            image.processing_status = "Indexed"
            image.rejection_reason = None
            summary["images"] += 1
        except Exception as error:
            image.processing_status = "Rejected"
            image.rejection_reason = f"Image embedding failed: {error}"[:2000]
            summary["rejected"].append({"file_name": image.file_name, "reason": image.rejection_reason})
    db.commit()
    return summary
