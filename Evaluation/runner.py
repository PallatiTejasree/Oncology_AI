"""Execute evaluation cases through the real Query retrieval layer."""

from __future__ import annotations

from Query.hybrid_search import reciprocal_rank_fusion
from Query.config import HYBRID_IMAGE_WEIGHT, HYBRID_TEXT_WEIGHT
from Query.retriever import ImageRetriever, TextRetriever

from Evaluation.schema import EvaluationCase


class RetrievalRunner:
    def __init__(self, device: str = "auto", text_retriever=None, image_retriever=None):
        self.device = device
        self._text = text_retriever
        self._images = image_retriever

    @property
    def text(self):
        if self._text is None:
            self._text = TextRetriever(device=self.device)
        return self._text

    @property
    def images(self):
        if self._images is None:
            self._images = ImageRetriever(device=self.device)
        return self._images

    def run(self, case: EvaluationCase, top_k: int) -> list[dict]:
        if case.query_type == "text":
            return self.text.search(case.query_text, top_k)
        if case.query_type == "text_to_image":
            return self.images.search_text(case.query_text, top_k)
        if case.query_type == "image":
            return self.images.search_image(case.image_path, top_k)
        if case.query_type == "hybrid":
            candidates = max(top_k * 2, top_k)
            text = self.text.search(case.query_text, candidates)
            images = self.images.search_image(case.image_path, candidates)
            # Match the production query path: the uploaded image is primary,
            # while report/OCR text supplies supporting clinical context.
            return reciprocal_rank_fusion(
                [images, text],
                top_k=top_k,
                weights=[HYBRID_IMAGE_WEIGHT, HYBRID_TEXT_WEIGHT],
            )
        raise ValueError(f"Unsupported query type: {case.query_type}")


def canonical_result_id(result: dict) -> str:
    return f"{result['modality']}:{result['id']}"
