from typing import Any, Literal

from pydantic import BaseModel, Field


class TextAnalysisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=50000)
    top_k: int = Field(default=5, ge=1, le=20)


class SessionAnalysisRequest(BaseModel):
    question: str | None = Field(default=None, max_length=20000)
    top_k: int = Field(default=5, ge=1, le=20)


GenerationMode = Literal["gemini_structured", "gemini_degraded", "extractive_fallback"]


class GeneralAnswer(BaseModel):
    answer: str
    limitations: list[str] = Field(default_factory=list)
    reference_citations: list[str] = Field(default_factory=list)


class FocusedAnswer(BaseModel):
    answer: str
    certainty: Literal["confirmed", "favored", "suspicious", "indeterminate", "negative", "pending", "insufficient_information"]
    citations: list[str]


Certainty = Literal["confirmed", "favored", "suspicious", "indeterminate", "negative", "pending", "insufficient_information"]


class CaseComplexity(BaseModel):
    level: Literal["low", "moderate", "high", "insufficient_information"]
    reason: str
    citations: list[str] = Field(default_factory=list)


class EvidenceSupport(BaseModel):
    level: Literal["Moderate", "Limited", "Insufficient"]
    explanation: str


class KeyFinding(BaseModel):
    title: str
    result: str
    meaning: str
    certainty: Certainty
    importance: Literal["critical", "high", "supporting"]
    citations: list[str] = Field(default_factory=list)


class Staging(BaseModel):
    documented_components: list[str] = Field(default_factory=list)
    unresolved_components: list[str] = Field(default_factory=list)
    final_stage: str | None = None
    can_assign_final_stage: bool = False
    explanation: str
    citations: list[str] = Field(default_factory=list)


class MedicalTerm(BaseModel):
    term: str
    definition: str


class FullReportAnswer(BaseModel):
    headline: str
    plain_language_summary: str
    case_complexity: CaseComplexity
    evidence_support: EvidenceSupport
    key_findings: list[KeyFinding] = Field(default_factory=list)
    staging: Staging
    limitations: list[str] = Field(default_factory=list)
    medical_terms: list[MedicalTerm] = Field(default_factory=list)
    safety_notice: str


class AnalysisResponseContract(BaseModel):
    """Stable API fields shared by new and historical analysis responses."""
    brief_response: bool = False
    response_contract: Literal["general", "focused", "full_report"] | None = None
    generation_mode: GenerationMode | None = None
    generation_status: GenerationMode | None = None
    structured_answer: dict[str, Any] | None = None
    summary: str
    care_urgency: dict[str, Any] | None = None
    case_complexity: dict[str, Any] | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    uploaded_sources: list[dict[str, Any]] = Field(default_factory=list)
    citation_validation: dict[str, Any] = Field(default_factory=dict)
    semantic_grounding: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    reliability: dict[str, Any] | None = None
