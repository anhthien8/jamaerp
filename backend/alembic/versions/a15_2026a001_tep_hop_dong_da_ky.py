"""Tệp hợp đồng đã ký: bảng contract_files.

26/10/2026. Idempotent — kiểm tra bảng trước khi tạo.

Revision ID: a15_2026a001
Revises: a14_2026a001
Create Date: 2026-10-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a15_2026a001'
down_revision: Union[str, Sequence[str], None] = 'a14_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "contract_files" in insp.get_table_names():
        return
    op.create_table(
        "contract_files",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("contract_id", sa.String(length=36), sa.ForeignKey("contracts.id"), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("uploaded_by", sa.String(length=36), nullable=True),
        sa.Column("uploaded_by_name", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_contract_files_contract_id", "contract_files", ["contract_id"])


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "contract_files" in insp.get_table_names():
        op.drop_index("ix_contract_files_contract_id", table_name="contract_files")
        op.drop_table("contract_files")
