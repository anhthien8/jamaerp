"""Vật tư Đợt 1 (25/10/2026): danh mục mẫu · cài giá bán · phiếu chọn theo dự án · hỏi giá NCC.

Quyền (chốt với chủ dự án, không thêm ô ma trận):
- Xem giá vốn / NCC / báo giá / % lãi: admin, executive, bộ phận Thu mua, trưởng phòng.
  Sale & Thiết kế chỉ thấy giá bán. Hàm `xem_gia_von`.
- Chốt giá, ghi báo giá, bảng «Cần hỏi giá», cài % lãi: Thu mua (hoặc admin).
- Tạo/sửa dòng phiếu: ai vào được dự án (`require_project_access`).
Giá bán (22/11/2026, Giám đốc chốt «đơn giá là hằng số»): mẫu có giá chuẩn (`gia_ban_co_dinh`,
chỉ Admin ấn định) thì bán đúng giá chuẩn; chưa có thì giá vốn × (1 + % nhóm). Tính ở server,
không ai gõ. Lời «khách đồng ý» có hiệu lực tới khi giá bán của dòng đổi.
"""

import json
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.projects import require_project_access
from app.chuan_hoa_unicode import nfc
from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.rbac import la_truong_nhom, la_truong_phong
from app.models.notification import Notification
from app.models.payroll import Transaction
from app.models.project import Project
from app.models.supplier import HANG_NCC, Supplier
from app.models.user import User
from app.models.vat_tu import (
    LY_DO_LOI_NHAN_HANG, NHAN_TRANG_THAI, SO_ANH_NHAN_HANG_TOI_THIEU, SO_NGAY_GIA_CU, TRANG_THAI_DONG,
    BaoGiaDongVatTu, DongPhieuVatTu, GiaNhapMauVatTu, GiaNhomVatTu, MauVatTu, NhanHangVatTu,
)
from app.services import vat_tu_sheet
from app.services.attendance_service import vn_today
from app.services.ncc import BoNcc

router = APIRouter(prefix="/vat-tu", tags=["vat-tu"])

PHONG_THU_MUA = ("PURCHASING", "PROCUREMENT")
# Dòng ĐÃ ĐẶT HÀNG (kể cả đơn vượt đang chờ Leader duyệt): tiền đã cam kết với NCC —
# không sửa, không xoá lặng lẽ; muốn bỏ thì Leader Thu mua huỷ kèm lý do (22/11/2026).
TT_DA_DAT = ("cho_duyet_dat", "da_dat", "giao_thieu", "da_giao")
COT_KHOA_SAU_DAT = ("so_luong", "mau_id", "ma_tu_do", "don_vi", "mau_thay_the_id", "ma_thay_the")
# Dòng CHƯA đặt hàng: khách chưa đồng ý thì giá bán còn đi theo giá chuẩn của mẫu
TT_CHUA_DAT = ("khach_chon", "hoi_ncc", "het_hang", "cho_khach_duyet_lai", "da_chot_gia")


def _now():
    return datetime.now(timezone.utc)


def _naive(t: datetime) -> datetime:
    return t.replace(tzinfo=None) if t.tzinfo else t


def la_thu_mua(user: User) -> bool:
    return user.role == "admin" or (user.department or "").upper() in PHONG_THU_MUA


def la_leader_thu_mua(user: User) -> bool:
    """Người duyệt đơn vượt báo giá/ngân sách: Leader bộ phận Thu mua (hoặc Admin)."""
    return user.role == "admin" or (
        (user.department or "").upper() in PHONG_THU_MUA and (la_truong_phong(user) or la_truong_nhom(user))
    )


PHONG_GIAM_SAT = ("OPS",)


def la_giam_sat(user: User, proj: Project | None) -> bool:
    """Người xác nhận hàng về công trình: Giám sát phụ trách dự án / bộ phận Giám sát (hoặc Admin)."""
    return user.role == "admin" or bool(proj and proj.pm_id == user.id) or (
        (user.department or "").upper() in PHONG_GIAM_SAT
    )


def gia_da_cu(luc: datetime | None) -> bool:
    """Giá khung quá SO_NGAY_GIA_CU ngày chưa hỏi lại NCC."""
    if not luc:
        return False
    return (_now().replace(tzinfo=None) - (luc.replace(tzinfo=None) if luc.tzinfo else luc)) > timedelta(days=SO_NGAY_GIA_CU)


def xem_gia_von(user: User) -> bool:
    return user.role in ("admin", "executive") or la_thu_mua(user) or la_truong_phong(user)


def yeu_cau_thu_mua(user: User = Depends(get_current_user)) -> User:
    if not la_thu_mua(user):
        raise HTTPException(403, "Chỉ bộ phận Thu mua mới làm được việc này")
    return user


def yeu_cau_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Chỉ Admin mới cài giá bán")
    return user


