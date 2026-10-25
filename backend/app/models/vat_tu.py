"""Vật tư Đợt 1 (25/10/2026): danh mục mẫu → phiếu chọn theo dự án → hỏi giá NCC.

Ba lớp (chốt với chủ dự án 25/10):
- `MauVatTu`: catalog mẫu cho khách chọn (nhập từ Google Sheet 12 tab theo kích
  thước gạch). Một mẫu nhiều NCC; giá vốn gần nhất tự cập nhật khi Thu mua chốt
  giá trong dự án.
- `GiaNhomVatTu`: % lãi theo nhóm, admin cài một chỗ. Giá bán = max(giá vốn ×
  (1 + %), giá cố định của mẫu) — không ai tự gõ giá bán.
- `DongPhieuVatTu` + `BaoGiaDongVatTu`: từng dòng khách chọn trong dự án, theo
  phòng; Thu mua ghi 2–3 báo giá NCC rồi chốt.

Giá vốn / NCC / lãi chỉ trả về cho Giám đốc, Thu mua, Trưởng phòng (lọc ở API).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _now():
    return datetime.now(timezone.utc)


# Trạng thái một dòng phiếu — đi theo đúng luồng thực tế của JAMA
TRANG_THAI_DONG = (
    "khach_chon",            # Thiết kế/KD ghi mẫu khách chọn
    "hoi_ncc",               # Thu mua đang hỏi NCC
    "het_hang",              # NCC báo hết → kèm mẫu thay thế
    "cho_khach_duyet_lai",   # đã có mẫu thay, chờ khách đồng ý
    "da_chot_gia",           # Thu mua chốt giá vốn + giá bán
    "da_dat",                # đã đặt hàng
    "da_giao",               # đã giao công trình
    "huy",
)
NHAN_TRANG_THAI = {
    "khach_chon": "Khách chọn",
    "hoi_ncc": "Đang hỏi NCC",
    "het_hang": "Hết hàng — đề xuất thay",
    "cho_khach_duyet_lai": "Chờ khách duyệt lại",
    "da_chot_gia": "Đã chốt giá",
    "da_dat": "Đã đặt hàng",
    "da_giao": "Đã giao",
    "huy": "Huỷ",
}


class MauVatTu(Base):
    __tablename__ = "mau_vat_tu"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ma: Mapped[str] = mapped_column(String(100), nullable=False)
    ten: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hang: Mapped[str | None] = mapped_column(String(100), nullable=True)      # thương hiệu
    nhom: Mapped[str] = mapped_column(String(100), nullable=False, default="Khác")  # 60x60, TBVS…
    be_mat: Mapped[str | None] = mapped_column(String(50), nullable=True)     # Bóng/Mờ/Nhám
    don_vi: Mapped[str] = mapped_column(String(20), nullable=False, default="m2")
    anh_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Link sản phẩm trên Shopee để Thu mua/khách check giá thị trường (25/10/2026).
    # Không tự cào Shopee (chặn bot, không có API mở) — người dùng dán link tay.
    link_shopee: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ghi_chu: Mapped[str | None] = mapped_column(Text, nullable=True)
    tinh_trang: Mapped[str | None] = mapped_column(String(100), nullable=True)  # «Còn hàng» theo sheet
    gia_tham_khao: Mapped[float | None] = mapped_column(Float, nullable=True)   # từ sheet
    gia_von_gan_nhat: Mapped[float | None] = mapped_column(Float, nullable=True)
    gia_von_cap_nhat_luc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ncc_gan_nhat_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("suppliers.id"), nullable=True)
    ncc_gan_nhat_ten: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gia_ban_co_dinh: Mapped[float | None] = mapped_column(Float, nullable=True)  # admin cài, tuỳ chọn
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    __table_args__ = (
        Index("ix_mau_vat_tu_ma", "ma"),
        Index("ix_mau_vat_tu_nhom", "nhom"),
    )


class AnhVatTu(Base):
    """Ảnh mẫu vật tư tải từ máy (25/10/2026) — JPG cạnh dài ≤800px lưu thẳng Postgres.

    Giống ảnh đại diện: không đi qua Kho ảnh Telegram (catalog nội bộ, không phải
    ảnh công trình). Xem qua URL ký HMAC /media/vat-tu/{id}/{sig}.jpg, ghi vào
    `MauVatTu.anh_url` như một link ảnh bình thường.
    """

    __tablename__ = "anh_vat_tu"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )


class GiaNhomVatTu(Base):
    """% lãi theo nhóm — một dòng/nhóm."""

    __tablename__ = "gia_nhom_vat_tu"

    nhom: Mapped[str] = mapped_column(String(100), primary_key=True)
    phan_tram_lai: Mapped[float] = mapped_column(Float, nullable=False, default=15.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class DongPhieuVatTu(Base):
    __tablename__ = "dong_phieu_vat_tu"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    phong: Mapped[str] = mapped_column(String(100), nullable=False, default="Chung")  # Phòng khách, WC1…
    hang_muc: Mapped[str | None] = mapped_column(String(255), nullable=True)           # Gạch sàn, gạch ốp…
    mau_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("mau_vat_tu.id"), nullable=True)
    ma_tu_do: Mapped[str | None] = mapped_column(String(150), nullable=True)   # khách chọn mã ngoài danh mục
    so_luong: Mapped[float] = mapped_column(Float, nullable=False, default=1)
    don_vi: Mapped[str] = mapped_column(String(20), nullable=False, default="m2")
    trang_thai: Mapped[str] = mapped_column(String(30), nullable=False, default="khach_chon")
    # Hết hàng → mẫu thay thế
    mau_thay_the_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("mau_vat_tu.id"), nullable=True)
    ma_thay_the: Mapped[str | None] = mapped_column(String(150), nullable=True)
    ly_do_doi: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Chốt giá (chỉ Thu mua) — các cột này KHÔNG trả về cho sale/thiết kế
    gia_von: Mapped[float | None] = mapped_column(Float, nullable=True)
    ncc_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("suppliers.id"), nullable=True)
    phan_tram_ap_dung: Mapped[float | None] = mapped_column(Float, nullable=True)
    gia_ban: Mapped[float | None] = mapped_column(Float, nullable=True)        # mọi vai + khách thấy
    chot_boi: Mapped[str | None] = mapped_column(String(36), nullable=True)
    chot_luc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Khách đồng ý (Đợt 1: nhân viên bấm thay khách; Đợt 2: portal)
    khach_dong_y_luc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    khach_ghi_chu: Mapped[str | None] = mapped_column(Text, nullable=True)
    ghi_chu: Mapped[str | None] = mapped_column(Text, nullable=True)
    thu_tu: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    __table_args__ = (
        Index("ix_dong_phieu_vat_tu_project", "project_id"),
        Index("ix_dong_phieu_vat_tu_trang_thai", "trang_thai"),
    )


class BaoGiaDongVatTu(Base):
    """Một NCC báo giá cho một dòng — Thu mua ghi 2–3 dòng rồi chọn một."""

    __tablename__ = "bao_gia_dong_vat_tu"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dong_id: Mapped[str] = mapped_column(String(36), ForeignKey("dong_phieu_vat_tu.id"), nullable=False)
    supplier_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("suppliers.id"), nullable=True)
    ncc_ten: Mapped[str] = mapped_column(String(255), nullable=False)   # gõ tay nếu NCC chưa có trong Kho
    gia: Mapped[float] = mapped_column(Float, nullable=False)
    con_hang: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ngay_giao: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ghi_chu: Mapped[str | None] = mapped_column(Text, nullable=True)
    duoc_chon: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    __table_args__ = (Index("ix_bao_gia_dong_vat_tu_dong", "dong_id"),)
