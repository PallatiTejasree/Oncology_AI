from pydantic import BaseModel, Field


class TextAnalysisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=50000)
    top_k: int = Field(default=5, ge=1, le=20)


class SessionAnalysisRequest(BaseModel):
    question: str | None = Field(default=None, max_length=20000)
    top_k: int = Field(default=5, ge=1, le=20)
