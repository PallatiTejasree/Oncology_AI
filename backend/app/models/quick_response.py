from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.db.database import Base


class QuickResponse(Base):
    """Database-managed reply for a complete, non-clinical message."""

    __tablename__ = "quick_responses"

    id = Column(Integer, primary_key=True, index=True)
    intent = Column(String(50), nullable=False, index=True)
    trigger_phrase = Column(String(255), nullable=False, unique=True, index=True)
    response_text = Column(Text, nullable=False)
    active = Column(Boolean, nullable=False, default=True, server_default="true", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
