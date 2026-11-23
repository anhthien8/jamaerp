"""Vật tư & NCC Đợt 1 (22/11/2026): ngày NCC hẹn giao, lịch sử nhận hàng, bằng chứng giá, giá nhập theo mẫu.

Giám đốc chốt 22/11: đơn giá bán là hằng số (bảng giá chuẩn do Giám đốc ấn định), Thu mua
chỉ nạp giá nhập và đặt hàng. Migration này thêm chỗ ghi dữ liệu, không đổi dữ liệu tiền.

- dong_phieu_vat_tu: ngay_giao_hen, ngay_giao_hen_dau, gia_xac_nhan_luc, khach_dong_y_boi,
  huy_luc, huy_boi, huy_ly_do.
- bao_gia_dong_vat_tu.nguon (tep | tay | chot); dòng cũ = 'tay', riêng dòng bot nhập từ tệp NCC = 'tep'.
- suppliers.hang (chinh | du_phong | thu).
- Bảng mới nhan_hang_vat_tu (mỗi lần Giám sát nhận hàng một dòng) — điền bù một dòng cho
  mỗi dòng vật tư đã có nhan_luc.
- Bảng mới gia_nhap_mau_vat_tu (giá nhập của NCC theo mẫu, không gắn dự án).
- Điền bù gia_xac_nhan_luc = chot_luc cho dòng đã chốt.
- Luật «khách đồng ý» đổi từ «bấm sau lúc chốt» sang «còn hiệu lực tới khi giá bán đổi»:
  dòng CHƯA đặt hàng mà theo luật cũ lời đồng ý chưa có hiệu lực (không ở «đã chốt giá», hoặc
  bấm TRƯỚC lần chốt gần nhất) thì xoá khach_dong_y_luc để giữ nguyên nghĩa. Chỉ chạy ở lần
  thêm cột — chạy lại sau khi code mới đã ghi lời đồng ý theo luật mới thì không đụng.

Mọi cột mới nullable hoặc có server_default; mốc thời gian đều naive. Chạy lại không đổi gì.

Revision ID: a29_2026b008
Revises: a28_2026b007
Create Date: 2026-11-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a29_2026b008'
down_revision: Union[str, Sequence[str], None] = 'a28_2026b007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COT_DONG = [
    ("ngay_giao_hen", sa.Date()), ("ngay_giao_hen_dau", sa.Date()), ("gia_xac_nhan_luc", sa.DateTime()),
    ("khach_dong_y_boi", sa.String(36)), ("huy_luc", sa.DateTime()), ("huy_boi", sa.String(36)),
    ("huy_ly_do", sa.Text()),
]


def _cot(insp, bang: str) -> set[str]:
    return {c["name"] for c in insp.get_columns(bang)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    bang = set(insp.get_table_names())

    da_co = _cot(insp, "dong_phieu_vat_tu")
    cot_moi = [(ten, kieu) for ten, kieu in COT_DONG if ten not in da_co]
    for ten, kieu in cot_moi:
        op.add_column("dong_phieu_vat_tu", sa.Column(ten, kieu, nullable=True))
    if "nguon" not in _cot(insp, "bao_gia_dong_vat_tu"):
        op.add_column("bao_gia_dong_vat_tu",
                      sa.Column("nguon", sa.String(10), nullable=False, server_default="tay"))
        # Báo giá bot nhập từ tệp NCC: ghi chú luôn kết bằng «… bởi <tên> (bot)» hoặc «Nhập qua bot bởi <tên>»
        # (chuỗi của bot_ghi_bao_gia không đổi từ commit đầu 8beb7c6 tới nay; ngoài nó chỉ có báo giá gõ tay).
        # Mẫu so khớp toàn ASCII nên không lệ thuộc dạng Unicode. Nằm trong nhánh thêm cột → chỉ chạy một lần.
        op.execute(sa.text(
            "UPDATE bao_gia_dong_vat_tu SET nguon = 'tep' "
            "WHERE ghi_chu LIKE '%(bot)%' OR ghi_chu LIKE '%qua bot b%'"
        ))
    if "hang" not in _cot(insp, "suppliers"):
        op.add_column("suppliers", sa.Column("hang", sa.String(20), nullable=True))

    if "gia_nhap_mau_vat_tu" not in bang:
        op.create_table(
            "gia_nhap_mau_vat_tu",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("mau_id", sa.String(36), sa.ForeignKey("mau_vat_tu.id"), nullable=False),
            sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id"), nullable=False),
            sa.Column("gia", sa.Float(), nullable=False),
            sa.Column("nguon", sa.String(10), nullable=False, server_default="tay"),
            sa.Column("ghi_chu", sa.Text(), nullable=True),
            sa.Column("created_by", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_gia_nhap_mau_vat_tu_mau", "gia_nhap_mau_vat_tu", ["mau_id"])
        op.create_index("ix_gia_nhap_mau_vat_tu_ncc", "gia_nhap_mau_vat_tu", ["supplier_id"])

    if "nhan_hang_vat_tu" not in bang:
        op.create_table(
            "nhan_hang_vat_tu",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("dong_id", sa.String(36), sa.ForeignKey("dong_phieu_vat_tu.id"), nullable=False),
            sa.Column("ket_qua", sa.String(10), nullable=False),
            sa.Column("sl_lan_nay", sa.Float(), nullable=True),
            sa.Column("sl_luy_ke", sa.Float(), nullable=True),
            sa.Column("ly_do_loi", sa.String(20), nullable=True),
            sa.Column("ghi_chu", sa.Text(), nullable=True),
            sa.Column("anh_ids", sa.Text(), nullable=True),
            sa.Column("boi", sa.String(36), nullable=True),
            sa.Column("luc", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_nhan_hang_vat_tu_dong", "nhan_hang_vat_tu", ["dong_id"])
        op.create_index("ix_nhan_hang_vat_tu_luc", "nhan_hang_vat_tu", ["luc"])
        # Điền bù: mỗi dòng đã có lần nhận → một sự kiện (id sự kiện = id dòng, chắc chắn không trùng).
        # Chỉ chạy lúc vừa tạo bảng nên không nhân đôi khi chạy lại.
        op.execute(sa.text(
            "INSERT INTO nhan_hang_vat_tu (id, dong_id, ket_qua, sl_lan_nay, sl_luy_ke, ghi_chu, anh_ids, boi, luc) "
            "SELECT id, id, COALESCE(nhan_ket_qua, 'du'), sl_nhan, sl_nhan, nhan_ghi_chu, nhan_anh_ids, nhan_boi, nhan_luc "
            "FROM dong_phieu_vat_tu WHERE nhan_luc IS NOT NULL"
        ))

    op.execute(sa.text(
        "UPDATE dong_phieu_vat_tu SET gia_xac_nhan_luc = chot_luc "
        "WHERE gia_xac_nhan_luc IS NULL AND chot_luc IS NOT NULL"
    ))
    # Luật cũ: lời đồng ý CHỈ có hiệu lực khi dòng ở «đã chốt giá» và bấm từ lúc chốt trở đi. Xoá đúng
    # phần ngược lại, trên dòng CHƯA đặt hàng (kể cả dòng chưa có giá: đồng ý khi chưa có giá là vô nghĩa) (dòng đã đặt/đã giao, và dòng huỷ sau khi
    # đặt — không mở lại được — thì lời đồng ý chỉ còn là lịch sử, không chặn bước nào).
    # Chỉ ở lần chạy thật sự thêm cột: sau đó code mới ghi «đồng ý trước, chốt sau» là hợp lệ.
    if cot_moi:
        op.execute(sa.text(
            "UPDATE dong_phieu_vat_tu SET khach_dong_y_luc = NULL "
            "WHERE khach_dong_y_luc IS NOT NULL "
            "AND trang_thai NOT IN ('cho_duyet_dat', 'da_dat', 'giao_thieu', 'da_giao') "
            "AND NOT (trang_thai = 'huy' AND sl_dat IS NOT NULL) "
            "AND NOT (trang_thai = 'da_chot_gia' AND (chot_luc IS NULL OR khach_dong_y_luc >= chot_luc))"
        ))


def downgrade() -> None:
    op.drop_table("nhan_hang_vat_tu")
    op.drop_table("gia_nhap_mau_vat_tu")
    with op.batch_alter_table("suppliers") as b:
        b.drop_column("hang")
    with op.batch_alter_table("bao_gia_dong_vat_tu") as b:
        b.drop_column("nguon")
    with op.batch_alter_table("dong_phieu_vat_tu") as b:
        for ten, _ in reversed(COT_DONG):
            b.drop_column(ten)
