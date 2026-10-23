"""Chế độ thưởng (23/10/2026) — cấu hình + tính bảng thưởng theo kỳ.

Một trang Cài đặt › Nhân sự › Chế độ thưởng gom 5 chương trình, mỗi cái bật/tắt
và chọn chu kỳ Tháng/Quý:

  1. Hũ doanh số — giá trị dự án thắng deal cả công ty chạm mốc thì mở quỹ, chia cho
     người nhận theo phạm vi (công ty / phòng / nhóm) và cách chia.
  2. Chuyên cần — 100 điểm, trừ đi trễ / quên tan ca / nghỉ không phép; đủ
     công không trễ thì thưởng.
  3. Tốc độ phản hồi khách — lead mới gọi trong N giờ, tin Zalo khách trả lời
     trong N phút giờ hành chính.
  4. Khách hàng đánh giá — khách chấm sao trên trang tiến độ ở từng mốc.
  5. Ngôi sao quý — top Điểm JAMA trong quý.

Điểm JAMA = trung bình có trọng số các thành phần theo phòng ban; nó NHÂN phần
thưởng hũ (≥90 ×1,2 … <50 không nhận). Thành phần thiếu dữ liệu (chưa chấm công,
chưa có Zalo, chưa ai đánh giá) thì bỏ ra và chia lại trọng số — không phạt
người chỉ vì hệ thống chưa thu được số.

Cấu hình nằm ở system_settings (không schema), có PHIÊN BẢN theo tháng hiệu
lực: sửa giữa kỳ chỉ áp từ kỳ sau, lịch sử giữ nguyên để kỳ cũ tính lại vẫn ra
đúng số đã chốt. Chốt kỳ sinh Bonus «chờ duyệt» + MỘT đơn duyệt cho cả bảng.
"""

from __future__ import annotations

import copy
import logging
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import AttendanceRecord
from app.models.danh_gia_khach import DanhGiaKhach
from app.models.employee_profile import EmployeeProfile
from app.models.lead import Activity, Lead
from app.models.leave import LeaveRequest
from app.models.payroll import Bonus
from app.models.project import Project
from app.models.user import Team, User
from app.models.zalo import ZaloGroup, ZaloMessage
from app.services.attendance_service import (
    VN_TZ,
    get_setting_json,
    is_period_locked,
    period_bounds,
    set_setting_json,
    vn_now,
    vn_today,
)

logger = logging.getLogger(__name__)

KEY_CAU_HINH = "che_do_thuong"
KEY_LOAI_TRU = "che_do_thuong_loai_tru:{ky}"      # {"user_ids": [...], "ly_do": {...}}
KEY_DA_CHOT = "che_do_thuong_da_chot:{ky}"        # {"luc", "approval_id", "tong", ...}
KEY_MOC_DA_BAO = "che_do_thuong_moc_da_bao:{ky}"  # {"so_moc": n}
KEY_ZALO = "che_do_thuong_zalo:{ky}"              # {"ngay": [...], "nguoi": {uid: [tong, dat]}}

# Hoạt động do hệ thống ghi — không phải lần liên hệ khách thật
LOAI_HD_HE_THONG = {"assignment", "lead_assigned", "stage_change", "contract_signed", "system", "ai"}
LOAI_HD_GIAO = {"assignment", "lead_assigned"}

CHUONG_TRINH = ("hu_doanh_so", "chuyen_can", "phan_hoi", "danh_gia", "ngoi_sao")
TEN_CHUONG_TRINH = {
    "hu_doanh_so": "Hũ doanh số",
    "chuyen_can": "Chuyên cần",
    "phan_hoi": "Phản hồi khách",
    "danh_gia": "Khách đánh giá",
    "ngoi_sao": "Ngôi sao quý",
}
THANH_PHAN_DIEM = ("doanh_so", "chuyen_can", "phan_hoi", "danh_gia")

CAU_HINH_MAC_DINH: dict = {
    "quy_tran_thang": 150_000_000,
    "tu_dong_chot": True,
    "chuong_trinh": {
        "hu_doanh_so": {
            "bat": True,
            "chu_ky": "thang",
            "moc": [
                {"doanh_so": 8_000_000_000, "quy": 20_000_000, "nhan": "Khởi động"},
                {"doanh_so": 12_000_000_000, "quy": 50_000_000, "nhan": "Tăng tốc"},
                {"doanh_so": 14_400_000_000, "quy": 100_000_000, "nhan": "Về đích"},
                {"doanh_so": 18_000_000_000, "quy": 200_000_000, "nhan": "Phá kỷ lục"},
            ],
            "cong_don": True,
            "pham_vi": "cong_ty",          # cong_ty | theo_phong | theo_nhom
            "cach_chia": "theo_doanh_so",  # chia_deu | theo_doanh_so | hon_hop
            "phong_nhan": ["SALES"],
            "bao_telegram": True,
            "ai_thay_hu": "kinh_doanh",    # kinh_doanh | tat_ca | quan_ly
        },
        "chuyen_can": {
            "bat": True,
            "chu_ky": "thang",
            "gio_vao_ca": "08:00",
            "tre_phut": 5,
            "tru_tre": 3,
            "tru_quen_ra": 2,
            "tru_nghi_khong_phep": 15,
            "thuong_du_cong": 500_000,
        },
        "phan_hoi": {
            "bat": True,
            "chu_ky": "thang",
            "phong": ["SALES"],
            "gio_goi": 2,
            "muc_tieu_goi": 90,
            "phut_zalo": 15,
            "muc_tieu_zalo": 85,
            "tru_qua_24h": 2,
            "thuong": 1_000_000,
        },
        "danh_gia": {
            "bat": True,
            "chu_ky": "quy",
            "thoi_diem": ["ky_hd_tk", "chot_ban_ve", "ban_giao", "sau_3_thang"],
            "nguong_sao": 4.5,
            "thuong_du_an": 3_000_000,
            "thuong_khen": 300_000,
        },
        "ngoi_sao": {
            "bat": False,
            "chu_ky": "quy",
            "giai": [5_000_000, 3_000_000, 2_000_000],
        },
    },
    "diem_jama": {
        "trong_so": {
            "SALES": {"doanh_so": 40, "chuyen_can": 20, "phan_hoi": 25, "danh_gia": 15},
            "DESIGN": {"chuyen_can": 40, "danh_gia": 60},
            "OPS": {"chuyen_can": 50, "danh_gia": 50},
            "PM": {"chuyen_can": 50, "danh_gia": 50},
            "_khac": {"chuyen_can": 100},
        },
        "he_so": [
            {"tu": 90, "he_so": 1.2},
            {"tu": 70, "he_so": 1.0},
            {"tu": 50, "he_so": 0.5},
            {"tu": 0, "he_so": 0.0},
        ],
    },
    "dieu_kien": {
        "con_lam_viec": True,
        "thu_viec_pct": 50,
        "ky_luat_khong_nhan": True,
        "nv_xem_diem": True,
    },
}


# ── Kỳ ──────────────────────────────────────────────────────────────────────

def ky_hien_tai() -> str:
    return vn_today().strftime("%Y-%m")


def ky_truoc(ky: str) -> str:
    y, m = int(ky[:4]), int(ky[5:7])
    return f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"


def ky_sau(ky: str) -> str:
    y, m = int(ky[:4]), int(ky[5:7])
    return f"{y + 1}-01" if m == 12 else f"{y}-{m + 1:02d}"


def kiem_tra_ky(ky: str) -> str:
    try:
        y, m = int(ky[:4]), int(ky[5:7])
        if len(ky) != 7 or ky[4] != "-" or not 1 <= m <= 12 or y < 2000:
            raise ValueError
    except (ValueError, TypeError, IndexError):
        raise ValueError("Kỳ phải có dạng YYYY-MM")
    return ky


