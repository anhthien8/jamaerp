"""PriceItem model — bảng đơn giá chuẩn cho Báo giá sơ bộ tức thì.

Mỗi hạng mục có 3 mức giá theo phân khúc (basic / standard / premium).
Đơn giá là GIÁ BÁN (đã gồm margin) — phòng Thu mua chịu trách nhiệm cập nhật.
Seed data chỉ là số tham khảo thị trường HCM, PHẢI được Thu mua rà lại trước khi dùng thật.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Float, Boolean, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


PRICE_CATEGORIES = [
    "tran_vach",      # Trần & vách thạch cao
    "san",            # Sàn (gỗ/gạch)
    "son_giay",       # Sơn & giấy dán tường
    "tu_bep",         # Tủ bếp & phụ kiện
    "tu_ao_go",       # Tủ áo & đồ gỗ nội thất
    "sofa_ban_ghe",   # Sofa, bàn ghế
    "giuong_nem",     # Giường & nệm
    "den_dien",       # Đèn & điện
    "rem_trang_tri",  # Rèm & trang trí
    "thiet_bi",       # Thiết bị (bếp, vệ sinh)
    "khac",           # Khác (vận chuyển, nhân công phát sinh...)
]

PRICE_UNITS = ["m2", "md", "bo", "cai", "tron_goi"]  # md = mét dài, bo = bộ


class PriceItem(Base):
    __tablename__ = "price_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)  # vd: TRAN-01
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False, default="m2")

    # Giá bán theo 3 phân khúc (VND / đơn vị)
    price_basic: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    price_standard: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    price_premium: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (Index("ix_price_items_category", "category", "is_active"),)

    def __repr__(self) -> str:
        return f"<PriceItem {self.code} {self.name}>"
