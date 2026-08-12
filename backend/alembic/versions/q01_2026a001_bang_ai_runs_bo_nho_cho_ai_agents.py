"""Bảng ai_runs — bộ nhớ cho AI Agents.

Trước đây các agent (chấm điểm lead, nhận định kinh doanh, Sales Co-Pilot) không nhớ
gì cả: mỗi lần chạy là dựng lại prompt từ đầu, kết quả dùng xong vứt. Bảng này lưu
từng lần chạy để (1) hỏi lại đúng câu cũ thì dùng lại, khỏi đốt quota, (2) có lịch sử
so kỳ, (3) biết bản này do LLM hay bộ luật sinh ra, (4) ghi nhận sale "đã làm" hay
"bỏ qua" gợi ý, để vòng sau Co-Pilot không nhắc lại đúng câu đó.

Cùng kiểu phòng thủ như o01/p01: kiểm tra tồn tại trước mỗi thao tác nên chạy lại an
toàn trên cả dev SQLite (create_all đã tạo sẵn bảng) lẫn prod Postgres.

Revision ID: q01_2026a001
Revises: p01_2026a001
Create Date: 2026-08-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'q01_2026a001'
down_revision: Union[str, Sequence[str], None] = 'p01_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    def ensure_index(table: str, name: str, cols: list[str]) -> None:
        if name not in {ix["name"] for ix in insp.get_indexes(table)}:
            op.create_index(name, table, cols, unique=False)

    if "ai_runs" not in tables:
        op.create_table(
            "ai_runs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("agent", sa.String(length=40), nullable=False),
            sa.Column("scope_type", sa.String(length=20), nullable=False, server_default="global"),
            # Không FK: scope_id trỏ tới nhiều bảng tuỳ scope_type, và bản ghi nhớ
            # phải sống sót khi lead/dự án bị xoá.
            sa.Column("scope_id", sa.String(length=36), nullable=True),
            sa.Column("input_hash", sa.String(length=64), nullable=False),
            sa.Column("output_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("source", sa.String(length=10), nullable=False, server_default="rule"),
            sa.Column("model_used", sa.String(length=120), nullable=True),
            sa.Column("outcome", sa.String(length=12), nullable=True),
            sa.Column("outcome_by", sa.String(length=36), nullable=True),
            sa.Column("outcome_at", sa.DateTime(), nullable=True),
            sa.Column("outcome_note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        # FK tạo rời để DB nào chưa có bảng users vẫn không vỡ. SQLite không hỗ trợ
        # ALTER TABLE ADD CONSTRAINT → bỏ qua (dev dùng create_all, ràng buộc có sẵn).
        if "users" in tables and bind.dialect.name != "sqlite":
            op.create_foreign_key(
                "fk_ai_runs_outcome_by", "ai_runs", "users", ["outcome_by"], ["id"]
            )
        op.create_index(
            "ix_ai_runs_scope", "ai_runs",
            ["agent", "scope_type", "scope_id", "created_at"], unique=False,
        )
        op.create_index(
            "ix_ai_runs_hash", "ai_runs", ["agent", "input_hash", "created_at"], unique=False
        )
    else:
        ensure_index("ai_runs", "ix_ai_runs_scope", ["agent", "scope_type", "scope_id", "created_at"])
        ensure_index("ai_runs", "ix_ai_runs_hash", ["agent", "input_hash", "created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "ai_runs" in set(insp.get_table_names()):
        op.drop_table("ai_runs")
