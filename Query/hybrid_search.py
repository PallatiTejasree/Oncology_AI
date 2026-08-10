"""Modality-aware retrieval and rank fusion.

MedCPT inner-product scores and BiomedCLIP cosine scores are not numerically
comparable. Text queries therefore keep report evidence primary and treat
text-to-image matches as optional supporting evidence.
"""

from __future__ import annotations

from collections import Counter

from Query.config import (
    DEFAULT_FUSION_K,
    DEFAULT_TOP_K,
    HYBRID_IMAGE_WEIGHT,
    HYBRID_TEXT_WEIGHT,
    TEXT_TO_IMAGE_MIN_COSINE_SCORE,
)
from Query.retriever import ImageRetriever, TextRetriever


def reciprocal_rank_fusion(
    result_lists: list[list[dict]],
    top_k: int = DEFAULT_TOP_K,
    fusion_k: int = DEFAULT_FUSION_K,
    weights: list[float] | None = None,
) -> list[dict]:
    if top_k < 1 or fusion_k < 1:
        raise ValueError("top_k and fusion_k must be positive")
    if weights is None:
        weights = [1.0] * len(result_lists)
    if len(weights) != len(result_lists) or any(weight <= 0 for weight in weights):
        raise ValueError("weights must contain one positive value per result list")
    fused: dict[str, dict] = {}
    for results, weight in zip(result_lists, weights):
        for rank, result in enumerate(results, start=1):
            key = f"{result['modality']}:{result['id']}"
            if key not in fused:
                fused[key] = {**result, "rrf_score": 0.0, "matched_retrievers": 0}
            fused[key]["rrf_score"] += weight / (fusion_k + rank)
            fused[key]["matched_retrievers"] += 1
    ranked = sorted(fused.values(), key=lambda item: item["rrf_score"], reverse=True)[:top_k]
    return [{**item, "fused_rank": rank} for rank, item in enumerate(ranked, start=1)]


