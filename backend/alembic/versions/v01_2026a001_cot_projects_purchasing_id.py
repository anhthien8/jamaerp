"""Cột projects.purchasing_id — PIC Báo giá – Thu mua.

Dự án vốn có 3 PIC (pm_id, designer_id, sales_id) nhưng THIẾU hẳn bộ phận
Dự toán – Thu mua, nên nhân sự PURCHASING không gắn được vào dự án và cũng
không lọc được «dự án của tôi».

Đo prod 05/09 trước khi sửa: 113 dự án — sales_id có đủ 113, nhưng pm_id 0 và
designer_id 0 (form tạo/sửa dự án chưa từng cho chọn 2 vai này).

Revision ID: v01_2026a001
Revises: u01_2026a001
Create Date: 2026-09-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'v01_2026a001'
down_revision: Union[str, Sequence[str], None] = 'u01_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "projects" not in set(insp.get_table_names()):
        return
    cols = {c["name"] for c in insp.get_columns("projects")}
    if "purchasing_id" not in cols:
        op.add_column("projects", sa.Column("purchasing_id", sa.String(length=36), nullable=True))

    # Index cho bộ lọc phạm vi dự án: subquery «dự án tôi có đầu việc» quét
    # tasks.assigned_to mỗi lần mở danh sách (2128 task prod, chưa từng có index).
    if "tasks" in set(insp.get_table_names()):
        idx = {i["name"] for i in insp.get_indexes("tasks")}
        if "ix_tasks_assigned" not in idx:
            op.create_index("ix_tasks_assigned", "tasks", ["assigned_to"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "projects" not in set(insp.get_table_names()):
        return
    if "tasks" in set(insp.get_table_names()):
        idx = {i["name"] for i in insp.get_indexes("tasks")}
        if "ix_tasks_assigned" in idx:
            op.drop_index("ix_tasks_assigned", table_name="tasks")
    cols = {c["name"] for c in insp.get_columns("projects")}
    if "purchasing_id" in cols:
        op.drop_column("projects", "purchasing_id")
