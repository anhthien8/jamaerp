"""Khách hàng: ngày sinh + số CCCD (25/10/2026).

Chủ dự án muốn tải ảnh căn cước của khách để tự điền thông tin, lấy ngày sinh
nhắc sale phụ trách tặng quà. Ảnh CCCD không lưu, chỉ lưu 2 trường này.

Revision ID: a14_2026a001
Revises: a13_2026a001
Create Date: 2026-10-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a14_2026a001'
down_revision: Union[str, Sequence[str], None] = 'a13_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "customers" not in set(insp.get_table_names()):
        return
    cot = {c["name"] for c in insp.get_columns("customers")}
    if "birthday" not in cot:
        op.add_column("customers", sa.Column("birthday", sa.Date(), nullable=True))
    if "national_id" not in cot:
        op.add_column("customers", sa.Column("national_id", sa.String(length=20), nullable=True))


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    cot = {c["name"] for c in insp.get_columns("customers")}
    if "national_id" in cot:
        op.drop_column("customers", "national_id")
    if "birthday" in cot:
        op.drop_column("customers", "birthday")
