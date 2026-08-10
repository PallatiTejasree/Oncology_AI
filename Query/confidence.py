"""Retrieval diagnostics; these values are not clinical confidence scores."""

from __future__ import annotations


def retrieval_diagnostics(results: list[dict]) -> dict:
    if not results:
        return {
            "status": "no_results",
            "top_retrieval_score": None,
            "score_margin": None,
            "calibrated": False,
        }
    top = float(results[0]["retrieval_score"])
    second = float(results[1]["retrieval_score"]) if len(results) > 1 else None
    return {
        "status": "retrieved",
        "top_retrieval_score": top,
        "score_margin": top - second if second is not None else None,
        "calibrated": False,
        "warning": "Retrieval scores are not diagnostic probabilities or calibrated confidence.",
    }
