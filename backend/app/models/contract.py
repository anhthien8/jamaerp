"""Contract model — hợp đồng with payment terms (SQLite-compatible)."""

import uuid
from datetime import datetime, date, timezone

from sqlalchemy import String, Text, Integer, Float, Date, ForeignKey, DateTime, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )
    quotation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("quotations.id"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # Statuses: draft, approved, sent, signed, completed, cancelled

    total_value: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Payment terms — 4 đợt 25% default
    payment_terms: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=lambda: {
            "installments": [
                {"name": "Đợt 1 (Đặt cọc)", "percentage": 25, "milestone": "signing", "status": "pending"},
                {"name": "Đợt 2 (Nghiệm thu phần thô)", "percentage": 25, "milestone": "rough_complete", "status": "pending"},
                {"name": "Đợt 3 (Nghiệm thu nội thất)", "percentage": 25, "milestone": "interior_complete", "status": "pending"},
                {"name": "Đợt 4 (Bàn giao)", "percentage": 25, "milestone": "handover", "status": "pending"},
            ]
        },
    )

    signed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    working_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    erp_contract_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    project = relationship("Project", back_populates="contracts")
    quotation = relationship("Quotation", back_populates="contract")

    __table_args__ = (
        Index("ix_contracts_project", "project_id"),
        Index("ix_contracts_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Contract {self.code} ({self.status})>"
