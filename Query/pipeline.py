"""High-level query pipeline used by the future FastAPI endpoints."""

from __future__ import annotations

from Query.confidence import retrieval_diagnostics
from Query.hybrid_search import HybridSearch


class QueryPipeline:
    def __init__(self, device: str = "auto"):
        self.search = HybridSearch(device=device)

    def query_text(self, query: str, top_k: int = 5) -> dict:
        result = self.search.search_text(query, top_k)
        result["diagnostics"] = {
            "text": retrieval_diagnostics(result["text_results"]),
            "images": retrieval_diagnostics(result["image_results"]),
        }
        result["diagnostics"]["selection"] = result.get("selection", {})
        return result

    def query_image(self, image_path: str, ocr_text: str | None = None, top_k: int = 5) -> dict:
        # The application needs captioned/labeled evidence for an explanation;
        # unlabeled legacy nearest-neighbor filenames are not useful context.
        result = self.search.search_image(
            image_path, ocr_text, top_k, interpretable_only=True
        )
        result["diagnostics"] = {
            "text": retrieval_diagnostics(result["text_results"]),
            "images": retrieval_diagnostics(result["image_results"]),
        }
        result["diagnostics"]["fusion"] = result.get("fusion", {})
        return result

    def query_images(self, image_paths: list[str], ocr_text: str | None = None, top_k: int = 5) -> dict:
        result = self.search.search_images(
            image_paths, ocr_text, top_k, interpretable_only=True
        )
        result["diagnostics"] = {
            "text": retrieval_diagnostics(result["text_results"]),
            "images": retrieval_diagnostics(result["image_results"]),
            "fusion": result.get("fusion", {}),
            "selection": result.get("selection", {}),
        }
        return result
