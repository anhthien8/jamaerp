"""Fixed Cost model (Chi phi Dinh phi)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Float, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FixedCost(Base):
    __tablename__ = "fixed_costs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    month: Mapped[str] = mapped_column(String(7), nullable=False)  # "2026-06"
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<FixedCost {self.category} {self.amount} ({self.month})>"
