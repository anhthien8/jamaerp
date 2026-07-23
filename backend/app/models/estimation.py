"""Estimation model — Dự toán cải tạo."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Float, Integer, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Estimation(Base):
    __tablename__ = "estimations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    estimation_type: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    # Types: manual (nhập số liệu), text (nhập mô tả), photo (chụp hình)

    # Input data
    description: Mapped[str | None] = mapped_column(Text, nullable=True)  # Mô tả / text
    photo_urls: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array URLs
    floor_count: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    area_sqm: Mapped[float] = mapped_column(Float, nullable=False, default=80)

    # Calculated results
    total_estimate: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Status
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # Statuses: draft, submitted, approved, ordered

    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_estimations_project", "project_id"),
        Index("ix_estimations_status", "status"),
    )

    def __repr__(self):
        return f"<Estimation {self.id} [{self.estimation_type}]>"


class EstimationItem(Base):
    """Mỗi dòng trong dự toán — liên kết với template đơn giá."""
    __tablename__ = "estimation_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    estimation_id: Mapped[str] = mapped_column(String(36), nullable=False)

    # Reference to renovation template item
    template_code: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "RD-01", "CF-1-01"
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="m2")

    # Quantity and pricing
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    total: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_estimation_items_estimation", "estimation_id"),
    )

    def __repr__(self):
        return f"<EstimationItem {self.name} x {self.quantity}>"
