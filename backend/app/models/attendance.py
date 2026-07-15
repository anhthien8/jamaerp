"""Attendance model — chấm công toàn công ty (văn phòng + công trình)."""

import uuid
from datetime import datetime, date, timezone

from sqlalchemy import String, Float, Boolean, Date, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    # Ngày công theo giờ VN (Asia/Ho_Chi_Minh) — KHÔNG dùng UTC để cắt ngày
    work_date: Mapped[date] = mapped_column(Date, nullable=False)

    check_in: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    check_out: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    check_in_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    check_in_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("projects.id"), nullable=True)

    source: Mapped[str] = mapped_column(String(20), nullable=False, default="web")
    # Sources: web, telegram, leave (ngày nghỉ phép), auto (hệ thống tự đóng ca)

    work_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    ot_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    ot_status: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    # OT statuses: none, pending, approved, rejected

    # Ca bị hệ thống tự đóng (quên checkout) — leader cần xác nhận lại giờ công
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    user = relationship("User", foreign_keys=[user_id])
    project = relationship("Project", foreign_keys=[project_id])

    __table_args__ = (
        # 1 người 1 bản ghi/ngày — check-in nhiều lần chỉ cập nhật check_out
        Index("ix_attendance_user_date", "user_id", "work_date", unique=True),
        Index("ix_attendance_date", "work_date"),
        Index("ix_attendance_ot_status", "ot_status"),
    )

    def __repr__(self) -> str:
        return f"<AttendanceRecord {self.user_id} {self.work_date}>"