def quy_cua(ky: str) -> tuple[str, date, date]:
    """'2026-11' → ('Q4/2026', 2026-10-01, 2027-01-01)."""
    y, m = int(ky[:4]), int(ky[5:7])
    q = (m - 1) // 3 + 1
    dau = date(y, 3 * q - 2, 1)
    het = date(y + 1, 1, 1) if q == 4 else date(y, 3 * q + 1, 1)
    return f"Q{q}/{y}", dau, het


def la_cuoi_quy(ky: str) -> bool:
    return int(ky[5:7]) % 3 == 0


def _utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _moc_utc(d: date) -> datetime:
    """Nửa đêm ngày d giờ VN → UTC aware."""
    return datetime.combine(d, time()).replace(tzinfo=VN_TZ).astimezone(timezone.utc)


def _naive(dt: datetime) -> datetime:
    """So sánh với cột DateTime không múi giờ (lưu naive UTC)."""
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _ngay_vn(dt: datetime | None) -> date | None:
    dt = _utc(dt)
    return dt.astimezone(VN_TZ).date() if dt else None


# ── Cấu hình có phiên bản ───────────────────────────────────────────────────

def _tron(goc: dict, moi: dict) -> dict:
    """Trộn sâu: khóa thiếu lấy mặc định; list thay nguyên cục."""
    kq = copy.deepcopy(goc)
    for k, v in (moi or {}).items():
        if isinstance(v, dict) and isinstance(kq.get(k), dict):
            kq[k] = _tron(kq[k], v)
        else:
            kq[k] = copy.deepcopy(v)
    return kq


def _so(v, mac_dinh: float = 0, nho_nhat: float = 0, lon_nhat: float | None = None) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return mac_dinh
    if x != x:  # NaN
        return mac_dinh
    x = max(nho_nhat, x)
    return min(lon_nhat, x) if lon_nhat is not None else x


def chuan_hoa_cau_hinh(cfg: dict) -> dict:
    """Ép kiểu + chặn số vô lý. Dữ liệu từ form admin, không tin tuyệt đối."""
    c = _tron(CAU_HINH_MAC_DINH, cfg or {})
    c["quy_tran_thang"] = _so(c.get("quy_tran_thang"), 0)
    c["tu_dong_chot"] = bool(c.get("tu_dong_chot"))
    ct = c["chuong_trinh"]
    for ma in CHUONG_TRINH:
        ct[ma]["bat"] = bool(ct[ma].get("bat"))
        if ct[ma].get("chu_ky") not in ("thang", "quy"):
            ct[ma]["chu_ky"] = CAU_HINH_MAC_DINH["chuong_trinh"][ma]["chu_ky"]

    hu = ct["hu_doanh_so"]
    moc = []
    for m in hu.get("moc") or []:
        if not isinstance(m, dict):
            continue
        ds, quy = _so(m.get("doanh_so")), _so(m.get("quy"))
        if ds > 0:
            moc.append({"doanh_so": ds, "quy": quy, "nhan": str(m.get("nhan") or "")[:40]})
    hu["moc"] = sorted(moc, key=lambda m: m["doanh_so"])[:8]
    hu["cong_don"] = bool(hu.get("cong_don"))
    if hu.get("pham_vi") not in ("cong_ty", "theo_phong", "theo_nhom"):
        hu["pham_vi"] = "cong_ty"
    if hu.get("cach_chia") not in ("chia_deu", "theo_doanh_so", "hon_hop"):
        hu["cach_chia"] = "theo_doanh_so"
    hu["phong_nhan"] = [str(p) for p in (hu.get("phong_nhan") or []) if p][:10] or ["SALES"]
    hu["bao_telegram"] = bool(hu.get("bao_telegram"))
    if hu.get("ai_thay_hu") not in ("kinh_doanh", "tat_ca", "quan_ly"):
        hu["ai_thay_hu"] = "kinh_doanh"

    cc = ct["chuyen_can"]
    try:
        hh, mm = str(cc.get("gio_vao_ca") or "08:00").split(":")[:2]
        cc["gio_vao_ca"] = f"{min(23, max(0, int(hh))):02d}:{min(59, max(0, int(mm))):02d}"
    except ValueError:
        cc["gio_vao_ca"] = "08:00"
    cc["tre_phut"] = int(_so(cc.get("tre_phut"), 5, 0, 120))
    for k in ("tru_tre", "tru_quen_ra", "tru_nghi_khong_phep"):
        cc[k] = _so(cc.get(k), 0, 0, 100)
    cc["thuong_du_cong"] = _so(cc.get("thuong_du_cong"))

    ph = ct["phan_hoi"]
    ph["phong"] = [str(p) for p in (ph.get("phong") or []) if p][:10] or ["SALES"]
    ph["gio_goi"] = _so(ph.get("gio_goi"), 2, 0.25, 72)
    ph["phut_zalo"] = _so(ph.get("phut_zalo"), 15, 1, 600)
    ph["muc_tieu_goi"] = _so(ph.get("muc_tieu_goi"), 90, 1, 100)
    ph["muc_tieu_zalo"] = _so(ph.get("muc_tieu_zalo"), 85, 1, 100)
    ph["tru_qua_24h"] = _so(ph.get("tru_qua_24h"), 0, 0, 100)
    ph["thuong"] = _so(ph.get("thuong"))

    dg = ct["danh_gia"]
    hop_le = set(CAU_HINH_MAC_DINH["chuong_trinh"]["danh_gia"]["thoi_diem"])
    dg["thoi_diem"] = [t for t in (dg.get("thoi_diem") or []) if t in hop_le]
    dg["nguong_sao"] = _so(dg.get("nguong_sao"), 4.5, 1, 5)
    dg["thuong_du_an"] = _so(dg.get("thuong_du_an"))
    dg["thuong_khen"] = _so(dg.get("thuong_khen"))

    ns = ct["ngoi_sao"]
    ns["giai"] = [_so(g) for g in (ns.get("giai") or [])][:5]

    dj = c["diem_jama"]
    ts = {}
    for phong, tp in (dj.get("trong_so") or {}).items():
        if isinstance(tp, dict):
            ts[str(phong)] = {k: _so(v, 0, 0, 100) for k, v in tp.items() if k in THANH_PHAN_DIEM}
    ts.setdefault("_khac", {"chuyen_can": 100})
    dj["trong_so"] = ts
    he = [{"tu": _so(h.get("tu"), 0, 0, 100), "he_so": _so(h.get("he_so"), 0, 0, 5)}
          for h in (dj.get("he_so") or []) if isinstance(h, dict)]
    dj["he_so"] = sorted(he, key=lambda h: -h["tu"]) or CAU_HINH_MAC_DINH["diem_jama"]["he_so"]

    dk = c["dieu_kien"]
    dk["con_lam_viec"] = bool(dk.get("con_lam_viec"))
    dk["thu_viec_pct"] = _so(dk.get("thu_viec_pct"), 50, 0, 100)
    dk["ky_luat_khong_nhan"] = bool(dk.get("ky_luat_khong_nhan"))
    dk["nv_xem_diem"] = bool(dk.get("nv_xem_diem"))
    return c


async def doc_kho(db: AsyncSession) -> dict:
    kho = await get_setting_json(db, KEY_CAU_HINH)
    if not isinstance(kho.get("phien_ban"), dict):
        kho["phien_ban"] = {}
    if not isinstance(kho.get("lich_su"), list):
        kho["lich_su"] = []
    return kho


async def doc_cau_hinh(db: AsyncSession, ky: str | None = None) -> tuple[dict, str | None]:
    """Cấu hình có hiệu lực cho kỳ `ky` = phiên bản mới nhất có tháng hiệu lực ≤ ky.

    Chưa lưu lần nào → mặc định (số mẫu đã duyệt), hiệu lực None.
    """
    ky = ky or ky_hien_tai()
    kho = await doc_kho(db)
    hop = sorted(k for k in kho["phien_ban"] if k <= ky)
    if not hop:
        # Kỳ trước lần lưu đầu: dùng phiên bản sớm nhất nếu có, không thì mặc định
        som = sorted(kho["phien_ban"])
        if som:
            return chuan_hoa_cau_hinh(kho["phien_ban"][som[0]]), som[0]
        return chuan_hoa_cau_hinh({}), None
    hl = hop[-1]
    return chuan_hoa_cau_hinh(kho["phien_ban"][hl]), hl


