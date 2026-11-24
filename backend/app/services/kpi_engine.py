"""KPI engine — chấm điểm hiệu suất phòng Kinh doanh + tín hiệu quá tải.

Phiên bản 2 (24/11/2026) — điểm bám MỤC TIÊU, không còn hệ số tự đặt:

  • Mỗi thành phần quy về 0–100 theo một mốc đạt công khai (xem `THANH_PHAN`).
  • Doanh số = giá trị dự án thắng deal (cùng nguồn với hũ thưởng & Bảng KD),
    KHÔNG đếm lead `signed_design` theo `updated_at` như bản 1 — bản đó cứ sửa
    lead đã thắng là deal được đếm lại vào tháng sửa.
  • Kỳ đang chạy so với mục tiêu ĐÃ CHIA THEO NGÀY ĐÃ QUA, để ngày 10 không ai
    bị kết luận «mới đạt 30%».
  • Thành phần thiếu mẫu (ít lead) bị loại khỏi phép tính và trọng số dồn sang
    phần còn lại, thay vì cho 0 hay 100 điểm oan.
  • «Hoạt động ghi trên app» chỉ hiển thị, KHÔNG tính điểm: sale đi gặp khách
    nhiều nhất lại là người ít mở app nhất.

Cả đội tính trong một lượt truy vấn gộp — không lặp theo từng lead.
"""

import json
import logging
import math
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta, timezone
from statistics import median

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.rbac import is_sales_coordinator
from app.models.user import User
from app.models.lead import ACTIVE_LEAD_STAGES, CSKH_ACTIVITY_TYPE, XAC_SUAT_STAGE, Lead, Activity
from app.models.project import Project
from app.models.attendance import AttendanceRecord
from app.models.leave import LeaveRequest
from app.models.performance import KpiSnapshot
from app.services.attendance_service import VN_TZ

logger = logging.getLogger(__name__)

PHIEN_BAN = 2

# Chỉ data_entry; KHÔNG gồm "leader" — leader cũng là trưởng phòng Thiết kế (rbac.py),
# trưởng nhóm Sale được lấy qua department == "SALES" bên dưới.
SALES_ROLES = ("data_entry",)

# ── Mốc chấm điểm ────────────────────────────────────────────────────────────
# Đổi số ở đây thì sửa luôn mục KPI trong frontend/src/lib/huong-dan-content.ts.
SO_NGAY_CHAM = 3            # hạn chăm mặc định cho bước không có trong bảng dưới
# Hạn chăm theo bước — MỘT định nghĩa «quá hạn» cho cả hệ thống: khớp
# OVERDUE_DAYS_BY_STAGE (frontend/src/components/leads/shared.tsx) và trang Dữ liệu chung.
# KPI mà dùng mốc khác thì sale thấy lead không gắn nhãn «Quá hạn» vẫn bị trừ điểm.
HAN_CHAM_THEO_BUOC: dict[str, int] = {
    "new": 3, "interested": 7, "surveyed": 5, "survey_scheduled": 7, "potential": 14,
}
CHAM_DUNG_HAN_DAT = 90.0    # ≥90% lead được chăm đúng hạn → 100 điểm
PHAN_HOI_TOT_GIO = 1.0      # phản hồi lead mới trong 1 giờ làm việc → 100 điểm
PHAN_HOI_KEM_GIO = 16.0     # từ 16 giờ làm việc trở lên → 0 điểm
TIEN_BUOC_DAT = 30.0        # ≥30% lead nhận trong kỳ tiến tới «Đang tư vấn» trở lên → 100
MAT_KHACH_TOT = 10.0        # ≤10% lead nhận trong kỳ bị mất → 100 điểm
MAT_KHACH_KEM = 50.0        # ≥50% → 0 điểm
MAU_TOI_THIEU_TY_LE = 5     # dưới 5 lead thì tỷ lệ % chưa có ý nghĩa
MAU_TOI_THIEU_PHAN_HOI = 3
LEAD_QUA_TAI = 25           # đang giữ quá 25 lead = quá tải (cùng mốc detect_burnout)
NGUONG_DAT, NGUONG_CAN_KEM = 80.0, 60.0

GIO_MO, GIO_DONG = 8, 18    # giờ làm việc T2–T7 (giờ VN)

# (mã, tên, trụ cột, trọng số %) — tổng 100
THANH_PHAN: list[tuple[str, str, str, int]] = [
    ("doanh_so", "Doanh số so với mục tiêu", "ket_qua", 30),
    ("deal", "Số deal thắng so với mục tiêu", "ket_qua", 20),
    ("cham_dung_han", "Lead đang giữ được chăm đúng hạn", "cham_khach", 15),
    ("phan_hoi", "Tốc độ phản hồi lead mới", "cham_khach", 15),
    ("tien_buoc", "Lead nhận trong kỳ tiến bước", "chat_luong", 10),
    ("mat_khach", "Tỷ lệ mất khách", "chat_luong", 10),
]
TRU_COT: dict[str, str] = {
    "ket_qua": "Kết quả", "cham_khach": "Chăm khách", "chat_luong": "Chất lượng",
}
TRONG_SO: dict[str, int] = {ma: w for ma, _, _, w in THANH_PHAN}
STAGE_TIEN_BUOC = ("interested", "surveyed", "survey_scheduled", "potential", "signed_design")
STAGE_GAN_CHOT = ("surveyed", "survey_scheduled", "potential")
LOAI_KHONG_PHAI_CHAM = ("assignment", "system", CSKH_ACTIVITY_TYPE)
VIEC_TOI_DA_LEAD = 20       # mỗi việc gửi kèm tối đa chừng này lead; số tổng nằm ở `tong_lead`


