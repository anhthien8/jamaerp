"""Bảng telegram_contacts — người bot đã gặp, để admin gán vào tài khoản.

Đợt 3 (23/10/2026): Bot API không liệt kê được thành viên nhóm, nên bot ghi
lại mỗi người nhắn trong nhóm / chat riêng / vừa vào nhóm. Bảng mới hoàn toàn,
không backfill dữ liệu → không dính bài học aware/naive trên Postgres.

Revision ID: a03_2026a001
Revises: a02_2026a001
Create Date: 2026-10-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a03_2026a001'
down_revision: Union[str, Sequence[str], None] = 'a02_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bang = set(sa.inspect(op.get_bind()).get_table_names())
    if "telegram_contacts" in bang:
        return
    op.create_table(
        "telegram_contacts",
        sa.Column("tg_user_id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("username", sa.String(length=100), nullable=True),
        sa.Column("first_name", sa.String(length=100), nullable=True),
        sa.Column("last_name", sa.String(length=100), nullable=True),
        sa.Column("chat_id", sa.String(length=32), nullable=True),
        sa.Column("chat_title", sa.String(length=200), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("linked_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("telegram_contacts")
