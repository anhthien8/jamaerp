"""Bảng bonuses (thưởng) — GĐ B hồ sơ nhân sự 360°.

Yêu cầu 12/09/2026: đề xuất thưởng qua Approval Center, tự cộng vào
dòng lương kỳ, chốt paid khi chi lương. Vòng đời: pending→approved→paid
(tương tự Commission/SalaryAdvance).

Revision ID: x01_2026a001
Revises: w01_2026a001
Create Date: 2026-09-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'x01_2026a001'
down_revision: Union[str, Sequence[str], None] = 'w01_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "bonuses" not in tables:
        op.create_table(
            "bonuses",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("period", sa.String(10), nullable=False),
            sa.Column("amount", sa.Float(), nullable=False),
            sa.Column("reason", sa.String(500), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("approval_id", sa.String(36), nullable=True),
            sa.Column("created_by", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_bonuses_user_period", "bonuses", ["user_id", "period"])
        op.create_index("ix_bonuses_period_status", "bonuses", ["period", "status"])


def downgrade() -> None:
    op.drop_table("bonuses")
