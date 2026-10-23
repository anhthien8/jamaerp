"""Sales Dashboard API — bảng điều khiển hiệu suất phòng Kinh doanh.

Dựng 13/10/2026 theo dashboard mẫu chủ dự án gửi. Khác `/dashboard/executive`
(nhìn toàn công ty, 1 thẻ 1 con số) ở chỗ đây là màn hình QUẢN TRỊ TEAM SALE:
mọi con số đều có mẫu số và có mốc so sánh — thực tế vs mục tiêu, kỳ này vs kỳ
trước, nhóm này vs nhóm khác, người này vs người khác.

Ba quy ước giữ nguyên từ `/dashboard/executive` để hai màn hình không trôi lệch:
  • cắt ngày theo GIỜ VN qua `khoang_ngay()`/`trong_ky()`;
  • `@router.get` nằm TRÊN `@cached`;
  • khóa cache gồm ĐỦ tham số (kỳ + nhóm), thiếu một cái là đổi lọc mà số không nhúc nhích.

CHƯA MỞ CHO AI NGOÀI ADMIN (yêu cầu chủ dự án: «làm demo trên tài khoản admin,
không publish»). Muốn mở cho Ban giám đốc / Trưởng phòng KD thì sửa đúng một
chỗ: `VAI_TRO_XEM` bên dưới.
"""

import json
import unicodedata
from calendar import monthrange
from datetime import datetime, timezone, timedelta, date

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func, exists
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User, Team
from app.models.lead import Lead, Activity
from app.models.project import Project
from app.models.quotation import Quotation
from app.models.notification import SystemSetting
from app.api.dashboard import khoang_ngay, trong_ky
from app.api.leads import STAGE_LABELS
from app.cache import cache, cached
from app.services.attendance_service import VN_TZ

router = APIRouter(prefix="/dashboard/sales", tags=["sales-dashboard"])


# ── Ai được xem ──────────────────────────────────────────────────────────────
# Cố ý KHÔNG đi qua ma trận phân quyền 25 ô: màn hình này gộp doanh số toàn
# phòng + xếp hạng từng nhân viên, mở bằng cách tích một ô là lộ cả bảng lương
# ngầm. Demo nên khóa cứng ở admin; nới ra là quyết định của chủ dự án.
VAI_TRO_XEM: set[str] = {"admin"}


def _chan_neu_khong_duoc_xem(user: User) -> None:
    if user.role not in VAI_TRO_XEM:
        raise HTTPException(
            status_code=403,
            detail="Bảng điều khiển Kinh doanh đang ở chế độ thử nghiệm, chỉ tài khoản quản trị xem được.",
        )


# ── Mục tiêu (mục tiêu THÁNG) ────────────────────────────────────────────────
# Toàn hệ thống chưa có bảng nào chứa mục tiêu/KPI phòng ban — `kpi_snapshots`
# chỉ lưu KẾT QUẢ đã chấm, không lưu đích cần đạt. Chứa ở `system_settings`
# (key/value, đã dùng cho custom_roles & cấu hình chấm công) nên KHÔNG cần
# migration — một bảng mới chỉ để giữ 5 con số là quá nặng tay, và demo không
# được phép đụng tới schema prod.
SALES_TARGETS_KEY = "sales_targets"

MUC_TIEU_MAC_DINH: dict = {
    "doanh_thu_thang": 14_400_000_000,   # đồng
    "hd_thiet_ke_thang": 24,
    "hd_thi_cong_thang": 18,
    "khach_khao_sat_thang": 120,
    "ty_le_lien_he_toi_thieu": 90,       # %
    # Khu vực nhà: lead ngoài danh sách này bị đếm là «khách tỉnh» (xa, chi phí
    # khảo sát/thi công cao) — đúng cách phòng KD đang phân loại data.
    "khu_vuc_trong_tam": ["TP. Hồ Chí Minh"],
    # Mục tiêu riêng từng nhóm: {"<team_id>": {"doanh_thu_thang": ...}}
    "theo_nhom": {},
}


async def doc_muc_tieu(db: AsyncSession) -> dict:
    """Đọc mục tiêu đã lưu, thiếu khóa nào thì lấy mặc định (không bao giờ vỡ)."""
    setting = await db.get(SystemSetting, SALES_TARGETS_KEY)
    luu = {}
    if setting and setting.value:
        try:
            parsed = json.loads(setting.value)
            if isinstance(parsed, dict):
                luu = parsed
        except (ValueError, TypeError):
            luu = {}
    return {**MUC_TIEU_MAC_DINH, **luu}


# ── Phân loại chất lượng data ────────────────────────────────────────────────
# 34 tỉnh/thành sau sáp nhập (Nghị quyết 202/2025/QH15) — PHẢI khớp
# REGION_OPTIONS ở frontend/src/lib/utils.ts.
#
# Dữ liệu cũ còn lưu tên QUẬN của TP.HCM (Q1, Q7, Gò Vấp…). Những giá trị đó
# KHÔNG nằm trong danh sách tỉnh nên được coi là khách nội thành — đúng ý nghĩa
# gốc, và tránh việc 96 lead cũ bị gắn oan nhãn «khách tỉnh».
TINH_THANH: set[str] = {
    "TP. Hồ Chí Minh", "Hà Nội", "Hải Phòng", "Đà Nẵng", "Cần Thơ", "Huế",
    "An Giang", "Bắc Ninh", "Cà Mau", "Cao Bằng", "Điện Biên", "Đắk Lắk",
    "Đồng Nai", "Đồng Tháp", "Gia Lai", "Hà Tĩnh", "Hưng Yên", "Khánh Hòa",
    "Lai Châu", "Lâm Đồng", "Lạng Sơn", "Lào Cai", "Nghệ An", "Ninh Bình",
    "Phú Thọ", "Quảng Ngãi", "Quảng Ninh", "Quảng Trị", "Sơn La", "Tây Ninh",
    "Thái Nguyên", "Thanh Hóa", "Tuyên Quang", "Vĩnh Long",
}

