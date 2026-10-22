"""Kho ảnh công trình (Storage Gateway) + phân loại nhật ký đầu việc.

Feedback 21/10/2026: gửi ảnh từ web/Telegram lỗi. Gốc: web nhét ảnh base64
vào `task_activities.media_url` VARCHAR(500) (Postgres từ chối), bot lưu
`file_id` Telegram thô làm link (ảnh vỡ). Đợt 2:

1. Bảng `media_files` — DB chỉ giữ metadata; ảnh nằm ở nhóm Telegram nội bộ
   (1 topic/dự án) + bản sao Drive.
2. `projects.telegram_topic_id`, `projects.drive_folder_id`.
3. `task_activities.kind` để portal khách chỉ hiện nhật ký tiến độ (trước đây
   khách thấy cả sự cố, yêu cầu vật tư, check-in của thợ). Backfill theo nội
   dung bằng UPDATE thuần — không chèn mốc thời gian nên không dính bài học
   aware/naive trên Postgres.

Revision ID: a02_2026a001
Revises: z01_2026a001
Create Date: 2026-10-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a02_2026a001'
down_revision: Union[str, Sequence[str], None] = 'z01_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    bang = set(insp.get_table_names())

    if "projects" in bang:
        cols = {c["name"] for c in insp.get_columns("projects")}
        if "telegram_topic_id" not in cols:
            op.add_column("projects", sa.Column("telegram_topic_id", sa.Integer(), nullable=True))
        if "drive_folder_id" not in cols:
            op.add_column("projects", sa.Column("drive_folder_id", sa.String(length=100), nullable=True))

    if "task_activities" in bang:
        cols = {c["name"] for c in insp.get_columns("task_activities")}
        if "kind" not in cols:
            op.add_column(
                "task_activities",
                sa.Column("kind", sa.String(length=20), nullable=False, server_default="khac"),
            )
        # Chỉ đụng dòng còn «khac» → chạy lại bao nhiêu lần cũng an toàn.
        for kind, dieu_kien in (
            ("cham_cong", "content LIKE 'CHECK-IN%' OR content LIKE 'CHECK-OUT%'"),
            ("vat_tu", "content LIKE 'Yeu cau vat tu:%' OR content LIKE 'Yêu cầu vật tư%'"),
            ("su_co", "content LIKE '[Bao cao su co%' OR content LIKE 'Sự cố%'"),
            ("tien_do", "media_url IS NOT NULL AND media_url <> ''"),
        ):
            bind.execute(sa.text(
                f"UPDATE task_activities SET kind = '{kind}' WHERE kind = 'khac' AND ({dieu_kien})"
            ))

    if "media_files" not in bang:
        op.create_table(
            "media_files",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("sha256", sa.String(length=80), nullable=False, unique=True),
            sa.Column("mime", sa.String(length=50), nullable=False, server_default="image/jpeg"),
            sa.Column("size_bytes", sa.Integer(), nullable=True),
            sa.Column("width", sa.Integer(), nullable=True),
            sa.Column("height", sa.Integer(), nullable=True),
            sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id"), nullable=True),
            sa.Column("uploaded_by", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("caption", sa.String(length=300), nullable=True),
            sa.Column("kind", sa.String(length=20), nullable=False, server_default="tien_do"),
            sa.Column("shared_with_customer", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("telegram_chat_id", sa.String(length=32), nullable=True),
            sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
            sa.Column("telegram_file_id", sa.String(length=255), nullable=True),
            sa.Column("telegram_file_path_cached", sa.String(length=255), nullable=True),
            sa.Column("cached_at", sa.DateTime(), nullable=True),
            sa.Column("drive_file_id", sa.String(length=100), nullable=True),
            sa.Column("mirror_status", sa.String(length=10), nullable=False, server_default="pending"),
            sa.Column("mirror_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_media_files_project", "media_files", ["project_id", "created_at"])
        op.create_index("ix_media_files_mirror", "media_files", ["mirror_status"])


def downgrade() -> None:
    bind = op.get_bind()
    bang = set(sa.inspect(bind).get_table_names())
    if "media_files" in bang:
        op.drop_index("ix_media_files_mirror", table_name="media_files")
        op.drop_index("ix_media_files_project", table_name="media_files")
        op.drop_table("media_files")
    with op.batch_alter_table("task_activities") as b:
        b.drop_column("kind")
    with op.batch_alter_table("projects") as b:
        b.drop_column("drive_folder_id")
        b.drop_column("telegram_topic_id")
