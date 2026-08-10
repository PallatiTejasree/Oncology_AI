"""Compatibility exports for rank fusion.

The previous generic MS-MARCO reranker was removed because it was not trained
for clinical oncology evidence and introduced an undeclared dependency.
"""

from Query.hybrid_search import reciprocal_rank_fusion

__all__ = ["reciprocal_rank_fusion"]