# Tình trạng liên hệ đồng nghĩa «data rác»: số sai hoặc khách không có nhu cầu.
CONTACT_KHONG_DAT = {"wrong_number", "no_need"}


def _chuan_hoa(s: str | None) -> str:
    """Bỏ dấu + hạ chữ thường để so tên tỉnh bất kể người nhập viết hoa/thiếu dấu.

    Đ/đ phải đổi tay: NFD KHÔNG tách được chữ này (U+0110/U+0111 là ký tự
    riêng, không phải D + dấu), nên «Đồng Nai» và «dong nai» sẽ không khớp nhau
    nếu chỉ dựa vào NFD.
    """
    if not s:
        return ""
    s = s.replace("Đ", "D").replace("đ", "d")
    khong_dau = unicodedata.normalize("NFD", s)
    khong_dau = "".join(c for c in khong_dau if unicodedata.category(c) != "Mn")
    return " ".join(khong_dau.lower().replace("tp.", "").replace("tp ", "").split())


def phan_loai_data(region: str | None, ngan_sach: str | None, contact_status: str | None,
                   trong_tam_chuan: set[str]) -> str:
    """Một lead rơi vào ĐÚNG MỘT rổ chất lượng — tổng 4 rổ luôn bằng tổng data.

    Thứ tự ưu tiên có chủ ý: số sai/không nhu cầu là rác thật nên xét trước;
    rồi tới khách tỉnh (đi khảo sát không nổi); rồi ngân sách thấp.
    """
    if contact_status in CONTACT_KHONG_DAT:
        return "khong_dat"
    chuan = _chuan_hoa(region)
    if chuan and chuan not in trong_tam_chuan and any(
        chuan == _chuan_hoa(t) for t in TINH_THANH
    ):
        return "khach_tinh"
    if ngan_sach == "duoi_200":
        return "ngan_sach_thap"
    return "dat_tieu_chuan"


NHAN_CHAT_LUONG: dict[str, str] = {
    "dat_tieu_chuan": "Data đạt tiêu chuẩn",
    "khach_tinh": "Khách tỉnh",
    "ngan_sach_thap": "Ngân sách thấp",
    "khong_dat": "Không đạt tiêu chuẩn",
}


# ── Phễu bán hàng ────────────────────────────────────────────────────────────
# Lead chỉ lưu TRẠNG THÁI HIỆN TẠI, không lưu lịch sử chuyển bước. Nếu đếm mỗi
# bước độc lập thì phễu sẽ phình chỗ nọ hụt chỗ kia (lead đã khảo sát nhưng
# stage vẫn 'new' → bước 5 nhiều hơn bước 4, nhìn như bảng lỗi).
#
# Nên quy mỗi lead về một ĐỘ SÂU 0–7 = bước xa nhất chứng minh được, rồi
# bước i = số lead có độ sâu ≥ i. Phễu vì thế luôn thu hẹp dần.
THU_TU_STAGE: dict[str, int] = {
    "new": 0, "interested": 1, "survey_scheduled": 2, "potential": 3, "signed_design": 4,
}

BUOC_PHEU: list[tuple[str, str]] = [
    ("data", "Data đạt tiêu chuẩn"),
    ("da_lien_he", "Đã liên hệ"),
    ("ket_noi_duoc", "Kết nối được"),
    ("dang_tu_van", "Đang tư vấn"),
    ("da_khao_sat", "Đã khảo sát"),
    ("da_bao_gia", "Đã gửi báo giá"),
    ("dam_phan", "Đang đàm phán"),
    ("ky_hd", "Deal đã thắng"),
]


def do_sau_pheu(l: dict) -> int:
    """Bước xa nhất một lead chứng minh được, 0 = chỉ mới là data."""
    rank = THU_TU_STAGE.get(l["stage"], 0)
    sau = 0
    if l["contact_status"] not in (None, "pending") or l["last_contacted_at"] or l["co_activity"]:
        sau = 1
    if l["contact_status"] == "reachable":
        sau = max(sau, 2)
    if rank >= 1:
        sau = max(sau, 3)
    if l["survey_date"]:
        sau = max(sau, 4)
    if rank >= 2 or l["co_bao_gia"]:
        sau = max(sau, 5)
    if rank >= 3:
        sau = max(sau, 6)
    if rank >= 4:
        sau = max(sau, 7)
    return sau


# Xác suất thắng theo bước — dùng cho dự báo có trọng số. Chốt theo tỷ lệ
# chuyển bước thực tế của phòng KD; sửa ở đây là đổi cả màn hình.
XAC_SUAT_STAGE: dict[str, float] = {
    "new": 0.05, "interested": 0.15, "survey_scheduled": 0.35,
    "potential": 0.60, "signed_design": 1.0,
}

STAGE_DANG_MO = ["new", "interested", "survey_scheduled", "potential"]


def gia_tri_lead(l: dict) -> float:
    """Giá trị quy đổi của một lead — ưu tiên số chắc chắn nhất đang có."""
    return float(
        l["design_contract_value"] or l["deal_value"] or l["estimated_budget"] or 0
    )


def _ty_le(phan: float, tong: float) -> float:
    return round(phan / tong * 100, 1) if tong else 0.0


def _ngay_vn(dt: datetime | None) -> date | None:
    if dt is None:
        return None
    moc = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return moc.astimezone(VN_TZ).date()


def muc_tieu_trong_ky(muc_tieu_thang: float, dau: date, het: date) -> float:
    """Chia mục tiêu THÁNG theo số ngày kỳ đang xem thực sự chiếm.

    Kỳ bắc qua nhiều tháng thì cộng dồn từng tháng. Nhờ vậy xem «7 ngày gần
    nhất» không bị so với mục tiêu cả tháng rồi kết luận team bết bát.
    """
    if muc_tieu_thang <= 0 or het < dau:
        return 0.0
    tong = 0.0
    moc = dau.replace(day=1)
    while moc <= het:
        so_ngay_thang = monthrange(moc.year, moc.month)[1]
        cuoi_thang = moc.replace(day=so_ngay_thang)
        phu = (min(het, cuoi_thang) - max(dau, moc)).days + 1
        if phu > 0:
            tong += muc_tieu_thang * phu / so_ngay_thang
        moc = cuoi_thang + timedelta(days=1)
    return tong


