from sqlalchemy import (
    Column,
    Integer,
    Text,
    Float,
    String,
    DateTime,
    ForeignKey,
    Boolean,
)

from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Summary(Base):
    __tablename__ = "summaries"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    session_id = Column(
        Integer,
        ForeignKey("upload_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )

    ai_summary = Column(
        Text,
        nullable=True,
    )

    confidence_score = Column(
        Float,
        nullable=True,
    )

    model_name = Column(
        String(100),
        nullable=True,
    )

    processing_status = Column(
        String(50),
        default="Completed",
    )

    query_type = Column(String(50), nullable=True)
    retrieval_status = Column(String(50), nullable=True)
    diagnostics_json = Column(Text, nullable=True)
    evidence_json = Column(Text, nullable=True)
    disclaimer = Column(Text, nullable=True)
    calibrated = Column(Boolean, nullable=False, default=False)
    processing_time_ms = Column(Integer, nullable=True)
    failure_reason = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    session = relationship(
        "UploadSession",
        back_populates="summaries",
    )
