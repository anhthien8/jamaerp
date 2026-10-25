"""Thư viện mẫu hợp đồng / biên bản (25/10/2026).

Tệp gốc (docx/doc/xlsx) lưu thẳng Postgres như giấy tờ nhân sự — repo public
nên mẫu HĐ không nằm trong code; BGĐ/Kế toán tải lên qua trang Hợp đồng.
13 mẫu ~37 MB, Postgres chịu được. Không xoá cứng: «Ẩn» = is_active False.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# hop_dong | bien_ban | thanh_toan | phu_luc | khac
NHOM_MAU = ("hop_dong", "bien_ban", "thanh_toan", "phu_luc", "khac")


class ContractTemplate(Base):
    __tablename__ = "contract_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False, default="khac")
    # Gợi ý mẫu theo loại HĐ trên form hợp đồng: thiet_ke | thi_cong | None
    contract_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Khóa so trùng khi tải lên lại cùng tên tệp → thay bản mới, tăng version
    file_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
