"""Bảng project_documents — tài liệu dự án tải thẳng từ CRM lên Kho Telegram.

23/10/2026: thay cảnh «tự gửi file vào nhóm Telegram rồi dán link vào ô Lưu
File». Bảng mới hoàn toàn, không backfill.

Revision ID: a05_2026a001
Revises: a04_2026a001
Create Date: 2026-10-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a05_2026a001'
down_revision: Union[str, Sequence[str], None] = 'a04_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bang = set(sa.inspect(op.get_bind()).get_table_names())
    if "project_documents" in bang:
        return
    op.create_table(
        "project_documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime", sa.String(length=100), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("telegram_chat_id", sa.String(length=32), nullable=True),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
        sa.Column("telegram_file_id", sa.String(length=255), nullable=True),
        sa.Column("uploaded_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_project_documents_project", "project_documents", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_project_documents_project", table_name="project_documents")
    op.drop_table("project_documents")
