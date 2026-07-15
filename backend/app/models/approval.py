"""ApprovalRequest model — engine phê duyệt dùng chung (phép, tạm ứng, lương, chi phí, OT)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Float, Integer, ForeignKey, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    # Types: leave | advance | payroll_period | expense | overtime  (material giữ bảng riêng, migrate sau)
    ref_id: Mapped[str] = mapped_column(String(36), nullable=False)  # id bản ghi gốc
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    requester_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    current_approver_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    # Chuỗi duyệt còn lại sau approver hiện tại — CSV user_id (đơn giản, đủ cho ≤3 cấp)
    next_approvers_csv: Mapped[str | None] = mapped_column(String(255), nullable=True)
    step: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    total_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    # Statuses: pending | approved | rejected | changes_requested | cancelled
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    acted_via: Mapped[str | None] = mapped_column(String(20), nullable=True)  # web | telegram

    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    escalated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # số lần escalate
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    requester = relationship("User", foreign_keys=[requester_id])
    current_approver = relationship("User", foreign_keys=[current_approver_id])

    __table_args__ = (
        Index("ix_approvals_approver_status", "current_approver_id", "status"),
        Index("ix_approvals_requester", "requester_id", "created_at"),
        Index("ix_approvals_type_ref", "type", "ref_id"),
        Index("ix_approvals_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<ApprovalRequest {self.type}:{self.ref_id} [{self.status}] step {self.step}/{self.total_steps}>"
