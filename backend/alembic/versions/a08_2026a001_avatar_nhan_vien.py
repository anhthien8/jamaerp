"""Ảnh đại diện nhân viên: cột users.avatar_ver + bảng user_avatars.

24/10/2026. Idempotent — kiểm tra cột/bảng trước khi tạo. Không backfill.

Revision ID: a08_2026a001
Revises: a07_2026a001
Create Date: 2026-10-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a08_2026a001'
down_revision: Union[str, Sequence[str], None] = 'a07_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    cot = {c["name"] for c in insp.get_columns("users")}
    if "avatar_ver" not in cot:
        op.add_column("users", sa.Column("avatar_ver", sa.Integer(), nullable=True))
    if "user_avatars" not in insp.get_table_names():
        op.create_table(
            "user_avatars",
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), primary_key=True),
            sa.Column("data", sa.LargeBinary(), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "user_avatars" in insp.get_table_names():
        op.drop_table("user_avatars")
    if "avatar_ver" in {c["name"] for c in insp.get_columns("users")}:
        op.drop_column("users", "avatar_ver")
