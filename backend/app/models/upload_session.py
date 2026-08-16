from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Text,
)

from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class UploadSession(Base):
    __tablename__ = "upload_sessions"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    session_name = Column(
        String(255),
        nullable=False,
    )
    custom_title = Column(String(80), nullable=True)

    status = Column(
        String(50),
        default="Processing",
    )

    input_type = Column(String(20), nullable=False, default="upload")
    original_query = Column(Text, nullable=True)
    top_k = Column(Integer, nullable=False, default=5)
    failure_reason = Column(Text, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    reports = relationship(
        "Report",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    medical_images = relationship(
        "MedicalImage",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    summaries = relationship(
        "Summary",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    chat_history = relationship(
        "ChatHistory",
        back_populates="session",
        cascade="all, delete-orphan",
    )
