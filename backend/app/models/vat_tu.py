"""Vật tư Đợt 1 (25/10/2026): danh mục mẫu → phiếu chọn theo dự án → hỏi giá NCC.

Ba lớp (chốt với chủ dự án 25/10):
- `MauVatTu`: catalog mẫu cho khách chọn (nhập từ Google Sheet 12 tab theo kích
  thước gạch). Một mẫu nhiều NCC; giá vốn gần nhất tự cập nhật khi Thu mua chốt
  giá trong dự án.
- `GiaNhomVatTu`: % lãi theo nhóm, admin cài một chỗ. Giá bán (22/11/2026, Giám đốc chốt
  «đơn giá là hằng số»): mẫu đã có giá chuẩn (`gia_ban_co_dinh`) thì bán đúng giá chuẩn,
  không đổi theo giá sỉ; mẫu chưa có thì giá vốn × (1 + % nhóm). Không ai tự gõ giá bán.
- `DongPhieuVatTu` + `BaoGiaDongVatTu`: từng dòng khách chọn trong dự án, theo
  phòng; Thu mua ghi 2–3 báo giá NCC rồi chốt.

Giá vốn / NCC / lãi chỉ trả về cho Giám đốc, Thu mua, Trưởng phòng (lọc ở API).
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, LargeBinary, String, Text
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
    "cho_duyet_dat",         # đơn vượt báo giá/ngân sách — chờ Leader Thu mua duyệt (13/11)
    "da_dat",                # đã đặt hàng
    "giao_thieu",            # Giám sát xác nhận hàng về THIẾU — chờ giao bù
    "da_giao",               # Giám sát xác nhận hàng về đủ
    "huy",
)
NHAN_TRANG_THAI = {
    "khach_chon": "Khách chọn",
    "hoi_ncc": "Đang hỏi NCC",
    "het_hang": "Hết hàng — đề xuất thay",
    "cho_khach_duyet_lai": "Chờ khách duyệt lại",
    "da_chot_gia": "Đã chốt giá",
    "cho_duyet_dat": "Chờ Leader Thu mua duyệt",
    "da_dat": "Đã đặt hàng",
    "giao_thieu": "Giao thiếu",
    "da_giao": "Đã giao",
    "huy": "Huỷ",
}
# Giá khung (giá vốn gần nhất / giá đã chốt) quá số ngày này = «giá cũ», phải hỏi
# lại NCC trước khi đặt (chốt 13/11/2026: trung bình 60 ngày).
SO_NGAY_GIA_CU = 60
# Giám sát phải chụp tối thiểu ngần này ảnh hiện trường mới xác nhận được hàng về.
SO_ANH_NHAN_HANG_TOI_THIEU = 2
# Nguồn một dòng báo giá NCC (22/11/2026): tệp NCC gửi (bot /baogia) · gõ tay · máy tự
# ghi khi Thu mua chốt bằng giá gõ tay. Báo giá «tep» là bằng chứng mạnh nhất.
NGUON_BAO_GIA = ("tep", "tay", "chot")
# Lý do hàng lỗi khi Giám sát nhận hàng — 3 lựa chọn cố định để còn đếm theo NCC.
LY_DO_LOI_NHAN_HANG = {
    "sai_mau": "Sai mẫu / sai màu",
    "hu_hong": "Hư hỏng, bể vỡ",
    "khac": "Lỗi khác",
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
    # 6 cột Shopee dưới đây đã ngừng dùng từ 23/11/2026: không còn đọc hay ghi, chỉ giữ cột trong DB.
    link_shopee: Mapped[str | None] = mapped_column(String(500), nullable=True)
    shopee_item_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    shopee_ten: Mapped[str | None] = mapped_column(String(255), nullable=True)
    link_shopee_aff: Mapped[str | None] = mapped_column(String(500), nullable=True)
    gia_shopee: Mapped[float | None] = mapped_column(Float, nullable=True)
    gia_shopee_luc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
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
    khach_dong_y_boi: Mapped[str | None] = mapped_column(String(36), nullable=True)  # None = khách tự bấm trên portal
    khach_ghi_chu: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Ngày của BẰNG CHỨNG giá sỉ đang chốt (ngày báo giá NCC), không phải ngày bấm chốt.
    # Luật «giá quá 60 ngày phải hỏi lại» đọc cột này — chốt lại đúng giá cũ không làm mới.
    gia_xac_nhan_luc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Huỷ dòng: ai, lúc nào, vì sao (dòng đã đặt chỉ Leader Thu mua huỷ, bắt buộc lý do)
    huy_luc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    huy_boi: Mapped[str | None] = mapped_column(String(36), nullable=True)
    huy_ly_do: Mapped[str | None] = mapped_column(Text, nullable=True)
    ghi_chu: Mapped[str | None] = mapped_column(Text, nullable=True)
    can_ngay: Mapped[date | None] = mapped_column(Date, nullable=True)  # công trình cần hàng trước ngày
    # ── Đặt hàng – duyệt – nhận hàng (13/11/2026) ──
    # Đơn đặt đối chiếu với báo giá: khối lượng ≤ so_luong, đơn giá ≤ gia_von đã chốt,
    # không đội ngân sách dự án → tự qua; vượt bất kỳ mức nào → Leader Thu mua duyệt.
    sl_dat: Mapped[float | None] = mapped_column(Float, nullable=True)
    gia_dat: Mapped[float | None] = mapped_column(Float, nullable=True)
    dat_boi: Mapped[str | None] = mapped_column(String(36), nullable=True)
    dat_luc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ly_do_vuot: Mapped[str | None] = mapped_column(Text, nullable=True)       # máy ghi: vượt gì, bao nhiêu
    duyet_dat_boi: Mapped[str | None] = mapped_column(String(36), nullable=True)
    duyet_dat_luc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    tu_choi_dat_ly_do: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Ngày NCC hẹn giao (22/11/2026). `_dau` = lời hẹn ĐẦU TIÊN, ghi một lần rồi không sửa —
    # tỷ lệ giao đúng hạn của NCC chấm theo cột này; `ngay_giao_hen` là hẹn hiện tại (có thể dời).
    ngay_giao_hen: Mapped[date | None] = mapped_column(Date, nullable=True)
    ngay_giao_hen_dau: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Nhận hàng tại công trình: Giám sát xác nhận đủ/thiếu kèm ≥2 ảnh hiện trường.
    nhan_ket_qua: Mapped[str | None] = mapped_column(String(10), nullable=True)  # du | thieu
    sl_nhan: Mapped[float | None] = mapped_column(Float, nullable=True)
    nhan_boi: Mapped[str | None] = mapped_column(String(36), nullable=True)
    nhan_luc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    nhan_ghi_chu: Mapped[str | None] = mapped_column(Text, nullable=True)
    nhan_anh_ids: Mapped[str | None] = mapped_column(Text, nullable=True)        # JSON list id media_files
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
    nguon: Mapped[str] = mapped_column(String(10), nullable=False, default="tay", server_default="tay")  # NGUON_BAO_GIA
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    __table_args__ = (Index("ix_bao_gia_dong_vat_tu_dong", "dong_id"),)


class GiaNhapMauVatTu(Base):
    """Giá nhập của một NCC cho một mẫu, KHÔNG gắn dự án (22/11/2026).

    Thu mua đi lấy giá nhiều NCC rồi nạp vào đây liên tục; Giám đốc nhìn các giá nhập này
    (cùng báo giá trong các dự án) để ấn định giá chuẩn `MauVatTu.gia_ban_co_dinh`.
    Mỗi lần nạp là một dòng mới — giữ lịch sử, không ghi đè.
    """

    __tablename__ = "gia_nhap_mau_vat_tu"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mau_id: Mapped[str] = mapped_column(String(36), ForeignKey("mau_vat_tu.id"), nullable=False)
    supplier_id: Mapped[str] = mapped_column(String(36), ForeignKey("suppliers.id"), nullable=False)
    gia: Mapped[float] = mapped_column(Float, nullable=False)
    nguon: Mapped[str] = mapped_column(String(10), nullable=False, default="tay", server_default="tay")  # tep | tay
    ghi_chu: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    __table_args__ = (
        Index("ix_gia_nhap_mau_vat_tu_mau", "mau_id"),
        Index("ix_gia_nhap_mau_vat_tu_ncc", "supplier_id"),
    )


class NhanHangVatTu(Base):
    """Mỗi LẦN Giám sát xác nhận hàng về = một dòng (22/11/2026), không ghi đè.

    `DongPhieuVatTu.nhan_*` vẫn giữ trạng thái mới nhất để màn hình đọc nhanh; bảng này
    giữ lịch sử: lần đầu giao thiếu, các lần giao bù, hàng lỗi — để chấm NCC và để
    đối soát công nợ theo tháng (cộng `sl_lan_nay` của các lần nhận trong kỳ).
    """

    __tablename__ = "nhan_hang_vat_tu"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dong_id: Mapped[str] = mapped_column(String(36), ForeignKey("dong_phieu_vat_tu.id"), nullable=False)
    ket_qua: Mapped[str] = mapped_column(String(10), nullable=False)             # du | thieu
    sl_lan_nay: Mapped[float | None] = mapped_column(Float, nullable=True)       # về thêm trong lần này
    sl_luy_ke: Mapped[float | None] = mapped_column(Float, nullable=True)        # tổng đã về tới lần này
    ly_do_loi: Mapped[str | None] = mapped_column(String(20), nullable=True)     # LY_DO_LOI_NHAN_HANG
    ghi_chu: Mapped[str | None] = mapped_column(Text, nullable=True)
    anh_ids: Mapped[str | None] = mapped_column(Text, nullable=True)             # JSON list id media_files của lần này
    boi: Mapped[str | None] = mapped_column(String(36), nullable=True)
    luc: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    __table_args__ = (
        Index("ix_nhan_hang_vat_tu_dong", "dong_id"),
        Index("ix_nhan_hang_vat_tu_luc", "luc"),
    )
