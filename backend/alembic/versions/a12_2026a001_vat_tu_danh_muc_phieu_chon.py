"""Vật tư Đợt 1: danh mục mẫu, % lãi theo nhóm, phiếu chọn theo dự án, báo giá NCC.

25/10/2026. Idempotent — kiểm tra từng bảng trước khi tạo.

Revision ID: a12_2026a001
Revises: a11_2026a001
Create Date: 2026-10-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a12_2026a001'
down_revision: Union[str, Sequence[str], None] = 'a11_2026a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    co = set(insp.get_table_names())

    if "mau_vat_tu" not in co:
        op.create_table(
            "mau_vat_tu",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("ma", sa.String(100), nullable=False),
            sa.Column("ten", sa.String(255), nullable=True),
            sa.Column("hang", sa.String(100), nullable=True),
            sa.Column("nhom", sa.String(100), nullable=False, server_default="Khác"),
            sa.Column("be_mat", sa.String(50), nullable=True),
            sa.Column("don_vi", sa.String(20), nullable=False, server_default="m2"),
            sa.Column("anh_url", sa.String(500), nullable=True),
            sa.Column("ghi_chu", sa.Text(), nullable=True),
            sa.Column("tinh_trang", sa.String(100), nullable=True),
            sa.Column("gia_tham_khao", sa.Float(), nullable=True),
            sa.Column("gia_von_gan_nhat", sa.Float(), nullable=True),
            sa.Column("gia_von_cap_nhat_luc", sa.DateTime(), nullable=True),
            sa.Column("ncc_gan_nhat_id", sa.String(36), sa.ForeignKey("suppliers.id"), nullable=True),
            sa.Column("ncc_gan_nhat_ten", sa.String(255), nullable=True),
            sa.Column("gia_ban_co_dinh", sa.Float(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_mau_vat_tu_ma", "mau_vat_tu", ["ma"])
        op.create_index("ix_mau_vat_tu_nhom", "mau_vat_tu", ["nhom"])

    if "gia_nhom_vat_tu" not in co:
        op.create_table(
            "gia_nhom_vat_tu",
            sa.Column("nhom", sa.String(100), primary_key=True),
            sa.Column("phan_tram_lai", sa.Float(), nullable=False, server_default="15"),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("updated_by", sa.String(36), nullable=True),
        )

    if "dong_phieu_vat_tu" not in co:
        op.create_table(
            "dong_phieu_vat_tu",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("phong", sa.String(100), nullable=False, server_default="Chung"),
            sa.Column("hang_muc", sa.String(255), nullable=True),
            sa.Column("mau_id", sa.String(36), sa.ForeignKey("mau_vat_tu.id"), nullable=True),
            sa.Column("ma_tu_do", sa.String(150), nullable=True),
            sa.Column("so_luong", sa.Float(), nullable=False, server_default="1"),
            sa.Column("don_vi", sa.String(20), nullable=False, server_default="m2"),
            sa.Column("trang_thai", sa.String(30), nullable=False, server_default="khach_chon"),
            sa.Column("mau_thay_the_id", sa.String(36), sa.ForeignKey("mau_vat_tu.id"), nullable=True),
            sa.Column("ma_thay_the", sa.String(150), nullable=True),
            sa.Column("ly_do_doi", sa.Text(), nullable=True),
            sa.Column("gia_von", sa.Float(), nullable=True),
            sa.Column("ncc_id", sa.String(36), sa.ForeignKey("suppliers.id"), nullable=True),
            sa.Column("phan_tram_ap_dung", sa.Float(), nullable=True),
            sa.Column("gia_ban", sa.Float(), nullable=True),
            sa.Column("chot_boi", sa.String(36), nullable=True),
            sa.Column("chot_luc", sa.DateTime(), nullable=True),
            sa.Column("khach_dong_y_luc", sa.DateTime(), nullable=True),
            sa.Column("khach_ghi_chu", sa.Text(), nullable=True),
            sa.Column("ghi_chu", sa.Text(), nullable=True),
            sa.Column("thu_tu", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_by", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_dong_phieu_vat_tu_project", "dong_phieu_vat_tu", ["project_id"])
        op.create_index("ix_dong_phieu_vat_tu_trang_thai", "dong_phieu_vat_tu", ["trang_thai"])

    if "bao_gia_dong_vat_tu" not in co:
        op.create_table(
            "bao_gia_dong_vat_tu",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("dong_id", sa.String(36), sa.ForeignKey("dong_phieu_vat_tu.id"), nullable=False),
            sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id"), nullable=True),
            sa.Column("ncc_ten", sa.String(255), nullable=False),
            sa.Column("gia", sa.Float(), nullable=False),
            sa.Column("con_hang", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("ngay_giao", sa.String(50), nullable=True),
            sa.Column("ghi_chu", sa.Text(), nullable=True),
            sa.Column("duoc_chon", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_by", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_bao_gia_dong_vat_tu_dong", "bao_gia_dong_vat_tu", ["dong_id"])


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    co = set(insp.get_table_names())
    for bang in ("bao_gia_dong_vat_tu", "dong_phieu_vat_tu", "gia_nhom_vat_tu", "mau_vat_tu"):
        if bang in co:
            op.drop_table(bang)
