"""Quotation model — design & construction quotes (SQLite-compatible)."""

import uuid
from datetime import datetime, date, timezone

from sqlalchemy import String, Text, Integer, Float, Date, ForeignKey, DateTime, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Quotation(Base):
    __tablename__ = "quotations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    # Types: design, construction

    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=True
    )
    lead_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("leads.id"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # Statuses: draft, approved, sent, rejected, expired

    total_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    tax_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Line items stored as JSON
    items: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    revision: Mapped[int] = mapped_column(Integer, default=1)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    erp_quotation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    project = relationship("Project", back_populates="quotations")
    lead = relationship("Lead", back_populates="quotations")
    creator = relationship("User", foreign_keys=[created_by])
    contract = relationship("Contract", back_populates="quotation", uselist=False)

    __table_args__ = (
        Index("ix_quotations_type_status", "type", "status"),
        Index("ix_quotations_project", "project_id"),
    )

    def __repr__(self) -> str:
        return f"<Quotation {self.code} ({self.status})>"
