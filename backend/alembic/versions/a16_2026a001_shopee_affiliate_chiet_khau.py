"""Shopee Affiliate cho mẫu vật tư + % chiết khấu NCC.

26/10/2026. Idempotent — chỉ thêm cột còn thiếu.

Revision ID: a16_2026a001
Revises: a15_2026a001
Create Date: 2026-10-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a16_2026a001'
down_revision: Union[str, Sequence[str], None] = 'a15_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COT_MAU = [
    sa.Column("shopee_item_id", sa.String(length=30), nullable=True),
    sa.Column("shopee_ten", sa.String(length=255), nullable=True),
    sa.Column("link_shopee_aff", sa.String(length=500), nullable=True),
    sa.Column("gia_shopee", sa.Float(), nullable=True),
    sa.Column("gia_shopee_luc", sa.DateTime(), nullable=True),
]


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    co = {c["name"] for c in insp.get_columns("mau_vat_tu")}
    for col in _COT_MAU:
        if col.name not in co:
            op.add_column("mau_vat_tu", col)
    if "chiet_khau_pct" not in {c["name"] for c in insp.get_columns("suppliers")}:
        op.add_column("suppliers", sa.Column("chiet_khau_pct", sa.Float(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("suppliers", "chiet_khau_pct")
    for col in reversed(_COT_MAU):
        op.drop_column("mau_vat_tu", col.name)