async def luu_cau_hinh(db: AsyncSession, cfg: dict, actor: User) -> tuple[dict, str]:
    """Lưu phiên bản mới. Lần đầu áp ngay kỳ này; các lần sau áp từ kỳ sau
    (luật chơi không đổi giữa chừng — nhân viên đang chạy theo số cũ)."""
    kho = await doc_kho(db)
    hien_tai = ky_hien_tai()
    da_chot = await get_setting_json(db, KEY_DA_CHOT.format(ky=hien_tai))
    hieu_luc = hien_tai if (not kho["phien_ban"] and not da_chot) else ky_sau(hien_tai)
    sach = chuan_hoa_cau_hinh(cfg)
    kho["phien_ban"][hieu_luc] = sach
    kho["lich_su"] = (kho["lich_su"] + [{
        "luc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "boi": actor.full_name,
        "boi_id": actor.id,
        "hieu_luc_tu": hieu_luc,
    }])[-50:]
    await set_setting_json(db, KEY_CAU_HINH, kho)
    return sach, hieu_luc


# ── Nguồn số liệu ───────────────────────────────────────────────────────────

async def doanh_so_theo_nguoi(db: AsyncSession, tu: date, den: date) -> tuple[float, dict[str | None, float]]:
    """Doanh số = giá trị dự án sinh ra khi THẮNG deal (lead → dự án) trong [tu, den).

    Chốt 23/10/2026: HĐ trên prod đều còn «nháp» nên không lấy HĐ đã ký. Ngày thắng =
    ngày tạo dự án (giờ VN) vì lead không lưu mốc thắng riêng. Bỏ dự án đã hủy và dự án
    tạo tay (không gắn lead). Giá trị = total_value, thiếu thì thiết kế + thi công.
    Trả (tổng công ty, {sales_id: doanh số}). Dự án không gắn sale vẫn vào tổng hũ.
    """
    tu_utc = datetime.combine(tu - timedelta(days=1), datetime.min.time())
    rows = (await db.execute(
        select(Project.total_value, Project.design_value, Project.construction_value,
               Project.created_at, Project.sales_id)
        .where(
            Project.lead_id.is_not(None),
            Project.status != "cancelled",
            Project.created_at >= tu_utc,
        )
    )).all()
    tong = 0.0
    theo: dict[str | None, float] = defaultdict(float)
    for tong_gt, tk, tc, tao_luc, sales_id in rows:
        ngay = _ngay_vn(tao_luc)
        if ngay is None or not (tu <= ngay < den):
            continue
        v = float(tong_gt or 0) or float(tk or 0) + float(tc or 0)
        tong += v
        theo[sales_id] += v
    return tong, dict(theo)


async def nguoi_xet_thuong(db: AsyncSession) -> list[User]:
    """Nhân viên đang làm, trừ Ban giám đốc / admin (không tự thưởng mình)."""
    rows = await db.execute(
        select(User).where(
            User.is_active == True,  # noqa: E712
            User.role.notin_(("admin", "executive")),
            or_(User.department.is_(None), User.department != "EXEC"),
        ).order_by(User.full_name)
    )
    return list(rows.scalars().all())


# ── 1. Hũ doanh số ──────────────────────────────────────────────────────────

def tinh_hu(cfg_hu: dict, tong: float, ds: dict[str | None, float], users: list[User]) -> dict:
    """Tính quỹ mở + phần chia trước hệ số. Hàm thuần — test trực tiếp."""
    moc = cfg_hu.get("moc") or []
    da_dat = [m for m in moc if tong >= m["doanh_so"]]
    if not da_dat:
        quy = 0.0
    elif cfg_hu.get("cong_don"):
        quy = sum(m["quy"] for m in da_dat)
    else:
        quy = max(m["quy"] for m in da_dat)
    tiep = next((m for m in moc if tong < m["doanh_so"]), None)

    phong_nhan = set(cfg_hu.get("phong_nhan") or ["SALES"])
    nhan = [u for u in users if (u.department or "") in phong_nhan]
    nhom: dict[str, list[User]] = defaultdict(list)
    for u in nhan:
        if cfg_hu.get("pham_vi") == "theo_phong":
            nhom[u.department or "_"].append(u)
        elif cfg_hu.get("pham_vi") == "theo_nhom":
            nhom[u.team_id or "_khong_nhom"].append(u)
        else:
            nhom["cong_ty"].append(u)

    chia: dict[str, float] = {}
    if quy > 0 and nhom:
        ds_nhom = {k: sum(ds.get(u.id, 0.0) for u in v) for k, v in nhom.items()}
        tong_nhom = sum(ds_nhom.values())
        for k, thanh_vien in nhom.items():
            if len(nhom) == 1:
                phan_nhom = quy
            elif tong_nhom > 0:
                phan_nhom = quy * ds_nhom[k] / tong_nhom
            else:
                phan_nhom = quy / len(nhom)
            if phan_nhom <= 0:
                continue
            ds_tv = {u.id: ds.get(u.id, 0.0) for u in thanh_vien}
            tong_tv = sum(ds_tv.values())
            co_ds = [uid for uid, v in ds_tv.items() if v > 0]
            cach = cfg_hu.get("cach_chia")
            for u in thanh_vien:
                deu = phan_nhom / len(thanh_vien)
                theo_ds = phan_nhom * ds_tv[u.id] / tong_tv if tong_tv > 0 else deu
                if cach == "chia_deu":
                    v = deu
                elif cach == "hon_hop":
                    # Nửa chia đều (ghi nhận cả đội), nửa theo doanh số — chỉ người có số
                    v = deu / 2 + (theo_ds / 2 if tong_tv > 0 else deu / 2)
                else:
                    v = theo_ds if tong_tv > 0 else (phan_nhom / len(co_ds) if co_ds and u.id in co_ds else 0.0)
                if v > 0:
                    chia[u.id] = chia.get(u.id, 0.0) + v

    return {
        "doanh_so": tong,
        "moc": [{**m, "dat": tong >= m["doanh_so"]} for m in moc],
        "so_moc_dat": len(da_dat),
        "quy_mo": quy,
        "moc_tiep": tiep,
        "con_thieu": (tiep["doanh_so"] - tong) if tiep else 0.0,
        "chia": chia,
    }


# ── 2. Chuyên cần ───────────────────────────────────────────────────────────

def _ngay_lam_viec(tu: date, den: date):
    d = tu
    while d < den:
        if d.weekday() != 6:  # Chủ nhật nghỉ
            yield d
        d += timedelta(days=1)