def cong_thuc() -> dict:
    """Bảng công thức để màn hình hiển thị đúng thứ đang chạy, không chép tay."""
    return {
        "phien_ban": PHIEN_BAN,
        "tru_cot": [
            {"ma": ma, "ten": ten, "trong_so": sum(t[3] for t in THANH_PHAN if t[2] == ma)}
            for ma, ten in TRU_COT.items()
        ],
        "thanh_phan": [
            {"ma": ma, "ten": ten, "tru": tru, "trong_so": w} for ma, ten, tru, w in THANH_PHAN
        ],
        "moc": {
            "so_ngay_cham": SO_NGAY_CHAM, "cham_dung_han_dat": CHAM_DUNG_HAN_DAT,
            "phan_hoi_tot_gio": PHAN_HOI_TOT_GIO, "phan_hoi_kem_gio": PHAN_HOI_KEM_GIO,
            "tien_buoc_dat": TIEN_BUOC_DAT, "mat_khach_tot": MAT_KHACH_TOT,
            "mat_khach_kem": MAT_KHACH_KEM, "mau_toi_thieu": MAU_TOI_THIEU_TY_LE,
            "lead_qua_tai": LEAD_QUA_TAI, "nguong_dat": NGUONG_DAT,
            "nguong_can_kem": NGUONG_CAN_KEM, "gio_mo": GIO_MO, "gio_dong": GIO_DONG,
        },
        "han_cham": HAN_CHAM_THEO_BUOC,
    }


# ---------------------------------------------------------------------------
# Period helpers
# ---------------------------------------------------------------------------

def parse_period(period: str) -> tuple[datetime, datetime]:
    """'YYYY-MM' → [đầu tháng, đầu tháng sau) theo GIỜ VIỆT NAM.

    Bản 1 cắt theo UTC nên deal chốt trước 7h sáng mùng 1 rơi vào tháng trước.
    """
    parts = period.split("-")
    year, month = int(parts[0]), int(parts[1])
    start = datetime(year, month, 1, tzinfo=VN_TZ)
    end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=VN_TZ)
    return start, end


def tien_do_ky(period: str) -> tuple[int, int]:
    """(số ngày đã qua, số ngày của kỳ) theo lịch VN — kỳ cũ = đủ ngày, kỳ chưa tới = 0."""
    dau_vn, het_vn = parse_period(period)
    now = datetime.now(timezone.utc)
    so_ngay = (het_vn.date() - dau_vn.date()).days
    if now >= het_vn:
        return so_ngay, so_ngay
    if now < dau_vn:
        return 0, so_ngay
    return (now.astimezone(VN_TZ).date() - dau_vn.date()).days + 1, so_ngay


def ky_truoc(period: str) -> str:
    start, _ = parse_period(period)
    return (start - timedelta(days=1)).strftime("%Y-%m")


def _utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def gio_lam_viec(a: datetime, b: datetime) -> float:
    """Số giờ làm việc (T2–T7, 8h–18h giờ VN) giữa hai mốc.

    Lead về 22h được gọi lúc 8h15 sáng hôm sau là 15 phút, không phải 10 tiếng.
    """
    if b <= a:
        return 0.0
    a, b = a.astimezone(VN_TZ), b.astimezone(VN_TZ)
    tong, ngay = 0.0, a.date()
    for _ in range(92):  # chặn trên: không lead nào cần đếm quá một quý
        if ngay > b.date():
            break
        if ngay.weekday() != 6:
            mo = datetime.combine(ngay, time(GIO_MO), VN_TZ)
            dong = datetime.combine(ngay, time(GIO_DONG), VN_TZ)
            lo, hi = max(a, mo), min(b, dong)
            if hi > lo:
                tong += (hi - lo).total_seconds() / 3600
        ngay += timedelta(days=1)
    return tong


def _tuyen_tinh(x: float, tot: float, kem: float) -> float:
    """100 điểm tại mốc `tot`, 0 điểm tại mốc `kem`, nội suy thẳng ở giữa."""
    if tot == kem:
        return 100.0 if x <= tot else 0.0
    return max(0.0, min(100.0, (kem - x) / (kem - tot) * 100))


def _dat_muc_tieu(thuc_te: float, muc_tieu: float) -> float | None:
    return min(100.0, thuc_te / muc_tieu * 100) if muc_tieu > 0 else None


def _tien_gon(v: float) -> str:
    """Số tiền gọn, cùng cách viết với frontend/src/lib/tien-gon.ts."""
    def gon(x: float, le: int) -> str:
        return f"{x:.{le}f}".rstrip("0").rstrip(".").replace(".", ",")
    if abs(v) >= 1e9:
        return f"{gon(v / 1e9, 2)} tỷ"
    if abs(v) >= 1e6:
        return f"{gon(v / 1e6, 1)}tr"
    return f"{round(v):,}đ".replace(",", ".")


def _gia_tri_lead(l: dict) -> float:
    return float(l["design_contract_value"] or l["deal_value"] or l["estimated_budget"] or 0)


