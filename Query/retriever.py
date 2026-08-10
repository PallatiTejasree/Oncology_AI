"""Chroma retrievers for MedCPT text and BiomedCLIP images."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from Ingestion.vectordb.chroma_client import get_client
from Ingestion.vectordb.collections import collection_space
from Query.config import (
    DEFAULT_FUSION_K,
    DEFAULT_TOP_K,
    IMAGE_COLLECTION,
    MAX_TOP_K,
    TEXT_LEXICAL_WEIGHT,
    TEXT_SEMANTIC_WEIGHT,
    TEXT_COLLECTION,
)
from Query.query_encoder import BiomedCLIPQueryEncoder, MedCPTQueryEncoder


def _top_k(value: int, collection_count: int) -> int:
    if value < 1:
        raise ValueError("top_k must be at least 1")
    if collection_count == 0:
        raise RuntimeError("The requested Chroma collection is empty")
    return min(value, MAX_TOP_K, collection_count)


def build_where(
    source_dataset: str | None = None,
    cancer_type: str | None = None,
    extra: dict | None = None,
) -> dict | None:
    """Build a valid Chroma metadata filter from optional constraints."""
    clauses = []
    if source_dataset:
        clauses.append({"source_dataset": {"$eq": source_dataset}})
    if cancer_type:
        clauses.append({"cancer_type": {"$eq": cancer_type}})
    if extra:
        clauses.append(extra)
    if not clauses:
        return None
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def _format_results(raw: dict, modality: str, metric: str) -> list[dict]:
    if not raw.get("ids") or not raw["ids"][0]:
        return []
    output = []
    documents = (raw.get("documents") or [[]])[0]
    metadatas = (raw.get("metadatas") or [[]])[0]
    distances = (raw.get("distances") or [[]])[0]
    for rank, (identifier, document, metadata, distance) in enumerate(
        zip(raw["ids"][0], documents, metadatas, distances), start=1
    ):
        distance = float(distance)
        retrieval_score = 1.0 - distance
        if metric == "cosine":
            # Clamp tiny float32 roundoff such as 1.00000035.
            retrieval_score = max(-1.0, min(1.0, retrieval_score))
        output.append(
            {
                "id": identifier,
                "rank": rank,
                "modality": modality,
                "document": document or "",
                "metadata": metadata or {},
                "distance": distance,
                # This is a retrieval score, not a calibrated confidence.
                "retrieval_score": retrieval_score,
                "metric": metric,
            }
        )
    return output


def _format_lexical_results(raw: dict) -> list[dict]:
    output = []
    for rank, (identifier, document, metadata) in enumerate(zip(
        raw.get("ids") or [], raw.get("documents") or [], raw.get("metadatas") or []
    ), start=1):
        output.append({
            "id": identifier, "rank": rank, "lexical_rank": rank,
            "modality": "text", "document": document or "",
            "metadata": metadata or {}, "distance": None,
            "retrieval_score": 1.0 / rank, "metric": "lexical_substring",
        })
    return output


def fuse_text_results(semantic: list[dict], lexical: list[dict], top_k: int) -> list[dict]:
    """Fuse MedCPT and exact-phrase candidates without comparing raw scores."""
    fused: dict[str, dict] = {}
    for results, weight, method in (
        (semantic, TEXT_SEMANTIC_WEIGHT, "semantic"),
        (lexical, TEXT_LEXICAL_WEIGHT, "lexical"),
    ):
        for rank, item in enumerate(results, start=1):
            identifier = str(item["id"])
            if identifier not in fused:
                fused[identifier] = {**item, "rrf_score": 0.0, "matched_retrievers": []}
            fused[identifier]["rrf_score"] += weight / (DEFAULT_FUSION_K + rank)
            fused[identifier]["matched_retrievers"].append(method)
            if method == "lexical":
                fused[identifier]["lexical_rank"] = rank
    ranked = sorted(
        fused.values(),
        key=lambda item: (
            item["rrf_score"],
            "lexical" in item["matched_retrievers"],
            -int(item.get("rank") or MAX_TOP_K + 1),
        ),
        reverse=True,
    )[:top_k]
    return [{**item, "rank": rank} for rank, item in enumerate(ranked, start=1)]


class TextRetriever:
    def __init__(self, encoder: MedCPTQueryEncoder | None = None, device: str = "auto"):
        self.collection = get_client().get_collection(TEXT_COLLECTION, embedding_function=None)
        if collection_space(self.collection) != "ip":
            raise RuntimeError("Text collection must use inner-product distance")
        self.encoder = encoder or MedCPTQueryEncoder(device)

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        where: dict | None = None,
        source_dataset: str | None = None,
        cancer_type: str | None = None,
    ) -> list[dict]:
        count = self.collection.count()
        vector = self.encoder.encode(query)
        where = build_where(source_dataset, cancer_type, where)
        candidate_k = _top_k(max(top_k * 5, MAX_TOP_K), count)
        raw = self.collection.query(
            query_embeddings=np.asarray([vector], dtype=np.float32),
            n_results=candidate_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        semantic = _format_results(raw, "text", "ip")
        words = query.split()
        lexical = []
        # Long exact phrases are high precision and common in pasted reports.
        # Short/general questions safely fall back to semantic MedCPT search.
        for size in (12, 8, 5):
            if len(words) < size:
                continue
            phrase = " ".join(words[:size])
            lexical_raw = self.collection.get(
                where=where,
                where_document={"$contains": phrase},
                limit=min(20, count),
                include=["documents", "metadatas"],
            )
            lexical = _format_lexical_results(lexical_raw)
            if lexical:
                break
        return fuse_text_results(semantic, lexical, top_k)


class ImageRetriever:
    def __init__(self, encoder: BiomedCLIPQueryEncoder | None = None, device: str = "auto"):
        self.collection = get_client().get_collection(IMAGE_COLLECTION, embedding_function=None)
        if collection_space(self.collection) != "cosine":
            raise RuntimeError("Image collection must use cosine distance")
        self.encoder = encoder or BiomedCLIPQueryEncoder(device)

    def _search_vector(self, vector: np.ndarray, top_k: int, where: dict | None) -> list[dict]:
        raw = self.collection.query(
            query_embeddings=np.asarray([vector], dtype=np.float32),
            n_results=_top_k(top_k, self.collection.count()),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        return _format_results(raw, "image", "cosine")

    def search_text(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        where: dict | None = None,
        source_dataset: str | None = None,
        cancer_type: str | None = None,
        include_legacy: bool = False,
    ) -> list[dict]:
        # Caption/text-to-image retrieval should prefer the labelled PMC
        # collection. The 206k legacy images have no captions or cancer labels
        # and otherwise overwhelm clinically interpretable results.
        if source_dataset is None and not include_legacy:
            source_dataset = "pmc_medical_images"
        where = build_where(source_dataset, cancer_type, where)
        return self._search_vector(self.encoder.encode_text(query), top_k, where)

    def search_image(
        self,
        image_path: str | Path,
        top_k: int = DEFAULT_TOP_K,
        where: dict | None = None,
        source_dataset: str | None = None,
        cancer_type: str | None = None,
    ) -> list[dict]:
        where = build_where(source_dataset, cancer_type, where)
        return self._search_vector(self.encoder.encode_image(image_path), top_k, where)


# Backward compatibility: Retriever previously meant text-only retrieval.
Retriever = TextRetriever