async def tinh_chuyen_can(db: AsyncSession, users: list[User], tu: date, den: date, cfg: dict) -> dict[str, dict]:
    uids = [u.id for u in users]
    if not uids:
        return {}
    het = min(den, vn_today())  # hôm nay chưa hết ngày → chưa tính vắng
    recs = (await db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.user_id.in_(uids),
            AttendanceRecord.work_date >= tu,
            AttendanceRecord.work_date < den,
        )
    )).scalars().all()
    # Ngày chấm công đầu tiên của từng người: trước đó hệ thống chưa dùng → không coi là vắng
    dau_tien = dict((await db.execute(
        select(AttendanceRecord.user_id, func.min(AttendanceRecord.work_date))
        .where(AttendanceRecord.user_id.in_(uids))
        .group_by(AttendanceRecord.user_id)
    )).all())
    nghi = (await db.execute(
        select(LeaveRequest).where(
            LeaveRequest.user_id.in_(uids),
            LeaveRequest.status == "approved",
            LeaveRequest.start_date < den,
            LeaveRequest.end_date >= tu,
        )
    )).scalars().all()
    ngay_phep: dict[str, set[date]] = defaultdict(set)
    for lv in nghi:
        d = lv.start_date
        while d <= lv.end_date:
            ngay_phep[lv.user_id].add(d)
            d += timedelta(days=1)

    hh, mm = (int(x) for x in cfg["gio_vao_ca"].split(":"))
    nguong = (datetime.combine(date.min, time(hh, mm)) + timedelta(minutes=cfg["tre_phut"])).time()
    theo_nguoi: dict[str, list[AttendanceRecord]] = defaultdict(list)
    for r in recs:
        theo_nguoi[r.user_id].append(r)

    kq: dict[str, dict] = {}
    for u in users:
        ds = theo_nguoi.get(u.id, [])
        if not ds or u.id not in dau_tien:
            kq[u.id] = {"co_du_lieu": False, "diem": None, "tre": 0, "quen_ra": 0, "nghi_kp": 0, "du_cong": False}
            continue
        tre = quen = 0
        co_mat: set[date] = set()
        for r in ds:
            co_mat.add(r.work_date)
            if r.check_in and r.project_id is None and (r.source or "") != "leave" and r.work_date.weekday() != 6:
                if _utc(r.check_in).astimezone(VN_TZ).time() > nguong:
                    tre += 1
            if r.needs_review and "auto-close" in (r.note or ""):
                quen += 1
        bat_dau = max(tu, dau_tien[u.id])
        vang = sum(
            1 for d in _ngay_lam_viec(bat_dau, het)
            if d not in co_mat and d not in ngay_phep.get(u.id, set())
        )
        diem = max(0.0, 100 - tre * cfg["tru_tre"] - quen * cfg["tru_quen_ra"] - vang * cfg["tru_nghi_khong_phep"])
        kq[u.id] = {
            "co_du_lieu": True, "diem": round(diem, 1), "tre": tre, "quen_ra": quen,
            "nghi_kp": vang, "du_cong": tre == 0 and vang == 0,
        }
    return kq


# ── 3. Phản hồi khách ───────────────────────────────────────────────────────

def _gio_hanh_chinh(dt: datetime) -> bool:
    v = _utc(dt).astimezone(VN_TZ)
    return v.weekday() != 6 and time(8, 0) <= v.time() <= time(17, 30)


def _dem_cho_zalo(msgs: list[ZaloMessage], tu: datetime, den: datetime, phut: float, bay_gio: datetime) -> tuple[int, int]:
    """Đếm lượt khách chờ BẮT ĐẦU trong [tu, den) giờ hành chính → (tổng, đạt).

    Chuỗi tin khách liên tiếp tính 1 lượt, đồng hồ chạy từ tin đầu tiên.
    """
    tong = dat = 0
    cho: datetime | None = None
    for m in msgs:
        t = _utc(m.created_at)
        if not m.is_staff:
            if cho is None and tu <= t < den and _gio_hanh_chinh(t):
                cho = t
        elif cho is not None:
            tong += 1
            dat += (t - cho) <= timedelta(minutes=phut)
            cho = None
    if cho is not None and bay_gio - cho > timedelta(minutes=phut):
        tong += 1  # quá hạn mà chưa ai trả lời
    return tong, dat


async def _zalo_truc_tiep(db: AsyncSession, uids: list[str], tu: datetime, den: datetime, phut: float) -> dict[str, list[int]]:
    nhom = (await db.execute(
        select(ZaloGroup.id, ZaloGroup.assigned_user_id).where(
            ZaloGroup.kind == "customer", ZaloGroup.assigned_user_id.in_(uids),
        )
    )).all()
    if not nhom:
        return {}
    chu = dict(nhom)
    msgs = (await db.execute(
        select(ZaloMessage).where(
            ZaloMessage.group_id.in_(list(chu)),
            ZaloMessage.created_at >= _naive(tu),
            ZaloMessage.created_at < _naive(den + timedelta(days=1)),
        ).order_by(ZaloMessage.created_at)
    )).scalars().all()
    theo_nhom: dict[str, list[ZaloMessage]] = defaultdict(list)
    for m in msgs:
        theo_nhom[m.group_id].append(m)
    bay_gio = datetime.now(timezone.utc)
    kq: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for gid, ds in theo_nhom.items():
        t, d = _dem_cho_zalo(ds, tu, den, phut, bay_gio)
        kq[chu[gid]][0] += t
        kq[chu[gid]][1] += d
    return dict(kq)


async def ghi_so_lieu_zalo(db: AsyncSession, ngay: date) -> None:
    """Chụp số liệu phản hồi Zalo của MỘT ngày vào system_settings.

    Tin Zalo thô bị xóa sau 7 ngày, nên cuối tháng không còn tin để tính —
    job tóm tắt Zalo hằng ngày gọi hàm này cho hôm qua trước khi xóa.
    """
    ky = ngay.strftime("%Y-%m")
    key = KEY_ZALO.format(ky=ky)
    luu = await get_setting_json(db, key)
    ngay_da = set(luu.get("ngay") or [])
    if ngay.isoformat() in ngay_da:
        return
    cfg, _ = await doc_cau_hinh(db, ky)
    ph = cfg["chuong_trinh"]["phan_hoi"]
    uids = [u.id for u in await nguoi_xet_thuong(db)]
    so = await _zalo_truc_tiep(db, uids, _moc_utc(ngay), _moc_utc(ngay + timedelta(days=1)), ph["phut_zalo"])
    nguoi = luu.get("nguoi") or {}
    for uid, (t, d) in so.items():
        cu = nguoi.get(uid) or [0, 0]
        nguoi[uid] = [cu[0] + t, cu[1] + d]
    ngay_da.add(ngay.isoformat())
    await set_setting_json(db, key, {"ngay": sorted(ngay_da), "nguoi": nguoi})


async def chup_zalo_bu(db: AsyncSession) -> int:
    """Chụp mọi ngày (6 ngày gần nhất → hôm qua) chưa chụp. Idempotent."""
    so = 0
    hom_nay = vn_today()
    for i in range(6, 0, -1):
        d = hom_nay - timedelta(days=i)
        luu = await get_setting_json(db, KEY_ZALO.format(ky=d.strftime("%Y-%m")))
        if d.isoformat() not in set(luu.get("ngay") or []):
            await ghi_so_lieu_zalo(db, d)
            so += 1
    return so


async def _zalo_trong_ky(db: AsyncSession, uids: list[str], tu: date, den: date, phut: float) -> dict[str, list[int]]:
    """Số đã chụp + tính trực tiếp những ngày chưa chụp (tin còn trong 7 ngày)."""
    kq: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    da_chup: set[str] = set()
    ky = tu.strftime("%Y-%m")
    while ky < den.strftime("%Y-%m") or ky == tu.strftime("%Y-%m"):
        luu = await get_setting_json(db, KEY_ZALO.format(ky=ky))
        da_chup |= set(luu.get("ngay") or [])
        for uid, (t, d) in (luu.get("nguoi") or {}).items():
            if uid in uids:
                kq[uid][0] += t
                kq[uid][1] += d
        ky = ky_sau(ky)
    het = min(den, vn_today() + timedelta(days=1))
    d = max(tu, vn_today() - timedelta(days=6))
    while d < het:
        if d.isoformat() not in da_chup:
            so = await _zalo_truc_tiep(db, uids, _moc_utc(d), _moc_utc(d + timedelta(days=1)), phut)
            for uid, (t, dd) in so.items():
                kq[uid][0] += t
                kq[uid][1] += dd
        d += timedelta(days=1)
    return dict(kq)


