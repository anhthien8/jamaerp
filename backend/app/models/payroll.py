"""Payroll, Commission, Transaction models."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Float, ForeignKey, DateTime, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # income, expense
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    # Categories: design_contract, construction_contract, material, labor, commission, salary, other
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    project_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("projects.id"), nullable=True)
    lead_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("leads.id"), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    # Statuses: pending, completed, cancelled
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    project = relationship("Project", foreign_keys=[project_id])
    lead = relationship("Lead", foreign_keys=[lead_id])
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        Index("ix_transactions_date", "date"),
        Index("ix_transactions_type", "type"),
    )


class Commission(Base):
    __tablename__ = "commissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    project_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("projects.id"), nullable=True)
    lead_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("leads.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    # Types: design_commission, construction_commission, leader_override
    rate: Mapped[float] = mapped_column(Float, nullable=False)  # e.g., 0.03 = 3%
    base_amount: Mapped[float] = mapped_column(Float, nullable=False)
    commission_amount: Mapped[float] = mapped_column(Float, nullable=False)
    milestone: Mapped[str] = mapped_column(String(30), nullable=False, default="signing")
    # Milestones: signing (50%), rough_complete (30%), handover (20%)
    milestone_pct: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # Statuses: pending, approved, paid
    period: Mapped[str | None] = mapped_column(String(10), nullable=True)  # e.g., "2026-06"
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    project = relationship("Project", foreign_keys=[project_id])


class Payroll(Base):
    __tablename__ = "payrolls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    period: Mapped[str] = mapped_column(String(10), nullable=False)  # "2026-06"
    base_salary: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    commission_total: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    bonus: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    deductions: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    net_salary: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # Statuses: draft, approved, paid
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_payrolls_period", "period"),
    )
