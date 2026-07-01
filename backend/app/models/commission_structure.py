"""Commission Structure model (Co cau hoa hong theo phong ban)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Float, Date, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CommissionStructure(Base):
    __tablename__ = "commission_structures"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    department: Mapped[str] = mapped_column(String(50), nullable=False)
    commission_type: Mapped[str] = mapped_column(String(50), nullable=False)
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    effective_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<CommissionStructure {self.department} {self.commission_type} {self.rate}>"
