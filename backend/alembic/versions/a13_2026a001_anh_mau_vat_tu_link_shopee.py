"""Ảnh mẫu vật tư tải từ máy + link Shopee check giá (25/10/2026).

Chủ dự án xem form Thêm/Sửa mẫu: dán link ảnh phải thấy ảnh ngay, cần nút tải
ảnh lên, và muốn kèm link Shopee tới sản phẩm để so giá thị trường.
- Bảng `anh_vat_tu`: bytes JPG (≤800px) lưu Postgres, xem qua URL ký HMAC
  /media/vat-tu/{id}/{sig}.jpg (giống ảnh đại diện, không qua Kho ảnh Telegram).
- Cột `mau_vat_tu.link_shopee`: dán tay — không cào Shopee.

Revision ID: a13_2026a001
Revises: a12_2026a001
Create Date: 2026-10-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a13_2026a001'
down_revision: Union[str, Sequence[str], None] = 'a12_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    bang = set(insp.get_table_names())
    if "mau_vat_tu" in bang:
        cot = {c["name"] for c in insp.get_columns("mau_vat_tu")}
        if "link_shopee" not in cot:
            op.add_column("mau_vat_tu", sa.Column("link_shopee", sa.String(length=500), nullable=True))
    if "anh_vat_tu" not in bang:
        op.create_table(
            "anh_vat_tu",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("data", sa.LargeBinary(), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "anh_vat_tu" in insp.get_table_names():
        op.drop_table("anh_vat_tu")
    if "mau_vat_tu" in insp.get_table_names() and "link_shopee" in {c["name"] for c in insp.get_columns("mau_vat_tu")}:
        op.drop_column("mau_vat_tu", "link_shopee")