def _viec_tiep(*, moc: datetime, dang_giu: list[dict], nhan: list[dict], duoc_cham, da_lien_he,
               diem: dict, tong_w: int, so_duoc_cham: int, doanh_so: float, so_deal: int,
               mt_ds: float, mt_deal: float, he_so: float, chua_du_lieu: bool) -> list[dict]:
    """Việc nên làm tiếp của MỘT người, xếp theo độ gấp, mỗi việc gắn lead cụ thể.

    Điểm KPI chỉ nói «đang ở đâu»; danh sách này nói «làm gì để lên». `diem_them`
    = điểm tổng tăng thêm nếu làm xong việc đó (ước lượng; các việc không cộng dồn tuyệt đối).
    """
    from app.api.leads import STAGE_LABELS  # import muộn: tránh vòng api ↔ services

    def buoc(ma: str) -> str:
        return f"«{STAGE_LABELS.get(ma, ma)}»"

    def gon(l: dict, ghi_chu: str | None = None) -> dict:
        return {"id": l["id"], "ten": l["name"], "sdt": l["phone"], "stage": l["stage"], "ghi_chu": ghi_chu}

    def them(ma: str, diem_moi: float | None = 100.0) -> float:
        d = diem[ma][2]
        if d is None or diem_moi is None or not tong_w:
            return 0.0
        return max(0.0, (diem_moi - d) * TRONG_SO[ma] / tong_w)

    ds: list[dict] = []

    def viec(ma: str, muc: str, tieu_de: str, ly_do: str, leads=(), diem_them: float = 0.0) -> None:
        leads = list(leads)
        ds.append({
            "ma": ma, "muc": muc, "tieu_de": tieu_de, "ly_do": ly_do,
            "diem_them": round(diem_them, 1) if diem_them >= 0.5 else None,
            "tong_lead": len(leads), "lead": leads[:VIEC_TOI_DA_LEAD],
        })

    if chua_du_lieu:
        viec("chua_co_lead", "xam", "Kỳ này bạn chưa có lead nào",
             "Nhắn trưởng nhóm hoặc điều phối Kinh doanh để nhận lead. Có lead là điểm bắt đầu được chấm.")
        return ds

    def diem_cham_neu_them(k: int) -> float | None:
        return _dat_muc_tieu((so_duoc_cham + k) / len(dang_giu) * 100, CHAM_DUNG_HAN_DAT)

    # 1. Lead mới chưa gọi lần nào — gấp nhất: mỗi giờ chờ là điểm phản hồi tụt.
    moi = sorted((l for l in dang_giu if l["stage"] == "new" and not da_lien_he(l)),
                 key=lambda l: l["nhan_luc"], reverse=True)
    id_moi = {l["id"] for l in moi}

    def cho(l: dict) -> str:
        g = gio_lam_viec(l["nhan_luc"], moc)
        if g < 1:
            return "Vừa nhận"
        if g <= 3 * (GIO_DONG - GIO_MO):
            return f"Chờ {g:.0f} giờ làm việc"
        return f"Nhận từ {l['nhan_luc'].astimezone(VN_TZ):%d/%m}"

    if moi:
        k = sum(1 for l in moi if not duoc_cham(l))
        viec("goi_lead_moi", "do", f"Gọi lần đầu cho {len(moi)} lead mới",
             f"Chưa có lần liên hệ nào từ lúc bạn nhận. Điểm phản hồi đếm theo giờ làm việc: trong "
             f"{PHAN_HOI_TOT_GIO:g} giờ là tối đa, càng để lâu càng tụt. Gọi xong ghi một dòng nhật ký ở thẻ lead.",
             (gon(l, cho(l)) for l in moi),
             them("cham_dung_han", diem_cham_neu_them(k)) if k else 0.0)

    # 2. Khách quá hạn chăm — lead gần chốt xếp trước.
    tre = [l for l in dang_giu if not duoc_cham(l) and l["id"] not in id_moi]
    if tre:
        def ngay_bo(l: dict) -> int:
            return (moc - max(_utc(l["last_contacted_at"]) or l["nhan_luc"], l["nhan_luc"])).days
        tre.sort(key=lambda l: (-XAC_SUAT_STAGE.get(l["stage"], 0), -ngay_bo(l)))
        viec("lien_he_lai", "do" if len(tre) >= 5 else "vang",
             f"Liên hệ lại {len(tre)} khách đã quá hạn chăm",
             "Lead gần chốt xếp trên. Gọi hoặc nhắn xong, ghi một dòng nhật ký ở thẻ lead là hết quá hạn; "
             "khách đã hẹn khảo sát thì nhập ngày khảo sát, lead có lịch phía trước không bị tính trễ.",
             (gon(l, f"{ngay_bo(l)} ngày chưa liên hệ (hạn {HAN_CHAM_THEO_BUOC.get(l['stage'], SO_NGAY_CHAM)} ngày)")
              for l in tre),
             them("cham_dung_han", diem_cham_neu_them(len(tre))))

    # 3. Hụt doanh số / deal so với mốc hôm nay → chỉ đúng các lead gần chốt nhất.
    thieu_ds = mt_ds * he_so - doanh_so if mt_ds > 0 else 0.0
    thieu_deal = math.ceil(mt_deal * he_so - so_deal - 1e-9) if mt_deal > 0 else 0
    if thieu_ds > 0 or thieu_deal > 0:
        gan = sorted((l for l in dang_giu if l["stage"] in STAGE_GAN_CHOT),
                     key=lambda l: (-XAC_SUAT_STAGE.get(l["stage"], 0) * _gia_tri_lead(l),
                                    -XAC_SUAT_STAGE.get(l["stage"], 0)))
        phan = ([f"{_tien_gon(thieu_ds)} doanh số"] if thieu_ds > 0 else []) \
            + ([f"{thieu_deal} deal"] if thieu_deal > 0 else [])
        da_co = f"đã có {_tien_gon(doanh_so)} từ {so_deal} deal" if so_deal else "chưa có deal nào"
        ly_do = (f"Cả tháng: mục tiêu {_tien_gon(mt_ds)}, {da_co}. " if mt_ds > 0
                 else f"Trong kỳ {da_co}. ")
        ly_do += ("Đây là các lead gần chốt nhất của bạn, dồn sức vào đây trước." if gan else
                  f"Bạn chưa có lead nào tới bước {buoc('surveyed')} hay {buoc('survey_scheduled')}: "
                  f"cần đưa lead {buoc('interested')} đi khảo sát.")
        viec("chot_deal", "vang", "Còn thiếu " + " và ".join(phan) + " so với mốc hôm nay", ly_do,
             (gon(l, f"Ước {_tien_gon(_gia_tri_lead(l))}" if _gia_tri_lead(l) else "Chưa nhập giá trị")
              for l in gan),
             them("doanh_so") + them("deal"))

    # 4. Tỷ lệ tiến bước thấp — hay gặp nhất là đã nói chuyện nhưng quên chuyển bước.
    d_tb = diem["tien_buoc"][2]
    if d_tb is not None and d_tb < 100:
        so_tb = sum(1 for l in nhan if l["stage"] in STAGE_TIEN_BUOC)
        can = math.ceil(TIEN_BUOC_DAT / 100 * len(nhan) - 1e-9) - so_tb
        ung_vien = [l for l in nhan if l["stage"] == "new" and l["id"] not in id_moi]
        viec("tien_buoc", "vang", f"Đưa thêm {can} lead sang {buoc('interested')}",
             f"Mới {so_tb}/{len(nhan)} lead nhận trong kỳ tiến bước (mốc đạt {TIEN_BUOC_DAT:g}%). "
             + (f"Các lead dưới đây đã liên hệ nhưng còn nằm ở {buoc('new')}: khách có nhu cầu thật thì "
                "chuyển bước để hệ thống ghi nhận." if ung_vien else
                "Tư vấn tới khi rõ nhu cầu rồi chuyển bước cho lead."),
             (gon(l) for l in ung_vien), them("tien_buoc"))

    # 5. Quá tải — không phải lỗi của sale, nhưng là việc cần báo.
    if len(dang_giu) > LEAD_QUA_TAI:
        viec("qua_tai", "vang", f"Đang giữ {len(dang_giu)} lead: báo trưởng nhóm san bớt",
             f"Quá {LEAD_QUA_TAI} lead đang mở thì khó chăm đúng hạn. Lead hết nhu cầu thì chuyển "
             f"{buoc('dormant')} hoặc {buoc('lost')} để danh sách nhẹ lại.")

    # 6. Mất khách cao — xem lại, lead còn cơ hội thì kéo về.
    d_mat = diem["mat_khach"][2]
    mat = [l for l in nhan if l["stage"] == "lost"]
    if d_mat is not None and d_mat < 100 and mat:
        viec("xem_lead_mat", "xam", f"Xem lại {len(mat)} lead đã mất trong kỳ",
             f"Đang mất {len(mat)}/{len(nhan)} lead nhận trong kỳ (mốc đạt là không quá {MAT_KHACH_TOT:g}%). "
             "Lead nào còn cơ hội thì kéo về lại bảng lead để chăm tiếp.",
             (gon(l, l["lost_reason"] or "Chưa ghi lý do mất") for l in mat))
    return ds


