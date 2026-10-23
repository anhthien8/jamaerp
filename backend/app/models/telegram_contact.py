"""Người Telegram bot đã gặp (Đợt 3, 23/10/2026).

Bot API không liệt kê được thành viên nhóm, nên bot ghi lại mỗi người nhắn
trong nhóm / chat riêng / vừa vào nhóm. Admin xem danh sách «Telegram chưa
gán» ở trang Tài khoản và gán vào nhân viên bằng 1 cú bấm — thay cho việc
nhân viên tự gõ /id rồi dán vào Cài đặt.
"""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _bay_gio() -> datetime:
    # Cột DateTime không múi giờ → luôn ghi naive UTC (bài học Postgres tz).
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TelegramContact(Base):
    __tablename__ = "telegram_contacts"

    tg_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    chat_id: Mapped[str | None] = mapped_column(String(32), nullable=True)  # nơi gặp lần cuối
    chat_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=_bay_gio)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=_bay_gio)
    linked_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
