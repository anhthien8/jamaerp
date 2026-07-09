"""Notification & SystemSetting models — in-app notifications + automation settings."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Boolean, ForeignKey, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


NOTIFICATION_TYPES = [
    "followup_reminder",   # nhắc chăm sóc lead
    "lead_recalled",       # lead bị thu hồi
    "lead_assigned",       # lead được giao
    "payment_reminder",    # nhắc hẹn thanh toán
    "bod_report",          # báo cáo BOD
    "system",
]


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False, default="system")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)  # frontend route e.g. /leads?id=x

    # Reference for dedupe (e.g. lead_id / contract_id)
    ref_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_notifications_user_read", "user_id", "read", "created_at"),
        Index("ix_notifications_dedupe", "user_id", "type", "ref_id", "read"),
    )

    def __repr__(self) -> str:
        return f"<Notification {self.type} → {self.user_id}>"


class SystemSetting(Base):
    """Simple key-value store for automation settings (KISS)."""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<SystemSetting {self.key}={self.value}>"


# Default automation settings
DEFAULT_AUTOMATION_SETTINGS: dict[str, str] = {
    "followup_reminder_days": "3",     # nhắc CSKH sau N ngày không liên hệ
    "lead_recall_days": "7",           # thu hồi lead sau N ngày không chăm sóc
    "lead_recall_enabled": "true",
    "payment_reminder_days": "3",      # nhắc thanh toán đợt pending sau N ngày ký HĐ
    "bod_report_enabled": "true",
    "bod_report_hour": "8",            # giờ gửi báo cáo (Asia/Ho_Chi_Minh)
    "telegram_group_chat_id": "",      # chat_id nhóm Telegram công ty (vd -100123456789)
    "group_briefing_enabled": "true",  # gửi briefing nhóm hàng ngày (không kèm tài chính)
}
