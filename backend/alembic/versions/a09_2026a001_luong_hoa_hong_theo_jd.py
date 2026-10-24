"""Lương từng người + hoa hồng theo JD.

24/10/2026. Idempotent — kiểm tra cột trước khi thêm. Không backfill dữ liệu
nhân sự (lương/BHXH nhập qua giao diện «Nhập Excel nhân sự», không qua repo).
- employee_profiles: contract_salary, insurance_salary, allowance_monthly,
  tax_code (MST cá nhân), insurance_start_date (ngày bắt đầu đóng BHXH)
- projects.khach_rieng (khách riêng của sale → hoa hồng 2%)
- contracts.contract_kind (thiet_ke | thi_cong)
- commissions: contract_id, installment_idx, note

Revision ID: a09_2026a001
Revises: a08_2026a001
Create Date: 2026-10-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a09_2026a001'
down_revision: Union[str, Sequence[str], None] = 'a08_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _cot() -> dict:
    # Hàm (không phải hằng) để mỗi lần chạy có Column mới — Column không gắn lại 2 bảng được.
    return {
        "employee_profiles": [
            sa.Column("contract_salary", sa.Float(), nullable=True),
            sa.Column("insurance_salary", sa.Float(), nullable=True),
            sa.Column("allowance_monthly", sa.Float(), nullable=True),
            sa.Column("tax_code", sa.String(length=20), nullable=True),
            sa.Column("insurance_start_date", sa.Date(), nullable=True),
        ],
        "projects": [
            sa.Column("khach_rieng", sa.Boolean(), nullable=False, server_default=sa.false()),
        ],
        "contracts": [
            sa.Column("contract_kind", sa.String(length=20), nullable=True),
        ],
        "commissions": [
            sa.Column("contract_id", sa.String(length=36), nullable=True),
            sa.Column("installment_idx", sa.Integer(), nullable=True),
            sa.Column("note", sa.String(length=255), nullable=True),
        ],
    }


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    for bang, cols in _cot().items():
        co = {c["name"] for c in insp.get_columns(bang)}
        for col in cols:
            if col.name not in co:
                op.add_column(bang, col)


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    for bang, cols in _cot().items():
        co = {c["name"] for c in insp.get_columns(bang)}
        for col in cols:
            if col.name in co:
                op.drop_column(bang, col.name)
