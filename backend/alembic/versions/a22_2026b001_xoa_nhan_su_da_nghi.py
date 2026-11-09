"""Xoá (ẩn) nhân sự đã nghỉ khỏi danh sách.

10/11/2026: thêm users.archived_at — người đã nghỉ bấm «Xoá» thì ẩn khỏi màn
Nhân sự nhưng giữ lịch sử lead/đầu việc. (Ngày khảo sát của lead dùng cột
leads.survey_date có sẵn.)

Revision ID: a22_2026b001
Revises: a21_2026a001
Create Date: 2026-11-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a22_2026b001'
down_revision: Union[str, Sequence[str], None] = 'a21_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("archived_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "archived_at")