# ---------------------------------------------------------------------------
# KPI computation
# ---------------------------------------------------------------------------

async def nguoi_duoc_cham(db: AsyncSession) -> list[User]:
    """Người gánh chỉ tiêu KD: sale + trưởng nhóm KD đang hoạt động.

    Không gồm BGĐ và điều phối KD (Admin CSKH) — họ chia data chứ không bán,
    tính vào chỉ làm loãng mục tiêu đầu người và hiện một dòng 0 điểm oan.
    """
    users = (await db.execute(
        select(User).where(
            or_(User.role.in_(SALES_ROLES),
                and_(User.department == "SALES", User.role.not_in(("admin", "executive")))),
            User.is_active == True,  # noqa: E712
        )
    )).scalars().all()
    return [u for u in users if not is_sales_coordinator(u)]


async def tinh_kpi_ky(db: AsyncSession, period: str, chi_user_ids: list[str] | None = None,
                      kem_viec: bool = False) -> dict[str, dict]:
    """Chấm KPI một kỳ cho cả đội (hoặc riêng `chi_user_ids`). → {user_id: {metrics, score}}.

    `kem_viec`: kèm `viec_tiep` — danh sách việc nên làm (chỉ có nghĩa với kỳ đang chạy).
    """
    dau_vn, het_vn = parse_period(period)
    dau, het = dau_vn.astimezone(timezone.utc), het_vn.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    moc = min(now, het)  # «hiện tại» của kỳ: kỳ cũ thì là lúc hết kỳ

    da_qua, so_ngay = tien_do_ky(period)
    he_so = da_qua / so_ngay

    doi = await nguoi_duoc_cham(db)
    nhom_cua: dict[str, str | None] = {u.id: u.team_id for u in doi}
    can_tinh = set(chi_user_ids) if chi_user_ids else set(nhom_cua)
    if not can_tinh:
        return {}
    ngoai_doi = can_tinh - set(nhom_cua)
    if ngoai_doi:
        for uid, tid in (await db.execute(
            select(User.id, User.team_id).where(User.id.in_(ngoai_doi))
        )).all():
            nhom_cua.setdefault(uid, tid)

    # ── Mục tiêu đầu người ───────────────────────────────────────────────────
    # Nhóm có mục tiêu riêng → chia cho người trong nhóm; không thì lấy mục
    # tiêu công ty chia đều cho cả đội gánh chỉ tiêu.
    from app.api.sales_dashboard import doc_muc_tieu  # import muộn: tránh vòng api ↔ services

    muc_tieu = await doc_muc_tieu(db)
    tong_nguoi = max(1, len(doi))
    nguoi_trong_nhom = Counter(u.team_id for u in doi if u.team_id)

    def muc_tieu_thang(uid: str, khoa: str) -> float:
        tid = nhom_cua.get(uid)
        rieng = (muc_tieu.get("theo_nhom") or {}).get(tid) or {} if tid else {}
        if rieng.get(khoa):
            return float(rieng[khoa]) / max(1, nguoi_trong_nhom.get(tid, 1))
        return float(muc_tieu.get(khoa) or 0) / tong_nguoi

    # ── Lead của cả đội: lấy một lần ─────────────────────────────────────────
    leads = [dict(r) for r in (await db.execute(
        select(
            Lead.id, Lead.assigned_to, Lead.stage, Lead.created_at, Lead.last_contacted_at,
            Lead.survey_date, Lead.deal_value, Lead.design_contract_value, Lead.estimated_budget,
            Lead.name, Lead.phone, Lead.lost_reason,
        ).where(Lead.assigned_to.in_(can_tinh))
    )).mappings().all()]

    # Lúc NHẬN lead = lần giao gần nhất trong/ trước kỳ; chưa từng giao thì là lúc tạo.
    # Đếm từ `created_at` sẽ phạt sale vì thời gian lead nằm chờ ở khâu chia data.
    lead_cua_doi = select(Lead.id).where(Lead.assigned_to.in_(can_tinh))
    giao_luc = dict((await db.execute(
        select(Activity.lead_id, func.max(Activity.created_at))
        .where(Activity.type == "assignment", Activity.created_at < het,
               Activity.lead_id.in_(lead_cua_doi))
        .group_by(Activity.lead_id)
    )).all())
    for l in leads:
        l["nhan_luc"] = _utc(giao_luc.get(l["id"]) or l["created_at"])
        l["nhan_trong_ky"] = dau <= l["nhan_luc"] < het

    # Lần chăm đầu tiên sau khi nhận — chỉ cần cho lead nhận trong kỳ.
    ids_trong_ky = [l["id"] for l in leads if l["nhan_trong_ky"]]
    cham_theo_lead: dict[str, list[datetime]] = defaultdict(list)
    for i in range(0, len(ids_trong_ky), 500):
        for lid, luc in (await db.execute(
            select(Activity.lead_id, Activity.created_at).where(
                Activity.lead_id.in_(ids_trong_ky[i:i + 500]),
                Activity.type.not_in(LOAI_KHONG_PHAI_CHAM),
                Activity.created_at >= dau,
            )
        )).all():
            cham_theo_lead[lid].append(_utc(luc))

    # ── Số phụ: hoạt động ghi trên app, ngày công, deal thắng ────────────────
    hoat_dong = dict((await db.execute(
        select(Activity.user_id, func.count(Activity.id)).where(
            Activity.user_id.in_(can_tinh), Activity.created_at >= dau, Activity.created_at < het,
            Activity.type.not_in(LOAI_KHONG_PHAI_CHAM),
        ).group_by(Activity.user_id)
    )).all())
    ngay_cong = dict((await db.execute(
        select(AttendanceRecord.user_id, func.count(AttendanceRecord.id)).where(
            AttendanceRecord.user_id.in_(can_tinh),
            AttendanceRecord.work_date >= dau_vn.date(), AttendanceRecord.work_date < het_vn.date(),
        ).group_by(AttendanceRecord.user_id)
    )).all())
    deal_cua: dict[str, list[float]] = defaultdict(list)
    for sid, tong, tk, tc in (await db.execute(
        select(Project.sales_id, Project.total_value, Project.design_value, Project.construction_value)
        .where(Project.sales_id.in_(can_tinh), Project.lead_id.is_not(None),
               Project.status != "cancelled", Project.created_at >= dau, Project.created_at < het)
    )).all():
        deal_cua[sid].append(float(tong or 0) or float(tk or 0) + float(tc or 0))

    lead_cua: dict[str, list[dict]] = defaultdict(list)
    for l in leads:
        lead_cua[l["assigned_to"]].append(l)

    ket_qua: dict[str, dict] = {}
    for uid in can_tinh:
        cua_toi = lead_cua.get(uid, [])
        nhan = [l for l in cua_toi if l["nhan_trong_ky"]]
        dang_giu = [l for l in cua_toi if l["stage"] in ACTIVE_LEAD_STAGES and l["nhan_luc"] < het]

        # Chăm đúng hạn: liên hệ trong hạn của bước đó, HOẶC mới nhận chưa quá hạn,
        # HOẶC đã có hẹn phía trước (có hẹn = đang chăm, không tính trễ).
        def duoc_cham(l: dict) -> bool:
            lien_he, hen = _utc(l["last_contacted_at"]), _utc(l["survey_date"])
            han = moc - timedelta(days=HAN_CHAM_THEO_BUOC.get(l["stage"], SO_NGAY_CHAM))
            return bool((lien_he and lien_he >= han) or l["nhan_luc"] >= han or (hen and hen > moc))

        def da_lien_he(l: dict) -> bool:
            lien_he = _utc(l["last_contacted_at"])
            return bool((lien_he and lien_he >= l["nhan_luc"])
                        or any(c >= l["nhan_luc"] for c in cham_theo_lead.get(l["id"], [])))
        so_duoc_cham = sum(1 for l in dang_giu if duoc_cham(l))
        tl_cham = so_duoc_cham / len(dang_giu) * 100 if dang_giu else None

        # Phản hồi lead mới (giờ làm việc). Lead còn «mới» mà chưa ai chạm thì
        # tính tới thời điểm hiện tại — bỏ ra khỏi mẫu là thưởng cho việc ngâm lead.
        # Lead đã tiến bước nhưng không có nhật ký = «chưa cập nhật», không chấm.
        gio_ph: list[float] = []
        for l in nhan:
            sau_nhan = [c for c in cham_theo_lead.get(l["id"], []) if c >= l["nhan_luc"]]
            lien_he = _utc(l["last_contacted_at"])
            if sau_nhan:
                gio_ph.append(gio_lam_viec(l["nhan_luc"], min(sau_nhan)))
            elif lien_he and lien_he >= l["nhan_luc"]:
                gio_ph.append(gio_lam_viec(l["nhan_luc"], lien_he))
            elif l["stage"] == "new":
                gio_ph.append(gio_lam_viec(l["nhan_luc"], moc))
        gio_phan_hoi = median(gio_ph) if len(gio_ph) >= MAU_TOI_THIEU_PHAN_HOI else None

        du_mau = len(nhan) >= MAU_TOI_THIEU_TY_LE
        so_tien_buoc = sum(1 for l in nhan if l["stage"] in STAGE_TIEN_BUOC)
        so_mat = sum(1 for l in nhan if l["stage"] == "lost")
        tl_tien_buoc = so_tien_buoc / len(nhan) * 100 if nhan else None
        tl_mat = so_mat / len(nhan) * 100 if nhan else None

        deals = deal_cua.get(uid, [])
        doanh_so, so_deal = sum(deals), len(deals)
        mt_ds = muc_tieu_thang(uid, "doanh_thu_thang")
        mt_deal = muc_tieu_thang(uid, "hd_thiet_ke_thang") + muc_tieu_thang(uid, "hd_thi_cong_thang")

        diem: dict[str, tuple[float | None, float | None, float | None, str | None]] = {
            # mã: (giá trị, mốc so sánh, điểm, lý do chưa chấm)
            "doanh_so": (doanh_so, mt_ds * he_so, _dat_muc_tieu(doanh_so, mt_ds * he_so),
                         "Chưa đặt mục tiêu doanh số"),
            "deal": (so_deal, mt_deal * he_so, _dat_muc_tieu(so_deal, mt_deal * he_so),
                     "Chưa đặt mục tiêu số deal"),
            "cham_dung_han": (tl_cham, CHAM_DUNG_HAN_DAT,
                              _dat_muc_tieu(tl_cham, CHAM_DUNG_HAN_DAT) if tl_cham is not None else None,
                              "Không giữ lead nào đang mở"),
            "phan_hoi": (gio_phan_hoi, PHAN_HOI_TOT_GIO,
                         _tuyen_tinh(gio_phan_hoi, PHAN_HOI_TOT_GIO, PHAN_HOI_KEM_GIO)
                         if gio_phan_hoi is not None else None,
                         f"Chưa đủ {MAU_TOI_THIEU_PHAN_HOI} lead mới để đo"),
            "tien_buoc": (tl_tien_buoc, TIEN_BUOC_DAT,
                          _dat_muc_tieu(tl_tien_buoc, TIEN_BUOC_DAT) if du_mau else None,
                          f"Nhận chưa đủ {MAU_TOI_THIEU_TY_LE} lead trong kỳ"),
            "mat_khach": (tl_mat, MAT_KHACH_TOT,
                          _tuyen_tinh(tl_mat, MAT_KHACH_TOT, MAT_KHACH_KEM) if du_mau else None,
                          f"Nhận chưa đủ {MAU_TOI_THIEU_TY_LE} lead trong kỳ"),
        }

        thanh_phan, tong_w, tong_diem = [], 0, 0.0
        tru_w: dict[str, int] = defaultdict(int)
        tru_diem: dict[str, float] = defaultdict(float)
        for ma, ten, tru, w in THANH_PHAN:
            gia_tri, moc_ss, d, ly_do = diem[ma]
            if d is not None:
                tong_w += w
                tong_diem += d * w
                tru_w[tru] += w
                tru_diem[tru] += d * w
            thanh_phan.append({
                "ma": ma, "ten": ten, "tru": tru, "trong_so": w,
                "gia_tri": round(gia_tri, 1) if gia_tri is not None else None,
                "moc": round(moc_ss, 1) if moc_ss is not None else None,
                "diem": round(d, 1) if d is not None else None,
                "ly_do": None if d is not None else ly_do,
            })

        # Không lead, không deal → không có gì để chấm; 0 điểm ở đây là «trống», không phải «kém».
        chua_du_lieu = not nhan and not dang_giu and not deals
        score = 0.0 if chua_du_lieu or not tong_w else round(tong_diem / tong_w, 1)

        du_bao = sum(_gia_tri_lead(l) * XAC_SUAT_STAGE.get(l["stage"], 0) for l in dang_giu)
        so_ngay_cong = ngay_cong.get(uid, 0)
        so_hoat_dong = hoat_dong.get(uid, 0)
        metrics = {
            "phien_ban": PHIEN_BAN,
            "tinh_luc": now.isoformat(),
            "chua_du_lieu": chua_du_lieu,
            "do_phu": tong_w,  # % trọng số thực sự có dữ liệu để chấm
            "tru_cot": {
                ma: (round(tru_diem[ma] / tru_w[ma], 1) if tru_w.get(ma) else None) for ma in TRU_COT
            },
            "thanh_phan": thanh_phan,
            "doanh_so": doanh_so,
            "muc_tieu_doanh_so": round(mt_ds),
            "muc_tieu_tien_do": round(mt_ds * he_so),
            "dat_muc_tieu_pct": round(doanh_so / (mt_ds * he_so) * 100, 1) if mt_ds * he_so > 0 else None,
            "deal_thang": so_deal,
            "lead_nhan": len(nhan),
            "lead_tien_buoc": so_tien_buoc,
            "lead_mat": so_mat,
            "lead_dang_giu": len(dang_giu),
            "lead_tre_cham": len(dang_giu) - so_duoc_cham,
            "ty_le_cham_dung_han": round(tl_cham, 1) if tl_cham is not None else None,
            "gio_phan_hoi": round(gio_phan_hoi, 1) if gio_phan_hoi is not None else None,
            "ty_le_tien_buoc": round(tl_tien_buoc, 1) if tl_tien_buoc is not None else None,
            "ty_le_mat": round(tl_mat, 1) if tl_mat is not None else None,
            "du_bao": round(du_bao),
            "hoat_dong": so_hoat_dong,
            "ngay_cong": so_ngay_cong,
            # Khóa bản 1 — giữ để bot/báo cáo cũ đọc snapshot không vỡ.
            "activity_rate": round(so_hoat_dong / max(1, so_ngay_cong), 2),
            "sla_compliance": round(tl_cham or 0, 1),
            "first_touch_hours": round(gio_phan_hoi or 0, 1),
            "signed_count": so_deal,
            "signed_value": doanh_so,
            "stage_conversion": round(tl_tien_buoc or 0, 1),
            "pipeline_value_weighted": round(du_bao),
            "lost_no_response_rate": round(tl_mat or 0, 1),
        }
        ket_qua[uid] = {"metrics": metrics, "score": score}
        if kem_viec:
            # Kỳ đã khép thì không còn gì để «làm tiếp».
            ket_qua[uid]["viec_tiep"] = _viec_tiep(
                moc=moc, dang_giu=dang_giu, nhan=nhan, duoc_cham=duoc_cham, da_lien_he=da_lien_he,
                diem=diem, tong_w=tong_w, so_duoc_cham=so_duoc_cham, doanh_so=doanh_so,
                so_deal=so_deal, mt_ds=mt_ds, mt_deal=mt_deal, he_so=he_so, chua_du_lieu=chua_du_lieu,
            ) if now < het else []

    return ket_qua


