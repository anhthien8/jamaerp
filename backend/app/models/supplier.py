"""Supplier model — NCC (Nhà cung cấp) for interior design materials."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Float, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    zalo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)  # HCM, Hà Nội, Trung Quốc...
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
    # Categories: wood, stone, metal, paint, glass, electrical, plumbing, furniture, fabric, general
    rating: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)  # 1-5 stars
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_suppliers_category", "category"),
        Index("ix_suppliers_name", "name"),
    )

    def __repr__(self):
        return f"<Supplier {self.name}>"


class SupplierQuote(Base):
    """NCC submit giá cho 1 vật tư cụ thể. Mỗi lần submit = 1 record."""
    __tablename__ = "supplier_quotes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    supplier_id: Mapped[str] = mapped_column(String(36), nullable=False)
    material_name: Mapped[str] = mapped_column(String(255), nullable=False)  # Tên vật tư
    material_category: Mapped[str | None] = mapped_column(String(50), nullable=True)  # wood, stone, etc.
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="m2")
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    min_quantity: Mapped[float] = mapped_column(Float, nullable=False, default=1)  # SL tối thiểu
    lead_time_days: Mapped[int | None] = mapped_column(nullable=True)  # Thời gian giao hàng
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    quote_date: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_supplier_quotes_material", "material_name"),
        Index("ix_supplier_quotes_supplier", "supplier_id"),
    )

    def __repr__(self):
        return f"<SupplierQuote {self.material_name} @ {self.unit_price}>"


class PriceComparison(Base):
    """Bảng so sánh giá — tổng hợp nhiều报价 từ nhiều NCC cho 1 vật tư."""
    __tablename__ = "price_comparisons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    material_name: Mapped[str] = mapped_column(String(255), nullable=False)
    material_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    best_supplier_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    best_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    quote_count: Mapped[int] = mapped_column(nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # Statuses: pending, compared, ordered
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_price_comparisons_material", "material_name"),
    )

    def __repr__(self):
        return f"<PriceComparison {self.material_name}>"
