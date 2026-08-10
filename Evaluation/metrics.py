"""Standard information-retrieval ranking metrics."""

from __future__ import annotations

import math


def _dcg(grades: list[int]) -> float:
    return sum((2**grade - 1) / math.log2(rank + 2) for rank, grade in enumerate(grades))


def evaluate_ranking(ranked_ids: list[str], qrels: dict[str, int], k: int) -> dict[str, float]:
    if k < 1:
        raise ValueError("k must be positive")
    relevant = {identifier for identifier, grade in qrels.items() if grade > 0}
    if not relevant:
        raise ValueError("At least one positive relevance judgment is required")

    retrieved = ranked_ids[:k]
    hits = [identifier in relevant for identifier in retrieved]
    hit_count = sum(hits)
    first_rank = next((rank for rank, hit in enumerate(hits, start=1) if hit), None)
    precision_sum = 0.0
    running_hits = 0
    for rank, hit in enumerate(hits, start=1):
        if hit:
            running_hits += 1
            precision_sum += running_hits / rank
    denominator = min(len(relevant), k)
    grades = [qrels.get(identifier, 0) for identifier in retrieved]
    ideal = sorted((grade for grade in qrels.values() if grade > 0), reverse=True)[:k]
    ideal_dcg = _dcg(ideal)

    return {
        f"judged@{k}": sum(identifier in qrels for identifier in retrieved) / k,
        f"precision@{k}": hit_count / k,
        f"recall@{k}": hit_count / len(relevant),
        f"hit_rate@{k}": float(hit_count > 0),
        f"mrr@{k}": 1.0 / first_rank if first_rank else 0.0,
        f"map@{k}": precision_sum / denominator,
        f"ndcg@{k}": _dcg(grades) / ideal_dcg if ideal_dcg else 0.0,
    }


def label_diagnostics(
    results: list[dict], expected_cancers: tuple[str, ...], expected_sources: tuple[str, ...], k: int
) -> dict[str, float | None]:
    top = results[:k]
    expected_cancer_set = {value.lower() for value in expected_cancers}
    expected_source_set = {value.lower() for value in expected_sources}

    cancer_matches = []
    source_matches = []
    for result in top:
        metadata = result.get("metadata") or {}
        cancers = {
            value.strip().lower()
            for value in str(metadata.get("cancer_type") or "").split("|")
            if value.strip()
        }
        source = str(metadata.get("source_dataset") or "").lower()
        cancer_matches.append(bool(cancers & expected_cancer_set))
        source_matches.append(source in expected_source_set)
    return {
        f"cancer_hit@{k}": float(any(cancer_matches)) if expected_cancer_set else None,
        f"source_hit@{k}": float(any(source_matches)) if expected_source_set else None,
    }
