"""Web Push: bảng push_subscriptions (mỗi máy bật thông báo một dòng).

25/10/2026. Idempotent — kiểm tra bảng trước khi tạo.

Revision ID: a11_2026a001
Revises: a10_2026a001
Create Date: 2026-10-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a11_2026a001'
down_revision: Union[str, Sequence[str], None] = 'a10_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "push_subscriptions" in insp.get_table_names():
        return
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("endpoint_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.String(length=255), nullable=False),
        sa.Column("auth", sa.String(length=255), nullable=False),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"])


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "push_subscriptions" in insp.get_table_names():
        op.drop_index("ix_push_subscriptions_user_id", table_name="push_subscriptions")
        op.drop_table("push_subscriptions")
