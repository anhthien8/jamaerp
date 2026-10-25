"""Thư viện mẫu hợp đồng / biên bản: bảng contract_templates.

25/10/2026. Idempotent — kiểm tra bảng trước khi tạo. Không seed dữ liệu
(tệp mẫu do BGĐ/Kế toán tải lên qua giao diện).

Revision ID: a10_2026a001
Revises: a09_2026a001
Create Date: 2026-10-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a10_2026a001'
down_revision: Union[str, Sequence[str], None] = 'a09_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "contract_templates" in insp.get_table_names():
        return
    op.create_table(
        "contract_templates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False, server_default="khac"),
        sa.Column("contract_kind", sa.String(length=20), nullable=True),
        sa.Column("file_key", sa.String(length=200), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_by_name", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_contract_templates_file_key", "contract_templates", ["file_key"])


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "contract_templates" in insp.get_table_names():
        op.drop_index("ix_contract_templates_file_key", table_name="contract_templates")
        op.drop_table("contract_templates")
