"""LangChain orchestration boundary used by the FastAPI analysis routes."""

from __future__ import annotations

import os
import logging
import time
from functools import lru_cache
from typing import Any

from langchain_core.runnables import RunnableLambda

from app.langchain.pipeline import get_analysis_pipeline


logger = logging.getLogger(__name__)


class LangChainAnalysisService:
    """Expose the existing clinical RAG pipeline as a LangChain runnable."""

    def __init__(self) -> None:
        # The encoders remain lazy: constructing this service does not load the
        # large retrieval models. They are loaded on the first analysis call.
        self.chain = RunnableLambda(self._invoke_pipeline)

    @staticmethod
    def _invoke_pipeline(payload: dict[str, Any]) -> dict[str, Any]:
        initialization_started = time.perf_counter()
        logger.info("[analysis] pipeline/model initialization started")
        pipeline = get_analysis_pipeline()
        logger.info(
            "[analysis] pipeline/model initialization: %.2fs",
            time.perf_counter() - initialization_started,
        )
        return pipeline.analyze(**payload)

    def analyze(self, **payload: Any) -> dict[str, Any]:
        return self.chain.invoke(payload)

    def status(self) -> dict[str, Any]:
        gemini_configured = bool(os.getenv("GEMINI_API_KEY"))
        return {
            "connected": True,
            "orchestrator": "LangChain RunnableLambda",
            "pipeline": "ClinicalAnalysisPipeline",
            "retrieval": "QueryPipeline + private Chroma retrieval",
            "generation_provider": "Google Gemini",
            "gemini_configured": gemini_configured,
            "gemini_model": os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
            "ready": gemini_configured,
        }


@lru_cache(maxsize=1)
def get_langchain_analysis_service() -> LangChainAnalysisService:
    return LangChainAnalysisService()
