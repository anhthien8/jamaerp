"""AuditLog model — truy vết thao tác nhạy cảm (lương, quyền, nghỉ việc, duyệt)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # user thực hiện (None = hệ thống/worker)
    actor_name: Mapped[str | None] = mapped_column(String(150), nullable=True)  # snapshot tên tại thời điểm
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    # Actions: user.create, user.role_change, user.deactivate, user.resign, user.undo_resign,
    #          salary_grade.update, payroll.generate, payroll.submit, payroll.approve,
    #          payroll.reject, payroll.pay, attendance.edit, ot.approve, ot.reject,
    #          leave.approve, leave.reject, approval.approve, approval.reject ...
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)  # user, payroll, attendance, leave, ...
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    before_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_actor", "actor_id", "created_at"),
        Index("ix_audit_action", "action", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} {self.entity_type}:{self.entity_id}>"