async def tinh_phan_hoi(db: AsyncSession, users: list[User], tu: date, den: date, cfg: dict) -> dict[str, dict]:
    ap_dung = [u for u in users if (u.department or "") in set(cfg["phong"])]
    uids = [u.id for u in ap_dung]
    if not uids:
        return {}
    tu_utc, den_utc = _moc_utc(tu), _moc_utc(den)
    bay_gio = datetime.now(timezone.utc)
    leads = (await db.execute(
        select(Lead.id, Lead.assigned_to, Lead.created_at).where(
            Lead.assigned_to.in_(uids),
            Lead.created_at >= _naive(tu_utc - timedelta(days=60)),
            Lead.created_at < _naive(den_utc),
        )
    )).all()
    hd_theo_lead: dict[str, list] = defaultdict(list)
    if leads:
        for lid, loai, luc in (await db.execute(
            select(Activity.lead_id, Activity.type, Activity.created_at)
            .where(Activity.lead_id.in_([r[0] for r in leads]))
            .order_by(Activity.created_at)
        )).all():
            hd_theo_lead[lid].append((loai or "", _utc(luc)))

    goi: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])  # tổng, đạt, quá 24h
    gioi_han = timedelta(hours=cfg["gio_goi"])
    for lid, nguoi, tao in leads:
        hd = hd_theo_lead.get(lid, [])
        giao = [t for loai, t in hd if loai in LOAI_HD_GIAO]
        bat_dau = giao[-1] if giao else _utc(tao)
        if not (tu_utc <= bat_dau < den_utc):
            continue
        lien_he = next((t for loai, t in hd if loai not in LOAI_HD_HE_THONG and t >= bat_dau), None)
        if lien_he is None and bay_gio - bat_dau < gioi_han:
            continue  # còn trong hạn, chưa xét
        g = goi[nguoi]
        g[0] += 1
        if lien_he is not None and lien_he - bat_dau <= gioi_han:
            g[1] += 1
        if (lien_he or bay_gio) - bat_dau > timedelta(hours=24):
            g[2] += 1

    zalo = await _zalo_trong_ky(db, uids, tu, den, cfg["phut_zalo"])

    kq: dict[str, dict] = {}
    for u in ap_dung:
        tong, dat, qua = goi.get(u.id, [0, 0, 0])
        zt, zd = zalo.get(u.id, [0, 0])
        ty_le_goi = round(dat * 100 / tong, 1) if tong else None
        ty_le_zalo = round(zd * 100 / zt, 1) if zt else None
        phan = []
        if ty_le_goi is not None:
            phan.append(min(1.0, ty_le_goi / cfg["muc_tieu_goi"]))
        if ty_le_zalo is not None:
            phan.append(min(1.0, ty_le_zalo / cfg["muc_tieu_zalo"]))
        diem = None
        if phan:
            diem = round(max(0.0, 100 * sum(phan) / len(phan) - qua * cfg["tru_qua_24h"]), 1)
        dat_muc_tieu = bool(phan) and (ty_le_goi is None or ty_le_goi >= cfg["muc_tieu_goi"]) \
            and (ty_le_zalo is None or ty_le_zalo >= cfg["muc_tieu_zalo"])
        kq[u.id] = {
            "co_du_lieu": bool(phan), "diem": diem,
            "lead": tong, "lead_dat": dat, "ty_le_goi": ty_le_goi, "qua_24h": qua,
            "zalo": zt, "zalo_dat": zd, "ty_le_zalo": ty_le_zalo,
            "dat_muc_tieu": dat_muc_tieu,
        }
    return kq


# ── 4. Khách đánh giá ───────────────────────────────────────────────────────

def doi_du_an(p: Project) -> list[str]:
    ds = []
    for uid in (p.sales_id, p.designer_id, p.pm_id, p.purchasing_id):
        if uid and uid not in ds:
            ds.append(uid)
    return ds


async def tinh_danh_gia(db: AsyncSession, tu: date, den: date, cfg: dict) -> tuple[dict[str, dict], list[dict]]:
    rows = (await db.execute(
        select(DanhGiaKhach).where(
            DanhGiaKhach.created_at >= _naive(_moc_utc(tu)),
            DanhGiaKhach.created_at < _naive(_moc_utc(den)),
        )
    )).scalars().all()
    if cfg.get("thoi_diem"):
        rows = [r for r in rows if r.moc in cfg["thoi_diem"]]
    theo_da: dict[str, list[DanhGiaKhach]] = defaultdict(list)
    for r in rows:
        theo_da[r.project_id].append(r)
    du_an = {}
    if theo_da:
        du_an = {p.id: p for p in (await db.execute(
            select(Project).where(Project.id.in_(list(theo_da)))
        )).scalars().all()}

    nguoi: dict[str, dict] = defaultdict(lambda: {"sao": [], "thuong_du_an": 0.0, "khen": 0, "thuong_khen": 0.0, "giu_lai": []})
    tom_tat = []
    for pid, ds in theo_da.items():
        p = du_an.get(pid)
        if not p:
            continue
        tb = sum(r.so_sao for r in ds) / len(ds)
        khieu_nai = any(r.so_sao <= 2 for r in ds)
        doi = doi_du_an(p)
        dat = not khieu_nai and tb >= cfg["nguong_sao"]
        for uid in doi:
            nguoi[uid]["sao"].append(tb)
            if khieu_nai:
                nguoi[uid]["giu_lai"].append(p.code)
            elif dat:
                nguoi[uid]["thuong_du_an"] += cfg["thuong_du_an"] / len(doi)
        for r in ds:
            if r.khen_user_id and r.so_sao >= 4:
                nguoi[r.khen_user_id]["khen"] += 1
                nguoi[r.khen_user_id]["thuong_khen"] += cfg["thuong_khen"]
        tom_tat.append({"project_id": pid, "code": p.code, "name": p.name, "sao_tb": round(tb, 2),
                        "so_luot": len(ds), "khieu_nai": khieu_nai, "dat": dat})

    kq = {}
    for uid, v in nguoi.items():
        sao_tb = round(sum(v["sao"]) / len(v["sao"]), 2) if v["sao"] else None
        kq[uid] = {**v, "sao": None, "sao_tb": sao_tb,
                   "co_du_lieu": sao_tb is not None, "diem": round(sao_tb * 20, 1) if sao_tb else None}
    return kq, tom_tat


# ── Điểm JAMA ───────────────────────────────────────────────────────────────

def diem_jama(phong: str | None, thanh_phan: dict[str, float | None], cfg_dj: dict) -> float | None:
    ts = cfg_dj["trong_so"].get(phong or "") or cfg_dj["trong_so"].get("_khac") or {}
    co = {k: w for k, w in ts.items() if w > 0 and thanh_phan.get(k) is not None}
    tong_w = sum(co.values())
    if tong_w <= 0:
        return None
    return round(sum(thanh_phan[k] * w for k, w in co.items()) / tong_w, 1)


def he_so_tu_diem(diem: float | None, cfg_dj: dict) -> float:
    if diem is None:
        return 1.0  # chưa đủ số để chấm → không phạt
    for h in cfg_dj["he_so"]:
        if diem >= h["tu"]:
            return h["he_so"]
    return 0.0


# ── Bảng thưởng ─────────────────────────────────────────────────────────────

def _lam_tron(v: float) -> float:
    return float(round(v / 1000) * 1000)  # tròn nghìn đồng