async def compute_kpi(db: AsyncSession, user_id: str, period: str, kem_viec: bool = False) -> dict:
    """KPI một người một kỳ → {metrics, score 0–100[, viec_tiep]}."""
    return (await tinh_kpi_ky(db, period, [user_id], kem_viec))[user_id]


async def snapshot_all(db: AsyncSession, period: str) -> int:
    """Snapshot KPI for all active sales users. Returns count of snapshots created/updated."""
    try:
        ket_qua = await tinh_kpi_ky(db, period)
    except Exception:
        logger.exception("KPI compute failed for period %s", period)
        await db.rollback()
        return 0

    co_san = {
        s.user_id: s for s in (await db.execute(
            select(KpiSnapshot).where(KpiSnapshot.period == period)
        )).scalars().all()
    }
    # Người có bản chụp nhưng nay không còn trong đội gánh chỉ tiêu (nghỉ việc,
    # chuyển phòng, điều phối KD): kỳ ĐANG CHẠY thì gỡ cho bảng khỏi dòng ma;
    # kỳ ĐÃ QUA là lịch sử — giữ người đó, chỉ chấm lại theo công thức hiện hành.
    ngoai_doi = [uid for uid in co_san if uid not in ket_qua]
    if ngoai_doi:
        if datetime.now(timezone.utc) < parse_period(period)[1]:
            for uid in ngoai_doi:
                await db.delete(co_san.pop(uid))
        else:
            ket_qua.update(await tinh_kpi_ky(db, period, ngoai_doi))

    for uid, kq in ket_qua.items():
        snap = co_san.get(uid)
        if snap:
            snap.metrics_json = json.dumps(kq["metrics"])
            snap.score = kq["score"]
        else:
            db.add(KpiSnapshot(user_id=uid, period=period,
                               metrics_json=json.dumps(kq["metrics"]), score=kq["score"]))
    await db.commit()

    await _compute_ranks(db, period)
    return len(ket_qua)


