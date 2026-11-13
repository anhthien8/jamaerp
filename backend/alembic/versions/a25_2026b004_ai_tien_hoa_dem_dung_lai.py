"""AI Tiến Hoá: đếm số lần một bản ai_runs được trả lại từ bộ nhớ (13/11/2026).

Một cột int mặc định 0 — bản ghi cũ coi như chưa từng được dùng lại. Bài học Co-Pilot
lưu ở system_settings (khoá ai_bai_hoc), không cần bảng mới.

Revision ID: a25_2026b004
Revises: a24_2026b003
Create Date: 2026-11-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a25_2026b004'
down_revision: Union[str, Sequence[str], None] = 'a24_2026b003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    da_co = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("ai_runs")}
    if "so_lan_dung_lai" not in da_co:
        op.add_column(
            "ai_runs",
            sa.Column("so_lan_dung_lai", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    with op.batch_alter_table("ai_runs") as batch_op:
        batch_op.drop_column("so_lan_dung_lai")
