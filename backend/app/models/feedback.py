"""Feedback model — employee feedback from Telegram/web."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

FEEDBACK_CATEGORIES = ["bug", "feature_request", "workflow_improvement", "other"]


class Feedback(Base):
    __tablename__ = "feedbacks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    telegram_user_id: Mapped[int | None] = mapped_column(nullable=True)

    category: Mapped[str] = mapped_column(String(30), nullable=False, default="other")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="new")
    admin_reply: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_feedbacks_status", "status"),
        Index("ix_feedbacks_user", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<Feedback {self.id} [{self.category}/{self.status}]>"
