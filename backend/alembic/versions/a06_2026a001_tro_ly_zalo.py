"""Trợ lý Zalo: lưu phiên, nhóm theo phòng ban, cờ tin nhân viên, bảng nhân viên Zalo + tóm tắt ngày.

23/10/2026: hoàn thiện spec 09 cho trưởng phòng/BGĐ. Cột mới đều nullable
(hoặc có mặc định) — không backfill. Hai bảng mới tạo nếu chưa có.

Revision ID: a06_2026a001
Revises: a05_2026a001
Create Date: 2026-10-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a06_2026a001'
down_revision: Union[str, Sequence[str], None] = 'a05_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _them_cot(bang: str, cot: sa.Column) -> None:
    insp = sa.inspect(op.get_bind())
    if bang not in insp.get_table_names():
        return
    if cot.name in {c["name"] for c in insp.get_columns(bang)}:
        return
    op.add_column(bang, cot)


def upgrade() -> None:
    _them_cot("zalo_session", sa.Column("credentials_enc", sa.Text(), nullable=True))
    _them_cot("zalo_groups", sa.Column("department", sa.String(length=20), nullable=True))
    _them_cot("zalo_groups", sa.Column("member_count", sa.Integer(), nullable=True))
    _them_cot("zalo_groups", sa.Column("last_message_at", sa.DateTime(), nullable=True))
    _them_cot("zalo_messages", sa.Column("is_staff", sa.Boolean(), nullable=False, server_default=sa.false()))

    bang = set(sa.inspect(op.get_bind()).get_table_names())
    if "zalo_staff" not in bang:
        op.create_table(
            "zalo_staff",
            sa.Column("zalo_id", sa.String(length=64), primary_key=True),
            sa.Column("name", sa.String(length=150), nullable=True),
            sa.Column("last_seen", sa.DateTime(), nullable=True),
        )
    if "zalo_digests" not in bang:
        op.create_table(
            "zalo_digests",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("day", sa.Date(), nullable=False),
            sa.Column("group_id", sa.String(length=36), sa.ForeignKey("zalo_groups.id"), nullable=False),
            sa.Column("msg_count", sa.Integer(), nullable=True),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("by_llm", sa.Boolean(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("day", "group_id", name="uq_zalo_digest_day_group"),
        )


def downgrade() -> None:
    op.drop_table("zalo_digests")
    op.drop_table("zalo_staff")
    op.drop_column("zalo_messages", "is_staff")
    op.drop_column("zalo_groups", "last_message_at")
    op.drop_column("zalo_groups", "member_count")
    op.drop_column("zalo_groups", "department")
    op.drop_column("zalo_session", "credentials_enc")
