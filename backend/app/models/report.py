from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
)

from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Report(Base):
    __tablename__ = "reports"

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

    file_name = Column(
        String(255),
        nullable=False,
    )

    file_path = Column(
        String(500),
        nullable=False,
    )

    extracted_text = Column(
        Text,
        nullable=True,
    )

    mime_type = Column(String(100), nullable=True)
    file_size = Column(Integer, nullable=True)
    sha256 = Column(String(64), nullable=True)
    processing_status = Column(String(50), nullable=False, default="Uploaded")
    rejection_reason = Column(Text, nullable=True)
    quality_score = Column(Float, nullable=True)
    quality_reasons_json = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    session = relationship(
        "UploadSession",
        back_populates="reports",
    )
