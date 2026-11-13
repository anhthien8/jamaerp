"""Vật tư: đặt hàng – Leader Thu mua duyệt – Giám sát nhận hàng kèm ảnh (13/11/2026).

Thêm cột cho dong_phieu_vat_tu. Toàn cột nullable, không đụng dữ liệu cũ:
dòng «đã đặt/đã giao» trước ngày này giữ nguyên, tiền vẫn tính theo giá chốt × SL phiếu.

Revision ID: a24_2026b003
Revises: a23_2026b002
Create Date: 2026-11-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a24_2026b003'
down_revision: Union[str, Sequence[str], None] = 'a23_2026b002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COT = [
    ("sl_dat", sa.Float()), ("gia_dat", sa.Float()), ("dat_boi", sa.String(36)), ("dat_luc", sa.DateTime()),
    ("ly_do_vuot", sa.Text()), ("duyet_dat_boi", sa.String(36)), ("duyet_dat_luc", sa.DateTime()),
    ("tu_choi_dat_ly_do", sa.Text()), ("nhan_ket_qua", sa.String(10)), ("sl_nhan", sa.Float()),
    ("nhan_boi", sa.String(36)), ("nhan_luc", sa.DateTime()), ("nhan_ghi_chu", sa.Text()),
    ("nhan_anh_ids", sa.Text()),
]


def upgrade() -> None:
    da_co = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("dong_phieu_vat_tu")}
    for ten, kieu in COT:
        if ten not in da_co:
            op.add_column("dong_phieu_vat_tu", sa.Column(ten, kieu, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("dong_phieu_vat_tu") as batch_op:
        for ten, _ in reversed(COT):
            batch_op.drop_column(ten)