async def dam_bao_snapshot(db: AsyncSession, period: str, tuoi_toi_da_phut: int = 10) -> None:
    """Bảo đảm kỳ có bản chụp đúng phiên bản và đủ mới trước khi đọc.

    • Kỳ chưa tới → không chụp (mọi chỉ số đều rỗng).
    • Kỳ đang chạy → chụp lại nếu bản cũ hơn `tuoi_toi_da_phut`.
    • Kỳ đã qua → chụp lại đúng một lần sau khi hết kỳ (job đêm chụp lúc 1h
      sáng nên ngày cuối tháng chưa vào), rồi đóng băng.
    """
    dau_vn, het_vn = parse_period(period)
    now = datetime.now(timezone.utc)
    if now < dau_vn:
        return
    cu_nhat: datetime | None = None
    rows = (await db.execute(
        select(KpiSnapshot.metrics_json).where(KpiSnapshot.period == period)
    )).scalars().all()
    for raw in rows:
        try:
            m = json.loads(raw)
            luc = datetime.fromisoformat(m["tinh_luc"]) if m.get("phien_ban") == PHIEN_BAN else None
        except (ValueError, TypeError, KeyError):
            luc = None
        if luc is None:
            cu_nhat = None
            break
        cu_nhat = luc if cu_nhat is None else min(cu_nhat, luc)
    if cu_nhat is not None:
        if now >= het_vn and cu_nhat >= het_vn:
            return
        if now < het_vn and now - cu_nhat < timedelta(minutes=tuoi_toi_da_phut):
            return
    await snapshot_all(db, period)


