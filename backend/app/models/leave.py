"""Leave models — nghỉ phép (đơn + số dư phép năm)."""

import uuid
from datetime import datetime, date, timezone

from sqlalchemy import String, Float, Integer, Date, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LeaveBalance(Base):
    __tablename__ = "leave_balances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    annual_total: Mapped[float] = mapped_column(Float, nullable=False, default=12)  # 12 ngày/năm theo luật
    annual_used: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    sick_used: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    unpaid_used: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_leave_balances_user_year", "user_id", "year", unique=True),
    )

    def __repr__(self) -> str:
        return f"<LeaveBalance {self.user_id} {self.year}: {self.annual_used}/{self.annual_total}>"


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    leave_type: Mapped[str] = mapped_column(String(20), nullable=False, default="annual")
    # Types: annual (phép năm — có lương), sick (ốm — BHXH chi trả), unpaid (không lương)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    days: Mapped[float] = mapped_column(Float, nullable=False)  # hỗ trợ 0.5 ngày
    reason: Mapped[str] = mapped_column(String(500), nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # Statuses: pending, approved, rejected, cancelled — đồng bộ với ApprovalRequest
    approval_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_leave_requests_user", "user_id", "start_date"),
        Index("ix_leave_requests_status", "status"),
        Index("ix_leave_requests_dates", "start_date", "end_date"),
    )

    def __repr__(self) -> str:
        return f"<LeaveRequest {self.user_id} {self.start_date}..{self.end_date} [{self.status}]>"
