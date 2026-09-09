"""Hồ sơ nhân sự mở rộng (spec 03 §1, dựng 09/09/2026) — CCCD, HĐLĐ, giấy tờ.

Tách khỏi bảng users: dữ liệu nhạy cảm (CCCD, ngân hàng) chỉ admin/kế toán đọc
đủ; users là bảng nóng cho auth/RBAC, không nên phình thêm cột ít đọc.
"""

import uuid
from datetime import datetime, date, timezone

from sqlalchemy import String, Integer, Date, DateTime, ForeignKey, Index, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EmployeeProfile(Base):
    __tablename__ = "employee_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, unique=True)

    # Giấy tờ tùy thân — API trả dạng che cho người không đủ quyền
    national_id: Mapped[str | None] = mapped_column(String(20), nullable=True)  # số CCCD
    national_id_issued_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    national_id_issued_place: Mapped[str | None] = mapped_column(String(100), nullable=True)

    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    emergency_contact: Mapped[str | None] = mapped_column(String(200), nullable=True)  # tên + SĐT

    # Chi lương
    bank_account: Mapped[str | None] = mapped_column(String(30), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    social_insurance_no: Mapped[str | None] = mapped_column(String(20), nullable=True)  # số sổ BHXH

    # Hợp đồng lao động — worker nhắc trước 30 ngày khi sắp hết hạn
    hire_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # ngày vào làm
    contract_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # probation | fixed_1y | fixed_2y | indefinite
    contract_signed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # NULL = không thời hạn

    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return f"<EmployeeProfile user={self.user_id}>"


class EmployeeDocument(Base):
    """Ảnh giấy tờ (CCCD/HĐLĐ scan) — JPG nén phía client, lưu thẳng Postgres.

    Chủ đích KHÔNG đẩy giấy tờ tùy thân lên nhóm Telegram như ảnh công trình
    (quyết định 09/09/2026). ~100 nhân sự × vài file ≤500KB là vài chục MB,
    Postgres chịu tốt; sang kho file riêng khi có media offload (spec 05).
    """

    __tablename__ = "employee_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # cccd_front | cccd_back | contract | other
    filename: Mapped[str] = mapped_column(String(200), nullable=False)
    mime: Mapped[str] = mapped_column(String(50), nullable=False, default="image/jpeg")
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    uploaded_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    uploaded_by_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_employee_documents_user", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<EmployeeDocument {self.doc_type} user={self.user_id}>"