async def tinh_bang_thuong(db: AsyncSession, ky: str) -> dict:
    """Bảng thưởng dự kiến của kỳ tháng `ky` (YYYY-MM).

    Chương trình chu kỳ «quý» tính trên cả quý nhưng chỉ CHI ở tháng cuối quý;
    tháng khác vẫn hiện tiến độ (dự kiến) để mọi người thấy đường đi.
    """
    kiem_tra_ky(ky)
    cfg, hieu_luc = await doc_cau_hinh(db, ky)
    ct = cfg["chuong_trinh"]
    tu, den = period_bounds(ky)
    ten_quy, tu_q, den_q = quy_cua(ky)
    cuoi_quy = la_cuoi_quy(ky)

    def khoang(ma: str) -> tuple[date, date, bool]:
        """(từ, đến, có chi trong kỳ này không)."""
        if ct[ma]["chu_ky"] == "quy":
            return tu_q, den_q, cuoi_quy
        return tu, den, True

    users = await nguoi_xet_thuong(db)
    theo_id = {u.id: u for u in users}
    teams = {t.id: t.name for t in (await db.execute(select(Team))).scalars().all()}
    thu_viec = set((await db.execute(
        select(EmployeeProfile.user_id).where(EmployeeProfile.contract_type == "probation")
    )).scalars().all())
    loai_tru = await get_setting_json(db, KEY_LOAI_TRU.format(ky=ky))
    ds_loai_tru = set(loai_tru.get("user_ids") or [])

    from app.api.sales_dashboard import doc_muc_tieu
    muc_tieu = await doc_muc_tieu(db)
    so_sale = max(1, sum(1 for u in users if (u.department or "") == "SALES"))

    # Hũ
    hu_tu, hu_den, hu_chi = khoang("hu_doanh_so")
    tong_hu, ds_hu = await doanh_so_theo_nguoi(db, hu_tu, hu_den)
    hu = tinh_hu(ct["hu_doanh_so"], tong_hu, ds_hu, users) if ct["hu_doanh_so"]["bat"] else None
    # Doanh số cá nhân trong tháng cho thành phần điểm
    if (hu_tu, hu_den) == (tu, den):
        ds_thang = ds_hu
    else:
        _, ds_thang = await doanh_so_theo_nguoi(db, tu, den)
    muc_tieu_nguoi = float(muc_tieu.get("doanh_thu_thang") or 0) / so_sale

    cc_tu, cc_den, cc_chi = khoang("chuyen_can")
    cc = await tinh_chuyen_can(db, users, cc_tu, cc_den, ct["chuyen_can"]) if ct["chuyen_can"]["bat"] else {}
    ph_tu, ph_den, ph_chi = khoang("phan_hoi")
    ph = await tinh_phan_hoi(db, users, ph_tu, ph_den, ct["phan_hoi"]) if ct["phan_hoi"]["bat"] else {}
    dg_tu, dg_den, dg_chi = khoang("danh_gia")
    dg, du_an_dg = (await tinh_danh_gia(db, dg_tu, dg_den, ct["danh_gia"])) if ct["danh_gia"]["bat"] else ({}, [])

    dj = cfg["diem_jama"]
    dk = cfg["dieu_kien"]
    nguoi = []
    for u in users:
        tp: dict[str, float | None] = {
            "doanh_so": (round(min(100.0, ds_thang.get(u.id, 0.0) / muc_tieu_nguoi * 100), 1)
                         if muc_tieu_nguoi > 0 and (u.department or "") == "SALES" else None),
            "chuyen_can": (cc.get(u.id) or {}).get("diem"),
            "phan_hoi": (ph.get(u.id) or {}).get("diem"),
            "danh_gia": (dg.get(u.id) or {}).get("diem"),
        }
        diem = diem_jama(u.department, tp, dj)
        he_so = he_so_tu_diem(diem, dj)
        khoan = []
        ghi_chu = []
        if hu and u.id in hu["chia"]:
            goc = hu["chia"][u.id]
            khoan.append({"ma": "hu_doanh_so", "nhan": f"Hũ doanh số (×{he_so:g})",
                          "so_tien": _lam_tron(goc * he_so), "goc": _lam_tron(goc), "chi_ky_nay": hu_chi})
        c = cc.get(u.id)
        if c and c["du_cong"] and ct["chuyen_can"]["thuong_du_cong"] > 0:
            khoan.append({"ma": "chuyen_can", "nhan": "Chuyên cần — đủ công không trễ",
                          "so_tien": _lam_tron(ct["chuyen_can"]["thuong_du_cong"]), "chi_ky_nay": cc_chi})
        p = ph.get(u.id)
        if p and p["dat_muc_tieu"] and ct["phan_hoi"]["thuong"] > 0:
            khoan.append({"ma": "phan_hoi", "nhan": "Phản hồi khách đạt mục tiêu",
                          "so_tien": _lam_tron(ct["phan_hoi"]["thuong"]), "chi_ky_nay": ph_chi})
        g = dg.get(u.id)
        if g:
            if g["thuong_du_an"] > 0:
                khoan.append({"ma": "danh_gia", "nhan": "Khách đánh giá dự án đạt chuẩn",
                              "so_tien": _lam_tron(g["thuong_du_an"]), "chi_ky_nay": dg_chi})
            if g["thuong_khen"] > 0:
                khoan.append({"ma": "danh_gia_khen", "nhan": f"Khách khen tên ({g['khen']} lần)",
                              "so_tien": _lam_tron(g["thuong_khen"]), "chi_ky_nay": dg_chi})
            if g["giu_lai"]:
                ghi_chu.append("Giữ thưởng dự án có khiếu nại: " + ", ".join(sorted(set(g["giu_lai"]))))

        ty_le = 1.0
        if dk["con_lam_viec"] and u.resign_date is not None:
            ty_le = 0.0
            ghi_chu.append("Đã có ngày nghỉ việc — không nhận")
        elif dk["ky_luat_khong_nhan"] and u.id in ds_loai_tru:
            ty_le = 0.0
            ghi_chu.append("Bị kỷ luật trong kỳ — không nhận")
        elif u.id in thu_viec and dk["thu_viec_pct"] < 100:
            ty_le = dk["thu_viec_pct"] / 100
            ghi_chu.append(f"Thử việc — nhận {dk['thu_viec_pct']:g}%")
        if ty_le != 1.0:
            for k in khoan:
                k["so_tien"] = _lam_tron(k["so_tien"] * ty_le)
        if diem is not None and he_so == 0 and u.id in (hu["chia"] if hu else {}):
            ghi_chu.append("Điểm JAMA dưới ngưỡng — không nhận phần hũ")

        nguoi.append({
            "user_id": u.id, "ten": u.full_name, "phong": u.department,
            "nhom": teams.get(u.team_id) if u.team_id else None,
            "doanh_so": ds_thang.get(u.id, 0.0),
            "diem": diem, "he_so": he_so, "thanh_phan": tp,
            "chi_tiet": {
                "chuyen_can": cc.get(u.id), "phan_hoi": ph.get(u.id),
                "danh_gia": ({k: v for k, v in g.items() if k != "sao"} if g else None),
            },
            "khoan": khoan,
            "tong": sum(k["so_tien"] for k in khoan if k["chi_ky_nay"]),
            "du_kien_cuoi_quy": sum(k["so_tien"] for k in khoan if not k["chi_ky_nay"]),
            "ghi_chu": ghi_chu,
        })

    # 5. Ngôi sao quý — top Điểm JAMA tính trên CẢ quý, chỉ ở tháng cuối quý
    ngoi_sao = []
    if ct["ngoi_sao"]["bat"] and ct["ngoi_sao"]["giai"]:
        ns_chi = cuoi_quy if ct["ngoi_sao"]["chu_ky"] == "quy" else True
        if ct["ngoi_sao"]["chu_ky"] == "quy":
            xep = await _diem_quy(db, users, tu_q, den_q, cfg, muc_tieu_nguoi * 3)
        else:
            xep = {r["user_id"]: r["diem"] for r in nguoi}
        hang = sorted(((d, uid) for uid, d in xep.items() if d is not None), reverse=True)
        theo_dong = {r["user_id"]: r for r in nguoi}
        for i, (d, uid) in enumerate(hang[: len(ct["ngoi_sao"]["giai"])]):
            giai = ct["ngoi_sao"]["giai"][i]
            dong = theo_dong[uid]
            ngoi_sao.append({"hang": i + 1, "user_id": uid, "ten": theo_id[uid].full_name, "diem": d, "giai": giai})
            if giai > 0 and not any("không nhận" in g for g in dong["ghi_chu"]):
                dong["khoan"].append({"ma": "ngoi_sao", "nhan": f"Ngôi sao {ten_quy} — hạng {i + 1}",
                                      "so_tien": _lam_tron(giai), "chi_ky_nay": ns_chi})
                if ns_chi:
                    dong["tong"] += _lam_tron(giai)
                else:
                    dong["du_kien_cuoi_quy"] += _lam_tron(giai)

    tong_chi = sum(r["tong"] for r in nguoi)
    so_bat = sum(1 for ma in CHUONG_TRINH if ct[ma]["bat"])
    da_chot = await get_setting_json(db, KEY_DA_CHOT.format(ky=ky))
    return {
        "ky": ky,
        "quy": ten_quy,
        "cuoi_quy": cuoi_quy,
        "hieu_luc_tu": hieu_luc,
        "chuong_trinh_bat": so_bat,
        "tong_chuong_trinh": len(CHUONG_TRINH),
        "tong_chi": tong_chi,
        "quy_tran": cfg["quy_tran_thang"],
        "vuot_tran": cfg["quy_tran_thang"] > 0 and tong_chi > cfg["quy_tran_thang"],
        "so_nguoi": len(nguoi),
        "so_nguoi_nhan": sum(1 for r in nguoi if r["tong"] > 0),
        "hu": ({k: v for k, v in hu.items() if k != "chia"} if hu else None),
        "du_an_danh_gia": du_an_dg,
        "ngoi_sao": ngoi_sao,
        "da_chot": da_chot or None,
        "nguoi": nguoi,
    }


