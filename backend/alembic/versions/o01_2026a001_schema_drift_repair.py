"""Sửa drift schema prod: cột model chưa từng có revision + bảng zalo bị stamp nhảy cóc.

Phát hiện 12/08/2026 khi GET /projects 500 trên prod (UndefinedColumnError pause_reason).
Diff toàn bộ ORM metadata vs information_schema prod cho ra đúng 8 đối tượng thiếu:
- projects.pause_reason / paused_at (vào model 24/07, sau baseline 15/07, quên viết revision)
- projects.warranty_end_date, tasks.final_file_versions (tương tự)
- 4 bảng zalo_* (h09 có create_table nhưng prod từng bị stamp qua mà không chạy)

Mọi thao tác đều kiểm tra tồn tại trước (inspector) — chạy lại an toàn trên cả DB
đã đủ schema (dev SQLite create_all) lẫn DB thiếu (prod Postgres).

Revision ID: o01_2026a001
Revises: n01_2026a001
Create Date: 2026-08-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'o01_2026a001'
down_revision: Union[str, Sequence[str], None] = 'n01_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    def missing_cols(table: str, wanted: dict[str, sa.Column]) -> list[sa.Column]:
        have = {c["name"] for c in insp.get_columns(table)}
        return [col for name, col in wanted.items() if name not in have]

    if "projects" in tables:
        for col in missing_cols("projects", {
            "pause_reason": sa.Column("pause_reason", sa.Text(), nullable=True),
            "paused_at": sa.Column("paused_at", sa.DateTime(), nullable=True),
            "warranty_end_date": sa.Column("warranty_end_date", sa.DateTime(), nullable=True),
        }):
            op.add_column("projects", col)

    if "tasks" in tables:
        for col in missing_cols("tasks", {
            "final_file_versions": sa.Column("final_file_versions", sa.JSON(), nullable=True),
        }):
            op.add_column("tasks", col)

    # ── Bảng Zalo (định nghĩa y hệt h09_2026a001) ──
    # Index kiểm tra độc lập với bảng: drift kiểu "bảng còn, index mất" cũng được vá.
    ZALO_INDEXES: dict[str, list[tuple[str, list[str]]]] = {
        "zalo_groups": [("ix_zalo_groups_kind", ["kind"])],
        "zalo_messages": [("ix_zalo_messages_group_time", ["group_id", "created_at"])],
        "zalo_signals": [
            ("ix_zalo_signals_status", ["status", "created_at"]),
            ("ix_zalo_signals_group", ["group_id"]),
            ("ix_zalo_signals_assigned", ["assigned_user_id", "status"]),
        ],
    }

    def ensure_indexes(table: str) -> None:
        have = {ix["name"] for ix in insp.get_indexes(table)}
        for name, cols in ZALO_INDEXES.get(table, []):
            if name not in have:
                op.create_index(name, table, cols, unique=False)

    if "zalo_session" not in tables:
        op.create_table(
            "zalo_session",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="logged_out"),
            sa.Column("qr_image", sa.Text(), nullable=True),
            sa.Column("account_name", sa.String(length=150), nullable=True),
            sa.Column("error_msg", sa.String(length=500), nullable=True),
            sa.Column("login_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("last_seen", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    if "zalo_groups" not in tables:
        op.create_table(
            "zalo_groups",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("zalo_group_id", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("kind", sa.String(length=20), nullable=False, server_default="internal"),
            sa.Column("assigned_user_id", sa.String(length=36), nullable=True),
            sa.Column("monitoring", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("consent_ref", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("zalo_group_id"),
        )
        op.create_index("ix_zalo_groups_kind", "zalo_groups", ["kind"], unique=False)
    else:
        ensure_indexes("zalo_groups")

    if "zalo_messages" not in tables:
        op.create_table(
            "zalo_messages",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("group_id", sa.String(length=36), nullable=False),
            sa.Column("sender_zalo_id", sa.String(length=64), nullable=True),
            sa.Column("sender_name", sa.String(length=150), nullable=True),
            sa.Column("text", sa.Text(), nullable=True),
            sa.Column("media_ref", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["group_id"], ["zalo_groups.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_zalo_messages_group_time", "zalo_messages", ["group_id", "created_at"], unique=False)
    else:
        ensure_indexes("zalo_messages")

    if "zalo_signals" not in tables:
        op.create_table(
            "zalo_signals",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("group_id", sa.String(length=36), nullable=False),
            sa.Column("source_msg_id", sa.String(length=36), nullable=True),
            sa.Column("type", sa.String(length=20), nullable=False),
            sa.Column("summary", sa.String(length=500), nullable=False),
            sa.Column("payload_json", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="new"),
            sa.Column("assigned_user_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["group_id"], ["zalo_groups.id"]),
            sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_zalo_signals_status", "zalo_signals", ["status", "created_at"], unique=False)
        op.create_index("ix_zalo_signals_group", "zalo_signals", ["group_id"], unique=False)
        op.create_index("ix_zalo_signals_assigned", "zalo_signals", ["assigned_user_id", "status"], unique=False)
    else:
        ensure_indexes("zalo_signals")


def downgrade() -> None:
    # Revision sửa drift — cố ý KHÔNG revert: upgrade() có guard tồn-tại nên không thể
    # biết đối tượng nào do chính nó thêm. `downgrade -1` chỉ lùi con trỏ version,
    # schema giữ nguyên (version tạm lệch schema); chạy upgrade lại vẫn no-op an toàn.
    pass
