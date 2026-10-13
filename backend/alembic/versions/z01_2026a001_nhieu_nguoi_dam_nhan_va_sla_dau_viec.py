"""Nhiều người đảm nhận một đầu việc + mốc SLA cho đầu việc.

Chủ dự án yêu cầu 13/10/2026:
1. Khu vực «Người đảm nhận» của đầu việc phải gắn được NHIỀU người, tất cả
   ngang vai (không có chính/phụ).
2. Phải có thông báo khi được gắn vào việc, khi việc quá hạn, khi việc vượt SLA.

Đo trước khi làm: cột `tasks.assigned_to` là FK đơn — mỗi việc chỉ một người.
Không bỏ cột này: 4 chỗ trong backend và cả FE đang đọc nó, và phạm vi xem dự án
của nhân viên dựa vào nó. Thay vào đó thêm bảng `task_assignees` làm nguồn sự
thật, còn `assigned_to` giữ lại như BẢN SAO của một người bất kỳ trong nhóm để
dữ liệu cũ và truy vấn cũ không gãy giữa chừng.

`started_at` cần cho SLA: SLA đếm từ lúc việc bắt đầu chạy, không phải từ lúc
dự án mở — 19 đầu việc mẫu sinh cùng lúc lúc «Deal thắng» nên đếm từ created_at
thì việc nghiệm thu vi phạm SLA ngay ngày đầu.

Revision ID: z01_2026a001
Revises: y01_2026a001
Create Date: 2026-10-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'z01_2026a001'
down_revision: Union[str, Sequence[str], None] = 'y01_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    bang = set(insp.get_table_names())
    if "tasks" not in bang:
        return

    cols = {c["name"] for c in insp.get_columns("tasks")}
    if "started_at" not in cols:
        op.add_column("tasks", sa.Column("started_at", sa.DateTime(), nullable=True))
    if "sla_due_at" not in cols:
        op.add_column("tasks", sa.Column("sla_due_at", sa.DateTime(), nullable=True))

    if "task_assignees" not in bang:
        op.create_table(
            "task_assignees",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("task_id", sa.String(length=36), sa.ForeignKey("tasks.id"), nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("task_id", "user_id", name="uq_task_assignee"),
        )
        op.create_index("ix_task_assignees_task", "task_assignees", ["task_id"])
        op.create_index("ix_task_assignees_user", "task_assignees", ["user_id"])

        # Backfill: mỗi việc đang có người làm → một dòng trong bảng mới. Dùng
        # hex(randomblob) / gen_random_uuid tuỳ DB thì kém di động, nên sinh id
        # bằng Python rồi chèn theo lô.
        import uuid
        from datetime import datetime, timezone

        rows = bind.execute(
            sa.text("SELECT id, assigned_to FROM tasks WHERE assigned_to IS NOT NULL")
        ).fetchall()
        # Người đã nghỉ việc bị xoá khỏi bảng users thì dòng cũ trong tasks vẫn
        # trỏ tới id đó; chèn thẳng sẽ vỡ khoá ngoại nên lọc trước.
        nguoi_that = {
            r[0] for r in bind.execute(sa.text("SELECT id FROM users")).fetchall()
        }
        now = datetime.now(timezone.utc)
        payload = [
            {"id": str(uuid.uuid4()), "task_id": tid, "user_id": uid, "created_at": now}
            for tid, uid in rows
            if uid in nguoi_that
        ]
        if payload:
            bang_moi = sa.table(
                "task_assignees",
                sa.column("id", sa.String),
                sa.column("task_id", sa.String),
                sa.column("user_id", sa.String),
                sa.column("created_at", sa.DateTime),
            )
            op.bulk_insert(bang_moi, payload)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    bang = set(insp.get_table_names())
    if "task_assignees" in bang:
        op.drop_index("ix_task_assignees_user", table_name="task_assignees")
        op.drop_index("ix_task_assignees_task", table_name="task_assignees")
        op.drop_table("task_assignees")
    if "tasks" in bang:
        cols = {c["name"] for c in insp.get_columns("tasks")}
        if "sla_due_at" in cols:
            op.drop_column("tasks", "sla_due_at")
        if "started_at" in cols:
            op.drop_column("tasks", "started_at")
