"""Kho ảnh công trình (Storage Gateway — Đợt 2, 23/10/2026).

Ảnh KHÔNG nằm trong DB: bản gốc đăng vào nhóm Telegram nội bộ «JAMA Công
trình» (mỗi dự án một topic), worker sao thêm một bản sang Google Drive công
ty. DB chỉ giữ metadata + mã file Telegram để stream lại qua
`/api/v1/media/{id}/{sig}.jpg`.

Lý do (feedback 21/10): web gửi ảnh base64 vào `task_activities.media_url`
VARCHAR(500) → Postgres từ chối; bot lưu `file_id` thô làm link → ảnh vỡ.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Loại ảnh — `tien_do` mặc định chia sẻ cho khách xem trên portal.
MEDIA_KINDS = ("tien_do", "su_co", "vat_tu", "khac")


class ProjectDocument(Base):
    """Tài liệu dự án (PDF/DWG/SKP/Excel…) tải thẳng từ ERP (23/10/2026).

    Trước đây nhân viên phải tự gửi file vào nhóm Telegram rồi dán link vào ô
    «Lưu File» — chủ dự án thấy làm khó nhân viên. Nay ERP nhận file (≤50MB, giới
    hạn gửi của Bot API) và bot đăng vào topic dự án trong nhóm Kho ảnh. Tải về:
    ≤20MB backend stream lại (giới hạn getFile); lớn hơn chuyển sang link tin nhắn
    Telegram (người trong nhóm mở được).
    """

    __tablename__ = "project_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("projects.id"), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    telegram_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    uploaded_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    __table_args__ = (
        Index("ix_project_documents_project", "project_id"),
    )


class MediaFile(Base):
    __tablename__ = "media_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # sha256 của JPG đã chuẩn hoá (ảnh từ web) hoặc "tg:<file_unique_id>" (ảnh
    # từ Telegram) — trùng thì trả bản cũ, không đăng lại.
    sha256: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    mime: Mapped[str] = mapped_column(String(50), nullable=False, default="image/jpeg")
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("projects.id"), nullable=True)
    uploaded_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    caption: Mapped[str | None] = mapped_column(String(300), nullable=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="tien_do")
    shared_with_customer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    telegram_chat_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    telegram_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Link tải của Telegram sống ~1 giờ → cache 50 phút.
    telegram_file_path_cached: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cached_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    drive_file_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # pending | done | error | skipped
    mirror_status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")
    mirror_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    __table_args__ = (
        Index("ix_media_files_project", "project_id", "created_at"),
        Index("ix_media_files_mirror", "mirror_status"),
    )

    def __repr__(self) -> str:
        return f"<MediaFile {self.id} {self.kind}>"
