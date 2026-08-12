"""Bổ sung 5 bảng (NCC, dự toán) + cột material_requests.task_id chưa từng có revision.

Phát hiện 12/08/2026 trong đợt QC/QA trước khi phát hành beta:
- GET /suppliers 500 (UndefinedTableError "suppliers") → cả module NCC chết trên prod.
- GET /dashboard/personal 500 (UndefinedColumnError "material_requests.task_id") →
  trang chủ của MỌI vai trò hỏng, đây là màn hình đầu tiên nhân viên nhìn thấy.

o01_2026a001 (cùng ngày) đã vá 8 đối tượng nhưng vẫn sót 6 cái này: bản diff lần đó
chạy khi Base.metadata chưa nạp đủ model. Lần này diff sau khi import app.main (kéo theo
toàn bộ router → toàn bộ model), đối chiếu information_schema prod, ra đúng 6 đối tượng:
- 5 bảng: suppliers, supplier_quotes, price_comparisons, estimations, estimation_items
- 1 cột: material_requests.task_id (+ index ix_material_requests_task)

Cùng kiểu phòng thủ như o01: kiểm tra tồn tại trước mỗi thao tác nên chạy lại an toàn
trên cả DB đã đủ schema (dev SQLite create_all) lẫn DB thiếu (prod Postgres).

Revision ID: p01_2026a001
Revises: o01_2026a001
Create Date: 2026-08-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'p01_2026a001'
down_revision: Union[str, Sequence[str], None] = 'o01_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    def ensure_index(table: str, name: str, cols: list[str]) -> None:
        if name not in {ix["name"] for ix in insp.get_indexes(table)}:
            op.create_index(name, table, cols, unique=False)

    # ── Cột thiếu: material_requests.task_id (model app/api/telegram_workflow.py) ──
    if "material_requests" in tables:
        have = {c["name"] for c in insp.get_columns("material_requests")}
        if "task_id" not in have:
            op.add_column("material_requests", sa.Column("task_id", sa.String(length=36), nullable=True))
            # FK tới tasks.id: tạo rời để DB nào chưa có bảng tasks vẫn không vỡ.
            # SQLite không hỗ trợ ALTER TABLE ADD CONSTRAINT → bỏ qua (dev dùng create_all,
            # ràng buộc đã nằm sẵn trong bảng khi tạo).
            if "tasks" in tables and bind.dialect.name != "sqlite":
                op.create_foreign_key(
                    "fk_material_requests_task_id", "material_requests", "tasks", ["task_id"], ["id"]
                )
        ensure_index("material_requests", "ix_material_requests_task", ["task_id"])

    # ── Nhóm NCC (app/models/supplier.py) ──
    if "suppliers" not in tables:
        op.create_table(
            "suppliers",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("contact_name", sa.String(length=255), nullable=True),
            sa.Column("phone", sa.String(length=20), nullable=True),
            sa.Column("zalo", sa.String(length=50), nullable=True),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("address", sa.String(length=500), nullable=True),
            sa.Column("region", sa.String(length=100), nullable=True),
            sa.Column("category", sa.String(length=50), nullable=False, server_default="general"),
            sa.Column("rating", sa.Float(), nullable=False, server_default="5.0"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_suppliers_category", "suppliers", ["category"], unique=False)
        op.create_index("ix_suppliers_name", "suppliers", ["name"], unique=False)
    else:
        ensure_index("suppliers", "ix_suppliers_category", ["category"])
        ensure_index("suppliers", "ix_suppliers_name", ["name"])

    if "supplier_quotes" not in tables:
        op.create_table(
            "supplier_quotes",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("supplier_id", sa.String(length=36), nullable=False),
            sa.Column("material_name", sa.String(length=255), nullable=False),
            sa.Column("material_category", sa.String(length=50), nullable=True),
            sa.Column("unit", sa.String(length=20), nullable=False, server_default="m2"),
            sa.Column("unit_price", sa.Float(), nullable=False),
            sa.Column("min_quantity", sa.Float(), nullable=False, server_default="1"),
            sa.Column("lead_time_days", sa.Integer(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("quote_date", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_supplier_quotes_material", "supplier_quotes", ["material_name"], unique=False)
        op.create_index("ix_supplier_quotes_supplier", "supplier_quotes", ["supplier_id"], unique=False)
    else:
        ensure_index("supplier_quotes", "ix_supplier_quotes_material", ["material_name"])
        ensure_index("supplier_quotes", "ix_supplier_quotes_supplier", ["supplier_id"])

    if "price_comparisons" not in tables:
        op.create_table(
            "price_comparisons",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("material_name", sa.String(length=255), nullable=False),
            sa.Column("material_category", sa.String(length=50), nullable=True),
            sa.Column("best_supplier_id", sa.String(length=36), nullable=True),
            sa.Column("best_price", sa.Float(), nullable=True),
            sa.Column("quote_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_price_comparisons_material", "price_comparisons", ["material_name"], unique=False)
    else:
        ensure_index("price_comparisons", "ix_price_comparisons_material", ["material_name"])

    # ── Nhóm dự toán cải tạo (app/models/estimation.py) ──
    if "estimations" not in tables:
        op.create_table(
            "estimations",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=True),
            sa.Column("estimation_type", sa.String(length=20), nullable=False, server_default="manual"),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("photo_urls", sa.Text(), nullable=True),
            sa.Column("floor_count", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("area_sqm", sa.Float(), nullable=False, server_default="80"),
            sa.Column("total_estimate", sa.Float(), nullable=False, server_default="0"),
            sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_estimations_project", "estimations", ["project_id"], unique=False)
        op.create_index("ix_estimations_status", "estimations", ["status"], unique=False)
    else:
        ensure_index("estimations", "ix_estimations_project", ["project_id"])
        ensure_index("estimations", "ix_estimations_status", ["status"])

    if "estimation_items" not in tables:
        op.create_table(
            "estimation_items",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("estimation_id", sa.String(length=36), nullable=False),
            sa.Column("template_code", sa.String(length=50), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("category", sa.String(length=50), nullable=False),
            sa.Column("unit", sa.String(length=20), nullable=False, server_default="m2"),
            sa.Column("quantity", sa.Float(), nullable=False, server_default="0"),
            sa.Column("unit_price", sa.Float(), nullable=False, server_default="0"),
            sa.Column("total", sa.Float(), nullable=False, server_default="0"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_estimation_items_estimation", "estimation_items", ["estimation_id"], unique=False)
    else:
        ensure_index("estimation_items", "ix_estimation_items_estimation", ["estimation_id"])


def downgrade() -> None:
    # Giống o01: revision sửa drift, cố ý KHÔNG revert. upgrade() có guard tồn-tại nên
    # không phân biệt được đối tượng nào do chính nó thêm; xoá nhầm sẽ mất dữ liệu thật.
    pass
