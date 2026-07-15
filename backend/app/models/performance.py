"""Performance models — KPI snapshots, coaching notes, review cycles."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Float, ForeignKey, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class KpiSnapshot(Base):
    __tablename__ = "kpi_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    period: Mapped[str] = mapped_column(String(10), nullable=False)  # "2026-07"

    metrics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0)  # 0-100

    rank_in_team: Mapped[int | None] = mapped_column(nullable=True)
    rank_overall: Mapped[int | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_kpi_user_period", "user_id", "period", unique=True),
    )

    def __repr__(self) -> str:
        return f"<KpiSnapshot {self.user_id} {self.period} score={self.score}>"


class CoachingNote(Base):
    __tablename__ = "coaching_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    coach_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    note: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="one_on_one")
    # Kinds: one_on_one, praise, concern, plan

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    user = relationship("User", foreign_keys=[user_id])
    coach = relationship("User", foreign_keys=[coach_id])

    __table_args__ = (
        Index("ix_coaching_user", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<CoachingNote {self.user_id} kind={self.kind}>"


class ReviewCycle(Base):
    __tablename__ = "review_cycles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    period: Mapped[str] = mapped_column(String(7), nullable=False)  # "2026-Q3"

    self_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    leader_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    goals_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending_self")
    # Statuses: pending_self, pending_leader, done

    suggested_grade_change: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_review_user_period", "user_id", "period", unique=True),
    )

    def __repr__(self) -> str:
        return f"<ReviewCycle {self.user_id} {self.period} status={self.status}>"
