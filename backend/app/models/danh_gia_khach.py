"""Khách hàng chấm sao trên trang tiến độ (Chế độ thưởng, 23/10/2026).

Khách mở link portal gửi qua Zalo, mỗi mốc của dự án (ký HĐ thiết kế, chốt bản
vẽ, bàn giao, sau 3 tháng) chấm 1 lần 1–5 sao, kèm nhận xét và có thể khen tên
một người trong đội dự án. Điểm trung bình theo quý vào Chế độ thưởng.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _bay_gio() -> datetime:
    # Cột DateTime không múi giờ → luôn ghi naive UTC (bài học Postgres tz).
    return datetime.now(timezone.utc).replace(tzinfo=None)


MOC_DANH_GIA = {
    "ky_hd_tk": "Ký hợp đồng thiết kế",
    "chot_ban_ve": "Chốt bản vẽ",
    "ban_giao": "Bàn giao",
    "sau_3_thang": "Sau 3 tháng sử dụng",
}


class DanhGiaKhach(Base):
    __tablename__ = "danh_gia_khach"
    __table_args__ = (UniqueConstraint("project_id", "moc", name="uq_danh_gia_du_an_moc"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    customer_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("customers.id"), nullable=True)
    moc: Mapped[str] = mapped_column(String(20), nullable=False)
    so_sao: Mapped[int] = mapped_column(Integer, nullable=False)
    nhan_xet: Mapped[str | None] = mapped_column(Text, nullable=True)
    khen_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_bay_gio, nullable=False, index=True)