async def _diem_quy(db: AsyncSession, users: list[User], tu: date, den: date, cfg: dict,
                    muc_tieu_quy: float) -> dict[str, float | None]:
    ct = cfg["chuong_trinh"]
    _, ds = await doanh_so_theo_nguoi(db, tu, den)
    cc = await tinh_chuyen_can(db, users, tu, den, ct["chuyen_can"]) if ct["chuyen_can"]["bat"] else {}
    ph = await tinh_phan_hoi(db, users, tu, den, ct["phan_hoi"]) if ct["phan_hoi"]["bat"] else {}
    dg, _ = (await tinh_danh_gia(db, tu, den, ct["danh_gia"])) if ct["danh_gia"]["bat"] else ({}, [])
    kq = {}
    for u in users:
        tp = {
            "doanh_so": (min(100.0, ds.get(u.id, 0.0) / muc_tieu_quy * 100)
                         if muc_tieu_quy > 0 and (u.department or "") == "SALES" else None),
            "chuyen_can": (cc.get(u.id) or {}).get("diem"),
            "phan_hoi": (ph.get(u.id) or {}).get("diem"),
            "danh_gia": (dg.get(u.id) or {}).get("diem"),
        }
        kq[u.id] = diem_jama(u.department, tp, cfg["diem_jama"])
    return kq


# ── Hũ cho Tổng quan ────────────────────────────────────────────────────────

def duoc_xem_hu(user: User, cfg_hu: dict) -> bool:
    if user.role in ("admin", "executive", "accountant"):
        return True
    ai = cfg_hu.get("ai_thay_hu")
    if ai == "tat_ca":
        return True
    if ai == "kinh_doanh":
        return (user.department or "") in ("SALES", "EXEC") or (user.department or "") in set(cfg_hu.get("phong_nhan") or [])
    return False


async def du_lieu_hu(db: AsyncSession, ky: str | None = None) -> dict:
    """Hũ + bảng «Ai đang đổ tiền vào hũ» (đội & cá nhân) — không lộ tiền thưởng từng người."""
    ky = ky or ky_hien_tai()
    cfg, _ = await doc_cau_hinh(db, ky)
    hu_cfg = cfg["chuong_trinh"]["hu_doanh_so"]
    if hu_cfg["chu_ky"] == "quy":
        nhan_ky, tu, den = quy_cua(ky)
    else:
        tu, den = period_bounds(ky)
        nhan_ky = f"Tháng {int(ky[5:7])}/{ky[:4]}"
    users = await nguoi_xet_thuong(db)
    tong, ds = await doanh_so_theo_nguoi(db, tu, den)
    hu = tinh_hu(hu_cfg, tong, ds, users)
    teams = {t.id: t.name for t in (await db.execute(select(Team))).scalars().all()}
    ten = {u.id: u.full_name for u in users}
    nhom_u = {u.id: u.team_id for u in users}

    ca_nhan = sorted(
        ({"user_id": uid, "ten": ten.get(uid, "—"), "doanh_so": v} for uid, v in ds.items() if uid and v > 0 and uid in ten),
        key=lambda r: -r["doanh_so"],
    )[:10]
    doi: dict[str, float] = defaultdict(float)
    for uid, v in ds.items():
        if uid in nhom_u and nhom_u[uid]:
            doi[nhom_u[uid]] += v
    doi_list = sorted(
        ({"team_id": tid, "ten": teams.get(tid, "—"), "doanh_so": v} for tid, v in doi.items() if v > 0),
        key=lambda r: -r["doanh_so"],
    )
    hom_nay = vn_today()
    so_ngay = (den - tu).days
    da_qua = max(0, min(so_ngay, (hom_nay - tu).days + 1))
    return {
        "ky": ky,
        "nhan_ky": nhan_ky,
        "bat": hu_cfg["bat"],
        "chu_ky": hu_cfg["chu_ky"],
        "cong_don": hu_cfg["cong_don"],
        "doanh_so": tong,
        "moc": hu["moc"],
        "so_moc_dat": hu["so_moc_dat"],
        "quy_mo": hu["quy_mo"],
        "quy_toi_da": (sum(m["quy"] for m in hu["moc"]) if hu_cfg["cong_don"]
                       else max((m["quy"] for m in hu["moc"]), default=0)),
        "moc_tiep": hu["moc_tiep"],
        "con_thieu": hu["con_thieu"],
        "ngay_da_qua": da_qua,
        "so_ngay": so_ngay,
        "ca_nhan": ca_nhan,
        "doi": doi_list,
    }


# ── Chốt kỳ ─────────────────────────────────────────────────────────────────

async def _on_bang_thuong_duyet(db: AsyncSession, request) -> None:
    rows = (await db.execute(
        select(Bonus).where(Bonus.approval_id == request.id, Bonus.status == "pending")
    )).scalars().all()
    for b in rows:
        b.status = "approved"
        b.resolved_at = datetime.now(timezone.utc)
    await db.flush()


async def _on_bang_thuong_tu_choi(db: AsyncSession, request) -> None:
    rows = (await db.execute(
        select(Bonus).where(Bonus.approval_id == request.id, Bonus.status == "pending")
    )).scalars().all()
    for b in rows:
        b.status = "rejected" if request.status == "rejected" else "cancelled"
        b.resolved_at = datetime.now(timezone.utc)
    # Cho phép chốt lại sau khi sửa
    ky = (request.ref_id or "").split(":")[-1]
    if ky:
        await set_setting_json(db, KEY_DA_CHOT.format(ky=ky), {})
    await db.flush()


def dang_ky_duyet() -> None:
    from app.services import approval_engine
    approval_engine.TYPE_LABELS.setdefault("bonus_batch", "Bảng thưởng")
    approval_engine.register_side_effect("bonus_batch", _on_bang_thuong_duyet)
    approval_engine.register_reject_effect("bonus_batch", _on_bang_thuong_tu_choi)


dang_ky_duyet()