async def _compute_ranks(db: AsyncSession, period: str) -> None:
    """Set rank_in_team and rank_overall for all snapshots in a period."""
    snapshots = (await db.execute(
        select(KpiSnapshot).where(KpiSnapshot.period == period)
    )).scalars().all()

    if not snapshots:
        return

    # Load users to get team info
    user_ids = {s.user_id for s in snapshots}
    users = (await db.execute(
        select(User).where(User.id.in_(user_ids))
    )).scalars().all()
    user_teams = {u.id: u.team_id for u in users}

    # Overall ranking (desc score)
    sorted_all = sorted(snapshots, key=lambda s: s.score, reverse=True)
    for i, s in enumerate(sorted_all, 1):
        s.rank_overall = i

    # Per-team ranking
    teams: dict[str, list] = {}
    for s in snapshots:
        tid = user_teams.get(s.user_id)
        if tid:
            teams.setdefault(tid, []).append(s)
    for team_snaps in teams.values():
        team_sorted = sorted(team_snaps, key=lambda s: s.score, reverse=True)
        for i, s in enumerate(team_sorted, 1):
            s.rank_in_team = i

    await db.commit()


# ---------------------------------------------------------------------------
# Burnout signals
# ---------------------------------------------------------------------------

async def detect_burnout(db: AsyncSession, user_id: str) -> dict:
    """Detect burnout signals for a user. Returns {signals: [...], risk_level: 'green'|'yellow'|'red'}."""
    now = datetime.now(timezone.utc)
    four_weeks_ago = now - timedelta(weeks=4)
    three_months_ago = now - timedelta(days=90)

    signals = []

    # 1. OT >10h/week × 3 consecutive weeks
    for weeks_back in range(3):
        week_start = now - timedelta(weeks=weeks_back + 1)
        week_end = now - timedelta(weeks=weeks_back)
        ot_q = await db.execute(
            select(func.coalesce(func.sum(AttendanceRecord.ot_hours), 0)).where(
                AttendanceRecord.user_id == user_id,
                AttendanceRecord.work_date >= week_start.date(),
                AttendanceRecord.work_date < week_end.date(),
            )
        )
        if (ot_q.scalar() or 0) > 10:
            if weeks_back < 2:
                continue
            signals.append("ot_extended")
            break

    # 2. Work on Sunday ≥3/month (cross-DB: filter in Python to avoid SQLite strftime)
    thirty_days_ago = (now - timedelta(days=30)).date()
    recent_records = (await db.execute(
        select(AttendanceRecord.work_date).where(
            AttendanceRecord.user_id == user_id,
            AttendanceRecord.work_date >= thirty_days_ago,
        )
    )).scalars().all()
    sunday_count = sum(1 for d in recent_records if d.weekday() == 6)  # Sunday = 6
    if sunday_count >= 3:
        signals.append("sunday_work")

    # 3. No leave in 90 days + balance ≥6
    leave_q = await db.execute(
        select(func.count(LeaveRequest.id)).where(
            LeaveRequest.user_id == user_id,
            LeaveRequest.start_date >= three_months_ago.date(),
            LeaveRequest.status.in_(["approved", "pending"]),
        )
    )
    leave_count = leave_q.scalar() or 0
    if leave_count == 0:
        signals.append("no_leave")

    # 4. Disengagement: activity_rate drop ≥40% vs 3-period average
    # (simplified: compare this period vs last 3 periods)
    # Skip for MVP — requires KpiSnapshot history

    # 5. Lead overload
    active_leads_q = await db.execute(
        select(func.count(Lead.id)).where(
            Lead.assigned_to == user_id,
            Lead.stage.in_(ACTIVE_LEAD_STAGES),
        )
    )
    active_count = active_leads_q.scalar() or 0
    if active_count > 25:  # default lead_cap
        signals.append("lead_overload")

    risk_level = "green"
    if len(signals) >= 2:
        risk_level = "yellow"
    if len(signals) >= 3:
        risk_level = "red"

    return {
        "signals": signals,
        "risk_level": risk_level,
        "active_leads": active_count,
    }


