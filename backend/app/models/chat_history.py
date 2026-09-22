from sqlalchemy import (
    Column,
    Integer,
    Text,
    DateTime,
    ForeignKey,
)

from sqlalchemy.sql import func

from app.db.database import Base


class ChatHistory(Base):
    __tablename__ = "chat_history"

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

    session_id = Column(
        Integer,
        ForeignKey("upload_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )

    question = Column(
        Text,
        nullable=False,
    )

    answer = Column(
        Text,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