class LoiChot(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def chot_ky(db: AsyncSession, ky: str, actor: User) -> dict:
    """Sinh Bonus «chờ duyệt» cho từng người + MỘT đơn duyệt cho cả bảng.

    Idempotent: kỳ đã chốt (và chưa bị từ chối) thì báo 409.
    """
    from app.services import approval_engine
    from app.services.audit import log_action

    kiem_tra_ky(ky)
    if ky >= ky_hien_tai():
        raise LoiChot(400, "Chỉ chốt được kỳ đã kết thúc")
    if (await get_setting_json(db, KEY_DA_CHOT.format(ky=ky))).get("luc"):
        raise LoiChot(409, f"Kỳ {ky} đã chốt rồi")
    bang = await tinh_bang_thuong(db, ky)
    nhan = [r for r in bang["nguoi"] if r["tong"] > 0]

    ky_luong = ky
    for _ in range(3):  # kỳ lương đã khóa → dời sang kỳ sau gần nhất chưa khóa
        if not await is_period_locked(db, ky_luong):
            break
        ky_luong = ky_sau(ky_luong)

    ghi = {"luc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "boi": actor.full_name,
           "so_nguoi": len(nhan), "tong": bang["tong_chi"], "ky_luong": ky_luong, "approval_id": None}
    if not nhan:
        await set_setting_json(db, KEY_DA_CHOT.format(ky=ky), ghi)
        return ghi

    nguoi_duyet = (await db.execute(
        select(User.id, User.role).where(User.is_active == True, User.role.in_(("accountant", "admin")))  # noqa: E712
        .order_by(User.created_at)
    )).all()
    nguoi_duyet = sorted(nguoi_duyet, key=lambda r: r[1] != "accountant")  # kế toán trước, admin sau
    chuoi: list[str] = []
    for uid, _vai in nguoi_duyet:
        if uid != actor.id and uid not in chuoi:
            chuoi.append(uid)
        if len(chuoi) == 2:
            break
    if not chuoi:
        raise LoiChot(409, "Không có người duyệt phù hợp — cần ít nhất 1 admin/kế toán khác người chốt")

    bonuses = []
    for r in nhan:
        ly_do = f"Chế độ thưởng {ky}: " + " · ".join(
            f"{k['nhan']} {k['so_tien']:,.0f}đ".replace(",", ".") for k in r["khoan"] if k["chi_ky_nay"] and k["so_tien"] > 0
        )
        b = Bonus(user_id=r["user_id"], period=ky_luong, amount=r["tong"], reason=ly_do[:500], created_by=actor.id)
        db.add(b)
        bonuses.append(b)
    await db.flush()
    try:
        don = await approval_engine.create_request(
            db, type_="bonus_batch", ref_id=f"che_do_thuong:{ky}",
            title=f"Bảng thưởng kỳ {ky} — {len(nhan)} người, {bang['tong_chi']:,.0f}đ".replace(",", "."),
            requester=actor, approver_ids=chuoi, amount=bang["tong_chi"], sla_hours=72,
        )
    except approval_engine.ApprovalError as err:
        raise LoiChot(err.status_code, err.detail)
    for b in bonuses:
        b.approval_id = don.id
    ghi["approval_id"] = don.id
    await set_setting_json(db, KEY_DA_CHOT.format(ky=ky), ghi)
    await log_action(db, actor=actor, action="che_do_thuong.chot", entity_type="che_do_thuong",
                     entity_id=ky, after=ghi)
    return ghi


async def tu_dong_chot(db: AsyncSession, ky: str) -> dict:
    """Worker mùng 1: chốt kỳ trước nếu bật «Tự động chốt»."""
    cfg, hieu_luc = await doc_cau_hinh(db, ky)
    if hieu_luc is None:
        return {"bo_qua": "chua_luu_cau_hinh"}  # admin chưa duyệt số lần nào → không tự sinh thưởng
    if not cfg["tu_dong_chot"]:
        return {"bo_qua": "tat_tu_dong"}
    if (await get_setting_json(db, KEY_DA_CHOT.format(ky=ky))).get("luc"):
        return {"bo_qua": "da_chot"}
    admin = (await db.execute(
        select(User).where(User.is_active == True, User.role == "admin").order_by(User.created_at).limit(1)  # noqa: E712
    )).scalar_one_or_none()
    if not admin:
        return {"bo_qua": "khong_co_admin"}
    try:
        return await chot_ky(db, ky, admin)
    except LoiChot as e:
        return {"bo_qua": e.detail}


# ── Báo mốc hũ lên nhóm Telegram công ty ────────────────────────────────────

def _ty(v: float) -> str:
    return f"{v / 1e9:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + " tỷ"


def _trieu(v: float) -> str:
    return f"{v / 1e6:,.0f}".replace(",", ".") + " triệu"


async def bao_moc_moi(db: AsyncSession) -> dict:
    """Hũ vừa vượt mốc mới → báo nhóm Telegram công ty. KHÔNG kèm số tiền từng người."""
    ky = ky_hien_tai()
    cfg, _ = await doc_cau_hinh(db, ky)
    hu_cfg = cfg["chuong_trinh"]["hu_doanh_so"]
    if not hu_cfg["bat"] or not hu_cfg["bao_telegram"]:
        return {"bo_qua": "tat"}
    hu = await du_lieu_hu(db, ky)
    khoa_ky = quy_cua(ky)[0] if hu_cfg["chu_ky"] == "quy" else ky
    key = KEY_MOC_DA_BAO.format(ky=khoa_ky)
    ghi = await get_setting_json(db, key)
    if "so_moc" not in ghi:
        # Lần đầu thấy kỳ này (mới deploy / đầu tháng): ghi nhận im lặng, không
        # dội lên nhóm các mốc đã qua từ trước — chỉ báo mốc MỚI từ giờ.
        await set_setting_json(db, key, {"so_moc": hu["so_moc_dat"]})
        return {"bo_qua": "ghi_nhan_lan_dau"}
    da_bao = int(ghi.get("so_moc") or 0)
    if hu["so_moc_dat"] <= da_bao:
        return {"bo_qua": "khong_co_moc_moi"}
    await set_setting_json(db, key, {"so_moc": hu["so_moc_dat"]})

    from app.services.automation import get_automation_settings
    from app.services.telegram_notify import send_telegram
    chat = (await get_automation_settings(db)).get("telegram_group_chat_id", "").strip()
    if not chat:
        return {"bo_qua": "chua_co_nhom"}
    moc = hu["moc"][hu["so_moc_dat"] - 1]
    dong = [
        f"🏆 <b>HŨ DOANH SỐ {hu['nhan_ky'].upper()} VỪA MỞ MỐC {hu['so_moc_dat']}!</b>",
        f"Doanh số ký HĐ đã đạt <b>{_ty(hu['doanh_so'])}</b> — vượt mốc {_ty(moc['doanh_so'])}"
        + (f" «{moc['nhan']}»" if moc.get("nhan") else ""),
        f"💰 Quỹ thưởng đang mở: <b>{_trieu(hu['quy_mo'])}</b>",
    ]
    if hu["moc_tiep"]:
        dong.append(f"🎯 Còn {_ty(hu['con_thieu'])} nữa là mở mốc tiếp ({_trieu(hu['moc_tiep']['quy'])}). Cố lên cả nhà!")
    else:
        dong.append("🔥 Đã phá hết các mốc — kỷ lục mới của JAMA!")
    try:
        await send_telegram(int(chat), "\n".join(dong))
    except (ValueError, Exception) as e:  # noqa: BLE001 — báo lỗi không được làm hỏng job
        logger.warning("bao_moc_moi: gửi Telegram lỗi: %s", e)
    return {"da_bao": hu["so_moc_dat"]}


async def viec_hang_gio(db: AsyncSession) -> dict:
    """Worker gọi mỗi giờ: báo mốc hũ, chụp số Zalo, mùng 1 (≥9h) tự chốt kỳ trước.

    Mọi bước đều idempotent qua system_settings — redeploy chạy lại không sinh trùng.
    """
    kq: dict = {}
    try:
        kq["zalo_chup"] = await chup_zalo_bu(db)
        await db.commit()
    except Exception as e:  # noqa: BLE001
        await db.rollback()
        logger.warning("che_do_thuong: chụp Zalo lỗi: %s", e)
    try:
        kq["moc"] = await bao_moc_moi(db)
        await db.commit()
    except Exception as e:  # noqa: BLE001
        await db.rollback()
        logger.warning("che_do_thuong: báo mốc lỗi: %s", e)
    bay_gio = vn_now()
    if bay_gio.day == 1 and bay_gio.hour >= 9:
        try:
            kq["chot"] = await tu_dong_chot(db, ky_truoc(ky_hien_tai()))
            await db.commit()
        except Exception as e:  # noqa: BLE001
            await db.rollback()
            logger.warning("che_do_thuong: tự chốt lỗi: %s", e)
    return kq