# ---------------------------------------------------------------------------
# Leaderboard (anonymized)
# ---------------------------------------------------------------------------

async def get_leaderboard(db: AsyncSession, period: str, current_user_id: str | None = None,
                          hien_het_ten: bool = False) -> dict:
    """Bảng xếp hạng một kỳ. Nhân viên chỉ thấy tên top 5 + chính mình;
    BGĐ (`hien_het_ten`) thấy đủ tên — người ra quyết định không thể đọc «Nhân viên #6»."""
    snapshots = (await db.execute(
        select(KpiSnapshot, User.full_name, User.team_id)
        .join(User, KpiSnapshot.user_id == User.id)
        .where(KpiSnapshot.period == period)
        .order_by(KpiSnapshot.score.desc())
    )).all()

    leaderboard = []
    my_rank = None
    for i, (snap, name, team_id) in enumerate(snapshots, 1):
        entry = {
            "rank": i,
            "score": snap.score,
            "is_me": snap.user_id == current_user_id,
        }
        if hien_het_ten or i <= 5 or snap.user_id == current_user_id:
            entry["name"] = name
            entry["team_id"] = team_id
        else:
            entry["name"] = None
        if snap.user_id == current_user_id:
            my_rank = i
        leaderboard.append(entry)

    return {"leaderboard": leaderboard, "my_rank": my_rank}
