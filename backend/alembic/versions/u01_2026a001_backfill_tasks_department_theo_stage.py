"""Backfill tasks.department theo stage.

19 task tự sinh khi lead thắng deal (PUT /leads/{id}/stage → signed_design) chỉ
đặt `stage`, để `department` NULL. Dropdown «Đảm nhận» trên FE lọc nhân sự theo
department và có nhánh «không có phòng ban → cho mọi người» ⇒ mọi task hiện toàn
bộ nhân sự công ty (đo prod 05/09: 2128/2128 task department NULL — user báo
«mục báo giá hiện cả nhân sự khác»).

Từ nay tạo task tự gán department = stage (acceptance → construction). Migration
này dọn phần tồn đọng. Chỉ đụng dòng department NULL; task đã có phòng ban do
người dùng chọn tay giữ nguyên.

Revision ID: u01_2026a001
Revises: t01_2026a001
Create Date: 2026-09-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'u01_2026a001'
down_revision: Union[str, Sequence[str], None] = 't01_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "tasks" not in set(insp.get_table_names()):
        return
    cols = {c["name"] for c in insp.get_columns("tasks")}
    if "department" not in cols or "stage" not in cols:
        return
    # CASE chuẩn SQL — chạy được cả SQLite (dev) lẫn Postgres (prod). Không đụng
    # updated_at/completed_at nên không làm lệch báo cáo tiến độ.
    bind.execute(sa.text("""
        UPDATE tasks
        SET department = CASE stage WHEN 'acceptance' THEN 'construction' ELSE stage END
        WHERE department IS NULL AND stage IS NOT NULL
    """))


def downgrade() -> None:
    # Không biết dòng nào vốn NULL — cố tình để trống.
    pass
