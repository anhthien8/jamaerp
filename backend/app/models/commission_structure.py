"""Commission Structure model (Co cau hoa hong theo phong ban)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Float, Date, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

TRANG_THAI_CHO_DUYET = "cho_duyet"
TRANG_THAI_DA_DUYET = "da_duyet"
TRANG_THAI_TU_CHOI = "tu_choi"


class CommissionStructure(Base):
    __tablename__ = "commission_structures"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    department: Mapped[str] = mapped_column(String(50), nullable=False)
    commission_type: Mapped[str] = mapped_column(String(50), nullable=False)
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    effective_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    # Chỉ dòng `da_duyet` (BGĐ đã xác nhận) mới được hợp đồng dùng — xem services/hoa_hong.py
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TRANG_THAI_CHO_DUYET)
    approval_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<CommissionStructure {self.department} {self.commission_type} {self.rate}>"
