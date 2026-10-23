"""Zalo Listener models — trợ lý nghe nhóm Zalo (spec 09).

Nguyên tắc dữ liệu: ZaloSignal là tài sản (giữ lâu), ZaloMessage là đệm tạm
(retention ≤7 ngày, job đêm xóa). Session lưu trạng thái đăng nhập QR để admin
theo dõi trên web; Ingest Service (Node zca-js) đẩy QR + heartbeat về qua API.
"""

import uuid
from datetime import date as date_type, datetime, timezone

from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, Index, Integer, Date, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ZaloSession(Base):
    """Singleton (id='default') — trạng thái phiên đăng nhập tài khoản Zalo listener."""

    __tablename__ = "zalo_session"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default="default")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="logged_out")
    # logged_out | awaiting_qr | qr_ready | logged_in | error
    qr_image: Mapped[str | None] = mapped_column(Text, nullable=True)   # data URI base64 (do ingest service đẩy lên)
    account_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    error_msg: Mapped[str | None] = mapped_column(String(500), nullable=True)
    login_requested: Mapped[bool] = mapped_column(Boolean, default=False)  # admin bấm đăng nhập → ingest service nhận
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # heartbeat gần nhất từ ingest service
    # Cookie + imei phiên Zalo (mã hóa Fernet) — dịch vụ khởi động lại tự vào, khỏi quét QR lại
    credentials_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )


class ZaloGroup(Base):
    __tablename__ = "zalo_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    zalo_group_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="internal")  # internal | customer
    assigned_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    monitoring: Mapped[bool] = mapped_column(Boolean, default=True)
    consent_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Phòng ban sở hữu nhóm — trưởng phòng phòng đó thấy tín hiệu + tóm tắt nhóm này
    department: Mapped[str | None] = mapped_column(String(20), nullable=True)
    member_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_zalo_groups_kind", "kind"),
    )


class ZaloMessage(Base):
    """RAW — retention ngắn (job đêm xóa >7 ngày). Chỉ đệm để phân tích + truy vết ngắn hạn."""

    __tablename__ = "zalo_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("zalo_groups.id"), nullable=False)
    sender_zalo_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sender_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)  # link, không lưu ảnh thô
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)  # người gửi là nhân viên (đã nhắn trong nhóm nội bộ)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_zalo_messages_group_time", "group_id", "created_at"),
    )


class ZaloSignal(Base):
    """OUTPUT có giá trị — giữ lâu, đẩy về Telegram/web."""

    __tablename__ = "zalo_signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("zalo_groups.id"), nullable=False)
    source_msg_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    # lead_candidate | commitment | quote_request | unanswered | deal_risk | faq
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="new")  # new | actioned | dismissed
    assigned_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    group = relationship("ZaloGroup", foreign_keys=[group_id])

    __table_args__ = (
        Index("ix_zalo_signals_status", "status", "created_at"),
        Index("ix_zalo_signals_group", "group_id"),
        Index("ix_zalo_signals_assigned", "assigned_user_id", "status"),
    )


class ZaloStaff(Base):
    """Tài khoản Zalo được coi là NHÂN VIÊN: đã từng nhắn trong nhóm nội bộ.

    Dùng để phân biệt tin khách/tin nhân viên trong nhóm khách (cảnh báo khách
    chờ). Giữ lâu, không nằm trong luật xóa tin thô 7 ngày.
    """

    __tablename__ = "zalo_staff"

    zalo_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class ZaloDigest(Base):
    """Tóm tắt cuối ngày của 1 nhóm — giữ lâu (là tín hiệu tổng hợp, không phải tin thô)."""

    __tablename__ = "zalo_digests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    day: Mapped[date_type] = mapped_column(Date, nullable=False)
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("zalo_groups.id"), nullable=False)
    msg_count: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    by_llm: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("day", "group_id", name="uq_zalo_digest_day_group"),
    )