class HybridSearch:
    def __init__(self, device: str = "auto"):
        self.text = TextRetriever(device=device)
        self.images = ImageRetriever(device=device)

    def search_text(self, query: str, top_k: int = DEFAULT_TOP_K) -> dict:
        candidate_k = max(top_k * 2, top_k)
        text_results = self.text.search(query, candidate_k)
        image_results = self.images.search_text(query, candidate_k)
        primary = text_results[:top_k]
        labels = [
            (item.get("metadata") or {}).get("cancer_type")
            for item in primary[:3]
        ]
        labels = [label for label in labels if label and label.lower() != "unknown"]
        counts = Counter(labels)
        consensus_label = counts.most_common(1)[0][0] if counts and counts.most_common(1)[0][1] >= 2 else None
        supporting_images = []
        exclusion_reasons = Counter()
        for item in image_results:
            score = float(item.get("retrieval_score", -1.0))
            label = (item.get("metadata") or {}).get("cancer_type")
            if score < TEXT_TO_IMAGE_MIN_COSINE_SCORE:
                exclusion_reasons["below_similarity_threshold"] += 1
                continue
            if consensus_label and label != consensus_label:
                exclusion_reasons["cancer_label_mismatch"] += 1
                continue
            supporting_images.append(item)
            if len(supporting_images) >= min(2, top_k):
                break
        return {
            "query_type": "text",
            "text_results": primary,
            "image_results": supporting_images,
            # Never interleave unrelated image hits into primary report evidence.
            "fused_results": primary,
            "supporting_image_results": supporting_images,
            "selection": {
                "primary_modality": "text",
                "text_cancer_consensus": consensus_label,
                "image_min_cosine_score": TEXT_TO_IMAGE_MIN_COSINE_SCORE,
                "candidate_images": len(image_results),
                "included_images": len(supporting_images),
                "excluded_images": len(image_results) - len(supporting_images),
                "exclusion_reasons": dict(exclusion_reasons),
            },
        }

    def search_image(
        self,
        image_path: str,
        ocr_text: str | None = None,
        top_k: int = DEFAULT_TOP_K,
        interpretable_only: bool = False,
    ) -> dict:
        candidate_k = max(top_k * 2, top_k)
        image_results = self.images.search_image(
            image_path,
            candidate_k,
            source_dataset="pmc_medical_images" if interpretable_only else None,
        )
        text_results = self.text.search(ocr_text, candidate_k) if ocr_text and ocr_text.strip() else []
        return {
            "query_type": "image_with_ocr" if text_results else "image",
            "text_results": text_results[:top_k],
            "image_results": image_results[:top_k],
            # The uploaded image is primary evidence for this query type; OCR
            # text augments it rather than displacing its closest match.
            "fused_results": reciprocal_rank_fusion(
                [image_results, text_results], top_k,
                weights=[HYBRID_IMAGE_WEIGHT, HYBRID_TEXT_WEIGHT]
            ),
            "fusion": {
                "method": "weighted_reciprocal_rank_fusion",
                "fusion_k": DEFAULT_FUSION_K,
                "image_queries": 1,
                "weights": {
                    "images_total": HYBRID_IMAGE_WEIGHT,
                    "text": HYBRID_TEXT_WEIGHT if text_results else 0.0,
                },
            },
        }

    def search_images(
        self,
        image_paths: list[str],
        ocr_text: str | None = None,
        top_k: int = DEFAULT_TOP_K,
        interpretable_only: bool = False,
    ) -> dict:
        """Fuse multiple query-image rankings without letting image count dominate."""
        clean_paths = list(dict.fromkeys(path for path in image_paths if path))
        if not clean_paths:
            raise ValueError("At least one image path is required")
        if len(clean_paths) == 1:
            return self.search_image(clean_paths[0], ocr_text, top_k, interpretable_only)

        candidate_k = max(top_k * 2, top_k)
        image_lists = [
            self.images.search_image(
                path,
                candidate_k,
                source_dataset="pmc_medical_images" if interpretable_only else None,
            )
            for path in clean_paths
        ]
        text_results = self.text.search(ocr_text, candidate_k) if ocr_text and ocr_text.strip() else []
        text_labels = [
            (item.get("metadata") or {}).get("cancer_type")
            for item in text_results[:3]
        ]
        text_labels = [label for label in text_labels if label and str(label).lower() != "unknown"]
        label_counts = Counter(text_labels)
        consensus_label = (
            label_counts.most_common(1)[0][0]
            if label_counts and label_counts.most_common(1)[0][1] >= 2
            else None
        )
        excluded_label_mismatch = 0
        if consensus_label:
            filtered_lists = []
            for results in image_lists:
                accepted = []
                for item in results:
                    label = str((item.get("metadata") or {}).get("cancer_type") or "")
                    labels = {part.strip().lower() for part in label.split("|") if part.strip()}
                    if str(consensus_label).lower() not in labels:
                        excluded_label_mismatch += 1
                        continue
                    accepted.append(item)
                filtered_lists.append(accepted)
            image_lists = filtered_lists
        per_image_weight = HYBRID_IMAGE_WEIGHT / len(image_lists)
        image_fused = reciprocal_rank_fusion(
            image_lists, candidate_k, weights=[per_image_weight] * len(image_lists)
        )
        lists = [*image_lists, text_results] if text_results else image_lists
        weights = [per_image_weight] * len(image_lists) + (
            [HYBRID_TEXT_WEIGHT] if text_results else []
        )
        return {
            "query_type": "multimodal" if text_results else "multi_image",
            "text_results": text_results[:top_k],
            "image_results": image_fused[:top_k],
            "fused_results": reciprocal_rank_fusion(lists, top_k, weights=weights),
            "fusion": {
                "method": "weighted_reciprocal_rank_fusion",
                "fusion_k": DEFAULT_FUSION_K,
                "image_queries": len(image_lists),
                "weights": {
                    "per_image": per_image_weight,
                    "images_total": HYBRID_IMAGE_WEIGHT,
                    "text": HYBRID_TEXT_WEIGHT if text_results else 0.0,
                },
            },
            "selection": {
                "text_cancer_consensus": consensus_label,
                "image_label_filter_applied": bool(consensus_label),
                "excluded_image_label_mismatch": excluded_label_mismatch,
                "included_image_candidates": sum(len(items) for items in image_lists),
            },
        }
