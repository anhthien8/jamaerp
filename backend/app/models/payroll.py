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
        Index("ix_transactions_type_date", "type", "date"),
        Index("ix_transactions_project", "project_id", "type"),
        Index("ix_transactions_status", "status"),
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

    # --- Công thực tế (nối từ bảng chấm công) ---
    work_days: Mapped[float] = mapped_column(Float, nullable=False, default=0)       # công thực tế (đã quy đổi)
    standard_days: Mapped[float] = mapped_column(Float, nullable=False, default=22)  # công chuẩn tháng
    ot_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0)        # OT đã duyệt
    ot_pay: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    allowance: Mapped[float] = mapped_column(Float, nullable=False, default=0)       # phụ cấp

    # --- Khấu trừ theo luật ---
    bhxh_employee: Mapped[float] = mapped_column(Float, nullable=False, default=0)   # 8+1.5+1% phía NLĐ
    bhxh_company: Mapped[float] = mapped_column(Float, nullable=False, default=0)    # 21.5% phía cty (báo cáo chi phí)
    pit: Mapped[float] = mapped_column(Float, nullable=False, default=0)             # thuế TNCN lũy tiến
    taxable_income: Mapped[float] = mapped_column(Float, nullable=False, default=0)  # thu nhập tính thuế (minh bạch phiếu lương)
    advance_deduction: Mapped[float] = mapped_column(Float, nullable=False, default=0)  # trừ tạm ứng
    gross_salary: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    # --- Snapshot & luồng duyệt ---
    salary_grade_id: Mapped[str | None] = mapped_column(String(36), nullable=True)   # bậc tại thời điểm tính
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    payslip_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # Statuses: draft -> pending_approval -> approved (khóa kỳ) -> paid
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_payrolls_period", "period"),
        Index("ix_payrolls_user_period", "user_id", "period", unique=True),
    )


class SalaryAdvance(Base):
    """Tạm ứng lương — duyệt qua Approval Center, tự trừ vào kỳ lương kế tiếp."""

    __tablename__ = "salary_advances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # Statuses: pending -> approved -> deducted | rejected | cancelled
    approval_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    period_deducted: Mapped[str | None] = mapped_column(String(10), nullable=True)  # kỳ lương đã trừ
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_advances_user_status", "user_id", "status"),
    )
