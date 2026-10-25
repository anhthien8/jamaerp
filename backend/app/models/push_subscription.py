"""Đăng ký Web Push của từng máy (25/10/2026).

Mỗi trình duyệt/điện thoại bấm «Bật thông báo trên máy này» → một dòng. Một
người có thể có nhiều máy. Máy gỡ app / thu hồi quyền → dịch vụ push trả 404/410
→ backend xoá dòng đó (không giữ đăng ký chết).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    # sha256(endpoint) — endpoint dài vài trăm ký tự, đánh unique trên bản băm
    endpoint_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    p256dh: Mapped[str] = mapped_column(String(255), nullable=False)
    auth: Mapped[str] = mapped_column(String(255), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