async def quyen_du_an(project_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> User:
    """Thu mua lo vật tư cho MỌI dự án; người khác phải vào được dự án (PIC/trưởng phòng/có việc)."""
    if la_thu_mua(user):
        if not await db.get(Project, project_id):
            raise HTTPException(404, "Project not found")
        return user
    return await require_project_access(project_id, user, db)


def tinh_gia_ban(gia_von: float, phan_tram: float, gia_co_dinh: float | None) -> tuple[float, float | None]:
    """(giá bán, % áp dụng). Mẫu có giá chuẩn → LUÔN đúng giá chuẩn (% None): giá sỉ lên xuống
    không kéo giá khách theo. Mẫu chưa có giá chuẩn → giá vốn × (1 + % nhóm)."""
    if gia_co_dinh and gia_co_dinh > 0:
        return float(gia_co_dinh), None
    return float(round(gia_von * (1 + phan_tram / 100))), phan_tram


def _dat_gia_ban(d: DongPhieuVatTu, gia_ban: float | None, phan_tram: float | None) -> None:
    """Chỗ DUY NHẤT ghi giá bán của dòng. Lời đồng ý của khách có hiệu lực tới khi GIÁ TRỊ giá
    bán đổi (chưa có ↔ có, hoặc lệch quá 0,5đ) — đổi thì xoá để khách duyệt lại giá mới."""
    cu = d.gia_ban
    if (cu is None) != (gia_ban is None) or (cu is not None and abs(cu - gia_ban) > 0.5):
        d.khach_dong_y_luc = d.khach_dong_y_boi = None
    d.gia_ban, d.phan_tram_ap_dung = gia_ban, phan_tram


def _gia_chuan(mau: MauVatTu | None) -> float | None:
    return float(mau.gia_ban_co_dinh) if mau and (mau.gia_ban_co_dinh or 0) > 0 else None


def _giu_gia_nhap(db: AsyncSession, b: BaoGiaDongVatTu, mau_id: str | None) -> bool:
    """Báo giá NCC sắp bị bỏ khỏi dòng → giữ làm giá nhập theo mẫu (căn cứ của Bảng giá chuẩn),
    giữ nguyên ngày và người ghi. Chỉ giữ được khi biết NCC và mẫu."""
    if not (b.supplier_id and mau_id):
        return False
    db.add(GiaNhapMauVatTu(mau_id=mau_id, supplier_id=b.supplier_id, gia=b.gia, nguon=b.nguon,
                           ghi_chu=b.ghi_chu, created_by=b.created_by,
                           created_at=_naive(b.created_at or _now())))
    return True


async def ap_mau_moi(db: AsyncSession, d: DongPhieuVatTu, doi_tu: tuple[str | None] | None = None) -> None:
    """Dòng vừa mang một mẫu / mã MỚI (dòng mới, đổi mẫu, khách nhận mẫu thay).
    `doi_tu=(mau_id cũ,)` khi dòng ĐỔI từ mẫu / mã khác: báo giá NCC trên dòng là của mẫu cũ → chuyển
    thành giá nhập của mẫu cũ rồi bỏ khỏi dòng (không để Bảng giá chuẩn và «chốt theo báo giá» hiểu
    nhầm là giá của mẫu mới).
    - Mã gõ tay trùng mã một mẫu đang dùng trong danh mục → gắn mẫu đó: gõ mã không lách được giá chuẩn.
    - Giá vốn, NCC, báo giá đang chốt là của mẫu CŨ → bỏ, dòng quay lại «hỏi NCC» để chốt giá mẫu mới.
    - Đơn vị theo mẫu (giá chuẩn tính trên đơn vị của mẫu). Giá bán = giá chuẩn của mẫu; mẫu chưa có
      giá chuẩn thì CHƯA có giá. Không suy giá bán từ giá vốn của mẫu cũ: sai giá mẫu mới, và người
      không được xem giá vốn đọc ngược ra được."""
    from app.services.vat_tu_bao_gia_tep import chuan_ma
    if not d.mau_id and chuan_ma(d.ma_tu_do):
        trung = (await _mau_theo_ma(db, [d.ma_tu_do])).get(chuan_ma(d.ma_tu_do))
        if trung:
            d.mau_id, d.ma_tu_do = trung.id, None
    if doi_tu is not None:
        for b in (await db.execute(select(BaoGiaDongVatTu).where(BaoGiaDongVatTu.dong_id == d.id))).scalars().all():
            _giu_gia_nhap(db, b, doi_tu[0])
            await db.delete(b)
    if d.gia_von is not None or d.trang_thai == "da_chot_gia":
        d.gia_von = d.ncc_id = d.phan_tram_ap_dung = d.chot_boi = d.chot_luc = d.gia_xac_nhan_luc = None
        if doi_tu is None:
            for b in (await db.execute(select(BaoGiaDongVatTu).where(
                    BaoGiaDongVatTu.dong_id == d.id, BaoGiaDongVatTu.duoc_chon.is_(True)))).scalars():
                b.duoc_chon = False
        if d.trang_thai == "da_chot_gia":
            d.trang_thai = "hoi_ncc"
    mau = await db.get(MauVatTu, d.mau_id) if d.mau_id else None
    if mau:
        d.don_vi = mau.don_vi
    _dat_gia_ban(d, _gia_chuan(mau), None)


async def ghi_doi_gia_chuan(db: AsyncSession, user: User, mau: MauVatTu, cu: float | None) -> None:
    """Gọi ngay SAU khi ghi `mau.gia_ban_co_dinh` — mọi lối ghi giá chuẩn đều qua đây. Giá đổi thì dòng
    CHƯA đặt hàng mà khách CHƯA đồng ý lấy ngay giá mới (bỏ giá chuẩn: giá vốn đã chốt × (1 + % nhóm),
    chưa chốt thì chưa có giá) — giá của dòng không còn tuỳ khách bấm đồng ý trước hay sau lúc Giám đốc
    đổi giá. Dòng khách đã đồng ý và dòng đã đặt hàng giữ nguyên. Có ghi nhật ký kiểm toán."""
    moi = mau.gia_ban_co_dinh
    if moi == cu:
        return
    await db.flush()  # mẫu vừa tạo phải có id trước khi tìm dòng theo mẫu
    chuan = _gia_chuan(mau)
    pt = None if chuan else (await _phan_tram_nhom(db)).get(mau.nhom, 15.0)
    so_dong = 0
    for d in (await db.execute(select(DongPhieuVatTu).where(
            DongPhieuVatTu.mau_id == mau.id, DongPhieuVatTu.trang_thai.in_(TT_CHUA_DAT),
            # Đồng ý trên dòng chưa có giá là vô nghĩa — dòng đó cũng nhận giá mới
            or_(DongPhieuVatTu.khach_dong_y_luc.is_(None), DongPhieuVatTu.gia_ban.is_(None))))).scalars():
        truoc = d.gia_ban
        if chuan:
            _dat_gia_ban(d, chuan, None)
        elif d.gia_von:
            _dat_gia_ban(d, *tinh_gia_ban(d.gia_von, pt, None))
        else:
            _dat_gia_ban(d, None, None)
        so_dong += d.gia_ban != truoc
    from app.services.audit import log_action
    await log_action(db, actor=user, action="vat_tu.gia_chuan", entity_type="mau_vat_tu", entity_id=mau.id,
                     before={"ma": mau.ma, "gia_ban_co_dinh": cu},
                     after={"gia_ban_co_dinh": moi, "so_dong_doi_gia": so_dong})


def _chi_admin_gia_chuan(data: dict, user: User) -> dict:
    """Giá chuẩn (`gia_ban_co_dinh`) chỉ Admin ấn định: người khác gửi lên thì bỏ qua, giữ giá đang lưu."""
    if user.role != "admin":
        data.pop("gia_ban_co_dinh", None)
    return data


# ── Schemas ────────────────────────────────────────────────────────────────

class MauIn(BaseModel):
    ma: str = Field(min_length=1, max_length=100)
    ten: str | None = None
    hang: str | None = None
    nhom: str = "Khác"
    be_mat: str | None = None
    don_vi: str = "m2"
    anh_url: str | None = Field(default=None, max_length=500)
    ghi_chu: str | None = None
    tinh_trang: str | None = None
    gia_tham_khao: float | None = None
    gia_ban_co_dinh: float | None = None
    ncc_gan_nhat_ten: str | None = Field(default=None, max_length=255)
    is_active: bool = True


class ImportSheetIn(BaseModel):
    url: str
    ghi_de: bool = False  # True: cập nhật mẫu trùng mã+nhóm; False: chỉ thêm mới


class GiaNhomIn(BaseModel):
    nhom: str
    phan_tram_lai: float = Field(ge=0, le=500)


class DongIn(BaseModel):
    phong: str = "Chung"
    hang_muc: str | None = None
    mau_id: str | None = None
    ma_tu_do: str | None = None
    so_luong: float = Field(default=1, gt=0)
    don_vi: str = "m2"
    ghi_chu: str | None = None
    can_ngay: date | None = None  # công trình cần hàng trước ngày


class DongPatch(BaseModel):
    phong: str | None = None
    hang_muc: str | None = None
    mau_id: str | None = None
    ma_tu_do: str | None = None
    so_luong: float | None = Field(default=None, gt=0)
    don_vi: str | None = None
    ghi_chu: str | None = None
    trang_thai: str | None = None
    mau_thay_the_id: str | None = None
    ma_thay_the: str | None = None
    ly_do_doi: str | None = None
    can_ngay: date | None = None
    huy_ly_do: str | None = None  # chỉ đọc khi trang_thai = huy; dòng đã đặt hàng thì bắt buộc


class BaoGiaIn(BaseModel):
    supplier_id: str | None = None
    ncc_ten: str | None = None
    gia: float = Field(gt=0)
    con_hang: bool = True
    ngay_giao: str | None = None
    ghi_chu: str | None = None


class ChotIn(BaseModel):
    bao_gia_id: str | None = None   # chọn một báo giá đã ghi…
    gia_von: float | None = Field(default=None, gt=0)  # …hoặc gõ thẳng giá vốn
    supplier_id: str | None = None
    ncc_ten: str | None = None


class KhachDongYIn(BaseModel):
    ghi_chu: str | None = None


class DatHangIn(BaseModel):
    so_luong: float | None = Field(default=None, gt=0)   # bỏ trống = đúng khối lượng báo giá
    don_gia: float | None = Field(default=None, gt=0)    # bỏ trống = đúng đơn giá đã chốt
    ngay_giao_hen: date | None = None                    # BẮT BUỘC (kiểm ở handler để trả 400 tiếng Việt)


class DuyetDatIn(BaseModel):
    dong_y: bool
    ly_do: str | None = None


class NhanHangIn(BaseModel):
    ket_qua: str                                  # du | thieu
    so_luong_nhan: float | None = Field(default=None, ge=0)  # «thiếu»: TỔNG đã về tới lần này (bắt buộc)
    ly_do_loi: str | None = None                  # khoá của LY_DO_LOI_NHAN_HANG, tuỳ chọn
    ghi_chu: str | None = None
    anh_ids: list[str] = Field(default_factory=list)


# ── Serializers ────────────────────────────────────────────────────────────

def _mau_dict(m: MauVatTu, thay_gia_von: bool) -> dict:
    d = {
        "id": m.id, "ma": m.ma, "ten": m.ten, "hang": m.hang, "nhom": m.nhom, "be_mat": m.be_mat,
        "don_vi": m.don_vi, "anh_url": m.anh_url, "ghi_chu": m.ghi_chu, "tinh_trang": m.tinh_trang,
        "is_active": m.is_active, "gia_ban_co_dinh": m.gia_ban_co_dinh if thay_gia_von else None,
    }
    if thay_gia_von:
        d.update({
            "gia_tham_khao": m.gia_tham_khao, "gia_von_gan_nhat": m.gia_von_gan_nhat,
            "gia_von_cap_nhat_luc": m.gia_von_cap_nhat_luc, "ncc_gan_nhat_ten": m.ncc_gan_nhat_ten,
            # Giá khung quá 60 ngày → nhãn «giá cũ», hỏi lại NCC trước khi đặt
            "gia_cu": bool(m.gia_von_gan_nhat) and gia_da_cu(m.gia_von_cap_nhat_luc),
        })
    return d


def _bao_gia_dict(b: BaoGiaDongVatTu) -> dict:
    return {
        "id": b.id, "supplier_id": b.supplier_id, "ncc_ten": b.ncc_ten, "gia": b.gia, "con_hang": b.con_hang,
        "ngay_giao": b.ngay_giao, "ghi_chu": b.ghi_chu, "duoc_chon": b.duoc_chon, "created_at": b.created_at,
        "nguon": b.nguon,
    }


def _dong_dict(d: DongPhieuVatTu, thay_gia_von: bool, mau: dict[str, MauVatTu], bao_gia: list[BaoGiaDongVatTu],
               ncc: dict[str, str], du_an: Project | None = None,
               anh: dict[str, str] | None = None, ten: dict[str, str] | None = None,
               nhan: list[NhanHangVatTu] | None = None) -> dict:
    anh, ten = anh or {}, ten or {}
    m = mau.get(d.mau_id or "")
    mt = mau.get(d.mau_thay_the_id or "")
    out = {
        "id": d.id, "project_id": d.project_id, "phong": d.phong, "hang_muc": d.hang_muc,
        "mau_id": d.mau_id, "ma": (m.ma if m else d.ma_tu_do), "hang": (m.hang if m else None),
        "nhom": (m.nhom if m else None), "anh_url": (m.anh_url if m else None), "ma_tu_do": d.ma_tu_do,
        "so_luong": d.so_luong, "don_vi": d.don_vi, "trang_thai": d.trang_thai,
        "trang_thai_nhan": NHAN_TRANG_THAI.get(d.trang_thai, d.trang_thai),
        "mau_thay_the_id": d.mau_thay_the_id, "ma_thay_the": (mt.ma if mt else d.ma_thay_the),
        "ly_do_doi": d.ly_do_doi, "gia_ban": d.gia_ban,
        "thanh_tien": (round(d.gia_ban * d.so_luong) if d.gia_ban else None),
        "chot_luc": d.chot_luc, "khach_dong_y_luc": d.khach_dong_y_luc, "khach_ghi_chu": d.khach_ghi_chu,
        "ghi_chu": d.ghi_chu, "can_ngay": d.can_ngay, "thu_tu": d.thu_tu, "created_at": d.created_at, "updated_at": d.updated_at,
        "so_bao_gia": len(bao_gia),
        # Đặt hàng – duyệt – nhận hàng (13/11): ai cũng thấy khối lượng + kết quả nhận, không lộ giá vốn
        "sl_dat": d.sl_dat, "dat_luc": d.dat_luc, "dat_boi": d.dat_boi, "dat_boi_ten": ten.get(d.dat_boi or ""),
        "ly_do_vuot": d.ly_do_vuot if thay_gia_von else None,
        "duyet_dat_luc": d.duyet_dat_luc, "duyet_dat_boi_ten": ten.get(d.duyet_dat_boi or ""),
        "tu_choi_dat_ly_do": d.tu_choi_dat_ly_do,
        "nhan_ket_qua": d.nhan_ket_qua, "sl_nhan": d.sl_nhan, "nhan_luc": d.nhan_luc,
        "nhan_boi_ten": ten.get(d.nhan_boi or ""), "nhan_ghi_chu": d.nhan_ghi_chu,
        "nhan_anh": [{"id": i, "url": anh[i]} for i in _ids_anh(d) if i in anh],
        # 22/11: ngày NCC hẹn giao (`_dau` = lời hẹn đầu, không sửa) + trễ hẹn — mọi vai đều thấy
        "ngay_giao_hen": d.ngay_giao_hen, "ngay_giao_hen_dau": d.ngay_giao_hen_dau,
        "tre_hen": bool(d.ngay_giao_hen and d.trang_thai in ("da_dat", "giao_thieu") and d.ngay_giao_hen < vn_today()),
        # Từng LẦN Giám sát nhận hàng (cũ → mới): không có giá, không có NCC
        "nhan_lich_su": [{
            "luc": n.luc, "boi_ten": ten.get(n.boi or ""), "ket_qua": n.ket_qua,
            "sl_lan_nay": n.sl_lan_nay, "sl_luy_ke": n.sl_luy_ke,
            "ly_do_loi": n.ly_do_loi, "ly_do_loi_nhan": LY_DO_LOI_NHAN_HANG.get(n.ly_do_loi or ""),
            "ghi_chu": n.ghi_chu,
        } for n in (nhan or [])],
        "huy_luc": d.huy_luc, "huy_boi_ten": ten.get(d.huy_boi or ""), "huy_ly_do": d.huy_ly_do,
    }
    if du_an is not None:
        out.update({"project_code": du_an.code, "project_name": du_an.name, "client_name": du_an.client_name})
    if thay_gia_von:
        out.update({
            "gia_von": d.gia_von, "ncc_id": d.ncc_id, "ncc_ten": ncc.get(d.ncc_id or ""),
            "phan_tram_ap_dung": d.phan_tram_ap_dung, "gia_dat": d.gia_dat,
            # Luật 60 ngày đọc ngày của BẰNG CHỨNG giá (báo giá NCC), không phải ngày bấm chốt
            "gia_xac_nhan_luc": d.gia_xac_nhan_luc,
            "gia_cu": d.trang_thai == "da_chot_gia" and gia_da_cu(d.gia_xac_nhan_luc or d.chot_luc),
            "lai": (round((d.gia_ban - d.gia_von) * d.so_luong) if d.gia_ban and d.gia_von else None),
            "bao_gia": [_bao_gia_dict(b) for b in bao_gia],
            "gia_von_gan_nhat": (m.gia_von_gan_nhat if m else None),
            "gia_tham_khao": (m.gia_tham_khao if m else None),
            # NCC của lần mua gần nhất + giá khung đã quá hạn chưa — để Thu mua chốt một chạm
            "ncc_gan_nhat_id": (m.ncc_gan_nhat_id if m else None),
            "ncc_gan_nhat_ten": (m.ncc_gan_nhat_ten if m else None),
            "gia_von_cap_nhat_luc": (m.gia_von_cap_nhat_luc.isoformat() if m and m.gia_von_cap_nhat_luc else None),
            "gia_gan_nhat_cu": bool(m and m.gia_von_gan_nhat) and gia_da_cu(m.gia_von_cap_nhat_luc),
        })
    return out


def _ids_anh(d: DongPhieuVatTu) -> list[str]:
    try:
        return [str(x) for x in json.loads(d.nhan_anh_ids or "[]")]
    except (TypeError, ValueError):
        return []


async def _goi_dong(db: AsyncSession, ds: list[DongPhieuVatTu], user: User, kem_du_an=False) -> list[dict]:
    thay = xem_gia_von(user)
    ids_mau = {x for d in ds for x in (d.mau_id, d.mau_thay_the_id) if x}
    mau = {m.id: m for m in (await db.execute(select(MauVatTu).where(MauVatTu.id.in_(ids_mau)))).scalars()} if ids_mau else {}
    bg: dict[str, list[BaoGiaDongVatTu]] = {d.id: [] for d in ds}
    if ds and thay:
        for b in (await db.execute(
            select(BaoGiaDongVatTu).where(BaoGiaDongVatTu.dong_id.in_(list(bg))).order_by(BaoGiaDongVatTu.gia)
        )).scalars():
            bg[b.dong_id].append(b)
    ncc_ids = {d.ncc_id for d in ds if d.ncc_id}
    ncc = {s.id: s.name for s in (await db.execute(select(Supplier).where(Supplier.id.in_(ncc_ids)))).scalars()} if ncc_ids and thay else {}
    du_an: dict[str, Project] = {}
    if kem_du_an and ds:
        du_an = {p.id: p for p in (await db.execute(select(Project).where(Project.id.in_({d.project_id for d in ds})))).scalars()}
    ids_anh = {i for d in ds for i in _ids_anh(d)}
    anh: dict[str, str] = {}
    if ids_anh:
        from app.models.media import MediaFile
        from app.services.media_gateway import url_media
        anh = {m.id: url_media(m) for m in (await db.execute(select(MediaFile).where(MediaFile.id.in_(ids_anh)))).scalars()}
    # Lịch sử nhận hàng: chỉ hỏi DB cho dòng đã có ít nhất một lần nhận
    ids_nhan = [d.id for d in ds if d.nhan_luc]
    nhan: dict[str, list[NhanHangVatTu]] = {}
    if ids_nhan:
        for n in (await db.execute(
            select(NhanHangVatTu).where(NhanHangVatTu.dong_id.in_(ids_nhan)).order_by(NhanHangVatTu.luc)
        )).scalars():
            nhan.setdefault(n.dong_id, []).append(n)
    ids_nguoi = {x for d in ds for x in (d.dat_boi, d.duyet_dat_boi, d.nhan_boi, d.huy_boi) if x}
    ids_nguoi |= {n.boi for ls in nhan.values() for n in ls if n.boi}
    ten = {i: n for i, n in (await db.execute(select(User.id, User.full_name).where(User.id.in_(ids_nguoi)))).all()} if ids_nguoi else {}
    return [_dong_dict(d, thay, mau, bg.get(d.id, []), ncc, du_an.get(d.project_id) if kem_du_an else None, anh, ten,
                       nhan.get(d.id)) for d in ds]


async def _phan_tram_nhom(db: AsyncSession) -> dict[str, float]:
    return {g.nhom: g.phan_tram_lai for g in (await db.execute(select(GiaNhomVatTu))).scalars()}


# ── Danh mục mẫu ───────────────────────────────────────────────────────────

@router.get("/mau")
async def danh_sach_mau(
    q: str | None = None, nhom: str | None = None, chi_dang_dung: bool = True,
    limit: int = Query(200, le=1000), offset: int = 0,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    stmt = select(MauVatTu)
    if chi_dang_dung:
        stmt = stmt.where(MauVatTu.is_active.is_(True))
    if nhom:
        stmt = stmt.where(MauVatTu.nhom == nhom)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(MauVatTu.ma.ilike(like) | MauVatTu.hang.ilike(like) | MauVatTu.ten.ilike(like))
    tong = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await db.execute(stmt.order_by(MauVatTu.nhom, MauVatTu.hang, MauVatTu.ma).limit(limit).offset(offset))).scalars().all()
    thay = xem_gia_von(user)
    return {"items": [_mau_dict(m, thay) for m in rows], "total": tong, "thay_gia_von": thay}


@router.get("/nhom")
async def danh_sach_nhom(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Nhóm + số mẫu; kèm % lãi nếu được xem giá vốn."""
    rows = (await db.execute(
        select(MauVatTu.nhom, func.count()).where(MauVatTu.is_active.is_(True)).group_by(MauVatTu.nhom).order_by(MauVatTu.nhom)
    )).all()
    pt = await _phan_tram_nhom(db) if xem_gia_von(user) else {}
    return [{"nhom": n, "so_mau": c, "phan_tram_lai": pt.get(n)} for n, c in rows]


async def _gan_ncc_mau(bo: BoNcc, m: MauVatTu) -> None:
    """Tên NCC gõ ở mẫu → nối với mục Nhà cung cấp (chưa có thì tạo)."""
    s = await bo.lay(m.ncc_gan_nhat_ten)
    m.ncc_gan_nhat_id = s.id if s else None
    if s:
        m.ncc_gan_nhat_ten = s.name


@router.get("/ncc")
async def ds_ncc(user: User = Depends(yeu_cau_thu_mua), db: AsyncSession = Depends(get_db)):
    """Tên NCC cho ô gợi ý khi Thu mua gõ."""
    rows = (await db.execute(
        select(Supplier.id, Supplier.name, Supplier.chiet_khau_pct).where(Supplier.is_active.is_(True)).order_by(Supplier.name)
    )).all()
    return [{"id": i, "name": n, "chiet_khau_pct": ck} for i, n, ck in rows]


@router.post("/mau", status_code=201)
async def tao_mau(body: MauIn, user: User = Depends(yeu_cau_thu_mua), db: AsyncSession = Depends(get_db)):
    m = MauVatTu(**_chi_admin_gia_chuan(body.model_dump(), user))
    db.add(m)
    await _gan_ncc_mau(BoNcc(db), m)
    await ghi_doi_gia_chuan(db, user, m, None)
    await db.commit()
    await db.refresh(m)
    return _mau_dict(m, True)


@router.put("/mau/{mau_id}")
async def sua_mau(mau_id: str, body: MauIn, user: User = Depends(yeu_cau_thu_mua), db: AsyncSession = Depends(get_db)):
    m = await db.get(MauVatTu, mau_id)
    if not m:
        raise HTTPException(404, "Không có mẫu này")
    gia_chuan_cu = m.gia_ban_co_dinh
    for k, v in _chi_admin_gia_chuan(body.model_dump(), user).items():
        setattr(m, k, v)
    await _gan_ncc_mau(BoNcc(db), m)
    await ghi_doi_gia_chuan(db, user, m, gia_chuan_cu)
    await db.commit()
    await db.refresh(m)
    return _mau_dict(m, True)


class AnhIn(BaseModel):
    data_base64: str  # JPG/PNG nén ở FE (canvas); server ép về JPG cạnh dài ≤800px


MAX_ANH_BYTES = 6 * 1024 * 1024


@router.post("/anh", status_code=201)
async def tai_anh_mau(body: AnhIn, user: User = Depends(yeu_cau_thu_mua), db: AsyncSession = Depends(get_db)):
    """Tải ảnh mẫu từ máy → lưu Postgres → trả `anh_url` ký HMAC để gắn vào mẫu.
    Tách khỏi mẫu để tải được ngay khi đang điền form «Thêm mẫu» (mẫu chưa có id)."""
    import base64
    import binascii

    from app.models.vat_tu import AnhVatTu
    from app.services.media_gateway import MediaError, lam_anh_mau, url_anh_vat_tu

    try:
        raw = base64.b64decode(body.data_base64.split(",")[-1], validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(422, "Ảnh gửi lên không hợp lệ")
    if not raw:
        raise HTTPException(422, "Ảnh rỗng")
    if len(raw) > MAX_ANH_BYTES:
        raise HTTPException(413, "Ảnh quá lớn (tối đa 6MB)")
    try:
        jpg = lam_anh_mau(raw)
    except MediaError as exc:
        raise HTTPException(422, str(exc))
    anh = AnhVatTu(data=jpg, size_bytes=len(jpg), created_by=user.id)
    db.add(anh)
    await db.commit()
    return {"id": anh.id, "anh_url": url_anh_vat_tu(anh.id), "size_bytes": len(jpg)}


@router.post("/mau/import-sheet")
async def nhap_tu_sheet(body: ImportSheetIn, user: User = Depends(yeu_cau_thu_mua), db: AsyncSession = Depends(get_db)):
    try:
        ds = await vat_tu_sheet.doc_sheet(body.url)
    except vat_tu_sheet.SheetError as e:
        raise HTTPException(400, str(e))
    except Exception as e:  # noqa: BLE001 — mạng, timeout…
        raise HTTPException(502, f"Không đọc được Google Sheet: {e}")
    # Khoá (mã, nhóm) NFC cả 2 phía (21/11/2026): sheet đã NFC ở doc_csv, phía DB chuẩn hoá
    # luôn để dòng cũ chưa qua migration vẫn khớp, không sinh mẫu trùng
    co = {(nfc(m.ma).upper(), nfc(m.nhom)): m for m in (await db.execute(select(MauVatTu))).scalars()}
    them = sua = 0
    bo = BoNcc(db)
    so_ncc_truoc = (await db.execute(select(func.count()).select_from(Supplier))).scalar() or 0
    for r in ds:
        _chi_admin_gia_chuan(r, user)
        khoa = (r["ma"].upper(), r["nhom"])
        if khoa in co:
            if body.ghi_de:
                gia_chuan_cu = co[khoa].gia_ban_co_dinh
                for k, v in r.items():
                    if v is not None:
                        setattr(co[khoa], k, v)
                await _gan_ncc_mau(bo, co[khoa])
                await ghi_doi_gia_chuan(db, user, co[khoa], gia_chuan_cu)
                sua += 1
            continue
        m = MauVatTu(**r)
        db.add(m)
        await _gan_ncc_mau(bo, m)
        await ghi_doi_gia_chuan(db, user, m, None)
        co[khoa] = m
        them += 1
    # Nhóm mới chưa có % lãi → tạo dòng mặc định 15% để admin chỉnh một chỗ
    pt = await _phan_tram_nhom(db)
    for nhom in {r["nhom"] for r in ds} - {nfc(k) for k in pt}:
        db.add(GiaNhomVatTu(nhom=nhom, phan_tram_lai=15.0, updated_by=user.id))
    await db.commit()
    so_ncc_sau = (await db.execute(select(func.count()).select_from(Supplier))).scalar() or 0
    return {"doc_duoc": len(ds), "them": them, "sua": sua, "ncc_moi": so_ncc_sau - so_ncc_truoc}


# ── Cài giá bán ───────────────────────────────────────────────────────────

@router.get("/cai-gia")
async def xem_cai_gia(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not xem_gia_von(user):
        raise HTTPException(403, "Bạn không được xem cài đặt giá")
    rows = (await db.execute(select(GiaNhomVatTu).order_by(GiaNhomVatTu.nhom))).scalars().all()
    return [{"nhom": g.nhom, "phan_tram_lai": g.phan_tram_lai, "updated_at": g.updated_at} for g in rows]


@router.put("/cai-gia")
async def cai_gia(body: list[GiaNhomIn], user: User = Depends(yeu_cau_admin), db: AsyncSession = Depends(get_db)):
    for item in body:
        # Tên nhóm là KHOÁ CHÍNH: tra bằng bản NFC (21/11/2026) — gõ dạng tổ hợp mà tra nguyên
        # văn thì không thấy dòng có sẵn, listener lại ghi bản NFC → nổ trùng khoá (500)
        nhom = nfc(item.nhom)
        g = await db.get(GiaNhomVatTu, nhom)
        if g:
            g.phan_tram_lai = item.phan_tram_lai
            g.updated_by = user.id
        else:
            db.add(GiaNhomVatTu(nhom=nhom, phan_tram_lai=item.phan_tram_lai, updated_by=user.id))
    await db.commit()
    return {"ok": True, "so_nhom": len(body)}


# ── Phiếu chọn theo dự án ─────────────────────────────────────────────────

async def _bao_thu_mua_dong_moi(db: AsyncSession, project_id: str, user: User, d: DongPhieuVatTu) -> None:
    """Dòng vật tư mới → báo Thu mua của dự án (hoặc cả phòng Thu mua). Gộp: còn
    thông báo chưa đọc của dự án thì không bắn thêm."""
    proj = await db.get(Project, project_id)
    if not proj:
        return
    ds = {getattr(proj, "purchasing_id", None)} - {None}
    if not ds:
        ds = set((await db.execute(select(User.id).where(
            User.department.in_(PHONG_THU_MUA), User.is_active == True  # noqa: E712
        ))).scalars())
    ds.discard(user.id)
    han = f" · cần trước {d.can_ngay.strftime('%d/%m')}" if d.can_ngay else ""
    for uid in ds:
        con = (await db.execute(select(Notification.id).where(
            Notification.user_id == uid, Notification.type == "vat_tu_moi",
            Notification.ref_id == project_id, Notification.read == False,  # noqa: E712
        ).limit(1))).first()
        if con:
            continue
        db.add(Notification(
            user_id=uid, type="vat_tu_moi", title=f"Vật tư mới cần hỏi giá · {proj.code}",
            body=f"{d.phong} · {d.ma_tu_do or 'mẫu trong danh mục'}{han}",
            link=f"/vat-tu?project={proj.id}", ref_id=project_id,
        ))


async def _dong_hoac_404(db: AsyncSession, dong_id: str) -> DongPhieuVatTu:
    d = await db.get(DongPhieuVatTu, dong_id)
    if not d:
        raise HTTPException(404, "Không có dòng vật tư này")
    return d


@router.get("/du-an/{project_id}/dong")
async def phieu_du_an(project_id: str, user: User = Depends(quyen_du_an), db: AsyncSession = Depends(get_db)):
    ds = (await db.execute(
        select(DongPhieuVatTu).where(DongPhieuVatTu.project_id == project_id)
        .order_by(DongPhieuVatTu.phong, DongPhieuVatTu.thu_tu, DongPhieuVatTu.created_at)
    )).scalars().all()
    items = await _goi_dong(db, ds, user)
    con = [i for i in items if i["trang_thai"] != "huy"]  # dòng đã huỷ vẫn hiện nhưng không cộng vào tổng
    tong_ban = sum(i["thanh_tien"] or 0 for i in con)
    out = {"items": items, "tong_gia_ban": tong_ban, "thay_gia_von": xem_gia_von(user), "co_the_chot": la_thu_mua(user)}
    if out["thay_gia_von"]:
        out["tong_lai"] = sum(i.get("lai") or 0 for i in con)
    return out


@router.post("/du-an/{project_id}/dong", status_code=201)
async def them_dong(project_id: str, body: DongIn, user: User = Depends(quyen_du_an), db: AsyncSession = Depends(get_db)):
    if not body.mau_id and not (body.ma_tu_do or "").strip():
        raise HTTPException(400, "Chọn mẫu trong danh mục hoặc gõ mã vật tư")
    if body.mau_id and not await db.get(MauVatTu, body.mau_id):
        raise HTTPException(404, "Mẫu không có trong danh mục")
    thu_tu = (await db.execute(
        select(func.coalesce(func.max(DongPhieuVatTu.thu_tu), 0)).where(DongPhieuVatTu.project_id == project_id)
    )).scalar_one() + 1
    d = DongPhieuVatTu(project_id=project_id, created_by=user.id, thu_tu=thu_tu, **body.model_dump())
    db.add(d)
    # Mẫu có giá chuẩn → dòng có giá bán ngay, khách duyệt được trước khi Thu mua chốt giá vốn
    await ap_mau_moi(db, d)
    await _bao_thu_mua_dong_moi(db, project_id, user, d)
    await db.commit()
    await db.refresh(d)
    return (await _goi_dong(db, [d], user))[0]


@router.patch("/dong/{dong_id}")
async def sua_dong(dong_id: str, body: DongPatch, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d = await _dong_hoac_404(db, dong_id)
    await quyen_du_an(d.project_id, user, db)
    data = body.model_dump(exclude_unset=True)
    ly_do_huy = (data.pop("huy_ly_do", None) or "").strip()[:1000] or None
    tt = data.get("trang_thai")
    tt_cu = d.trang_thai
    if tt is not None:
        if tt not in TRANG_THAI_DONG:
            raise HTTPException(400, "Trạng thái không hợp lệ")
        # Bước thuộc Thu mua: hỏi NCC, báo hết hàng, đặt, giao. Chốt giá đi lối riêng.
        if tt in ("hoi_ncc", "het_hang") and not la_thu_mua(user):
            raise HTTPException(403, "Bước này do Thu mua cập nhật")
        if tt == "da_chot_gia":
            raise HTTPException(400, "Chốt giá bằng nút «Chốt giá»")
        # 13/11: đặt hàng phải đối chiếu báo giá, nhận hàng phải có ảnh hiện trường —
        # không còn đổi tay trạng thái.
        if tt in ("da_dat", "cho_duyet_dat"):
            raise HTTPException(400, "Đặt hàng bằng nút «Đặt hàng» để đối chiếu với báo giá")
        if tt in ("da_giao", "giao_thieu"):
            raise HTTPException(400, "Hàng về do Giám sát xác nhận kèm ảnh hiện trường")
        if tt == "het_hang" and not (data.get("mau_thay_the_id") or data.get("ma_thay_the") or d.mau_thay_the_id or d.ma_thay_the):
            raise HTTPException(400, "Hết hàng thì phải kèm mẫu thay thế")
    # Dòng có ĐƠN ĐẶT HÀNG trên sổ: đang đặt / đã giao, hoặc đã huỷ SAU khi đặt (giữ nguyên làm lịch sử đơn)
    huy_sau_dat = tt_cu == "huy" and d.sl_dat is not None
    if tt_cu in TT_DA_DAT or huy_sau_dat:
        if any(k in data and data[k] != getattr(d, k) for k in COT_KHOA_SAU_DAT):
            raise HTTPException(400, "Dòng đã đặt hàng — không sửa được mẫu, số lượng, đơn vị. " + (
                "Cần mua lại thì tạo dòng mới" if huy_sau_dat
                else "Cần đổi thì Leader Thu mua huỷ dòng này rồi tạo dòng mới"))
        if huy_sau_dat and tt not in (None, "huy"):
            # Mở lại rồi chốt NCC khác / đặt lại sẽ trộn lịch sử nhận hàng và lời hẹn giao của hai đơn
            raise HTTPException(400, "Dòng đã từng đặt hàng rồi huỷ — không mở lại được. Cần mua lại thì tạo dòng mới")
        if tt is not None and not huy_sau_dat:
            if tt != "huy":
                raise HTTPException(400, "Dòng đã đặt hàng — chỉ huỷ được, không lùi về bước trước")
            if not la_leader_thu_mua(user):
                raise HTTPException(403, "Dòng đã đặt hàng — chỉ Leader Thu mua (hoặc Admin) huỷ được")
            if tt_cu == "da_giao":
                raise HTTPException(400, "Hàng đã giao đủ — không huỷ được")
            if not ly_do_huy:
                raise HTTPException(400, "Huỷ dòng đã đặt hàng thì phải ghi lý do")
    if data.get("mau_id") and data["mau_id"] != d.mau_id and not await db.get(MauVatTu, data["mau_id"]):
        raise HTTPException(404, "Mẫu không có trong danh mục")
    truoc = {"trang_thai": tt_cu, "sl_dat": d.sl_dat, "gia_dat": d.gia_dat, "ncc_id": d.ncc_id, "project_id": d.project_id}
    mau_cu = (d.mau_id, None if d.mau_id else d.ma_tu_do)
    for k, v in data.items():
        setattr(d, k, v)
    if (d.mau_id, None if d.mau_id else d.ma_tu_do) != mau_cu:
        # Mẫu / mã khác: hết chốt giá vốn của mẫu cũ, giá + đơn vị theo mẫu mới; giá đổi thì khách duyệt lại
        await ap_mau_moi(db, d, doi_tu=(mau_cu[0],))
    elif d.mau_id and not (tt_cu in TT_DA_DAT or huy_sau_dat):
        mau = await db.get(MauVatTu, d.mau_id)
        if mau:
            d.don_vi = mau.don_vi  # đơn vị theo mẫu, gõ khác cũng không đổi: giá chuẩn tính trên đơn vị của mẫu
    if tt == "huy" and tt_cu != "huy":
        d.huy_luc, d.huy_boi, d.huy_ly_do = _naive(_now()), user.id, ly_do_huy
        if tt_cu == "giao_thieu" and (d.sl_nhan or 0) > 0:
            # Hàng đã về một phần: tiền phần ĐÃ NHẬN phải còn trong chi phí dự án → không huỷ cả dòng mà
            # đóng dòng ở số đã nhận. Phần chưa về coi như bỏ (huy_* + nhật ký ghi lại); mua tiếp thì tạo dòng mới
            d.so_luong = d.sl_dat = d.sl_nhan
            d.trang_thai = "da_giao"
        if tt_cu in TT_DA_DAT:
            from app.services.audit import log_action
            await log_action(db, actor=user, action="vat_tu.huy_dong", entity_type="dong_vat_tu", entity_id=d.id,
                             before=truoc, after={"trang_thai": d.trang_thai, "sl_dat": d.sl_dat, "huy_ly_do": ly_do_huy})
    elif tt not in (None, "huy") and tt_cu == "huy":
        d.huy_luc = d.huy_boi = d.huy_ly_do = None  # mở lại dòng đã huỷ (chưa từng đặt hàng)
    if tt is not None:
        await db.flush()
        from app.services.dong_bo_tai_chinh import tinh_lai_spent
        await tinh_lai_spent(db, d.project_id)
    if tt == "het_hang":
        # Có mẫu thay → tự chuyển sang chờ khách duyệt lại khi thiết kế xem xong; Đợt 1 giữ het_hang
        pass
    await db.commit()
    await db.refresh(d)
    return (await _goi_dong(db, [d], user))[0]


@router.delete("/dong/{dong_id}", status_code=204)
async def xoa_dong(dong_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    d = await _dong_hoac_404(db, dong_id)
    await quyen_du_an(d.project_id, user, db)
    if d.trang_thai in TT_DA_DAT:
        raise HTTPException(400, "Dòng đã đặt hàng — không xoá được. Cần bỏ thì Leader Thu mua huỷ dòng kèm lý do")
    if d.trang_thai == "huy" and d.sl_dat is not None:
        raise HTTPException(400, "Dòng đã từng đặt hàng rồi huỷ — không xoá được, giữ làm lịch sử đơn")
    if d.trang_thai == "da_chot_gia" and user.role != "admin":
        raise HTTPException(400, "Dòng đã chốt giá — chỉ Admin xoá được")
    # Dòng từng nhận hàng rồi bị huỷ: giữ lại, lịch sử nhận hàng dùng để chấm NCC
    if (await db.execute(select(NhanHangVatTu.id).where(NhanHangVatTu.dong_id == d.id).limit(1))).first():
        raise HTTPException(400, "Dòng đã có lịch sử nhận hàng — không xoá được")
    bao_gias = (await db.execute(select(BaoGiaDongVatTu).where(BaoGiaDongVatTu.dong_id == d.id))).scalars().all()
    giu = 0
    for b in bao_gias:
        # Báo giá NCC là căn cứ của Bảng giá chuẩn — xoá dòng (sale cũng xoá được) không được làm mất
        giu += _giu_gia_nhap(db, b, d.mau_id)
        await db.delete(b)
    pid, ten, tt_cu = d.project_id, await _ma_dong(db, d), d.trang_thai
    await db.delete(d)
    await db.flush()
    # Audit 27/10: xoá dòng đã chốt mà chi phí dự án không giảm
    from app.services.dong_bo_tai_chinh import tinh_lai_spent
    await tinh_lai_spent(db, pid)
    from app.services.audit import log_action
    await log_action(db, actor=user, action="vat_tu.xoa_dong", entity_type="dong_vat_tu",
                     entity_id=dong_id, before={"ten": ten, "trang_thai": tt_cu, "project_id": pid,
                                                "so_bao_gia": len(bao_gias), "giu_lam_gia_nhap": giu})
    await db.commit()


@router.post("/dong/{dong_id}/khach-dong-y")
async def khach_dong_y(dong_id: str, body: KhachDongYIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Đợt 1: nhân viên bấm thay khách (kèm ghi chú); Đợt 2 khách tự bấm trên portal."""
    d = await _dong_hoac_404(db, dong_id)
    await quyen_du_an(d.project_id, user, db)
    if d.trang_thai in TT_DA_DAT or d.trang_thai == "huy":
        raise HTTPException(400, "Dòng đã đặt hàng hoặc đã huỷ — không ghi lại lời đồng ý của khách")
    doi_mau_thay = d.trang_thai in ("cho_khach_duyet_lai", "het_hang")
    if not doi_mau_thay and d.gia_ban is None:
        raise HTTPException(400, "Dòng chưa có giá bán — chưa có gì để khách đồng ý")
    if d.khach_dong_y_luc and not doi_mau_thay:
        # Khách đã đồng ý, không còn gì chờ duyệt → giữ nguyên ai ghi, lúc nào, qua kênh nào
        return (await _goi_dong(db, [d], user))[0]
    d.khach_dong_y_luc, d.khach_dong_y_boi = _now(), user.id
    d.khach_ghi_chu = body.ghi_chu
    if doi_mau_thay:
        # Khách đồng ý mẫu thay → mẫu thay trở thành mẫu chính, quay lại hỏi giá
        if d.mau_thay_the_id or d.ma_thay_the:
            mau_truoc = d.mau_id
            d.mau_id, d.ma_tu_do = d.mau_thay_the_id, (None if d.mau_thay_the_id else d.ma_thay_the)
            d.mau_thay_the_id = d.ma_thay_the = None
            # Giá theo mẫu mới. Giá không đổi → lời đồng ý vừa ghi giữ nguyên; đổi → khách duyệt lại giá
            await ap_mau_moi(db, d, doi_tu=(mau_truoc,))
        d.trang_thai = "hoi_ncc"
    await db.commit()
    await db.refresh(d)
    return (await _goi_dong(db, [d], user))[0]


# ── Thu mua: cần hỏi giá, báo giá, chốt ───────────────────────────────────

@router.get("/can-hoi-gia")
async def can_hoi_gia(
    trang_thai: str | None = None, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    if not xem_gia_von(user):
        raise HTTPException(403, "Bảng này dành cho Thu mua / Ban giám đốc")
    tt = [trang_thai] if trang_thai else ["khach_chon", "hoi_ncc", "het_hang", "cho_khach_duyet_lai"]
    ds = (await db.execute(
        select(DongPhieuVatTu).where(DongPhieuVatTu.trang_thai.in_(tt))
        .order_by(DongPhieuVatTu.can_ngay.asc().nulls_last(), DongPhieuVatTu.created_at)
    )).scalars().all()
    return {"items": await _goi_dong(db, ds, user, kem_du_an=True)}


@router.post("/dong/{dong_id}/bao-gia", status_code=201)
async def them_bao_gia(dong_id: str, body: BaoGiaIn, user: User = Depends(yeu_cau_thu_mua), db: AsyncSession = Depends(get_db)):
    d = await _dong_hoac_404(db, dong_id)
    ten = (body.ncc_ten or "").strip()
    if body.supplier_id:
        s = await db.get(Supplier, body.supplier_id)
        if not s:
            raise HTTPException(404, "NCC không có trong Kho")
        ten = ten or s.name
    if not ten:
        raise HTTPException(400, "Cần tên NCC")
    supplier_id = body.supplier_id
    if not supplier_id:
        s = await BoNcc(db).lay(ten)
        if s:
            supplier_id, ten = s.id, s.name
    b = BaoGiaDongVatTu(dong_id=d.id, supplier_id=supplier_id, ncc_ten=ten, gia=body.gia, con_hang=body.con_hang,
                        ngay_giao=body.ngay_giao, ghi_chu=body.ghi_chu, nguon="tay", created_by=user.id)
    db.add(b)
    if d.trang_thai == "khach_chon":
        d.trang_thai = "hoi_ncc"
    await db.commit()
    await db.refresh(d)
    return (await _goi_dong(db, [d], user))[0]


@router.delete("/bao-gia/{bao_gia_id}", status_code=204)
async def xoa_bao_gia(bao_gia_id: str, user: User = Depends(yeu_cau_thu_mua), db: AsyncSession = Depends(get_db)):
    b = await db.get(BaoGiaDongVatTu, bao_gia_id)
    if not b:
        raise HTTPException(404, "Không có báo giá này")
    if b.duoc_chon:
        raise HTTPException(400, "Báo giá đã chốt — không xoá")
    await db.delete(b)
    await db.commit()


@router.post("/dong/{dong_id}/chot")
async def chot_gia(dong_id: str, body: ChotIn, user: User = Depends(yeu_cau_thu_mua), db: AsyncSession = Depends(get_db)):
    """Thu mua chốt giá vốn (bắt buộc kèm NCC) → để lại bằng chứng giá → server tính giá bán
    → ghi «giá gần nhất» về mẫu → báo PIC; giá vốn làm giá chuẩn lời dưới hệ số thì báo Giám đốc."""
    d = await _dong_hoac_404(db, dong_id)
    if d.trang_thai in TT_DA_DAT or d.trang_thai == "huy":
        raise HTTPException(400, "Dòng này không còn ở bước chốt giá")
    gia_von, supplier_id, ncc_ten = body.gia_von, body.supplier_id, (body.ncc_ten or "").strip() or None
    bao_gias = (await db.execute(select(BaoGiaDongVatTu).where(BaoGiaDongVatTu.dong_id == d.id))).scalars().all()
    chon = None
    if body.bao_gia_id:
        chon = next((b for b in bao_gias if b.id == body.bao_gia_id), None)
        if not chon:
            raise HTTPException(404, "Báo giá không thuộc dòng này")
        gia_von, supplier_id, ncc_ten = chon.gia, chon.supplier_id, chon.ncc_ten
    if not gia_von:
        raise HTTPException(400, "Cần chọn một báo giá hoặc gõ giá vốn")
    # NCC bắt buộc (22/11/2026): giá vốn không rõ của ai thì không đối chiếu, không chấm NCC được
    if supplier_id:
        ncc = await db.get(Supplier, supplier_id)
        if not ncc:
            raise HTTPException(404, "NCC không có trong Kho")
    else:
        ncc = await BoNcc(db).lay(ncc_ten)
    if not ncc:
        raise HTTPException(400, "Chốt giá phải kèm nhà cung cấp")
    supplier_id, ncc_ten = ncc.id, ncc.name
    mau = await db.get(MauVatTu, d.mau_id) if d.mau_id else None

    def _bang(a: float | None) -> bool:
        return a is not None and abs(a - gia_von) <= 0.5

    # Ngày của BẰNG CHỨNG giá (luật 60 ngày đọc mốc này): chốt qua một báo giá → ngày báo giá đó;
    # gõ lại đúng giá đang nhớ của cùng NCC (ở mẫu, hoặc lần chốt trước của chính dòng này) → giữ
    # ngày cũ, vì dùng lại giá cũ không phải bằng chứng mới; còn lại → bây giờ. Giá đang nhớ mà CHƯA rõ
    # NCC (chốt trước 22/11 không kèm NCC) coi như của cùng NCC: gõ lại kèm tên NCC không làm mới giá.
    bay_gio = _naive(_now())
    if chon:
        xac_nhan = _naive(chon.created_at or bay_gio)
    elif mau and _bang(mau.gia_von_gan_nhat) and mau.ncc_gan_nhat_id in (None, supplier_id) and mau.gia_von_cap_nhat_luc:
        xac_nhan = _naive(mau.gia_von_cap_nhat_luc)
    elif _bang(d.gia_von) and d.ncc_id in (None, supplier_id) and (d.gia_xac_nhan_luc or d.chot_luc):
        xac_nhan = _naive(d.gia_xac_nhan_luc or d.chot_luc)
    else:
        xac_nhan = bay_gio
    if chon:
        chon.supplier_id, chon.ncc_ten = supplier_id, ncc_ten
    else:
        # Giá gõ tay cũng để lại một dòng báo giá — tra được «giá này của ai, từ ngày nào»
        chon = BaoGiaDongVatTu(dong_id=d.id, supplier_id=supplier_id, ncc_ten=ncc_ten, gia=gia_von,
                               nguon="chot", created_by=user.id, created_at=xac_nhan)
        db.add(chon)
    for b in bao_gias:
        b.duoc_chon = b is chon
    chon.duoc_chon = True

    nhom = mau.nhom if mau else "Khác"
    pt = (await _phan_tram_nhom(db)).get(nhom, 15.0)
    chuan = _gia_chuan(mau)
    if not chuan:
        _dat_gia_ban(d, *tinh_gia_ban(gia_von, pt, None))
    elif d.gia_ban is None or not d.khach_dong_y_luc:
        _dat_gia_ban(d, chuan, None)
    # else: mẫu có giá chuẩn và khách ĐÃ đồng ý giá đang ghi → đóng băng, giá vốn không kéo giá khách
    d.gia_von, d.ncc_id, d.gia_xac_nhan_luc = gia_von, supplier_id, xac_nhan
    d.chot_boi, d.chot_luc, d.trang_thai = user.id, _now(), "da_chot_gia"
    if mau:
        mau.gia_von_gan_nhat, mau.gia_von_cap_nhat_luc = gia_von, xac_nhan
        mau.ncc_gan_nhat_id, mau.ncc_gan_nhat_ten = supplier_id, ncc_ten
        theo_he_so = round(gia_von * (1 + pt / 100))
        if chuan and theo_he_so > chuan:
            # Giá chuẩn không tự đổi theo giá sỉ — chỉ báo Giám đốc (Admin) xét lại, không báo ai khác
            await _bao(db, await _ds_admin(db), f"Giá chuẩn cần xét lại · {mau.ma}",
                       f"Giá nhập mới {_tien(gia_von)}/{mau.don_vi} ({ncc_ten}) · giá chuẩn {_tien(chuan)} · "
                       f"hệ số nhóm {nhom} {pt:g}% → cần bán từ {_tien(theo_he_so)}",
                       None, f"xet-gia-{mau.id}", link="/vat-tu?tab=gia-chuan&loc=duoi_he_so")
    # Báo người phụ trách dự án (thiết kế + KD) — họ chỉ thấy giá bán
    proj = await db.get(Project, d.project_id)
    if proj:
        ma = mau.ma if mau else (d.ma_tu_do or "")
        for uid in {proj.designer_id, proj.sales_id, proj.pm_id} - {None, user.id}:
            db.add(Notification(
                user_id=uid, type="vat_tu", title=f"Đã chốt giá vật tư · {proj.code}",
                body=f"{d.phong} · {ma}: {int(d.gia_ban):,}đ/{d.don_vi}".replace(",", "."),
                link=f"/vat-tu?project={proj.id}", ref_id=d.id,
            ))
    await db.commit()
    await db.refresh(d)
    return (await _goi_dong(db, [d], user))[0]


# ── Đặt hàng – Leader Thu mua duyệt – Giám sát nhận hàng (13/11/2026) ───────
# Luật chốt với chủ dự án: mọi đơn đối chiếu khối lượng + đơn giá với báo giá.
# Nằm trong báo giá và không đội ngân sách → tự qua. Vượt BẤT KỲ mức nào → Leader
# Thu mua duyệt (chưa có biên độ %; xem số liệu ~1 tháng rồi mới nới).

def _tien(v: float) -> str:
    return f"{int(round(v)):,}đ".replace(",", ".")


def _so(v: float) -> str:
    return f"{v:g}"


async def _tong_da_dat(db: AsyncSession, project_id: str, tru_dong: str) -> float:
    """Tiền vật tư đã cam kết của dự án (đã đặt + đang chờ duyệt), không tính dòng đang xét.
    Đơn giá gõ lúc đặt thấp hơn giá vốn đã chốt thì tính theo giá đã chốt — như đơn đang xét ở `dat_hang`."""
    gia = func.coalesce(DongPhieuVatTu.gia_dat, DongPhieuVatTu.gia_von)
    v = (await db.execute(
        select(func.coalesce(func.sum(
            case((gia < DongPhieuVatTu.gia_von, DongPhieuVatTu.gia_von), else_=gia)
            * func.coalesce(DongPhieuVatTu.sl_dat, DongPhieuVatTu.so_luong)), 0))
        .where(DongPhieuVatTu.project_id == project_id, DongPhieuVatTu.id != tru_dong,
               DongPhieuVatTu.trang_thai.in_(("cho_duyet_dat", "da_dat", "giao_thieu", "da_giao")),
               DongPhieuVatTu.gia_von.is_not(None))
    )).scalar()
    return float(v or 0)


async def _ma_dong(db: AsyncSession, d: DongPhieuVatTu) -> str:
    mau = await db.get(MauVatTu, d.mau_id) if d.mau_id else None
    return (mau.ma if mau else d.ma_tu_do) or d.hang_muc or "vật tư"


async def _bao(db: AsyncSession, ids: set, title: str, body: str, proj: Project | None, ref: str,
               link: str | None = None) -> None:
    """Thông báo trong app + Telegram. Mặc định mở phiếu vật tư của dự án; `link` để mở chỗ khác."""
    from app.services.automation import _notify
    ids = {i for i in ids if i}
    if not ids:
        return
    link = link or f"/vat-tu?project={proj.id}"
    for u in (await db.execute(select(User).where(User.id.in_(ids), User.is_active == True))).scalars():  # noqa: E712
        await _notify(db, u, "vat_tu", title, body, link=link, ref_id=ref)


async def _ds_admin(db: AsyncSession) -> set[str]:
    return set((await db.execute(select(User.id).where(User.role == "admin", User.is_active == True))).scalars())  # noqa: E712


async def _ds_leader_thu_mua(db: AsyncSession) -> set[str]:
    ds = (await db.execute(select(User).where(
        func.upper(User.department).in_(PHONG_THU_MUA), User.is_active == True  # noqa: E712
    ))).scalars().all()
    ids = {u.id for u in ds if la_leader_thu_mua(u)}
    if not ids:  # bộ phận chưa có Leader → Admin duyệt thay
        ids = await _ds_admin(db)
    return ids


@router.post("/dong/{dong_id}/dat-hang")
async def dat_hang(dong_id: str, body: DatHangIn, user: User = Depends(yeu_cau_thu_mua), db: AsyncSession = Depends(get_db)):
    """Thu mua đặt hàng. Trong báo giá → «Đã đặt»; vượt → «Chờ Leader Thu mua duyệt»."""
    d = await _dong_hoac_404(db, dong_id)
    if d.trang_thai != "da_chot_gia" or not d.gia_von:
        raise HTTPException(400, "Chỉ đặt được dòng đã chốt giá")
    if not d.ncc_id:  # dòng chốt trước 22/11 không kèm NCC: lời hẹn giao, lịch sử nhận hàng sẽ không thuộc NCC nào
        raise HTTPException(400, "Dòng chốt giá chưa có nhà cung cấp — chốt lại kèm NCC rồi đặt hàng")
    # Đặt hàng khi khách chưa đồng ý giá bán = rủi ro công ty ôm hàng (27/10/2026).
    # 22/11: lời đồng ý còn hiệu lực tới khi giá bán đổi (`_dat_gia_ban` xoá khi đổi) — khách
    # đồng ý giá chuẩn TRƯỚC khi Thu mua chốt giá vốn vẫn tính.
    if d.gia_ban is not None and not d.khach_dong_y_luc:
        raise HTTPException(400, "Khách chưa đồng ý giá bán — bấm «Khách đồng ý» trước khi đặt hàng")
    if gia_da_cu(d.gia_xac_nhan_luc or d.chot_luc):
        raise HTTPException(400, f"Giá chốt đã quá {SO_NGAY_GIA_CU} ngày — hỏi lại NCC, ghi báo giá mới rồi chốt lại trước khi đặt")
    if not body.ngay_giao_hen:
        raise HTTPException(400, "Chọn ngày NCC hẹn giao")
    if body.ngay_giao_hen < vn_today():
        raise HTTPException(400, "Ngày NCC hẹn giao không được trước hôm nay")
    proj = await db.get(Project, d.project_id)
    sl = body.so_luong or d.so_luong
    gia = body.don_gia or d.gia_von
    vuot: list[str] = []
    if sl > d.so_luong + 1e-9:
        vuot.append(f"Khối lượng {_so(sl)} {d.don_vi} vượt báo giá {_so(d.so_luong)} {d.don_vi}")
    if gia > d.gia_von + 0.5:
        vuot.append(f"Đơn giá {_tien(gia)} vượt báo giá {_tien(d.gia_von)}")
    if proj and proj.budget_total:
        # Ngân sách dự án là trần của TOÀN BỘ chi phí (chốt 22/11/2026): vật tư đã đặt + đơn này
        # + các khoản chi khác của dự án. Bỏ loại «material»: tiền trả NCC đã nằm trong vật tư đã đặt.
        chi_khac = float((await db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.project_id == d.project_id, Transaction.type == "expense",
                Transaction.status != "cancelled", Transaction.category != "material")
        )).scalar() or 0)
        # Sàn là giá vốn đã chốt: gõ đơn giá thấp (nhầm, hoặc cho lọt trần) không làm ngân sách «còn dư»
        tong = await _tong_da_dat(db, d.project_id, d.id) + sl * max(gia, d.gia_von) + chi_khac
        if tong > float(proj.budget_total) + 0.5:
            vuot.append(f"Tổng chi phí dự án {_tien(tong)} vượt ngân sách {_tien(float(proj.budget_total))}")
    d.sl_dat, d.gia_dat, d.dat_boi, d.dat_luc = sl, gia, user.id, _now()
    d.ngay_giao_hen = body.ngay_giao_hen
    if d.ngay_giao_hen_dau is None:  # lời hẹn ĐẦU ghi một lần — chấm NCC giao đúng hạn theo mốc này
        d.ngay_giao_hen_dau = body.ngay_giao_hen
    d.tu_choi_dat_ly_do = None
    d.ly_do_vuot = "; ".join(vuot) or None
    ma = await _ma_dong(db, d)
    if not vuot:
        d.trang_thai, d.duyet_dat_boi, d.duyet_dat_luc = "da_dat", None, None
    else:
        # Đơn vượt của AI cũng chờ duyệt — Leader tự đặt không còn tự qua (22/11/2026)
        d.trang_thai, d.duyet_dat_boi, d.duyet_dat_luc = "cho_duyet_dat", None, None
        if proj:
            nguoi_duyet = await _ds_leader_thu_mua(db)
            if user.id in nguoi_duyet:  # Leader tự đặt → Leader khác và Admin duyệt
                nguoi_duyet |= await _ds_admin(db)
            await _bao(db, nguoi_duyet - {user.id}, f"Đơn đặt hàng vượt báo giá cần duyệt · {proj.code}",
                       f"{d.phong} · {ma}: {d.ly_do_vuot}. Người đặt: {user.full_name}", proj, f"duyet-dat-{d.id}")
    if d.trang_thai == "da_dat" and proj:
        # Báo Giám sát: hàng sắp về, nhận hàng phải chụp ảnh hiện trường
        await _bao(db, {proj.pm_id} - {user.id}, f"Vật tư đã đặt · {proj.code}",
                   f"{d.phong} · {ma}: {_so(sl)} {d.don_vi}. Khi hàng về, xác nhận đủ/thiếu kèm ảnh hiện trường.",
                   proj, f"dat-{d.id}")
    await db.flush()
    from app.services.dong_bo_tai_chinh import tinh_lai_spent
    await tinh_lai_spent(db, d.project_id)
    await db.commit()
    await db.refresh(d)
    return (await _goi_dong(db, [d], user))[0]


@router.post("/dong/{dong_id}/duyet-dat")
async def duyet_dat(dong_id: str, body: DuyetDatIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Leader Thu mua duyệt / từ chối đơn vượt báo giá hoặc ngân sách."""
    if not la_leader_thu_mua(user):
        raise HTTPException(403, "Chỉ Leader Thu mua mới duyệt được đơn vượt báo giá")
    d = await _dong_hoac_404(db, dong_id)
    if d.trang_thai != "cho_duyet_dat":
        raise HTTPException(400, "Dòng này không chờ duyệt đặt hàng")
    if d.dat_boi == user.id and user.role != "admin":
        raise HTTPException(403, "Không tự duyệt đơn mình đặt — nhờ Leader Thu mua khác hoặc Admin duyệt")
    ly_do = (body.ly_do or "").strip()
    if not body.dong_y and not ly_do:
        raise HTTPException(400, "Từ chối thì ghi lý do để Thu mua biết đường sửa")
    proj = await db.get(Project, d.project_id)
    ma = await _ma_dong(db, d)
    nguoi_dat = d.dat_boi
    d.duyet_dat_boi, d.duyet_dat_luc = user.id, _now()
    if body.dong_y:
        d.trang_thai = "da_dat"
    else:
        # Trả về bước đã chốt giá để Thu mua sửa khối lượng/đơn giá rồi đặt lại
        d.trang_thai, d.tu_choi_dat_ly_do = "da_chot_gia", ly_do[:1000]
        d.sl_dat, d.gia_dat = None, None
        d.ngay_giao_hen = d.ngay_giao_hen_dau = None  # đơn chưa từng được đặt → chưa có lời hẹn nào
    if proj:
        if body.dong_y:
            await _bao(db, {nguoi_dat} - {user.id}, f"Đơn vượt báo giá đã được duyệt · {proj.code}",
                       f"{d.phong} · {ma} — {user.full_name} duyệt", proj, f"duyet-dat-ok-{d.id}")
            await _bao(db, {proj.pm_id} - {user.id}, f"Vật tư đã đặt · {proj.code}",
                       f"{d.phong} · {ma}: {_so(d.sl_dat or d.so_luong)} {d.don_vi}. Khi hàng về, xác nhận đủ/thiếu kèm ảnh hiện trường.",
                       proj, f"dat-{d.id}")
        else:
            await _bao(db, {nguoi_dat} - {user.id}, f"Đơn đặt hàng bị từ chối · {proj.code}",
                       f"{d.phong} · {ma}: {ly_do}", proj, f"duyet-dat-tc-{d.id}")
    await db.flush()
    from app.services.dong_bo_tai_chinh import tinh_lai_spent
    await tinh_lai_spent(db, d.project_id)
    await db.commit()
    await db.refresh(d)
    return (await _goi_dong(db, [d], user))[0]


@router.post("/dong/{dong_id}/nhan-hang")
async def nhan_hang(dong_id: str, body: NhanHangIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Giám sát xác nhận hàng về công trình đủ/thiếu — bắt buộc ≥2 ảnh hiện trường.

    Ảnh tải trước qua /media/upload-batch (vào Kho ảnh Telegram của dự án), ở đây chỉ
    nhận id và KIỂM lại ở server: phải là ảnh của đúng dự án này.
    """
    from app.models.media import MediaFile

    d = await _dong_hoac_404(db, dong_id)
    proj = await db.get(Project, d.project_id)
    if not la_giam_sat(user, proj):
        raise HTTPException(403, "Hàng về do Giám sát công trình xác nhận — Thu mua chỉ xem")
    if user.role != "admin":
        await require_project_access(d.project_id, user, db)
    if d.trang_thai not in ("da_dat", "giao_thieu"):
        raise HTTPException(400, "Chỉ xác nhận được dòng đã đặt hàng")
    if body.ket_qua not in ("du", "thieu"):
        raise HTTPException(400, "Kết quả nhận hàng: đủ hoặc thiếu")
    ly_do_loi = body.ly_do_loi or None  # ô chọn để trống gửi "" = không ghi lỗi
    if ly_do_loi is not None and ly_do_loi not in LY_DO_LOI_NHAN_HANG:
        raise HTTPException(400, "Lý do hàng lỗi không hợp lệ")
    ghi_chu = (body.ghi_chu or "").strip()
    if body.ket_qua == "thieu" and not ghi_chu:
        raise HTTPException(400, "Hàng thiếu thì ghi rõ thiếu gì, bao nhiêu")
    ids = list(dict.fromkeys(body.anh_ids))
    hop_le = set((await db.execute(
        select(MediaFile.id).where(MediaFile.id.in_(ids), MediaFile.project_id == d.project_id)
    )).scalars()) if ids else set()
    ids = [i for i in ids if i in hop_le]
    if len(ids) < SO_ANH_NHAN_HANG_TOI_THIEU:
        raise HTTPException(400, f"Cần tối thiểu {SO_ANH_NHAN_HANG_TOI_THIEU} ảnh chụp tại hiện trường mới xác nhận được")
    sl_dat = d.sl_dat or d.so_luong
    da_ve = (d.sl_nhan or 0) if d.trang_thai == "giao_thieu" else 0  # tổng đã về TRƯỚC lần này
    luy_ke = sl_dat if body.ket_qua == "du" else body.so_luong_nhan   # tổng đã về TỚI lần này
    if luy_ke is None:
        raise HTTPException(400, "Hàng thiếu thì ghi tổng số lượng đã về tới giờ")
    if body.ket_qua == "thieu" and luy_ke >= sl_dat:
        raise HTTPException(400, "Số lượng nhận đã đủ — chọn «Đủ hàng»")
    if luy_ke < da_ve:
        raise HTTPException(400, f"Tổng đã về không thể ít hơn lần trước ({_so(da_ve)} {d.don_vi})")
    # Lần nhận bù sau «giao thiếu»: giữ ảnh các lần trước để còn đối chứng
    d.nhan_anh_ids = json.dumps(list(dict.fromkeys(_ids_anh(d) + ids)))
    luc = _naive(_now())
    d.nhan_ket_qua, d.nhan_boi, d.nhan_luc, d.nhan_ghi_chu = body.ket_qua, user.id, luc, ghi_chu[:1000] or None
    d.sl_nhan = luy_ke
    d.trang_thai = "da_giao" if body.ket_qua == "du" else "giao_thieu"
    # Mỗi LẦN nhận một dòng lịch sử, không ghi đè: giao thiếu, giao bù, hàng lỗi — để chấm NCC
    db.add(NhanHangVatTu(
        dong_id=d.id, ket_qua=body.ket_qua, sl_lan_nay=round(luy_ke - da_ve, 3), sl_luy_ke=luy_ke,
        ly_do_loi=ly_do_loi, ghi_chu=ghi_chu[:1000] or None, anh_ids=json.dumps(ids), boi=user.id, luc=luc,
    ))
    ma = await _ma_dong(db, d)
    if proj:
        nhan = {d.dat_boi, getattr(proj, "purchasing_id", None)} - {user.id}
        if body.ket_qua == "du":
            await _bao(db, nhan, f"Hàng về đủ · {proj.code}",
                       f"{d.phong} · {ma} — {user.full_name} xác nhận, {len(ids)} ảnh", proj, f"nhan-{d.id}")
        else:
            await _bao(db, (nhan | await _ds_leader_thu_mua(db)) - {user.id}, f"Hàng về THIẾU · {proj.code}",
                       f"{d.phong} · {ma}: {ghi_chu}. {user.full_name} xác nhận, {len(ids)} ảnh", proj, f"nhan-thieu-{d.id}")
    await db.commit()
    await db.refresh(d)
    return (await _goi_dong(db, [d], user))[0]


@router.get("/viec-dat-nhan")
async def viec_dat_nhan(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Hai hàng chờ: đơn vượt chờ Leader duyệt, và hàng đã đặt chờ Giám sát nhận."""
    cho_duyet: list[DongPhieuVatTu] = []
    if la_thu_mua(user) or user.role == "executive":
        cho_duyet = list((await db.execute(
            select(DongPhieuVatTu).where(DongPhieuVatTu.trang_thai == "cho_duyet_dat").order_by(DongPhieuVatTu.dat_luc)
        )).scalars())
    q = select(DongPhieuVatTu).where(DongPhieuVatTu.trang_thai.in_(("da_dat", "giao_thieu"))).order_by(DongPhieuVatTu.dat_luc)
    if not (la_thu_mua(user) or user.role in ("admin", "executive") or la_truong_phong(user)):
        # Giám sát: chỉ hàng của dự án mình phụ trách
        q = q.join(Project, Project.id == DongPhieuVatTu.project_id).where(Project.pm_id == user.id)
    cho_nhan = list((await db.execute(q)).scalars())
    # Dòng chính người này phải ra công trình xác nhận (cho «Việc của tôi»): Giám sát phụ trách
    # dự án hoặc người bộ phận Giám sát — Admin/Thu mua chỉ xem nên không tính.
    pm_theo_du_an = dict((await db.execute(
        select(Project.id, Project.pm_id).where(Project.id.in_({d.project_id for d in cho_nhan}))
    )).all()) if cho_nhan else {}
    la_bp_giam_sat = (user.department or "").upper() in PHONG_GIAM_SAT
    nhan_cua_toi = [d.id for d in cho_nhan if la_bp_giam_sat or pm_theo_du_an.get(d.project_id) == user.id]
    return {
        "nhan_cua_toi": nhan_cua_toi,
        "cho_duyet": await _goi_dong(db, cho_duyet, user, kem_du_an=True),
        "cho_nhan": await _goi_dong(db, cho_nhan, user, kem_du_an=True),
        "la_leader_thu_mua": la_leader_thu_mua(user),
        "so_anh_toi_thieu": SO_ANH_NHAN_HANG_TOI_THIEU,
    }


@router.get("/tong-quan")
async def tong_quan(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Số liệu cho đầu trang: số mẫu, số dòng theo trạng thái."""
    so_mau = (await db.execute(select(func.count()).select_from(MauVatTu).where(MauVatTu.is_active.is_(True)))).scalar_one()
    theo_tt = dict((await db.execute(
        select(DongPhieuVatTu.trang_thai, func.count()).group_by(DongPhieuVatTu.trang_thai)
    )).all())
    return {"so_mau": so_mau, "theo_trang_thai": theo_tt, "thay_gia_von": xem_gia_von(user), "la_thu_mua": la_thu_mua(user),
            "la_leader_thu_mua": la_leader_thu_mua(user), "la_giam_sat": la_giam_sat(user, None),
            "so_anh_toi_thieu": SO_ANH_NHAN_HANG_TOI_THIEU, "so_ngay_gia_cu": SO_NGAY_GIA_CU,
            "ly_do_loi_nhan_hang": LY_DO_LOI_NHAN_HANG}


# ── Bot Telegram nhập báo giá từ tệp (25/10/2026) ─────────────────────────
# Luồng: Thu mua gửi tệp cho bot → /bot/trich-bao-gia đọc + khớp mã với phiếu
# dự án → bot hiện bản xem trước → người bấm «Ghi» → /bot/ghi-bao-gia.
# Không bao giờ ghi thẳng từ tệp.

class TrichBaoGiaIn(BaseModel):
    project_id: str
    file_id: str | None = None   # tệp gửi qua Telegram (ảnh chụp bảng giá)
    sheet_url: str | None = None  # link Google Sheet chia sẻ công khai (30/10/2026: thay tệp)
    file_name: str | None = None
    mime: str | None = None


async def _tai_nguon(body: TrichBaoGiaIn, proj: Project, db: AsyncSession) -> tuple[bytes, str | None, str | None]:
    """Bytes báo giá từ link Google Sheet (lưu link vào dự án) hoặc tệp Telegram."""
    from app.services import vat_tu_bao_gia_tep as tep

    if body.sheet_url:
        data = await tep.tai_google_sheet(body.sheet_url)
        link = tep.chuan_link_sheet(body.sheet_url)
        if proj.bao_gia_sheet_url != link:
            proj.bao_gia_sheet_url = link
            await db.commit()
        return data, body.file_name or "google_sheet.xlsx", None
    if not body.file_id:
        raise tep.TepError("Gửi link Google Sheet báo giá")
    return await tep.tai_tep_telegram(body.file_id), body.file_name, body.mime


class BaoGiaBotItem(BaseModel):
    dong_id: str
    ncc_ten: str = Field(min_length=1, max_length=150)
    gia: float = Field(gt=0)
    con_hang: bool = True
    ghi_chu: str | None = Field(default=None, max_length=300)


class TaoDongBotItem(BaseModel):
    """Dòng phiếu tạo mới từ tệp báo giá (dự án chưa có phiếu). Mẫu tra lại theo mã ở máy chủ."""
    ma: str = Field(min_length=1, max_length=150)
    phong: str | None = Field(default=None, max_length=100)
    so_luong: float | None = Field(default=None, gt=0)
    don_vi: str | None = Field(default=None, max_length=20)
    ncc_ten: str = Field(min_length=1, max_length=150)
    gia: float = Field(gt=0)
    con_hang: bool = True
    ghi_chu: str | None = Field(default=None, max_length=300)


class GhiBaoGiaIn(BaseModel):
    items: list[BaoGiaBotItem] = Field(default_factory=list, max_length=200)
    project_id: str | None = None                                  # bắt buộc khi có tao_dong
    tao_dong: list[TaoDongBotItem] = Field(default_factory=list, max_length=300)
    nguon: str | None = Field(default=None, max_length=200)  # «tệp baogia.xlsx»
    ncc_mst: str | None = Field(default=None, max_length=20)      # AI đọc được trong tệp
    ncc_dia_chi: str | None = Field(default=None, max_length=500)


async def _dong_cho_khop(db: AsyncSession, project_id: str) -> list[dict]:
    ds = (await db.execute(
        select(DongPhieuVatTu).where(DongPhieuVatTu.project_id == project_id).order_by(DongPhieuVatTu.thu_tu)
    )).scalars().all()
    ids = {d.mau_id for d in ds if d.mau_id}
    mau = {m.id: m for m in (await db.execute(select(MauVatTu).where(MauVatTu.id.in_(ids)))).scalars()} if ids else {}
    out = []
    for d in ds:
        m = mau.get(d.mau_id or "")
        out.append({
            "dong_id": d.id, "ma": (m.ma if m else d.ma_tu_do), "ma_phieu": (m.ma if m else d.ma_tu_do),
            "phong": d.phong, "so_luong": d.so_luong, "don_vi_phieu": d.don_vi, "trang_thai": d.trang_thai,
        })
    return out


@router.post("/bot/trich-bao-gia")
async def bot_trich_bao_gia(body: TrichBaoGiaIn, user: User = Depends(yeu_cau_thu_mua), db: AsyncSession = Depends(get_db)):
    """Đọc tệp báo giá NCC (Excel/CSV/PDF/ảnh) từ Telegram → bản xem trước đã khớp
    mã với phiếu vật tư dự án. CHƯA ghi gì."""
    from app.services import vat_tu_bao_gia_tep as tep

    proj = await db.get(Project, body.project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    dong = await _dong_cho_khop(db, proj.id)
    try:
        data, ten_tep, mime = await _tai_nguon(body, proj, db)
        loai, chu = tep.tep_sang_chu(data, ten_tep, mime)
        if tep.la_bao_gia_khach(body.file_name, chu):
            # Báo giá JAMA gửi khách gửi nhầm vào luồng NCC → bot tự chuyển sang /phatsinh (30/10/2026)
            return {"la_bao_gia_khach": True, "project_code": proj.code}
        kq = await tep.trich_tu_anh(data, body.mime) if loai == "image" else await tep.trich_tu_chu(chu)
    except tep.TepError as e:
        raise HTTPException(e.status, str(e))
    tao_moi: list[dict] = []
    if dong:
        khop, khong = tep.khop_ma(kq["items"], dong)
    else:
        # Dự án chưa có phiếu (29/10/2026): mọi mã có giá → đề xuất TẠO dòng phiếu mới.
        # Mã có trong Danh mục mẫu thì gắn mẫu, không thì ghi mã tự do. Chưa ghi gì.
        khop = []
        khong = [it for it in kq["items"] if it.get("gia") is None]
        mau = await _mau_theo_ma(db, [it["ma"] for it in kq["items"] if it.get("gia") is not None])
        for it in kq["items"]:
            if it.get("gia") is None:
                continue
            m = mau.get(tep.chuan_ma(it["ma"]))
            tao_moi.append({**it, "ma": m.ma if m else it["ma"], "co_trong_danh_muc": bool(m),
                            "phong": it.get("phong") or "Chung",
                            # Mã có trong danh mục: dòng tạo ra mang đơn vị của MẪU → xem trước hiện đúng đơn vị đó
                            "don_vi": m.don_vi if m else (it.get("don_vi") or "m2")})
    return {
        "project_code": proj.code, "project_name": proj.name, "ncc_ten": kq["ncc_ten"],
        "ncc_mst": kq.get("ncc_mst"), "ncc_dia_chi": kq.get("ncc_dia_chi"),
        "loai_tep": loai, "so_dong_phieu": len(dong), "so_doc_duoc": len(kq["items"]),
        "khop": khop, "khong_khop": khong[:30], "tao_moi": tao_moi,
    }


async def _mau_theo_ma(db: AsyncSession, mas: list[str]) -> dict[str, MauVatTu]:
    """Tra Danh mục mẫu theo mã đã chuẩn hoá («TM 76006» ≡ «tm-76006»)."""
    from app.services.vat_tu_bao_gia_tep import chuan_ma
    can = {chuan_ma(m) for m in mas if m}
    if not can:
        return {}
    out: dict[str, MauVatTu] = {}
    for m in (await db.execute(select(MauVatTu).where(MauVatTu.is_active.is_(True)))).scalars():
        k = chuan_ma(m.ma)
        if k in can and k not in out:
            out[k] = m
    return out


@router.post("/bot/ghi-bao-gia", status_code=201)
async def bot_ghi_bao_gia(body: GhiBaoGiaIn, user: User = Depends(yeu_cau_thu_mua), db: AsyncSession = Depends(get_db)):
    """Ghi hàng loạt báo giá đã được Thu mua xác nhận trên bot. Ghi chú ghi rõ nguồn tệp + người nhập."""
    if not body.items and not body.tao_dong:
        raise HTTPException(400, "Không có dòng nào để ghi")
    ghi, loi, tao = 0, [], 0
    nguon = f"Nhập từ {body.nguon} bởi {user.full_name} (bot)" if body.nguon else f"Nhập qua bot bởi {user.full_name}"
    bo = BoNcc(db)
    if body.tao_dong:
        from app.services.vat_tu_bao_gia_tep import chuan_ma
        if not body.project_id or not await db.get(Project, body.project_id):
            raise HTTPException(404, "Project not found")
        mau = await _mau_theo_ma(db, [t.ma for t in body.tao_dong])
        thu_tu = (await db.execute(
            select(func.coalesce(func.max(DongPhieuVatTu.thu_tu), 0)).where(DongPhieuVatTu.project_id == body.project_id)
        )).scalar_one()
        for t in body.tao_dong:
            m = mau.get(chuan_ma(t.ma))
            thu_tu += 1
            d = DongPhieuVatTu(
                project_id=body.project_id, created_by=user.id, thu_tu=thu_tu,
                phong=(t.phong or "Chung").strip()[:100] or "Chung",
                mau_id=m.id if m else None, ma_tu_do=None if m else t.ma.strip(),
                so_luong=t.so_luong or 1, don_vi=(t.don_vi or (m.don_vi if m else "m2"))[:20],
                ghi_chu=f"Tạo từ báo giá — {nguon}"[:500], trang_thai="hoi_ncc",
            )
            db.add(d)
            if m:
                await ap_mau_moi(db, d)  # đơn vị theo mẫu; mẫu có giá chuẩn → có giá bán ngay
            await db.flush()
            s = await bo.lay(t.ncc_ten, body.ncc_mst, body.ncc_dia_chi)
            ghi_chu = f"{t.ghi_chu} · {nguon}" if t.ghi_chu else nguon
            db.add(BaoGiaDongVatTu(dong_id=d.id, supplier_id=s.id if s else None,
                                   ncc_ten=s.name if s else t.ncc_ten.strip(), gia=t.gia, con_hang=t.con_hang,
                                   ghi_chu=ghi_chu[:500], nguon="tep", created_by=user.id))
            tao += 1
            ghi += 1
    for it in body.items:
        d = await db.get(DongPhieuVatTu, it.dong_id)
        if not d:
            loi.append({"dong_id": it.dong_id, "loi": "Không có dòng này"})
            continue
        ghi_chu = f"{it.ghi_chu} · {nguon}" if it.ghi_chu else nguon
        s = await bo.lay(it.ncc_ten, body.ncc_mst, body.ncc_dia_chi)
        db.add(BaoGiaDongVatTu(dong_id=d.id, supplier_id=s.id if s else None,
                               ncc_ten=s.name if s else it.ncc_ten.strip(), gia=it.gia, con_hang=it.con_hang,
                               ghi_chu=ghi_chu[:500], nguon="tep", created_by=user.id))
        if d.trang_thai == "khach_chon":
            d.trang_thai = "hoi_ncc"
        ghi += 1
    await db.commit()
    return {"ghi": ghi, "tao": tao, "loi": loi}


# ── Bot nhập BÁO GIÁ PHÁT SINH gửi khách (30/10/2026) ─────────────────────
# Tệp JAMA báo khách → (A) phụ lục NHÁP dưới HĐ gốc (khách chốt = ký trên web)
# + (B) dòng phiếu vật tư cho hạng mục SL > 0 để Thu mua hỏi NCC. Giảm trừ
# (SL âm, CĐT cấp) chỉ trừ tiền phụ lục, không sinh dòng mua.

class PhatSinhItem(BaseModel):
    hang_muc: str = Field(min_length=1, max_length=255)
    dvt: str | None = Field(default=None, max_length=20)
    kl: float | None = None
    sl: float | None = None
    don_gia: float | None = None
    thanh_tien: float
    kich_thuoc: str | None = Field(default=None, max_length=60)
    ghi_chu: str | None = Field(default=None, max_length=300)


class GhiPhatSinhIn(BaseModel):
    project_id: str
    contract_id: str
    tieu_de: str = Field(min_length=3, max_length=255)
    items: list[PhatSinhItem] = Field(min_length=1, max_length=200)
    nguon: str | None = Field(default=None, max_length=200)


async def _quyen_phat_sinh(project_id: str, user: User, db: AsyncSession) -> Project:
    from app.api.contracts import _yeu_cau_quyen_hop_dong
    await _yeu_cau_quyen_hop_dong(user, db)
    proj = await db.get(Project, project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    if not la_thu_mua(user):
        await require_project_access(project_id, user, db)
    return proj


async def _hd_goc(db: AsyncSession, project_id: str) -> list:
    from app.models.contract import Contract
    return list((await db.execute(
        select(Contract).where(Contract.project_id == project_id, Contract.parent_contract_id.is_(None),
                               Contract.status != "cancelled").order_by(Contract.created_at)
    )).scalars())


DAU_PL_BOT = "[Phát sinh qua bot]"  # đầu ghi chú phụ lục bot tạo → tệp gửi lần sau CẬP NHẬT phụ lục này


async def _pl_bot_nhap(db: AsyncSession, goc_id: str):
    """Phụ lục bot tạo, còn NHÁP (khách chưa ký) — mới nhất. Ký rồi thì tệp sau tạo phụ lục mới."""
    from app.models.contract import Contract
    return (await db.execute(
        select(Contract).where(Contract.parent_contract_id == goc_id, Contract.status == "draft",
                               Contract.notes.like(f"{DAU_PL_BOT}%"))
        .order_by(Contract.created_at.desc()).limit(1)
    )).scalars().first()


def _cua_pl(d: DongPhieuVatTu, code: str) -> bool:
    g = d.ghi_chu or ""
    return g == f"Phát sinh {code}" or g.startswith(f"Phát sinh {code} · ")


def _so_luong_mua(it: PhatSinhItem | dict) -> float:
    g = it if isinstance(it, dict) else it.model_dump()
    kl, sl = g.get("kl"), g.get("sl")
    return round((kl if kl and kl > 0 else 1) * (sl if sl and sl > 0 else 1), 3)


@router.post("/bot/trich-phat-sinh")
async def bot_trich_phat_sinh(body: TrichBaoGiaIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Đọc tệp báo giá phát sinh gửi khách → xem trước (tổng tự tính, đối chiếu tổng
    trong tệp, tên khách có khớp dự án không, HĐ gốc để gắn phụ lục). CHƯA ghi gì."""
    from app.services import vat_tu_bao_gia_tep as tep

    proj = await _quyen_phat_sinh(body.project_id, user, db)
    try:
        data, ten_tep, mime = await _tai_nguon(body, proj, db)
        loai, chu = tep.tep_sang_chu(data, ten_tep, mime)
        if loai == "image":
            kq = await tep.trich_tu_anh(data, body.mime, tep._PROMPT_PHAT_SINH, tep.chuan_hoa_phat_sinh)
        else:
            kq = await tep.trich_tu_chu(tep.chi_sheet_phat_sinh(chu), tep._PROMPT_PHAT_SINH, tep.chuan_hoa_phat_sinh)
    except tep.TepError as e:
        raise HTTPException(e.status, str(e))
    tong = sum(it["thanh_tien"] for it in kq["items"])
    hd = await _hd_goc(db, proj.id)
    return {
        "project_code": proj.code, "project_name": proj.name, "client_name": proj.client_name,
        "khach_trong_tep": kq["khach_hang"], "tieu_de": kq["tieu_de"],
        # None = không đủ chữ để so; False = tên tệp/khách trong tệp không giống khách dự án → bot cảnh báo
        "khop_khach": tep.ten_khop(proj.client_name, body.file_name, kq["khach_hang"]),
        "items": kq["items"], "tong": tong, "tong_file": kq["tong_file"],
        "lech_tong": (kq["tong_file"] is not None and abs(kq["tong_file"] - tong) > 1000),
        "so_dong_mua": sum(1 for it in kq["items"] if (it["sl"] is None or it["sl"] > 0) and it["thanh_tien"] > 0),
        "hop_dong": [{"id": c.id, "code": c.code, "title": c.title, "status": c.status,
                      # có phụ lục nháp từ tệp trước → lần này CẬP NHẬT nó (tệp mới nhất là chuẩn)
                      "cap_nhat": ({"code": pl.code, "total_value": pl.total_value} if pl else None)}
                     for c in hd for pl in [await _pl_bot_nhap(db, c.id)]],
        "loai_tep": loai,
    }


@router.post("/bot/ghi-phat-sinh", status_code=201)
async def bot_ghi_phat_sinh(body: GhiPhatSinhIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Ghi phát sinh đã xem trước: phụ lục nháp + dòng phiếu vật tư (trạng thái «Khách chọn»)."""
    from app.api.contracts import tao_phu_luc_cho
    from app.models.contract import Contract

    await _quyen_phat_sinh(body.project_id, user, db)
    goc = await db.get(Contract, body.contract_id)
    if not goc or goc.project_id != body.project_id:
        raise HTTPException(404, "Không tìm thấy hợp đồng của dự án này")
    if goc.parent_contract_id or goc.status == "cancelled":
        raise HTTPException(400, "Chọn hợp đồng gốc còn hiệu lực để gắn phụ lục")
    tong = sum(it.thanh_tien for it in body.items)
    nguon = f"tệp {body.nguon}" if body.nguon else "bot"
    dong_note = []
    for it in body.items:
        so = " × ".join(f"{v:g}" for v in (it.kl, it.sl) if v is not None)
        dong_note.append(f"- {it.hang_muc}" + (f" ({so} {it.dvt or ''})".rstrip() if so else "")
                         + f": {it.thanh_tien:,.0f}đ".replace(",", "."))
    notes = (f"{DAU_PL_BOT} Nhập từ {nguon} bởi {user.full_name}. Gửi khách tham khảo — khách chốt thì ký phụ lục.\n"
             + "\n".join(dong_note))
    pl = await _pl_bot_nhap(db, goc.id)
    cu = None
    xoa, da_xu_ly = 0, set()
    if pl:
        # Tệp mới nhất = chuẩn: ghi đè phụ lục nháp + dòng vật tư Thu mua chưa đụng tới
        from app.services.dong_bo_tai_chinh import dong_bo_gia_tri_du_an
        cu = pl.total_value
        pl.title, pl.total_value, pl.notes = body.tieu_de, tong, notes[:5000]
        pl.payment_terms = {"installments": [] if tong <= 0 else [
            {"name": "Thu phụ lục", "percentage": 100, "milestone": "signing", "status": "pending"}]}
        for d in (await db.execute(select(DongPhieuVatTu).where(DongPhieuVatTu.project_id == body.project_id))).scalars():
            if not _cua_pl(d, pl.code):
                continue
            if d.trang_thai == "khach_chon":
                await db.delete(d)
                xoa += 1
            else:
                da_xu_ly.add(nfc(d.hang_muc or "").strip().lower())  # Thu mua đã hỏi giá/chốt → giữ, không tạo lại
        await db.flush()
        await dong_bo_gia_tri_du_an(db, goc.project_id)
        from app.cache import cache
        cache.clear_prefix("pl")
    else:
        pl = await tao_phu_luc_cho(db, goc, body.tieu_de, tong, notes[:5000])

    thu_tu = (await db.execute(
        select(func.coalesce(func.max(DongPhieuVatTu.thu_tu), 0)).where(DongPhieuVatTu.project_id == body.project_id)
    )).scalar_one()
    tao = 0
    for it in body.items:
        if (it.sl is not None and it.sl <= 0) or it.thanh_tien <= 0:
            continue  # giảm trừ: CĐT cấp, không mua
        if nfc(it.hang_muc).strip().lower() in da_xu_ly:  # NFC: tệp gõ dạng tổ hợp vẫn nhận ra dòng đã có
            continue
        thu_tu += 1
        gia_khach = f"Giá báo khách {it.don_gia:,.0f}đ/{it.dvt or 'đv'}".replace(",", ".") if it.don_gia else ""
        ghi = " · ".join(x for x in (f"Phát sinh {pl.code}", it.kich_thuoc, it.ghi_chu, gia_khach) if x)
        d = DongPhieuVatTu(
            project_id=body.project_id, created_by=user.id, thu_tu=thu_tu,
            phong="Phát sinh", hang_muc=it.hang_muc[:255], ma_tu_do=it.hang_muc[:150],
            so_luong=_so_luong_mua(it), don_vi=(it.dvt or "cái")[:20],
            ghi_chu=ghi[:500], trang_thai="khach_chon",
        )
        db.add(d)
        await ap_mau_moi(db, d)  # mã trùng mẫu trong danh mục → gắn mẫu, giá chuẩn + đơn vị theo mẫu
        tao += 1
    await db.commit()
    return {"phu_luc": {"id": pl.id, "code": pl.code, "total_value": tong}, "tao_dong": tao,
            "cap_nhat": cu is not None, "gia_tri_cu": cu, "xoa_dong_cu": xoa, "giu_dong": len(da_xu_ly)}


# ── Gợi ý NCC cho một mẫu (26/10/2026) ──

async def _mau_hoac_404(db: AsyncSession, mau_id: str) -> MauVatTu:
    m = await db.get(MauVatTu, mau_id)
    if not m:
        raise HTTPException(404, "Không có mẫu này")
    return m


@router.get("/mau/{mau_id}/goi-y-ncc")
async def goi_y_ncc(mau_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Xếp NCC cho một mẫu: hạng (chính → dự phòng → đang thử → chưa xếp) → còn hàng → giá sau
    chiết khấu thấp nhất → tổng tiền JAMA đã mua của NCC cao nhất."""
    if not xem_gia_von(user):
        raise HTTPException(403, "Chỉ Thu mua / Ban giám đốc xem được giá NCC")
    await _mau_hoac_404(db, mau_id)
    bgs = (await db.execute(
        select(BaoGiaDongVatTu).join(DongPhieuVatTu, DongPhieuVatTu.id == BaoGiaDongVatTu.dong_id)
        .where(DongPhieuVatTu.mau_id == mau_id).order_by(BaoGiaDongVatTu.created_at.desc())
    )).scalars().all()
    moi_nhat: dict[str, BaoGiaDongVatTu] = {}  # mỗi NCC lấy báo giá mới nhất
    for b in bgs:
        moi_nhat.setdefault(b.supplier_id or f"ten:{(b.ncc_ten or '').strip().lower()}", b)
    sids = [b.supplier_id for b in moi_nhat.values() if b.supplier_id]
    ncc = {s.id: s for s in (await db.execute(select(Supplier).where(Supplier.id.in_(sids)))).scalars()} if sids else {}
    da_mua = dict((await db.execute(
        select(DongPhieuVatTu.ncc_id, func.sum(DongPhieuVatTu.gia_von * DongPhieuVatTu.so_luong))
        .where(DongPhieuVatTu.ncc_id.in_(sids), DongPhieuVatTu.gia_von.is_not(None), DongPhieuVatTu.trang_thai != "huy")
        .group_by(DongPhieuVatTu.ncc_id)
    )).all()) if sids else {}
    items = []
    for b in moi_nhat.values():
        s = ncc.get(b.supplier_id or "")
        ck = float(s.chiet_khau_pct or 0) if s else 0.0
        sau_ck = round(b.gia * (1 - ck / 100))
        items.append({
            "supplier_id": b.supplier_id, "ncc_ten": s.name if s else b.ncc_ten, "hang": s.hang if s else None,
            "gia": b.gia, "chiet_khau_pct": ck,
            "gia_sau_ck": sau_ck, "da_mua": round(float(da_mua.get(b.supplier_id, 0) or 0)),
            "con_hang": b.con_hang, "bao_gia_luc": b.created_at,
        })
    thu_tu_hang = {k: i for i, k in enumerate(HANG_NCC)}  # chinh, du_phong, thu; None/khác xếp cuối
    items.sort(key=lambda x: (thu_tu_hang.get(x["hang"], len(thu_tu_hang)), not x["con_hang"], x["gia_sau_ck"], -x["da_mua"]))
    return {"items": items, "goi_y": items[0] if items else None}
