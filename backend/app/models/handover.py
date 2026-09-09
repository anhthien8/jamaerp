"""Vết bàn giao lead/task giữa nhân viên (dựng 09/09/2026).

Trước đây bàn giao nghỉ việc chỉ để vết dạng text trên Activity từng lead + 1
dòng audit tổng số — không truy ngược được «khách X đã sang tay ai». Từ nay mỗi
lead/task đổi chủ khi nghỉ việc = 1 dòng ở đây, tên chụp lại tại thời điểm bàn
giao (người nghỉ có thể bị đổi tên/xóa nhãn sau này).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class HandoverRecord(Base):
    __tablename__ = "handover_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    from_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    from_user_name: Mapped[str] = mapped_column(String(100), nullable=False)
    to_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    to_user_name: Mapped[str] = mapped_column(String(100), nullable=False)

    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)  # lead | task
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)  # snapshot tên khách/việc

    reason: Mapped[str] = mapped_column(String(20), nullable=False, default="resign")  # resign | manual
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    actor_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_handover_from_user", "from_user_id"),
        Index("ix_handover_to_user", "to_user_id"),
    )

    def __repr__(self) -> str:
        return f"<HandoverRecord {self.entity_type}:{self.entity_id} {self.from_user_id}→{self.to_user_id}>"
