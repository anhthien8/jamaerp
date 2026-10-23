"""Bảng lead_attachments — ảnh đính kèm ghi chú lead, thay ô dán link Drive.

23/10/2026: lưu Postgres (LargeBinary) như employee_documents, không qua Kho
ảnh Telegram vì lead chỉ Kinh doanh + BGĐ được thấy. Bảng mới hoàn toàn,
không backfill → không dính bài học aware/naive trên Postgres.

Revision ID: a04_2026a001
Revises: a03_2026a001
Create Date: 2026-10-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a04_2026a001'
down_revision: Union[str, Sequence[str], None] = 'a03_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bang = set(sa.inspect(op.get_bind()).get_table_names())
    if "lead_attachments" in bang:
        return
    op.create_table(
        "lead_attachments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("lead_id", sa.String(length=36), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("mime", sa.String(length=50), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("uploaded_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_lead_attachments_lead", "lead_attachments", ["lead_id"])


def downgrade() -> None:
    op.drop_index("ix_lead_attachments_lead", table_name="lead_attachments")
    op.drop_table("lead_attachments")