def so_thang_phu(dau: date, het: date) -> float:
    """Kỳ đang xem tương đương bao nhiêu tháng (để nhân mục tiêu nguyên tháng)."""
    return muc_tieu_trong_ky(1.0, dau, het)


# ─────────────────────────────────────────────────────────────────────────────
# GET /dashboard/sales
# ─────────────────────────────────────────────────────────────────────────────

@router.get("")
@cached(ttl=120, prefix="dashboard", key_fn=lambda *a, **kw: [
    kw.get("current_user").id if kw.get("current_user") else "anon",
    kw.get("tu") or "-", kw.get("den") or "-", kw.get("team_id") or "-",
])
async def sales_dashboard(
    tu: str | None = Query(None, description="Từ ngày YYYY-MM-DD (giờ VN)"),
    den: str | None = Query(None, description="Đến ngày YYYY-MM-DD (giờ VN)"),
    team_id: str | None = Query(None, description="Chỉ xem một nhóm KD"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toàn bộ số liệu của một màn hình trong MỘT lần gọi.

    Cố ý gộp chứ không tách 10 endpoint: nhân viên xem trên 4G, 10 request là
    10 lần chờ, và tách ra thì mỗi khối có thể rơi vào kỳ khác nhau khi người
    dùng đổi bộ lọc giữa lúc tải.

    Kỳ mặc định là THÁNG NÀY (khác Tổng quan mặc định «toàn bộ»): mọi mục tiêu
    đều là mục tiêu tháng, cộng dồn cả lịch sử rồi so với mục tiêu tháng thì
    con số vô nghĩa.
    """
    _chan_neu_khong_duoc_xem(current_user)

    now = datetime.now(timezone.utc)
    hom_nay_vn = now.astimezone(VN_TZ).date()
    if not tu and not den:
        tu = hom_nay_vn.replace(day=1).isoformat()
        den = hom_nay_vn.isoformat()
    dau, het = khoang_ngay(tu, den)
    ngay_dau = datetime.strptime(tu, "%Y-%m-%d").date() if tu else None
    ngay_het = datetime.strptime(den, "%Y-%m-%d").date() if den else None
    if ngay_dau and ngay_het and ngay_dau > ngay_het:
        ngay_dau, ngay_het = ngay_het, ngay_dau
    so_ngay_ky = (ngay_het - ngay_dau).days + 1 if (ngay_dau and ngay_het) else None

    # Kỳ TRƯỚC cùng độ dài — mốc so sánh cho mọi mũi tăng/giảm trên thẻ KPI.
    if ngay_dau and ngay_het:
        truoc_het = ngay_dau - timedelta(days=1)
        truoc_dau = truoc_het - timedelta(days=so_ngay_ky - 1)
        dau_truoc, het_truoc = khoang_ngay(truoc_dau.isoformat(), truoc_het.isoformat())
    else:
        truoc_dau = truoc_het = dau_truoc = het_truoc = None

    muc_tieu = await doc_muc_tieu(db)
    trong_tam_chuan = {_chuan_hoa(t) for t in muc_tieu.get("khu_vuc_trong_tam") or []}

    # ── Danh mục nhóm & người ────────────────────────────────────────────────
    nhom_rows = (await db.execute(
        select(Team.id, Team.name).where(Team.department == "SALES").order_by(Team.name)
    )).all()
    ten_nhom = {i: n for i, n in nhom_rows}
    if team_id and team_id not in ten_nhom:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhóm kinh doanh này.")

    nguoi_rows = (await db.execute(
        select(User.id, User.full_name, User.team_id, User.is_active)
        .where(User.department == "SALES")
    )).all()
    ten_nguoi = {i: n for i, n, _, _ in nguoi_rows}
    nhom_cua_nguoi = {i: t for i, _, t, _ in nguoi_rows}
    nguoi_trong_nhom = {i for i, _, t, _ in nguoi_rows if team_id and t == team_id}

    # ── Lead: lấy MỘT lần rồi tính hết trong Python ──────────────────────────
    # 11 khối trên màn hình đều cắt cùng tập lead này theo các chiều khác nhau.
    # Chạy 11 truy vấn GROUP BY thì vừa chậm vừa dễ lệch nhau mỗi khi sửa một
    # chỗ; phòng KD prod có ~620 lead nên gom về Python là rẻ hơn hẳn.
    co_bao_gia = exists(select(Quotation.id).where(Quotation.lead_id == Lead.id).correlate(Lead))
    co_activity = exists(select(Activity.id).where(Activity.lead_id == Lead.id).correlate(Lead))

    async def tai_lead(d, h):
        q = select(
            Lead.id, Lead.stage, Lead.contact_status, Lead.last_contacted_at,
            Lead.survey_date, Lead.created_at, Lead.assigned_to, Lead.team_id,
            Lead.region, Lead.ngan_sach_khoang, Lead.source, Lead.lost_reason,
            Lead.estimated_budget, Lead.deal_value, Lead.design_contract_value,
            co_bao_gia.label("co_bao_gia"), co_activity.label("co_activity"),
        )
        q = trong_ky(q, Lead.created_at, d, h)
        if team_id:
            q = q.where(Lead.team_id == team_id)
        rows = (await db.execute(q)).mappings().all()
        ds = [dict(r) for r in rows]
        for l in ds:
            l["ro"] = phan_loai_data(
                l["region"], l["ngan_sach_khoang"], l["contact_status"], trong_tam_chuan
            )
            l["do_sau"] = do_sau_pheu(l)
        return ds

    leads = await tai_lead(dau, het)
    leads_truoc = await tai_lead(dau_truoc, het_truoc) if dau_truoc else []

    # ── Doanh số: giá trị dự án thắng deal (đổi 23/10/2026, giống hũ thưởng) ──
    # Không đếm hợp đồng «đã ký» nữa vì trên prod HĐ đều nằm ở `draft` → bảng
    # luôn 0. Mỗi lead bấm Thắng sinh một Project có `lead_id`: ngày ghi nhận =
    # ngày tạo dự án (giờ VN), giá trị = `total_value`, thiếu thì TK + TC. Loại
    # suy từ `project_type` (chỉ thi công → thi_cong, còn lại → thiet_ke).
    # Chặn dưới cho truy vấn: màn này không bao giờ cần dự án cũ hơn mốc sớm
    # nhất trong hai thứ — đầu kỳ so sánh, và đầu của 6 tháng-liền-trước (tức 11
    # tháng trước tháng hiện tại) mà ô «Tổng doanh thu chu kỳ» dùng. Không chặn
    # thì mỗi lần mở bảng là kéo về TOÀN BỘ dự án từ ngày khai trương.
    moc_cu_nhat = hom_nay_vn.replace(day=1)
    for _ in range(11):
        moc_cu_nhat = (moc_cu_nhat - timedelta(days=1)).replace(day=1)
    for m in (truoc_dau, ngay_dau):
        if m and m < moc_cu_nhat:
            moc_cu_nhat = m

    q_hd = (
        select(
            Project.total_value, Project.design_value, Project.construction_value,
            Project.created_at, Project.project_type, Project.sales_id,
        )
        .where(Project.lead_id.is_not(None), Project.status != "cancelled")
    )
    if tu or den:
        # Lọc chính xác theo ngày VN làm ở Python ngay dưới
        q_hd = q_hd.where(Project.created_at >= khoang_ngay(moc_cu_nhat.isoformat(), None)[0])
    hd_rows = (await db.execute(q_hd)).mappings().all()

    hop_dong = []
    for r in hd_rows:
        if team_id and (r["sales_id"] not in nguoi_trong_nhom):
            continue
        ngay = _ngay_vn(r["created_at"])
        if ngay is None:
            continue
        hop_dong.append({
            "ngay": ngay,
            "gia_tri": float(r["total_value"] or 0)
            or float(r["design_value"] or 0) + float(r["construction_value"] or 0),
            "loai": "thi_cong" if r["project_type"] == "construction_only" else "thiet_ke",
            "sales_id": r["sales_id"],
        })

    def hd_trong(d1: date | None, d2: date | None):
        if d1 is None or d2 is None:
            return hop_dong
        return [h for h in hop_dong if d1 <= h["ngay"] <= d2]

    hd_ky = hd_trong(ngay_dau, ngay_het)
    hd_truoc = hd_trong(truoc_dau, truoc_het)

    # ── Thẻ KPI ──────────────────────────────────────────────────────────────
    he_so_thang = so_thang_phu(ngay_dau, ngay_het) if ngay_dau and ngay_het else 1.0

    def the_kpi(ten: str, thuc_te: float, truoc: float, mt_thang: float,
                don_vi: str, nguyen_thang: bool = True) -> dict:
        """Một thẻ KPI: thực tế, mục tiêu kỳ, % hoàn thành, và so với kỳ trước.

        `muc_tieu_tien_do` là mục tiêu đã chia theo số ngày ĐÃ TRÔI QUA của kỳ
        — để phân biệt «mới đạt 21% vì mới ngày 14» với «đang thật sự chậm».
        """
        mt_ky = mt_thang * he_so_thang
        da_troi = (min(hom_nay_vn, ngay_het) - ngay_dau).days + 1 if ngay_dau and ngay_het else 0
        tien_do = (
            muc_tieu_trong_ky(mt_thang, ngay_dau, min(hom_nay_vn, ngay_het))
            if ngay_dau and ngay_het and da_troi > 0 else 0.0
        )
        return {
            "ma": ten,
            "thuc_te": round(thuc_te, 2) if don_vi == "%" else thuc_te,
            "muc_tieu": round(mt_ky, 2),
            "muc_tieu_thang": mt_thang,
            "muc_tieu_tien_do": round(tien_do, 2),
            "phan_tram": _ty_le(thuc_te, mt_ky),
            "ky_truoc": round(truoc, 2) if don_vi == "%" else truoc,
            "delta_pct": _ty_le(thuc_te - truoc, truoc) if truoc else None,
            "dat_tien_do": thuc_te >= tien_do if tien_do else None,
            "don_vi": don_vi,
        }

    doanh_thu = sum(h["gia_tri"] for h in hd_ky)
    doanh_thu_truoc = sum(h["gia_tri"] for h in hd_truoc)
    hd_tk = sum(1 for h in hd_ky if h["loai"] == "thiet_ke")
    hd_tc = sum(1 for h in hd_ky if h["loai"] == "thi_cong")
    khao_sat = sum(1 for l in leads if l["survey_date"])
    khao_sat_truoc = sum(1 for l in leads_truoc if l["survey_date"])

    def ty_le_lien_he(ds) -> float:
        da_goi = [l for l in ds if l["do_sau"] >= 1]
        return _ty_le(sum(1 for l in da_goi if l["contact_status"] == "reachable"), len(da_goi))

    kpi = [
        the_kpi("doanh_thu", doanh_thu, doanh_thu_truoc, float(muc_tieu["doanh_thu_thang"]), "vnd"),
        the_kpi("hd_thiet_ke", hd_tk, sum(1 for h in hd_truoc if h["loai"] == "thiet_ke"),
                float(muc_tieu["hd_thiet_ke_thang"]), "hop_dong"),
        the_kpi("hd_thi_cong", hd_tc, sum(1 for h in hd_truoc if h["loai"] == "thi_cong"),
                float(muc_tieu["hd_thi_cong_thang"]), "hop_dong"),
        the_kpi("khach_khao_sat", khao_sat, khao_sat_truoc,
                float(muc_tieu["khach_khao_sat_thang"]), "khach"),
    ]
    # Tỷ lệ liên hệ là NGƯỠNG SÀN, không phải chỉ tiêu cộng dồn — không chia
    # theo ngày, không nhân theo số tháng.
    tl_lien_he = ty_le_lien_he(leads)
    nguong = float(muc_tieu["ty_le_lien_he_toi_thieu"])
    kpi.append({
        "ma": "ty_le_lien_he", "thuc_te": tl_lien_he, "muc_tieu": nguong,
        "muc_tieu_thang": nguong, "muc_tieu_tien_do": nguong,
        "phan_tram": _ty_le(tl_lien_he, nguong),
        "ky_truoc": ty_le_lien_he(leads_truoc),
        "delta_pct": (_ty_le(tl_lien_he - ty_le_lien_he(leads_truoc), ty_le_lien_he(leads_truoc))
                      if ty_le_lien_he(leads_truoc) else None),
        "dat_tien_do": tl_lien_he >= nguong, "don_vi": "%", "la_nguong": True,
    })

    # ── Doanh số 6 tháng gần nhất ────────────────────────────────────────────
    moc_thang = hom_nay_vn.replace(day=1)
    cac_thang: list[date] = []
    m = moc_thang
    for _ in range(6):
        cac_thang.append(m)
        m = (m - timedelta(days=1)).replace(day=1)
    cac_thang.reverse()

    theo_thang = []
    for t in cac_thang:
        cuoi = t.replace(day=monthrange(t.year, t.month)[1])
        tong = sum(h["gia_tri"] for h in hop_dong if t <= h["ngay"] <= cuoi)
        theo_thang.append({
            "thang": t.strftime("%Y-%m"),
            "nhan": f"T{t.month:02d}",
            "thuc_te": tong,
            "muc_tieu": float(muc_tieu["doanh_thu_thang"]),
        })

    # 6 tháng liền trước, để nói «+28% so với 6 tháng trước» có căn cứ
    dau_6 = cac_thang[0]
    truoc_6_het = dau_6 - timedelta(days=1)
    truoc_6_dau = truoc_6_het.replace(day=1)
    for _ in range(5):
        truoc_6_dau = (truoc_6_dau - timedelta(days=1)).replace(day=1)
    tong_6 = sum(x["thuc_te"] for x in theo_thang)
    tong_6_truoc = sum(h["gia_tri"] for h in hop_dong if truoc_6_dau <= h["ngay"] <= truoc_6_het)
    co_so = [x for x in theo_thang if x["thuc_te"] > 0]
    chu_ky = {
        "tong": tong_6,
        "trung_binh": round(tong_6 / 6),
        "delta_pct": _ty_le(tong_6 - tong_6_truoc, tong_6_truoc) if tong_6_truoc else None,
        "cao_nhat": max(co_so, key=lambda x: x["thuc_te"]) if co_so else None,
        "thap_nhat": min(co_so, key=lambda x: x["thuc_te"]) if co_so else None,
    }

    # ── Chất lượng data marketing ────────────────────────────────────────────
    tong_data = len(leads)
    dem_ro = {k: 0 for k in NHAN_CHAT_LUONG}
    for l in leads:
        dem_ro[l["ro"]] += 1
    chat_luong = {
        "tong": tong_data,
        "delta_pct": _ty_le(tong_data - len(leads_truoc), len(leads_truoc)) if leads_truoc else None,
        "ro": [
            {"ma": k, "nhan": NHAN_CHAT_LUONG[k], "so_luong": v, "phan_tram": _ty_le(v, tong_data)}
            for k, v in dem_ro.items()
        ],
    }

    # Mọi khối hiệu suất bên dưới CHỈ tính data đạt tiêu chuẩn — chấm nhân viên
    # bằng cả data rác thì người nhận nhiều data tỉnh/số sai bị oan.
    dat_chuan = [l for l in leads if l["ro"] == "dat_tieu_chuan"]

    # ── Phễu bán hàng ────────────────────────────────────────────────────────
    goc = len(dat_chuan)
    pheu = []
    truoc_buoc = None
    for i, (ma, nhan) in enumerate(BUOC_PHEU):
        n = sum(1 for l in dat_chuan if l["do_sau"] >= i)
        pheu.append({
            "ma": ma, "nhan": nhan, "so_luong": n,
            "phan_tram_goc": _ty_le(n, goc),
            "phan_tram_buoc_truoc": _ty_le(n, truoc_buoc) if truoc_buoc is not None else None,
        })
        truoc_buoc = n

    # ── Hiệu suất theo nhóm ──────────────────────────────────────────────────
    # Nhóm KHÔNG có lead trong kỳ vẫn phải hiện 1 dòng số 0 (cùng lý do vì sao
    # /executive đặt điều kiện kỳ vào ON của outerjoin): im lặng biến mất khỏi
    # bảng là cách nhanh nhất để một nhóm đứng im mà không ai thấy.
    ds_nhom = [team_id] if team_id else list(ten_nhom.keys())
    hieu_suat_nhom = []
    for tid in ds_nhom:
        cua_nhom = [l for l in leads if l["team_id"] == tid]
        chuan_nhom = [l for l in cua_nhom if l["ro"] == "dat_tieu_chuan"]
        thanh_vien = {i for i, t in nhom_cua_nguoi.items() if t == tid}
        ds_mt = (muc_tieu.get("theo_nhom") or {}).get(tid) or {}
        mt_nhom = float(ds_mt.get("doanh_thu_thang") or 0) * he_so_thang
        dthu_nhom = sum(h["gia_tri"] for h in hd_ky if h["sales_id"] in thanh_vien)
        hieu_suat_nhom.append({
            "team_id": tid,
            "nhom": ten_nhom.get(tid, "Chưa có nhóm"),
            "data_nhan": len(cua_nhom),
            "dat_tieu_chuan": len(chuan_nhom),
            "pct_dat": _ty_le(len(chuan_nhom), len(cua_nhom)),
            "khach_tinh": sum(1 for l in cua_nhom if l["ro"] == "khach_tinh"),
            "ngan_sach_thap": sum(1 for l in cua_nhom if l["ro"] == "ngan_sach_thap"),
            "khong_dat": sum(1 for l in cua_nhom if l["ro"] == "khong_dat"),
            "lien_he": sum(1 for l in chuan_nhom if l["do_sau"] >= 1),
            "khao_sat": sum(1 for l in chuan_nhom if l["do_sau"] >= 4),
            "bao_gia": sum(1 for l in chuan_nhom if l["do_sau"] >= 5),
            "ky_hd": sum(1 for l in chuan_nhom if l["do_sau"] >= 7),
            "doanh_so": dthu_nhom,
            "muc_tieu": round(mt_nhom, 2),
            "pct_muc_tieu": _ty_le(dthu_nhom, mt_nhom) if mt_nhom else None,
        })
    hieu_suat_nhom.sort(key=lambda x: x["doanh_so"], reverse=True)

    # Lead chưa gắn nhóm vẫn phải lộ ra, không được rụng khỏi tổng
    chua_nhom = [l for l in leads if not l["team_id"]]
    if chua_nhom and not team_id:
        hieu_suat_nhom.append({
            "team_id": None, "nhom": "Chưa gắn nhóm",
            "data_nhan": len(chua_nhom),
            "dat_tieu_chuan": sum(1 for l in chua_nhom if l["ro"] == "dat_tieu_chuan"),
            "pct_dat": _ty_le(sum(1 for l in chua_nhom if l["ro"] == "dat_tieu_chuan"), len(chua_nhom)),
            "khach_tinh": sum(1 for l in chua_nhom if l["ro"] == "khach_tinh"),
            "ngan_sach_thap": sum(1 for l in chua_nhom if l["ro"] == "ngan_sach_thap"),
            "khong_dat": sum(1 for l in chua_nhom if l["ro"] == "khong_dat"),
            "lien_he": sum(1 for l in chua_nhom if l["do_sau"] >= 1),
            "khao_sat": sum(1 for l in chua_nhom if l["do_sau"] >= 4),
            "bao_gia": sum(1 for l in chua_nhom if l["do_sau"] >= 5),
            "ky_hd": sum(1 for l in chua_nhom if l["do_sau"] >= 7),
            "doanh_so": 0, "muc_tieu": 0, "pct_muc_tieu": None,
        })

    # ── Hiệu suất từng nhân viên ─────────────────────────────────────────────
    nv: dict[str, dict] = {}
    for l in dat_chuan:
        uid = l["assigned_to"]
        if not uid:
            continue
        o = nv.setdefault(uid, {
            "user_id": uid, "ten": ten_nguoi.get(uid, "—"),
            "nhom": ten_nhom.get(nhom_cua_nguoi.get(uid) or "", "Chưa có nhóm"),
            "data": 0, "lien_he": 0, "khao_sat": 0, "bao_gia": 0, "ky_hd": 0,
            "ton_qua_han": 0, "tong_ngay_cho": 0, "co_moc_cho": 0, "doanh_so": 0.0,
        })
        o["data"] += 1
        o["lien_he"] += 1 if l["do_sau"] >= 1 else 0
        o["khao_sat"] += 1 if l["do_sau"] >= 4 else 0
        o["bao_gia"] += 1 if l["do_sau"] >= 5 else 0
        o["ky_hd"] += 1 if l["do_sau"] >= 7 else 0
        if l["stage"] in STAGE_DANG_MO:
            moc = l["last_contacted_at"] or l["created_at"]
            ngay_cho = (now - (moc if moc.tzinfo else moc.replace(tzinfo=timezone.utc))).days
            o["tong_ngay_cho"] += max(ngay_cho, 0)
            o["co_moc_cho"] += 1
            if l["last_contacted_at"] is None and ngay_cho >= 3:
                o["ton_qua_han"] += 1
    for h in hd_ky:
        if h["sales_id"] in nv:
            nv[h["sales_id"]]["doanh_so"] += h["gia_tri"]

    mt_nguoi_thang = (
        float(muc_tieu["doanh_thu_thang"]) / max(len([u for u in nguoi_rows if u[3]]), 1)
    )
    mt_nguoi = mt_nguoi_thang * he_so_thang
    for o in nv.values():
        o["pct_khao_sat"] = _ty_le(o["khao_sat"], o["data"])
        o["pct_bao_gia"] = _ty_le(o["bao_gia"], o["data"])
        o["pct_ky"] = _ty_le(o["ky_hd"], o["data"])
        o["pct_muc_tieu"] = _ty_le(o["doanh_so"], mt_nguoi)
        o["ngay_cho_tb"] = round(o["tong_ngay_cho"] / o["co_moc_cho"], 1) if o["co_moc_cho"] else 0

    top_nv = sorted(nv.values(), key=lambda x: (-x["doanh_so"], -x["ky_hd"]))[:10]

    # ── Nhân viên cần hỗ trợ ─────────────────────────────────────────────────
    # Chỉ xét người có đủ data để kết luận (≥5), và nêu VẤN ĐỀ CỤ THỂ kèm số —
    # «cần hỗ trợ» không kèm lý do thì trưởng nhóm không biết dạy cái gì.
    NGUONG_DU_DATA = 5
    can_ho_tro = []
    for o in nv.values():
        if o["data"] < NGUONG_DU_DATA:
            continue
        van_de = []
        if o["ton_qua_han"] > 0:
            van_de.append({"ma": "ton_data", "nhan": f"{o['ton_qua_han']} data chưa liên hệ sau 3 ngày", "muc_do": "gap"})
        if o["khao_sat"] == 0:
            van_de.append({"ma": "chua_khao_sat", "nhan": "Chưa có khảo sát nào", "muc_do": "gap"})
        elif o["pct_khao_sat"] < 15:
            van_de.append({"ma": "khao_sat_thap", "nhan": f"Tỷ lệ khảo sát thấp ({o['pct_khao_sat']}%)", "muc_do": "canh_bao"})
        if o["khao_sat"] > 0 and o["pct_bao_gia"] < 20:
            van_de.append({"ma": "bao_gia_thap", "nhan": f"Tỷ lệ báo giá thấp ({o['pct_bao_gia']}%)", "muc_do": "canh_bao"})
        if o["ngay_cho_tb"] >= 7:
            van_de.append({"ma": "follow_up", "nhan": f"Follow-up chậm (trung bình {o['ngay_cho_tb']} ngày)", "muc_do": "canh_bao"})
        if van_de:
            can_ho_tro.append({**o, "van_de": van_de, "van_de_chinh": van_de[0]["nhan"]})
    can_ho_tro.sort(key=lambda x: (-len(x["van_de"]), x["doanh_so"]))
    can_ho_tro = can_ho_tro[:10]

    # ── Cảnh báo & việc cần làm ──────────────────────────────────────────────
    canh_bao = []

    def them_canh_bao(ma, tieu_de, so_luong, nhan_hd, muc_do, metric=None):
        if so_luong:
            canh_bao.append({
                "ma": ma, "tieu_de": tieu_de, "so_luong": so_luong,
                "nhan_hanh_dong": nhan_hd, "muc_do": muc_do, "metric": metric,
            })

    def tuoi_ngay(l) -> int:
        moc = l["created_at"]
        return (now - (moc if moc.tzinfo else moc.replace(tzinfo=timezone.utc))).days

    def ngay_tu_lien_he(l) -> int | None:
        if not l["last_contacted_at"]:
            return None
        moc = l["last_contacted_at"]
        return (now - (moc if moc.tzinfo else moc.replace(tzinfo=timezone.utc))).days

    bao_gia_treo = [
        l for l in dat_chuan
        if l["do_sau"] >= 5 and l["stage"] in STAGE_DANG_MO
        and (ngay_tu_lien_he(l) is None or ngay_tu_lien_he(l) >= 7)
    ]
    them_canh_bao("bao_gia_treo", "khách đã báo giá quá 7 ngày chưa follow",
                  len(bao_gia_treo), "Cần xử lý ngay", "gap", "leads_by_stage")
    chua_lien_he = [l for l in dat_chuan if l["do_sau"] < 1 and tuoi_ngay(l) >= 1]
    them_canh_bao("sla_24h", "data chưa liên hệ sau 24 giờ",
                  len(chua_lien_he), "Vi phạm SLA", "gap", "leads_by_stage")
    ton_30 = [l for l in dat_chuan if l["stage"] in STAGE_DANG_MO and tuoi_ngay(l) >= 30]
    them_canh_bao("ton_30_ngay", "lead mở quá 30 ngày chưa chốt",
                  len(ton_30), "Rà soát & quyết định đóng", "canh_bao")
    them_canh_bao("khach_tinh", f"data khách tỉnh ({_ty_le(dem_ro['khach_tinh'], tong_data)}% tổng data)",
                  dem_ro["khach_tinh"], "Cần phân tích nguồn", "theo_doi")
    them_canh_bao("ngan_sach_thap", f"data ngân sách thấp ({_ty_le(dem_ro['ngan_sach_thap'], tong_data)}% tổng data)",
                  dem_ro["ngan_sach_thap"], "Cần phân tích kịch bản", "theo_doi")
    them_canh_bao("khong_dat", f"data không đạt tiêu chuẩn ({_ty_le(dem_ro['khong_dat'], tong_data)}% tổng data)",
                  dem_ro["khong_dat"], "Cập nhật tiêu chí lọc", "theo_doi")
    thieu_phan_cong = [l for l in dat_chuan if not l["assigned_to"]]
    them_canh_bao("chua_phan_cong", "data đạt chuẩn chưa có người phụ trách",
                  len(thieu_phan_cong), "Chia data ngay", "gap")
    MUC_DO_UU_TIEN = {"gap": 0, "canh_bao": 1, "theo_doi": 2}
    canh_bao.sort(key=lambda x: (MUC_DO_UU_TIEN[x["muc_do"]], -x["so_luong"]))

    # ─────────────────────────────────────────────────────────────────────────
    # 6 khối ĐỀ XUẤT THÊM — không có trong dashboard mẫu, dựng được vì dữ liệu
    # đã sẵn trong CSDL mà chưa chỗ nào hiển thị.
    # ─────────────────────────────────────────────────────────────────────────

    # (1) Tốc độ pipeline. KHÔNG phải «thời gian nằm ở mỗi bước» — hệ thống chưa
    # lưu lịch sử chuyển bước nên không tính nổi. Đây là TUỔI TRUNG BÌNH của
    # lead đang đứng ở mỗi bước: bước nào tuổi cao là bước đang bị ứ.
    toc_do = []
    for st in STAGE_DANG_MO + ["signed_design"]:
        o_buoc = [l for l in dat_chuan if l["stage"] == st]
        toc_do.append({
            "stage": st, "nhan": STAGE_LABELS.get(st, st), "so_luong": len(o_buoc),
            "tuoi_tb": round(sum(tuoi_ngay(l) for l in o_buoc) / len(o_buoc), 1) if o_buoc else 0,
            "tuoi_max": max((tuoi_ngay(l) for l in o_buoc), default=0),
        })

    # (2) Tồn kho lead theo tuổi — nhìn ra khối data đang nguội dần
    RO_TUOI = [(0, 7, "0–7 ngày"), (8, 30, "8–30 ngày"), (31, 90, "31–90 ngày"), (91, 10**6, "Trên 90 ngày")]
    dang_mo = [l for l in dat_chuan if l["stage"] in STAGE_DANG_MO]
    ton_kho = []
    for lo, hi, nhan in RO_TUOI:
        trong_ro = [l for l in dang_mo if lo <= tuoi_ngay(l) <= hi]
        ton_kho.append({
            "nhan": nhan, "so_luong": len(trong_ro),
            "phan_tram": _ty_le(len(trong_ro), len(dang_mo)),
            "gia_tri": sum(gia_tri_lead(l) for l in trong_ro),
        })

    # (3) Chuyển đổi theo nguồn — biết nguồn nào đáng tiêu thêm tiền marketing
    theo_nguon: dict[str, dict] = {}
    for l in leads:
        k = l["source"] or "khong_ro"
        o = theo_nguon.setdefault(k, {"nguon": k, "tong": 0, "dat_chuan": 0, "khao_sat": 0, "ky_hd": 0, "gia_tri": 0.0})
        o["tong"] += 1
        if l["ro"] == "dat_tieu_chuan":
            o["dat_chuan"] += 1
            o["khao_sat"] += 1 if l["do_sau"] >= 4 else 0
            if l["do_sau"] >= 7:
                o["ky_hd"] += 1
                o["gia_tri"] += gia_tri_lead(l)
    nguon_ds = sorted(theo_nguon.values(), key=lambda x: -x["tong"])
    for o in nguon_ds:
        o["pct_dat_chuan"] = _ty_le(o["dat_chuan"], o["tong"])
        o["pct_ky"] = _ty_le(o["ky_hd"], o["dat_chuan"])

    # (4) Dự báo có trọng số — pipeline đang mở × xác suất thắng từng bước
    du_bao_buoc = []
    for st in STAGE_DANG_MO:
        o_buoc = [l for l in dat_chuan if l["stage"] == st]
        gt = sum(gia_tri_lead(l) for l in o_buoc)
        du_bao_buoc.append({
            "stage": st, "nhan": STAGE_LABELS.get(st, st), "so_luong": len(o_buoc),
            "gia_tri": gt, "xac_suat": XAC_SUAT_STAGE[st], "du_bao": gt * XAC_SUAT_STAGE[st],
        })
    du_bao = {
        "gia_tri_pipeline": sum(x["gia_tri"] for x in du_bao_buoc),
        "du_bao_co_trong_so": round(sum(x["du_bao"] for x in du_bao_buoc)),
        "theo_buoc": du_bao_buoc,
        "con_thieu": max(float(muc_tieu["doanh_thu_thang"]) * he_so_thang - doanh_thu, 0),
    }

    # (5) Lý do mất lead — cột `lost_reason` có dữ liệu từ 27/08 mà chưa màn
    # hình nào đọc tới
    ly_do: dict[str, int] = {}
    mat = [l for l in leads if l["stage"] == "lost"]
    for l in mat:
        ly_do[(l["lost_reason"] or "Không ghi lý do").strip()] = ly_do.get(
            (l["lost_reason"] or "Không ghi lý do").strip(), 0
        ) + 1
    ly_do_mat = [
        {"ly_do": k, "so_luong": v, "phan_tram": _ty_le(v, len(mat))}
        for k, v in sorted(ly_do.items(), key=lambda kv: -kv[1])
    ]

    # (6) Phân khúc theo mức ngân sách — ô này thêm 22/09 và tới nay chưa dùng
    NHAN_NGAN_SACH = {
        "duoi_200": "Dưới 200 triệu", "tu_200_500": "Từ 200–500 triệu",
        "tren_500": "Trên 500 triệu", "khong_ro": "Chưa ghi ngân sách",
    }
    theo_ngan_sach = []
    for k, nhan in NHAN_NGAN_SACH.items():
        trong_muc = [l for l in leads if (l["ngan_sach_khoang"] or "khong_ro") == k]
        ky = [l for l in trong_muc if l["do_sau"] >= 7]
        theo_ngan_sach.append({
            "muc": k, "nhan": nhan, "tong": len(trong_muc),
            "phan_tram": _ty_le(len(trong_muc), tong_data),
            "ky_hd": len(ky), "pct_ky": _ty_le(len(ky), len(trong_muc)),
            "gia_tri": sum(gia_tri_lead(l) for l in ky),
        })

    return {
        "ky": {
            "tu": tu, "den": den, "so_ngay": so_ngay_ky,
            "ky_truoc_tu": truoc_dau.isoformat() if truoc_dau else None,
            "ky_truoc_den": truoc_het.isoformat() if truoc_het else None,
            "he_so_thang": round(he_so_thang, 3),
        },
        "team_id": team_id,
        "danh_sach_nhom": [{"id": i, "ten": n} for i, n in nhom_rows],
        "cap_nhat_luc": now.isoformat(),
        "muc_tieu": muc_tieu,
        "kpi": kpi,
        "chu_ky_6_thang": chu_ky,
        "doanh_so_theo_thang": theo_thang,
        "chat_luong_data": chat_luong,
        "hieu_suat_nhom": hieu_suat_nhom,
        "pheu": pheu,
        "top_nhan_vien": top_nv,
        "can_ho_tro": can_ho_tro,
        "canh_bao": canh_bao,
        # Đề xuất thêm
        "toc_do_pipeline": toc_do,
        "ton_kho_lead": ton_kho,
        "theo_nguon": nguon_ds,
        "du_bao": du_bao,
        "ly_do_mat": ly_do_mat,
        "theo_ngan_sach": theo_ngan_sach,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Thiết lập mục tiêu
# ─────────────────────────────────────────────────────────────────────────────

class MucTieuIn(BaseModel):
    doanh_thu_thang: float = Field(ge=0)
    hd_thiet_ke_thang: int = Field(ge=0)
    hd_thi_cong_thang: int = Field(ge=0)
    khach_khao_sat_thang: int = Field(ge=0)
    ty_le_lien_he_toi_thieu: float = Field(ge=0, le=100)
    khu_vuc_trong_tam: list[str] = Field(default_factory=lambda: ["TP. Hồ Chí Minh"])
    theo_nhom: dict[str, dict[str, float]] = Field(default_factory=dict)


@router.get("/muc-tieu")
async def xem_muc_tieu(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _chan_neu_khong_duoc_xem(current_user)
    return await doc_muc_tieu(db)


@router.put("/muc-tieu")
async def luu_muc_tieu(
    payload: MucTieuIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ghi mục tiêu tháng. Phải xóa cache `dashboard` ngay, nếu không người sửa
    mục tiêu sẽ thấy % cũ đứng im tới 2 phút rồi tưởng là lưu không ăn."""
    _chan_neu_khong_duoc_xem(current_user)
    gia_tri = json.dumps(payload.model_dump(), ensure_ascii=False)
    setting = await db.get(SystemSetting, SALES_TARGETS_KEY)
    if setting:
        setting.value = gia_tri
    else:
        db.add(SystemSetting(key=SALES_TARGETS_KEY, value=gia_tri))
    await db.commit()
    cache.clear_prefix("dashboard")
    return await doc_muc_tieu(db)
