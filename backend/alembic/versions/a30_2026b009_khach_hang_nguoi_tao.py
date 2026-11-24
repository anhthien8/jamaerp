"""Khách hàng: cột customers.created_by — người tạo hồ sơ tay.

24/11/2026: danh sách Khách hàng lọc theo người chăm sóc (nhân viên thấy khách của
mình, trưởng phòng thấy khách phòng mình). Người chăm sóc = sale của lead → sale dự
án → người tạo hồ sơ. Khách tạo tay chưa gắn lead/dự án chỉ còn mỗi mốc «người tạo»
để biết thuộc về ai.

Cột nullable, không điền bù: khách cũ không ghi lại ai tạo. Khách cũ vô chủ (không
lead, không dự án) từ nay chỉ Ban giám đốc / Kế toán / điều phối KD thấy.

Revision ID: a30_2026b009
Revises: a29_2026b008
Create Date: 2026-11-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a30_2026b009'
down_revision: Union[str, Sequence[str], None] = 'a29_2026b008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    da_co = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("customers")}
    if "created_by" not in da_co:
        op.add_column("customers", sa.Column("created_by", sa.String(36), nullable=True))


def downgrade() -> None:
    da_co = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("customers")}
    if "created_by" in da_co:
        with op.batch_alter_table("customers") as batch_op:
            batch_op.drop_column("created_by")
