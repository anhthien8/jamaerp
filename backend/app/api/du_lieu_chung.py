"""Dữ liệu chung — CRM phản ánh thực tế tới đâu (BGĐ) + Đối chiếu (trưởng phòng).

Dựng 20/11/2026 theo spec «Dữ liệu chung v1» (thiết kế 1 bằng chứng trước, ghép
câu chính + 3 thẻ «Hôm nay» + trang đối chiếu của thiết kế 3).

Vì sao có màn hình này: 4 phòng báo cáo bằng PDF riêng, cùng một khách mà mỗi
phòng ghi một trạng thái. Đo prod 20/11: Kinh doanh cập nhật CRM hằng ngày, ba
phòng còn lại gần như không (5 task_activities tổng cộng). Trang này ĐO chứ không
phạt — chỉ số mới 2 tháng đầu chỉ đo, không đưa vào thưởng.

Nguyên tắc không được phá:
  • Vắng dấu vết KHÔNG BAO GIỜ bị gọi là «lệch» và không có trạng thái «không làm»
    — «chưa cập nhật» = CRM chưa có dấu vết, không có nghĩa là không làm.
  • Không dùng `projects.updated_at`, `leads.updated_at`, `last_contacted_at`:
    hệ thống tự ghi (đồng bộ tài chính, topic Telegram, job thu hồi lead) nên nhiễu.
  • Dấu vết gán theo PHÒNG CỦA NGƯỜI LÀM trước; chỉ khi người đó không thuộc 4
    phòng mới rơi về phòng của đầu việc — luồng /baocao gắn hoạt động vào
    `tasks[0]` (việc thiết kế) nên gán theo đầu việc sẽ làm Thiết kế «tươi» nhờ
    báo cáo của Thi công.
  • Không module nào trong kpi_engine / che_do_thuong / payroll được đọc điểm này
    (có test grep chặn).
  • Không lưu lịch sử điểm, không xếp hạng cá nhân, không job gửi tự động.

Không migration: ngưỡng ở SystemSetting `du_lieu_chung`, lịch sử đối chiếu và
đổi giai đoạn ở `audit_logs` có sẵn.

21/11/2026 — kênh nhận thông báo: đo prod chỉ 2/63 người bật thông báo trên máy,
6 người liên kết Telegram; trưởng phòng Thi công chỉ thấy tin trong chuông. GET
trả thêm `kenh_thong_bao` + `truong_phong[].co_thong_bao_may`; tin nhắc gửi người
chưa bật thông báo kèm dòng mời cài app; `POST /nhac-cai-app` nhắc riêng việc cài
app + bật thông báo (loại `nhac_cai_app`, 1 tin/người/ngày VN).

26/11/2026 (vòng 4) — trưởng 4 phòng được XEM trang chính cùng BGĐ. CHỈ XEM, không
mở rộng quyền vốn có: bản của trưởng phòng là bản BGĐ đem LỌC (`_loc_cho_truong_phong`,
không tính lại) nên số tổng hợp giống hệt BGĐ; tiền ẩn (None) và danh sách không xếp
theo tiền; dòng chi tiết chỉ còn dự án/lead người đó vốn đã thấy ở trang Dự án/Lead (lọc
phạm vi TRƯỚC rồi mới cắt 50/200 dòng); GET trả `nguoi_xem` để giao diện khỏi tự suy
quyền. Các POST nhắc vẫn chỉ BGĐ.
"""

from __future__ import annotations

import copy
import html
import json
from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import and_, case, distinct, exists, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import cache, cached
from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.rbac import (
    PIC_THEO_PHONG_BAN, VAI_TRO_BGD, VAI_TRO_TRUONG_PHONG, duoc_xem_lead, duoc_xem_lead_nay,
)
from app.models.audit import AuditLog
from app.models.contract import Contract
from app.models.lead import ACTIVE_LEAD_STAGES, Activity, Lead
from app.models.media import MediaFile, ProjectDocument
from app.models.notification import Notification
from app.models.project import Project, Task, TaskActivity, TaskAssignee
from app.models.push_subscription import PushSubscription
from app.models.quotation import Quotation
from app.models.user import User
from app.models.vat_tu import DongPhieuVatTu
from app.services.attendance_service import VN_TZ, get_setting_json, vn_today
from app.services.task_sla import PHONG_CONG_TY_THEO_PHONG_VIEC, _utc

router = APIRouter(prefix="/dashboard/du-lieu-chung", tags=["du-lieu-chung"])


# ── Hằng số ──────────────────────────────────────────────────────────────────

KHOA_CAU_HINH = "du_lieu_chung"
LOAI_THONG_BAO = "du_lieu_chung"
# Nhắc cài app + bật thông báo trên điện thoại (21/11/2026). Loại riêng nên KHÔNG
# tính vào giới hạn 2 tin `du_lieu_chung`/người/ngày.
LOAI_NHAC_CAI_APP = "nhac_cai_app"
DUONG_CAI_APP = "/cai-app"
TOI_DA_CHUA_BAT = 200

CAU_HINH_MAC_DINH: dict = {
    "moc_bat_dau": "2026-11-20",
    "chay_thu_ngay": 60,
    "cua_so": {
        # Khớp OVERDUE_DAYS_BY_STAGE ở frontend/src/components/leads/shared.tsx
        "lead": {"new": 3, "interested": 7, "surveyed": 5, "survey_scheduled": 7, "potential": 14},
        "DESIGN": 14,
        "PURCHASING": 10,
        "OPS": 7,            # đang thi công
        "OPS_ban_giao": 14,  # đang bàn giao (acceptance)
    },
    "ngay_doi_chieu": 7,
    "lead_treo_ngay": 60,
    "toi_da_tin_ngay": 2,
}

PHONG_4 = ("SALES", "DESIGN", "PURCHASING", "OPS")
TEN_PHONG = {
    "SALES": "Kinh doanh",
    "DESIGN": "Thiết kế",
    "PURCHASING": "Dự toán – Thu mua",
    "OPS": "Thi công / Giám sát",
}
# Khối «Kênh nhận thông báo»: 4 phòng + mọi bộ phận khác (BGĐ, Kế toán, HR…)
PHONG_KENH = (*PHONG_4, "KHAC")
TEN_PHONG_KENH = {**TEN_PHONG, "KHAC": "Bộ phận khác"}

TRANG_THAI_CHAY = ("active", "paused")
GIAI_DOAN_LAM = ("design", "quotation", "procurement", "construction", "acceptance")
THU_TU_GIAI_DOAN = {s: i for i, s in enumerate(GIAI_DOAN_LAM)} | {"completed": len(GIAI_DOAN_LAM)}
CHU_GIAI_DOAN = {
    "design": "DESIGN",
    "quotation": "PURCHASING",
    "procurement": "PURCHASING",
    "construction": "OPS",
    "acceptance": "OPS",
}
GIAI_DOAN_CUA_PHONG = {
    "DESIGN": ("design",),
    "PURCHASING": ("quotation", "procurement"),
    "OPS": ("construction", "acceptance"),
}
NHAN_GIAI_DOAN = {
    "design": "Thiết kế",
    "quotation": "Báo giá/Dự toán",
    "procurement": "Thu mua",
    "construction": "Thi công",
    "acceptance": "Bàn giao",
    "completed": "Hoàn thành",
    "paused": "Chưa xếp giai đoạn",
}
NHAN_GIAI_DOAN_LEAD = {
    "new": "Tiếp nhận mới",
    "interested": "Đang tư vấn",
    "surveyed": "Đã khảo sát",
    "survey_scheduled": "Đã gửi báo giá",
    "potential": "Đang đàm phán",
    "signed_design": "Deal đã thắng",
    "lost": "Mất",
    "dormant": "Ngủ đông",
}

# Activity lead KHÔNG phải người thật chăm khách: job thu hồi ghi 'assignment',
# hệ thống/AI tự ghi, ký HĐ tự sinh khi Deal thắng.
LOAI_ACTIVITY_LEAD_BO = ("assignment", "lead_assigned", "system", "ai", "contract_signed")
# Đối chiếu lead chỉ xét deal đang chờ ký
LEAD_DOI_CHIEU = ("survey_scheduled", "potential")
# Lead đổi được ngay trên trang đối chiếu; muốn sang lost/signed_design thì vào /leads
LEAD_DOI_DUOC = (*ACTIVE_LEAD_STAGES, "dormant")

VAT_TU_DA_DAT = ("da_dat", "giao_thieu", "da_giao")
TASK_COORDINATOR_LIKE = "Task % created by Task Coordinator%"

NHAN_QUY_TAC = {
    "K1": "Lead có người phụ trách",
    "K2": "Lead có khu vực",
    "K3": "Lead có nguồn",
    "K4": "Lead có ngân sách",
    "K5": "Lead có ngày khảo sát",
    "K6": "Dự án có địa chỉ",
    "K7": "Dự án có sale phụ trách",
    "T1": "Có thiết kế phụ trách",
    "T2": "Việc thiết kế hiện tại có người làm",
    "P1": "Có người Dự toán – Thu mua phụ trách",
    "P2": "Có giá trị hoặc báo giá",
    "P3": "Việc báo giá/thu mua hiện tại có người làm",
    "C1": "Có giám sát phụ trách",
    "C2": "Có ngày khởi công",
    "C3": "Có hạn bàn giao",
    "C4": "Việc thi công hiện tại có người làm",
    "L1": "CRM chậm hơn thực tế",
    "L2": "Đã có dự án nhưng lead chưa ở «Deal đã thắng»",
    "L3": "Deal đã thắng nhưng chưa có dự án",
    "L4": "Tiến độ 100% nhưng chưa hoàn thành",
    "L5": "Ngày bàn giao/khởi công không khớp giai đoạn",
}
QUY_TAC_DU = {
    "SALES": ("K1", "K2", "K3", "K4", "K5", "K6", "K7"),
    "DESIGN": ("T1", "T2"),
    "PURCHASING": ("P1", "P2", "P3"),
    "OPS": ("C1", "C2", "C3", "C4"),
}
QUY_TAC_LECH = {
    "SALES": ("L2", "L3"),
    "DESIGN": ("L1",),
    "PURCHASING": ("L1",),
    "OPS": ("L1", "L4", "L5"),
}

NHAN_DAU_VET = {
    "hoat_dong": "Báo cáo/ghi chú việc",
    "viec": "Bắt đầu/xong đầu việc",
    "ban_ve": "Tải bản vẽ",
    "tai_lieu": "Tải tài liệu",
    "anh": "Ảnh công trình",
    "vat_tu": "Phiếu vật tư",
    "bao_gia": "Báo giá",
    "nhan_hang": "Nhận hàng",
    "de_xuat_vat_tu": "Đề xuất vật tư",
    "doi_giai_doan": "Đổi giai đoạn",
    "doi_chieu": "Đối chiếu",
    "lead": "Hoạt động lead",
    "tao_lead": "Tạo lead",
}

TOI_DA_CAN_XEM = 200
TOI_DA_CAN_XEM_MOI_PHONG = 50


# ── Tiện ích thời gian / người ───────────────────────────────────────────────

def _iso(dt: datetime | None) -> str | None:
    dt = _utc(dt)
    return dt.isoformat() if dt else None


def _ngay_vn(dt: datetime | None) -> date | None:
    dt = _utc(dt)
    return dt.astimezone(VN_TZ).date() if dt else None


def _dau_ngay_vn_utc(ngay: date) -> datetime:
    """00:00 giờ VN của `ngay`, đổi ra UTC naive — so với cột DateTime naive (UTC)."""
    return datetime.combine(ngay, time.min, VN_TZ).astimezone(timezone.utc).replace(tzinfo=None)


def phong_goc(user) -> str:
    """UPPER(department) nguyên gốc — 'PM' vẫn là 'PM'."""
    return (getattr(user, "department", None) or "").upper()


def phong_cua(user) -> str:
    """Phòng của user = UPPER(department); phòng 'PM' cũ coi là OPS.

    CHỈ dùng để GÁN DẤU VẾT và xét PIC Giám sát (C1) hợp lệ. Mọi chỗ cho phép
    HÀNH ĐỘNG (trưởng phòng, quyền /doi-chieu, người nhận nhắc, danh sách người
    trong phòng, pic_id) dùng `phong_goc` — vì các guard ghi dữ liệu dùng chung
    (la_truong_phong, _kiem_quyen_phan_cong_pic) đọc department nguyên gốc, đổi
    PM→OPS ở đây sẽ mời người dùng bấm những thao tác backend luôn từ chối.
    """
    d = phong_goc(user)
    return "OPS" if d == "PM" else d


def la_nguoi_that(user) -> bool:
    return bool(user) and bool(user.is_active) and user.role != "admin"


def la_truong_phong_cua(user, phong: str) -> bool:
    """Trưởng phòng ĐÚNG phòng `phong` — theo department nguyên gốc (PM không tính là OPS)."""
    return phong_goc(user) == phong and user.role in VAI_TRO_TRUONG_PHONG.get(phong, set())


def phong_truong_phong(user) -> str | None:
    p = phong_goc(user)
    return p if p in PHONG_4 and la_truong_phong_cua(user, p) else None


def _doc_json(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        v = json.loads(raw)
        return v if isinstance(v, dict) else {}
    except (TypeError, ValueError):
        return {}


async def doc_cau_hinh(db: AsyncSession) -> dict:
    """Cấu hình đã trộn mặc định (cua_so trộn sâu). Chỉ đọc, không ghi."""
    luu = await get_setting_json(db, KHOA_CAU_HINH)
    ch = json.loads(json.dumps(CAU_HINH_MAC_DINH))
    for k, v in (luu or {}).items():
        if k == "cua_so" and isinstance(v, dict):
            for k2, v2 in v.items():
                if k2 == "lead" and isinstance(v2, dict):
                    ch["cua_so"]["lead"].update(v2)
                else:
                    ch["cua_so"][k2] = v2
        else:
            ch[k] = v
    return ch


def _moc(ch: dict) -> date:
    try:
        return date.fromisoformat(str(ch.get("moc_bat_dau")))
    except (TypeError, ValueError):
        return date.fromisoformat(CAU_HINH_MAC_DINH["moc_bat_dau"])


# ── Điểm ─────────────────────────────────────────────────────────────────────

def muc_theo_diem(diem: int | None) -> str:
    if diem is None:
        return "it_ho_so"
    if diem >= 80:
        return "sat"
    if diem >= 50:
        return "can_bo_sung"
    return "chua_phan_anh"


def tinh_diem(thanh_phan: dict, so_ho_so: int) -> tuple[int | None, str]:
    """Điểm = round(trung bình các thành phần có mẫu số >0 và đang áp dụng).

    Phạm vi 0 → «Không có hồ sơ», <3 → «Ít hồ sơ» (diem=None). Không bao giờ
    trả 0 hay 100 giả.
    """
    if so_ho_so <= 0:
        return None, "khong_co_ho_so"
    if so_ho_so < 3:
        return None, "it_ho_so"
    pct = []
    for ten in ("du", "tuoi", "doi_chieu"):
        tp = thanh_phan.get(ten) or {}
        if ten == "doi_chieu" and not tp.get("ap_dung"):
            continue
        if (tp.get("tong") or 0) > 0:
            pct.append(tp["dat"] / tp["tong"] * 100)
    if not pct:
        return None, "it_ho_so"
    diem = int(round(sum(pct) / len(pct)))
    return diem, muc_theo_diem(diem)


# ── Nạp dữ liệu ──────────────────────────────────────────────────────────────

class _DauVet:
    __slots__ = ("luc", "loai", "nguoi")

    def __init__(self, luc: datetime, loai: str, nguoi: str | None):
        self.luc, self.loai, self.nguoi = luc, loai, nguoi


class _DuLieu:
    """Mọi thứ đã nạp + đã tính sẵn, dùng chung cho GET chính, /nhac, /doi-chieu."""


def _them_dau_vet(bang: dict, khoa, luc: datetime | None, loai: str, nguoi: str | None) -> None:
    luc = _utc(luc)
    if luc is None:
        return
    cu = bang.get(khoa)
    if cu is None or luc > cu.luc:
        bang[khoa] = _DauVet(luc, loai, nguoi)


async def _nap(db: AsyncSession) -> _DuLieu:  # noqa: C901 — một lượt nạp, tính bằng Python
    d = _DuLieu()
    d.ch = await doc_cau_hinh(db)
    d.now = datetime.now(timezone.utc)
    d.hom_nay = vn_today()
    now_naive = d.now.replace(tzinfo=None)
    d.cutoff30 = now_naive - timedelta(days=30)
    ngay_dc = int(d.ch.get("ngay_doi_chieu") or 7)
    d.ngay_dc = ngay_dc

    du_an_chay = select(Project.id).where(Project.status.in_(TRANG_THAI_CHAY))

    # Người dùng (cả người đã nghỉ, để hiện tên dấu vết cũ)
    d.users = {u.id: u for u in (await db.execute(select(
        User.id, User.full_name, User.role, User.department, User.is_active, User.telegram_user_id,
    ))).all()}
    # Ai đã bật «thông báo trên máy» (≥1 máy đăng ký Web Push) — 21/11/2026
    d.co_push = await _nguoi_co_push(db)

    # Dự án đang chạy — cột nhẹ
    d.projects = list((await db.execute(select(
        Project.id, Project.code, Project.name, Project.client_name, Project.address,
        Project.status, Project.stage, Project.total_value, Project.pm_id, Project.designer_id,
        Project.sales_id, Project.purchasing_id, Project.lead_id, Project.start_date,
        Project.target_end_date, Project.handover_date, Project.progress, Project.pause_reason,
        Project.bao_gia_sheet_url,
    ).where(Project.status.in_(TRANG_THAI_CHAY)))).all())
    d.pmap = {p.id: p for p in d.projects}

    d.hoan_thanh_30 = list((await db.execute(select(Project.id, Project.total_value).where(
        Project.status == "completed", Project.handover_date >= d.cutoff30,
    ))).all())

    # Đầu việc
    d.tasks = list((await db.execute(select(
        Task.id, Task.project_id, Task.title, Task.stage, Task.department, Task.status,
        Task.order, Task.assigned_to, Task.started_at, Task.completed_at, Task.final_file_versions,
    ).where(Task.project_id.in_(du_an_chay)))).all())
    d.tmap = {t.id: t for t in d.tasks}
    co_nguoi = set((await db.execute(select(distinct(TaskAssignee.task_id)).where(
        TaskAssignee.task_id.in_(select(Task.id).where(Task.project_id.in_(du_an_chay)))
    ))).scalars().all())
    d.tasks_theo_du_an: dict[str, list] = {}
    for t in d.tasks:
        d.tasks_theo_du_an.setdefault(t.project_id, []).append(t)
    for ds in d.tasks_theo_du_an.values():
        ds.sort(key=lambda t: (t.order or 0))
    d.task_co_nguoi = {t.id for t in d.tasks if t.assigned_to or t.id in co_nguoi}

    # ── Dấu vết dự án theo phòng: ev[(project_id, phong)] ──
    ev: dict = {}
    # L1: bằng chứng 30 ngày theo giai đoạn
    bc30: dict[str, tuple[str, str]] = {}  # project_id -> (giai_doan, mô tả)

    def _bc(pid: str, gd: str, mo_ta: str) -> None:
        cu = bc30.get(pid)
        if cu is None or THU_TU_GIAI_DOAN[gd] > THU_TU_GIAI_DOAN[cu[0]]:
            bc30[pid] = (gd, mo_ta)

    def _phong_theo_viec(task_dept: str | None, task_stage: str | None) -> str | None:
        # TaskCreate.department là chữ tự do ('DESIGN', 'Design'…) — hạ chữ như
        # task_sla._phong_cua_viec; không khớp thì rơi về giai đoạn của việc.
        return (PHONG_CONG_TY_THEO_PHONG_VIEC.get((task_dept or "").strip().lower())
                or PHONG_CONG_TY_THEO_PHONG_VIEC.get((task_stage or "").strip().lower()))

    def _phong_nguoi_hoac_viec(uid: str | None, task_dept, task_stage) -> str | None:
        u = d.users.get(uid) if uid else None
        if u is not None and phong_cua(u) in PHONG_4:
            return phong_cua(u)
        return _phong_theo_viec(task_dept, task_stage)

    # (a) task_activities — INNER JOIN users loại user 'system'; bỏ dòng Task Coordinator tự ghi
    for pid, uid, tdept, tstage, luc in (await db.execute(
        select(Task.project_id, TaskActivity.user_id, Task.department, Task.stage,
               func.max(TaskActivity.created_at))
        .join(Task, Task.id == TaskActivity.task_id)
        .join(User, User.id == TaskActivity.user_id)
        .where(Task.project_id.in_(du_an_chay), ~TaskActivity.content.like(TASK_COORDINATOR_LIKE))
        .group_by(Task.project_id, TaskActivity.user_id, Task.department, Task.stage)
    )).all():
        phong = _phong_nguoi_hoac_viec(uid, tdept, tstage)
        if phong:
            _them_dau_vet(ev, (pid, phong), luc, "hoat_dong", uid)
        u = d.users.get(uid)
        if u is not None and phong_cua(u) == "OPS" and _utc(luc) >= _utc(d.cutoff30):
            _bc(pid, "construction", "Giám sát báo cáo trên CRM")

    # (b) bắt đầu/xong đầu việc, (c) bản vẽ final — gán theo phòng của đầu việc
    for t in d.tasks:
        phong = _phong_theo_viec(t.department, t.stage)
        if phong:
            _them_dau_vet(ev, (t.project_id, phong), t.started_at, "viec", None)
            _them_dau_vet(ev, (t.project_id, phong), t.completed_at, "viec", None)
            for v in (t.final_file_versions or []) if isinstance(t.final_file_versions, list) else []:
                if isinstance(v, dict) and v.get("uploaded_at"):
                    try:
                        luc = datetime.fromisoformat(str(v["uploaded_at"]).replace("Z", "+00:00"))
                    except ValueError:
                        continue
                    _them_dau_vet(ev, (t.project_id, phong), luc, "ban_ve", None)
        if (t.status in ("done", "completed") and t.completed_at is not None
                and t.stage in THU_TU_GIAI_DOAN and _utc(t.completed_at) >= _utc(d.cutoff30)):
            _bc(t.project_id, t.stage,
                f"Việc «{t.title}» ({NHAN_GIAI_DOAN.get(t.stage, t.stage)}) xong {_ngay_vn(t.completed_at):%d/%m}")

    # (d) tài liệu dự án — phòng người tải, không thuộc 4 phòng thì theo đầu việc gắn kèm
    for pid, uid, tid, luc in (await db.execute(
        select(ProjectDocument.project_id, ProjectDocument.uploaded_by, ProjectDocument.task_id,
               func.max(ProjectDocument.created_at))
        .where(ProjectDocument.project_id.in_(du_an_chay))
        .group_by(ProjectDocument.project_id, ProjectDocument.uploaded_by, ProjectDocument.task_id)
    )).all():
        t = d.tmap.get(tid) if tid else None
        phong = _phong_nguoi_hoac_viec(uid, t.department if t else None, t.stage if t else None)
        if phong:
            _them_dau_vet(ev, (pid, phong), luc, "tai_lieu", uid)

    # (e) ảnh công trình — người tải không thuộc 4 phòng thì tính cho OPS
    d.anh_ops_30: set[str] = set()
    for pid, uid, luc in (await db.execute(
        select(MediaFile.project_id, MediaFile.uploaded_by, func.max(MediaFile.created_at))
        .where(MediaFile.project_id.in_(du_an_chay))
        .group_by(MediaFile.project_id, MediaFile.uploaded_by)
    )).all():
        u = d.users.get(uid) if uid else None
        phong = phong_cua(u) if u is not None and phong_cua(u) in PHONG_4 else "OPS"
        _them_dau_vet(ev, (pid, phong), luc, "anh", uid)
        if u is not None and phong_cua(u) == "OPS" and _utc(luc) >= _utc(d.cutoff30):
            _bc(pid, "construction", f"Ảnh công trình của Giám sát ngày {_ngay_vn(luc):%d/%m}")

    # (f)(g) vật tư
    for pid, cap_nhat, chot, dat, duyet, nhan, so_da_dat in (await db.execute(
        select(DongPhieuVatTu.project_id, func.max(DongPhieuVatTu.updated_at),
               func.max(DongPhieuVatTu.chot_luc), func.max(DongPhieuVatTu.dat_luc),
               func.max(DongPhieuVatTu.duyet_dat_luc), func.max(DongPhieuVatTu.nhan_luc),
               # L1 chỉ xét bằng chứng 30 ngày: dòng đã đặt/đã giao CŨ (dự án sau đó
               # quay lại báo giá/thiết kế để làm lại) không được thành lệch vĩnh viễn.
               func.sum(case((and_(
                   DongPhieuVatTu.trang_thai.in_(VAT_TU_DA_DAT),
                   func.coalesce(DongPhieuVatTu.dat_luc, DongPhieuVatTu.updated_at) >= d.cutoff30,
               ), 1), else_=0)))
        .where(DongPhieuVatTu.project_id.in_(du_an_chay))
        .group_by(DongPhieuVatTu.project_id)
    )).all():
        for luc in (cap_nhat, chot, dat, duyet):
            _them_dau_vet(ev, (pid, "PURCHASING"), luc, "vat_tu", None)
        _them_dau_vet(ev, (pid, "OPS"), nhan, "nhan_hang", None)
        if so_da_dat:
            _bc(pid, "procurement", "Có dòng vật tư đã đặt/đã giao trong 30 ngày")
    for pid, luc in (await db.execute(
        select(Quotation.project_id, func.max(Quotation.updated_at))
        .where(Quotation.project_id.in_(du_an_chay)).group_by(Quotation.project_id)
    )).all():
        _them_dau_vet(ev, (pid, "PURCHASING"), luc, "bao_gia", None)
    d.co_bao_gia_duyet = set((await db.execute(select(distinct(Quotation.project_id)).where(
        Quotation.project_id.in_(du_an_chay), Quotation.status == "approved",
    ))).scalars().all())
    from app.api.telegram_workflow import MaterialRequest
    for pid, luc in (await db.execute(
        select(MaterialRequest.project_id, func.max(MaterialRequest.created_at))
        .where(MaterialRequest.project_id.in_(du_an_chay)).group_by(MaterialRequest.project_id)
    )).all():
        _them_dau_vet(ev, (pid, "OPS"), luc, "de_xuat_vat_tu", None)

    # (h) audit: đối chiếu + đổi giai đoạn
    moc = _moc(d.ch)
    moc_naive = _dau_ngay_vn_utc(moc)
    cutoff_audit = min(moc_naive, now_naive - timedelta(days=60))
    d.doi_chieu: dict = {}       # (loai, id, phong) -> list[(luc, ket_qua, nguoi_id, ten)]
    d.doi_chieu_moi_nhat: dict = {}  # (loai, id) -> (luc, ket_qua, ten, phong) bất kể phòng
    d.da_xep_tu_moc: set[str] = set()
    for loai_th, eid, action, actor_id, actor_name, before, after, luc in (await db.execute(
        select(AuditLog.entity_type, AuditLog.entity_id, AuditLog.action, AuditLog.actor_id,
               AuditLog.actor_name, AuditLog.before_json, AuditLog.after_json, AuditLog.created_at)
        .where(AuditLog.entity_type.in_(("project", "lead")),
               or_(AuditLog.action.like("doi_chieu:%"), AuditLog.action == "doi_giai_doan"),
               AuditLog.created_at >= cutoff_audit)
        .order_by(AuditLog.created_at)
    )).all():
        loai = "du_an" if loai_th == "project" else "lead"
        sau = _doc_json(after)
        if action == "doi_giai_doan":
            if loai == "du_an":
                u = d.users.get(actor_id) if actor_id else None
                if u is not None and phong_cua(u) in PHONG_4:
                    _them_dau_vet(ev, (eid, phong_cua(u)), luc, "doi_giai_doan", actor_id)
                if (_doc_json(before).get("stage") == "paused" and sau.get("stage") != "paused"
                        and _utc(luc) >= _utc(moc_naive)):
                    d.da_xep_tu_moc.add(eid)
            continue
        phong = action.split(":", 1)[1] if ":" in action else ""
        kq = sau.get("ket_qua") or "dung"
        d.doi_chieu.setdefault((loai, eid, phong), []).append((_utc(luc), kq, actor_id, actor_name))
        d.doi_chieu_moi_nhat[(loai, eid)] = (_utc(luc), kq, actor_name, phong)
        # Đối chiếu có SỬA (không chỉ bấm «đúng») là một lần cập nhật CRM thật — gán
        # theo PHÒNG CỦA NGƯỜI BẤM (spec B2.2h), không theo phòng ghi trong action:
        # BGĐ sửa hộ OPS không được làm OPS «tươi» khi chưa ai ở OPS chạm CRM.
        # «Đúng» thì KHÔNG tính dấu vết — nó đi vào trạng thái «chưa cập nhật».
        if loai == "du_an" and (kq != "dung" or sau.get("pic_id")):
            u = d.users.get(actor_id) if actor_id else None
            if u is not None and phong_cua(u) in PHONG_4:
                _them_dau_vet(ev, (eid, phong_cua(u)), luc, "doi_chieu", actor_id)
    d.ev = ev
    d.bc30 = bc30

    # ── Lead ──
    d.leads = list((await db.execute(select(
        Lead.id, Lead.name, Lead.stage, Lead.assigned_to, Lead.region, Lead.source,
        Lead.ngan_sach_khoang, Lead.estimated_budget, Lead.survey_date, Lead.created_at,
        Lead.design_contract_value, Lead.deal_value, Lead.address, Lead.team_id,
    ).where(Lead.stage.in_(ACTIVE_LEAD_STAGES)))).all())
    ev_lead: dict = {}
    for lid, loai_act, uid, luc in (await db.execute(
        select(Activity.lead_id, Activity.type, Activity.user_id, func.max(Activity.created_at))
        .where(Activity.lead_id.in_(select(Lead.id).where(Lead.stage.in_(ACTIVE_LEAD_STAGES))),
               Activity.type.notin_(LOAI_ACTIVITY_LEAD_BO))
        .group_by(Activity.lead_id, Activity.type, Activity.user_id)
    )).all():
        _them_dau_vet(ev_lead, lid, luc, "lead", uid)
    for l in d.leads:
        if l.id not in ev_lead:
            _them_dau_vet(ev_lead, l.id, l.created_at, "tao_lead", None)
    d.ev_lead = ev_lead

    lead_cua_du_an = {p.lead_id for p in d.projects if p.lead_id}
    d.stage_lead_cua_du_an = dict((await db.execute(
        select(Lead.id, Lead.stage).where(Lead.id.in_(lead_cua_du_an))
    )).all()) if lead_cua_du_an else {}
    d.lead_thang_chua_du_an = list((await db.execute(
        select(Lead.id, Lead.name).where(
            Lead.stage == "signed_design", ~exists().where(Project.lead_id == Lead.id),
        )
    )).all())

    # Thông báo «Dữ liệu chung» đã gửi
    d.thong_bao = list((await db.execute(select(
        Notification.user_id, Notification.ref_id, Notification.read, Notification.created_at,
    ).where(Notification.type == LOAI_THONG_BAO))).all())
    d.nhac_cai_app_cuoi = await _lan_nhac_cai_app_cuoi(db)
    return d


async def _nguoi_co_push(db: AsyncSession) -> set[str]:
    """user_id có ít nhất 1 máy đã bật Web Push (push_subscriptions)."""
    return set((await db.execute(select(distinct(PushSubscription.user_id)))).scalars().all())


async def _lan_nhac_cai_app_cuoi(db: AsyncSession) -> dict | None:
    """Lần nhắc cài app gần nhất: giờ gửi cuối + số người nhận trong NGÀY VN đó."""
    cuoi = (await db.execute(select(func.max(Notification.created_at)).where(
        Notification.type == LOAI_NHAC_CAI_APP))).scalar()
    if cuoi is None:
        return None
    ngay = _ngay_vn(cuoi)
    so = (await db.execute(select(func.count(distinct(Notification.user_id))).where(
        Notification.type == LOAI_NHAC_CAI_APP,
        Notification.created_at >= _dau_ngay_vn_utc(ngay),
        Notification.created_at < _dau_ngay_vn_utc(ngay + timedelta(days=1)),
    ))).scalar() or 0
    return {"luc": _iso(cuoi), "so_nguoi": int(so)}


# ── Tính toán ───────────────────────────────────────────────────────────────

def _pic_hop_le(d: _DuLieu, uid: str | None, phong: str) -> bool:
    u = d.users.get(uid) if uid else None
    return la_nguoi_that(u) and phong_cua(u) == phong


def _viec_hien_tai(d: _DuLieu, p, giai_doan: str):
    for t in d.tasks_theo_du_an.get(p.id, []):
        if t.stage == giai_doan and t.status not in ("done", "completed", "cancelled"):
            return t
    return None


def _kiem_du_an(d: _DuLieu, p, phong: str) -> dict[str, bool]:
    """{mã quy tắc: đạt?} — chỉ các quy tắc ĐANG ÁP DỤNG cho hồ sơ này."""
    kq: dict[str, bool] = {}
    if phong == "SALES":
        kq["K6"] = bool((p.address or "").strip())
        kq["K7"] = _pic_hop_le(d, p.sales_id, "SALES")
    elif phong == "DESIGN":
        kq["T1"] = _pic_hop_le(d, p.designer_id, "DESIGN")
        t = _viec_hien_tai(d, p, "design")
        if t is not None:
            kq["T2"] = t.id in d.task_co_nguoi
    elif phong == "PURCHASING":
        kq["P1"] = _pic_hop_le(d, p.purchasing_id, "PURCHASING")
        kq["P2"] = bool((p.total_value or 0) > 0 or (p.bao_gia_sheet_url or "").strip()
                        or p.id in d.co_bao_gia_duyet)
        t = _viec_hien_tai(d, p, p.stage)
        if t is not None:
            kq["P3"] = t.id in d.task_co_nguoi
    elif phong == "OPS":
        kq["C1"] = _pic_hop_le(d, p.pm_id, "OPS")
        kq["C2"] = p.start_date is not None
        kq["C3"] = p.target_end_date is not None
        t = _viec_hien_tai(d, p, p.stage)
        if t is not None:
            kq["C4"] = t.id in d.task_co_nguoi
    return kq


def _kiem_lead(d: _DuLieu, l) -> dict[str, bool]:
    kq = {
        "K1": la_nguoi_that(d.users.get(l.assigned_to)) if l.assigned_to else False,
        "K2": bool((l.region or "").strip()),
        "K3": bool((l.source or "").strip()),
    }
    if l.stage in ("surveyed", "survey_scheduled", "potential"):
        kq["K4"] = bool((l.ngan_sach_khoang or "").strip()) or (l.estimated_budget or 0) > 0
    if l.stage == "surveyed":
        kq["K5"] = l.survey_date is not None
    return kq


def _cua_so_du_an(d: _DuLieu, p, phong: str) -> int:
    cs = d.ch["cua_so"]
    if phong == "OPS":
        return int(cs["OPS_ban_giao"] if p.stage == "acceptance" else cs["OPS"])
    return int(cs[phong])


def _gia_tri_lead(l) -> float:
    return float(l.design_contract_value or l.deal_value or l.estimated_budget or 0)


def _dau_vet_dict(d: _DuLieu, dv: _DauVet | None) -> dict | None:
    if dv is None:
        return None
    u = d.users.get(dv.nguoi) if dv.nguoi else None
    return {"luc": _iso(dv.luc), "loai": dv.loai, "nguoi": u.full_name if u else None}


def _doi_chieu_cuoi(d: _DuLieu, loai: str, eid: str, phong: str) -> dict | None:
    ds = d.doi_chieu.get((loai, eid, phong))
    if not ds:
        return None
    luc, kq, _uid, ten = ds[-1]
    return {"luc": _iso(luc), "ket_qua": kq, "nguoi": ten}


def _doi_chieu_trong_han(d: _DuLieu, loai: str, eid: str, phong: str):
    """Lần đối chiếu cuối còn trong `ngay_doi_chieu` ngày, hoặc None."""
    ds = d.doi_chieu.get((loai, eid, phong))
    if not ds:
        return None
    luc, kq, _uid, _ten = ds[-1]
    return (luc, kq) if d.now - luc <= timedelta(days=d.ngay_dc) else None


def _tinh_lech(d: _DuLieu) -> list[dict]:
    lech: list[dict] = []
    hom_nay = d.hom_nay
    for p in d.projects:
        if p.stage not in GIAI_DOAN_LAM:
            continue
        chu = CHU_GIAI_DOAN[p.stage]
        # L1 — giai đoạn theo bằng chứng 30 ngày đi trước CRM
        bc = d.bc30.get(p.id)
        if bc and THU_TU_GIAI_DOAN[bc[0]] > THU_TU_GIAI_DOAN[p.stage]:
            lech.append({
                "ma": "L1", "loai": "du_an", "id": p.id, "ma_ho_so": p.code, "ten": p.name,
                "crm_ghi": f"Giai đoạn «{NHAN_GIAI_DOAN[p.stage]}»",
                "bang_chung": f"{bc[1]} → «{NHAN_GIAI_DOAN[bc[0]]}»",
                "phong_lien_quan": list(dict.fromkeys([chu, CHU_GIAI_DOAN.get(bc[0], "OPS")])),
            })
        # L2 — dự án trỏ lead chưa «Deal đã thắng»
        if p.lead_id and p.lead_id in d.stage_lead_cua_du_an:
            st = d.stage_lead_cua_du_an[p.lead_id]
            if st != "signed_design":
                lech.append({
                    "ma": "L2", "loai": "du_an", "id": p.id, "ma_ho_so": p.code, "ten": p.name,
                    "crm_ghi": f"Lead đang ở «{NHAN_GIAI_DOAN_LEAD.get(st, st)}»",
                    "bang_chung": f"Đã có dự án {p.code}",
                    "phong_lien_quan": ["SALES"],
                })
        # L4 — tiến độ 100% mà chưa hoàn thành
        if (p.progress or 0) >= 100:
            lech.append({
                "ma": "L4", "loai": "du_an", "id": p.id, "ma_ho_so": p.code, "ten": p.name,
                "crm_ghi": f"Giai đoạn «{NHAN_GIAI_DOAN[p.stage]}»",
                "bang_chung": "Tiến độ đầu việc 100%",
                "phong_lien_quan": list(dict.fromkeys([chu, "OPS"])),
            })
        # L5 — ngày bàn giao đã qua mà còn chạy / khởi công ở tương lai mà đang thi công
        ngay_bg = _ngay_vn(p.handover_date)
        ngay_kc = _ngay_vn(p.start_date)
        # «đã qua» = trước hôm nay; bàn giao đúng hôm nay là đang làm, chưa lệch.
        if ngay_bg is not None and ngay_bg < hom_nay and p.status == "active":
            lech.append({
                "ma": "L5", "loai": "du_an", "id": p.id, "ma_ho_so": p.code, "ten": p.name,
                "crm_ghi": f"Đang chạy, giai đoạn «{NHAN_GIAI_DOAN[p.stage]}»",
                "bang_chung": f"Ngày bàn giao {ngay_bg:%d/%m/%Y} đã qua",
                "phong_lien_quan": list(dict.fromkeys([chu, "OPS"])),
            })
        elif ngay_kc is not None and ngay_kc > hom_nay and p.stage == "construction":
            lech.append({
                "ma": "L5", "loai": "du_an", "id": p.id, "ma_ho_so": p.code, "ten": p.name,
                "crm_ghi": "Giai đoạn «Thi công»",
                "bang_chung": f"Ngày khởi công {ngay_kc:%d/%m/%Y} chưa tới",
                "phong_lien_quan": ["OPS"],
            })
    # L3 — lead thắng mà chưa có dự án
    for lid, ten in d.lead_thang_chua_du_an:
        lech.append({
            "ma": "L3", "loai": "lead", "id": lid, "ma_ho_so": None, "ten": ten,
            "crm_ghi": "Lead «Deal đã thắng»",
            "bang_chung": "Chưa có dự án nào gắn với lead này",
            "phong_lien_quan": ["SALES"],
        })
    return lech


def _goi_y_giai_doan(d: _DuLieu, p) -> tuple[str | None, str]:
    """Gợi ý giai đoạn cho dự án cũ chưa xếp, theo bằng chứng. Không suy ra được → None."""
    tasks = d.tasks_theo_du_an.get(p.id, [])
    goi_y, ly_do = None, "Không suy ra được"
    co_lam = [t for t in tasks if t.status in ("done", "completed") or t.started_at or t.status == "in_progress"]
    if co_lam:
        mo = next((t for t in tasks if t.status not in ("done", "completed", "cancelled")
                   and t.stage in GIAI_DOAN_LAM), None)
        if mo is None:
            goi_y, ly_do = "completed", "Mọi đầu việc đã xong"
        else:
            goi_y, ly_do = mo.stage, f"Việc đang mở đầu tiên: «{mo.title}»"
    bc = d.bc30.get(p.id)
    if bc and (goi_y is None or THU_TU_GIAI_DOAN[bc[0]] > THU_TU_GIAI_DOAN[goi_y]):
        goi_y, ly_do = bc[0], bc[1]
    return goi_y, ly_do


# «Hồ sơ cần xem»: phần tử ứng viên là (nhóm, -giá trị, dòng) — nhóm 0 lệch, 1 chưa rõ,
# 2 thiếu thông tin (dự án KD xét K6/K7 luôn ở nhóm 2).

def _khoa_can_xem_bgd(x: tuple) -> tuple:
    """BGĐ: lệch → chưa rõ → thiếu; trong nhóm giá trị cao trước, rồi thiếu nhiều trước."""
    return x[0], x[1], -len(x[2]["thieu"])


def _khoa_can_xem_khong_tien(x: tuple) -> tuple:
    """Người không được xem tiền: cùng nhóm lệch → chưa rõ → thiếu nhưng KHÔNG theo giá trị —
    tiền ẩn mà thứ tự (hay việc chọn 50 dòng đầu) vẫn theo tiền thì dòng đầu chính là hồ sơ
    giá trị nhất, vẫn là lộ tiền. Thiếu nhiều trước, rồi mã dự án / tên lead."""
    r = x[2]
    return x[0], -len(r["thieu"]), (r["ma"] or r["ten"] or "").lower(), r["id"]


def _chon_can_xem(theo_phong: dict[str, list[tuple]], khoa) -> list[dict]:
    """Mỗi phòng tối đa 50 dòng để phòng nào cũng có mặt, tổng ≤200 — xếp theo `khoa`."""
    chon: list[tuple] = []
    for phong in PHONG_4:
        chon.extend(sorted(theo_phong[phong], key=khoa)[:TOI_DA_CAN_XEM_MOI_PHONG])
    chon.sort(key=khoa)
    return [x[2] for x in chon[:TOI_DA_CAN_XEM]]


def _tinh(d: _DuLieu) -> dict:  # noqa: C901
    """Toàn bộ số liệu trang «Dữ liệu chung» từ dữ liệu đã nạp."""
    ch = d.ch
    now = d.now
    hom_nay = d.hom_nay
    lead_treo_ngay = int(ch.get("lead_treo_ngay") or 60)

    da_xep = [p for p in d.projects if p.stage in GIAI_DOAN_LAM]
    chua_xep = [p for p in d.projects if p.stage not in GIAI_DOAN_LAM]

    lech = _tinh_lech(d)
    lech_theo_id: dict[str, list[dict]] = {}
    for r in lech:
        lech_theo_id.setdefault(r["id"], []).append(r)
        # L2 thuộc về dự án nhưng vế sai nằm ở LEAD — gắn cả vào lead để vòng KD
        # (duyệt theo lead) đánh dấu được «lệch».
        if r["ma"] == "L2":
            p = d.pmap.get(r["id"])
            if p is not None and p.lead_id:
                lech_theo_id.setdefault(p.lead_id, []).append(r)

    # Nhắc
    ref_hom_nay = hom_nay.isoformat()
    dau_ngay = _utc(_dau_ngay_vn_utc(hom_nay))

    def _nhac_cuoi(tien_to: str) -> dict | None:
        ds = [n for n in d.thong_bao if (n.ref_id or "").startswith(tien_to)]
        if not ds:
            return None
        cuoi = max(ds, key=lambda n: _utc(n.created_at))
        cung_ref = [n for n in ds if n.ref_id == cuoi.ref_id]
        return {"luc": _iso(cuoi.created_at), "da_xem": any(n.read for n in cung_ref)}

    def _nhac_lan_dau(tien_to: str) -> datetime | None:
        ds = [_utc(n.created_at) for n in d.thong_bao if (n.ref_id or "").startswith(tien_to)]
        return min(ds) if ds else None

    def _da_nhac_hom_nay(ref: str) -> dict | None:
        ds = [n for n in d.thong_bao if n.ref_id == ref and _utc(n.created_at) >= dau_ngay]
        if not ds:
            return None
        return {"luc": _iso(min(_utc(n.created_at) for n in ds)), "da_xem": any(n.read for n in ds)}

    def _truong_phong(phong: str) -> list[dict]:
        return [
            {"id": u.id, "ten": u.full_name, "co_telegram": bool(u.telegram_user_id),
             "co_thong_bao_may": u.id in d.co_push}
            for u in d.users.values()
            if u.is_active and la_truong_phong_cua(u, phong)
        ]

    phong_out: list[dict] = []
    can_xem_theo_phong: dict[str, list[tuple]] = {p: [] for p in PHONG_4}
    dat_phan_anh: set[str] = set()
    lead_treo = 0

    for phong in PHONG_4:
        quy_tac_dem: dict[str, list[int]] = {m: [0, 0] for m in QUY_TAC_DU[phong]}
        trang_thai = {"co_dau_vet": 0, "chua_cap_nhat": 0, "chua_ro": 0, "dang_cho": 0, "lech": 0}
        tuoi_dat = tuoi_tong = 0
        dc_dat = dc_tong = 0
        dau_vet_gan_nhat: _DauVet | None = None
        so_ho_so = 0
        tre_han = 0

        def _phan_loai(loai: str, rid: str, tuoi: bool, cho: bool, lech_ds: list) -> str:
            if lech_ds:
                return "lech"
            if cho:
                return "dang_cho"
            if tuoi:
                return "co_dau_vet"
            dc = _doi_chieu_trong_han(d, loai, rid, phong)
            if dc and dc[1] == "dung":
                return "chua_cap_nhat"
            return "chua_ro"

        if phong == "SALES":
            so_ho_so = len(d.leads)
            for l in d.leads:
                kiem = _kiem_lead(d, l)
                for m, ok in kiem.items():
                    quy_tac_dem[m][1] += 1
                    quy_tac_dem[m][0] += int(ok)
                dv = d.ev_lead.get(l.id)
                tuoi_ngay = (now - dv.luc).total_seconds() / 86400 if dv else 10 ** 6
                if dv and (dau_vet_gan_nhat is None or dv.luc > dau_vet_gan_nhat.luc) and dv.loai != "tao_lead":
                    dau_vet_gan_nhat = dv
                if l.stage in LEAD_DOI_CHIEU:
                    dc_tong += 1
                    if _doi_chieu_trong_han(d, "lead", l.id, phong):
                        dc_dat += 1
                if tuoi_ngay > lead_treo_ngay:
                    lead_treo += 1   # nới lỏng: ra khỏi mẫu số Tươi, không vào bộ đếm
                    continue
                dc = _doi_chieu_trong_han(d, "lead", l.id, phong)
                cho = bool(dc and dc[1] == "tam_dung")
                cua_so = int(ch["cua_so"]["lead"].get(l.stage, 7))
                tuoi = tuoi_ngay <= cua_so
                if not cho:
                    tuoi_tong += 1
                    tuoi_dat += int(tuoi)
                lech_ds = [r for r in lech_theo_id.get(l.id, []) if "SALES" in r["phong_lien_quan"]]
                tt = _phan_loai("lead", l.id, tuoi, cho, lech_ds)
                trang_thai[tt] += 1
                thieu = [m for m, ok in kiem.items() if not ok]
                if tt in ("lech", "chua_ro") or thieu:
                    can_xem_theo_phong[phong].append((
                        0 if tt == "lech" else (1 if tt == "chua_ro" else 2), -_gia_tri_lead(l), {
                            "loai": "lead", "id": l.id, "ma": None, "ten": l.name, "khach": l.name,
                            "giai_doan": l.stage, "gia_tri": _gia_tri_lead(l), "phong_giu": phong,
                            "thieu": thieu, "trang_thai": tt,
                            "dau_vet_cuoi": _dau_vet_dict(d, dv),
                            "doi_chieu_cuoi": _doi_chieu_cuoi(d, "lead", l.id, phong),
                            "da_hoi_hom_nay": _da_nhac_hom_nay(f"dlc:hs:{l.id}:{ref_hom_nay}") is not None,
                        }))
            # K6/K7 trên dự án đã xếp (chỉ Đủ)
            for p in da_xep:
                kiem = _kiem_du_an(d, p, phong)
                for m, ok in kiem.items():
                    quy_tac_dem[m][1] += 1
                    quy_tac_dem[m][0] += int(ok)
                thieu = [m for m, ok in kiem.items() if not ok]
                if thieu:
                    # Dự án chỉ xét Đủ cho KD (Tươi KD tính trên lead) → xếp nhóm «thiếu trường»
                    can_xem_theo_phong[phong].append((2, -(p.total_value or 0), _dong_can_xem(
                        d, p, phong, thieu,
                        "co_dau_vet" if d.ev.get((p.id, phong)) else "chua_ro", ref_hom_nay)))
        else:
            pham_vi = [p for p in da_xep if p.stage in GIAI_DOAN_CUA_PHONG[phong]]
            so_ho_so = len(pham_vi)
            for p in pham_vi:
                kiem = _kiem_du_an(d, p, phong)
                for m, ok in kiem.items():
                    quy_tac_dem[m][1] += 1
                    quy_tac_dem[m][0] += int(ok)
                dv = d.ev.get((p.id, phong))
                if dv and (dau_vet_gan_nhat is None or dv.luc > dau_vet_gan_nhat.luc):
                    dau_vet_gan_nhat = dv
                tuoi = bool(dv) and (now - dv.luc) <= timedelta(days=_cua_so_du_an(d, p, phong))
                dc = _doi_chieu_trong_han(d, "du_an", p.id, phong)
                cho = p.status == "paused" or bool(dc and dc[1] == "tam_dung")
                if not cho:
                    tuoi_tong += 1
                    tuoi_dat += int(tuoi)
                dc_tong += 1
                if dc:
                    dc_dat += 1
                lech_ds = [r for r in lech_theo_id.get(p.id, []) if phong in r["phong_lien_quan"]]
                tt = _phan_loai("du_an", p.id, tuoi, cho, lech_ds)
                trang_thai[tt] += 1
                if tuoi or (dc and dc[1] == "dung"):
                    dat_phan_anh.add(p.id)
                if (phong == "OPS" and p.status == "active" and p.stage in ("construction", "acceptance")
                        and p.target_end_date is not None and _ngay_vn(p.target_end_date) < hom_nay):
                    tre_han += 1
                thieu = [m for m, ok in kiem.items() if not ok]
                if tt in ("lech", "chua_ro") or thieu:
                    can_xem_theo_phong[phong].append((
                        0 if tt == "lech" else (1 if tt == "chua_ro" else 2),
                        -(p.total_value or 0),
                        _dong_can_xem(d, p, phong, thieu, tt, ref_hom_nay),
                    ))

        du_dat = sum(v[0] for v in quy_tac_dem.values())
        du_tong = sum(v[1] for v in quy_tac_dem.values())
        lan_dau = _nhac_lan_dau(f"dlc:{phong}:")
        ap_dung = bool(lan_dau and now - lan_dau >= timedelta(days=d.ngay_dc))
        thanh_phan = {
            "du": {"dat": du_dat, "tong": du_tong},
            "tuoi": {"dat": tuoi_dat, "tong": tuoi_tong},
            "doi_chieu": {"dat": dc_dat, "tong": dc_tong, "ap_dung": ap_dung},
        }
        diem, muc = tinh_diem(thanh_phan, so_ho_so)

        quy_tac = [
            {"ma": m, "nhan": NHAN_QUY_TAC[m], "loai": "du", "dat": v[0], "tong": v[1]}
            for m, v in quy_tac_dem.items() if v[1] > 0
        ]
        for m in QUY_TAC_LECH[phong]:
            if phong == "SALES":
                tong = (len([p for p in d.projects if p.lead_id in d.stage_lead_cua_du_an])
                        if m == "L2" else len(d.lead_thang_chua_du_an))
                so_lech = len({r["id"] for r in lech if r["ma"] == m})
                if m == "L3":
                    tong = so_lech  # chỉ biết số lead thắng thiếu dự án
            else:
                pham_vi_ids = {p.id for p in da_xep if p.stage in GIAI_DOAN_CUA_PHONG[phong]}
                tong = len(pham_vi_ids)
                so_lech = len({r["id"] for r in lech if r["ma"] == m and r["id"] in pham_vi_ids})
            quy_tac.append({"ma": m, "nhan": NHAN_QUY_TAC[m], "loai": "lech",
                            "dat": max(tong - so_lech, 0), "tong": tong})

        phong_out.append({
            "ma": phong,
            "ten": TEN_PHONG[phong],
            "truong_phong": _truong_phong(phong),
            "so_ho_so": so_ho_so,
            "diem": diem,
            "muc": muc,
            "thanh_phan": thanh_phan,
            "trang_thai": trang_thai,
            "quy_tac": quy_tac,
            "tre_han": tre_han,
            "dau_vet_gan_nhat": _dau_vet_dict(d, dau_vet_gan_nhat),
            "lan_nhac_cuoi": _nhac_cuoi(f"dlc:{phong}:"),
        })

    # Hồ sơ cần xem — mỗi phòng tối đa 50 để phòng nào cũng có mặt, tổng ≤200. Giữ cả
    # danh sách ứng viên CHƯA cắt: bản trưởng phòng lọc phạm vi trước rồi mới cắt
    # (_loc_cho_truong_phong). Chỉ nuôi danh sách — không số tổng hợp nào đọc nó.
    d.can_xem_theo_phong = can_xem_theo_phong
    can_xem_out = _chon_can_xem(can_xem_theo_phong, _khoa_can_xem_bgd)

    # Phản ánh
    tong = len(d.projects)
    phan_anh = {"dat": len(dat_phan_anh), "tong": tong,
                "pct": int(round(len(dat_phan_anh) / tong * 100)) if tong else None}

    # Dải quy trình
    muc_phong = {x["ma"]: x["muc"] for x in phong_out}

    def _o(ma: str, nhan: str, gia_tri: list[float], phong: str | None) -> dict:
        co = [v for v in gia_tri if (v or 0) > 0]
        return {"ma": ma, "nhan": nhan, "so_luong": len(gia_tri), "tong_tien": float(sum(co)),
                "so_co_gia_tri": len(co), "phong": phong, "muc": muc_phong.get(phong) if phong else None}

    dai = [_o("lead_mo", "Lead đang mở", [_gia_tri_lead(l) for l in d.leads], "SALES")]
    for gd in GIAI_DOAN_LAM:
        dai.append(_o(gd, NHAN_GIAI_DOAN[gd], [p.total_value or 0 for p in da_xep if p.stage == gd],
                      CHU_GIAI_DOAN[gd]))
    dai.append(_o("hoan_thanh_30", "Hoàn thành 30 ngày", [r.total_value or 0 for r in d.hoan_thanh_30], None))

    tam_dung = [p for p in d.projects if p.status == "paused"]
    ngoai_dai = {
        "chua_xep": {"so_luong": len(chua_xep), "da_xep_tu_moc": len(d.da_xep_tu_moc)},
        "tam_dung": {"so_luong": len(tam_dung),
                     "co_ly_do": sum(1 for p in tam_dung if (p.pause_reason or "").strip())},
        "lead_treo": lead_treo,
    }

    # Hôm nay — tối đa 3 thẻ
    hom_nay_the: list[dict] = []
    if chua_xep:
        da_nhac = _da_nhac_hom_nay(f"dlc:chua_xep:{ref_hom_nay}")
        hom_nay_the.append({
            "ma": "chua_xep", "phong": "chua_xep",
            "tieu_de": f"{len(chua_xep)} dự án cũ chưa xếp giai đoạn",
            "so_luong": len(chua_xep),
            "nut": ({"nhan": "Nhờ 3 trưởng phòng nhận", "hanh_dong": "nhac_chua_xep",
                     "phong": "chua_xep", "link": None} if da_nhac is None else
                    {"nhan": "Xem dữ liệu cũ", "hanh_dong": "mo", "phong": "chua_xep",
                     "link": "/doi-chieu?phong=DESIGN&tab=chua_xep"}),
            "da_nhac": da_nhac,
        })
    ung_vien = [
        x for x in phong_out
        if x["muc"] != "khong_co_ho_so" and x["truong_phong"]
        and _da_nhac_hom_nay(f"dlc:{x['ma']}:{ref_hom_nay}") is None
    ]
    ung_vien.sort(key=lambda x: (x["diem"] is None, x["diem"] if x["diem"] is not None else 0, -x["so_ho_so"]))
    for x in ung_vien[: 3 - len(hom_nay_the)]:
        so = x["trang_thai"]["chua_ro"] + x["trang_thai"]["lech"]
        hom_nay_the.append({
            "ma": f"phong_{x['ma']}", "phong": x["ma"],
            "tieu_de": f"{x['ten']}: {so} hồ sơ chưa rõ hoặc lệch trên CRM",
            "so_luong": so,
            "nut": {"nhan": "Nhắc trưởng phòng", "hanh_dong": "nhac", "phong": x["ma"],
                    "link": f"/doi-chieu?phong={x['ma']}"},
            "da_nhac": None,
        })

    # Đã xong chờ BGĐ
    cho_bgd = []
    for p in d.projects:
        moi = d.doi_chieu_moi_nhat.get(("du_an", p.id))
        if moi and moi[1] == "da_xong" and p.stage != "completed":
            cho_bgd.append({"id": p.id, "ma": p.code, "khach": p.client_name, "boi": moi[2],
                            "luc": _iso(moi[0])})

    du_lieu_cu = []
    for p in sorted(chua_xep, key=lambda p: -(p.total_value or 0)):
        gy, ly_do = _goi_y_giai_doan(d, p)
        du_lieu_cu.append({"id": p.id, "ma": p.code, "ten": p.name, "gia_tri": float(p.total_value or 0),
                           "goi_y_giai_doan": gy, "ly_do_goi_y": ly_do})

    moc = _moc(ch)
    chay_thu_den = moc + timedelta(days=int(ch.get("chay_thu_ngay") or 60))
    return {
        "cap_nhat_luc": now.isoformat(),
        "chay_thu": hom_nay <= chay_thu_den,
        "chay_thu_den": chay_thu_den.isoformat(),
        "moc_bat_dau": moc.isoformat(),
        "cau_hinh": {
            "cua_so": ch["cua_so"],
            "ngay_doi_chieu": d.ngay_dc,
            "lead_treo_ngay": lead_treo_ngay,
        },
        "phan_anh": phan_anh,
        "hom_nay": hom_nay_the,
        "dai_quy_trinh": dai,
        "ngoai_dai": ngoai_dai,
        "phong": phong_out,
        "lech": lech,
        "can_xem": can_xem_out,
        "cho_bgd": cho_bgd,
        "du_lieu_cu": du_lieu_cu,
        "kenh_thong_bao": _kenh_thong_bao(d),
    }


def _phong_kenh(u) -> str:
    """Phòng cho khối «Kênh nhận thông báo»: phong_cua (PM→OPS), ngoài 4 phòng → KHAC."""
    p = phong_cua(u)
    return p if p in PHONG_4 else "KHAC"


def _kenh_thong_bao(d: _DuLieu) -> dict:
    """Ai nhận được nhắc qua kênh nào — đo prod 21/11: 63 người, 2 người bật thông
    báo máy, 6 liên kết Telegram → phần lớn chỉ thấy tin khi tự mở chuông.

    Phạm vi: người thật đang làm (không tính admin). `chi_chuong` = không có máy
    bật thông báo VÀ không liên kết Telegram.
    """
    def _dem() -> dict:
        return {"tong": 0, "co_thong_bao_may": 0, "co_telegram": 0, "chi_chuong": 0}

    tong = _dem()
    theo_phong = {p: _dem() for p in PHONG_KENH}
    for u in d.users.values():
        if not la_nguoi_that(u):
            continue
        phong = _phong_kenh(u)
        may = u.id in d.co_push
        tg = bool(u.telegram_user_id)
        for dem in (tong, theo_phong[phong]):
            dem["tong"] += 1
            dem["co_thong_bao_may"] += int(may)
            dem["co_telegram"] += int(tg)
            dem["chi_chuong"] += int(not may and not tg)
    return {
        **tong,
        "theo_phong": [{"phong": p, "ten": TEN_PHONG_KENH[p], **theo_phong[p]} for p in PHONG_KENH],
        "chua_bat": _ds_chua_bat(d)[:TOI_DA_CHUA_BAT],
        "lan_nhac_cai_app_cuoi": d.nhac_cai_app_cuoi,
    }


def _ds_chua_bat(d: _DuLieu, phong: str | None = None) -> list[dict]:
    """Người thật chưa có máy nào bật thông báo, theo phòng kênh rồi tên — CHƯA cắt 200.

    `phong`: chỉ người phòng kênh đó. Bản trưởng phòng lọc phòng TRƯỚC rồi mới cắt: cắt
    200 người cả công ty trước (Kinh doanh xếp đầu) thì phòng xếp sau (Giám sát) có thể
    ra danh sách rỗng trong khi thanh của phòng vẫn đếm N người chưa bật.
    """
    thu_tu = {p: i for i, p in enumerate(PHONG_KENH)}
    ds: list[tuple] = []
    for u in d.users.values():
        if not la_nguoi_that(u) or u.id in d.co_push:
            continue
        ph = _phong_kenh(u)
        if phong is None or ph == phong:
            ds.append((thu_tu[ph], (u.full_name or "").lower(), u.id, {
                "id": u.id, "ten": u.full_name, "phong": ph, "co_telegram": bool(u.telegram_user_id),
            }))
    ds.sort(key=lambda x: x[:3])
    return [x[3] for x in ds]


def _dong_can_xem(d: _DuLieu, p, phong: str, thieu: list[str], tt: str, ref_hom_nay: str) -> dict:
    return {
        "loai": "du_an", "id": p.id, "ma": p.code, "ten": p.name, "khach": p.client_name,
        "giai_doan": p.stage, "gia_tri": float(p.total_value or 0), "phong_giu": phong,
        "thieu": thieu, "trang_thai": tt,
        "dau_vet_cuoi": _dau_vet_dict(d, d.ev.get((p.id, phong))),
        "doi_chieu_cuoi": _doi_chieu_cuoi(d, "du_an", p.id, phong),
        "da_hoi_hom_nay": any(n.ref_id == f"dlc:hs:{p.id}:{ref_hom_nay}" for n in d.thong_bao),
    }


async def _tin_hieu_30_ngay(db: AsyncSession, cutoff30: datetime) -> dict:
    so_act = (await db.execute(
        select(func.count(TaskActivity.id)).join(User, User.id == TaskActivity.user_id)
        .where(TaskActivity.created_at >= cutoff30, ~TaskActivity.content.like(TASK_COORDINATOR_LIKE))
    )).scalar() or 0
    so_anh, du_an_co_anh = (await db.execute(
        select(func.count(MediaFile.id), func.count(distinct(MediaFile.project_id)))
        .where(MediaFile.created_at >= cutoff30)
    )).one()
    viec_xong = {gd: 0 for gd in GIAI_DOAN_LAM}
    for gd, so in (await db.execute(
        select(Task.stage, func.count(Task.id))
        .where(Task.completed_at >= cutoff30, Task.status.in_(("done", "completed")))
        .group_by(Task.stage)
    )).all():
        if gd in viec_xong:
            viec_xong[gd] = int(so)
    phieu = (await db.execute(select(func.count(DongPhieuVatTu.id)).where(
        DongPhieuVatTu.created_at >= cutoff30))).scalar() or 0
    bao_gia = (await db.execute(select(func.count(Quotation.id)).where(
        Quotation.created_at >= cutoff30))).scalar() or 0
    hd = (await db.execute(select(func.count(Contract.id)).where(
        Contract.status.in_(("signed", "active", "completed")),
        or_(Contract.signed_date >= cutoff30.date(),
            (Contract.signed_date.is_(None)) & (Contract.updated_at >= cutoff30)),
    ))).scalar() or 0
    act_cuoi = (await db.execute(
        select(func.max(TaskActivity.created_at)).join(User, User.id == TaskActivity.user_id)
        .where(~TaskActivity.content.like(TASK_COORDINATOR_LIKE))
    )).scalar()
    anh_cuoi = (await db.execute(select(func.max(MediaFile.created_at)))).scalar()
    return {
        "task_activities": int(so_act),
        "anh": int(so_anh or 0),
        "du_an_co_anh": int(du_an_co_anh or 0),
        "viec_xong": viec_xong,
        "phieu_vat_tu": int(phieu),
        "bao_gia": int(bao_gia),
        "hd_da_ky": int(hd),
        "lan_cuoi": {"task_activity": _iso(act_cuoi), "anh": _iso(anh_cuoi)},
    }


# ── Quyền ────────────────────────────────────────────────────────────────────

def _chan_neu_khong_phai_bgd(user: User) -> None:
    """Chặn mọi THAO TÁC (gửi nhắc) — từ 26/11 trưởng phòng xem được trang nhưng không nhắc."""
    if user.role not in VAI_TRO_BGD:
        raise HTTPException(status_code=403, detail="Chỉ Ban Giám đốc được gửi nhắc ở trang «Dữ liệu chung».")


async def _xep_hang_gui(db: AsyncSession, khoa: str) -> None:
    """Cho các lượt gửi nhắc CÙNG LOẠI chạy lần lượt (21/11/2026).

    Chặn «1 tin/người/ngày» là SELECT tin hôm nay rồi mới INSERT: hai request chồng
    nhau (2 tài khoản BGĐ bấm cùng lúc, hoặc bấm nút khác khi lượt trước còn đang chờ
    Telegram) đều thấy «chưa nhắc» và cùng gửi → mỗi người nhận 2 tin. Postgres: khoá
    advisory theo giao dịch — lượt sau đứng chờ tới khi lượt trước commit/rollback, rồi
    câu SELECT chặn trùng (READ COMMITTED, chụp lại dữ liệu mỗi câu) thấy tin vừa ghi.
    SQLite (test) bỏ qua: không có hàm này, mà ghi vốn đã tuần tự."""
    if db.get_bind().dialect.name != "postgresql":
        return
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": khoa})


def _phong_doi_chieu(user: User, phong: str | None) -> str:
    """Phòng người này được đối chiếu. BGĐ: mọi phòng; trưởng phòng: chỉ phòng mình."""
    if user.role in VAI_TRO_BGD:
        if phong not in PHONG_4:
            raise HTTPException(status_code=400, detail="Chọn phòng cần đối chiếu")
        return phong
    cua_minh = phong_truong_phong(user)
    if cua_minh is None:
        raise HTTPException(status_code=403, detail="Chỉ trưởng phòng và Ban Giám đốc được đối chiếu dữ liệu.")
    if phong is None:
        return cua_minh
    if phong != cua_minh:
        raise HTTPException(status_code=403, detail="Bạn chỉ đối chiếu được hồ sơ của phòng mình.")
    if phong == "SALES" and not duoc_xem_lead(user):
        raise HTTPException(status_code=403, detail="Chỉ bộ phận Kinh doanh và Ban Giám đốc được xem dữ liệu lead")
    return phong


# ── Trưởng phòng xem cùng (vòng 4, 26/11/2026) ──────────────────────────────
# Chủ dự án: «mở quyền xem dashboard báo cáo công ty cho các trưởng phòng xem cùng».
# CHỈ XEM — không mở thêm thao tác nào và không mở rộng quyền vốn có của ai.

KHOA_TIEN = ("tong_tien", "gia_tri")
# L2 của BGĐ ghi «Lead đang ở «<giai đoạn lead>»» — giai đoạn lead là dữ liệu lead
# (chặn cứng 22/09: chỉ Kinh doanh + BGĐ thấy lead). Người không được xem lead đó
# nhận chữ chung, không lộ hơn chính quy tắc L2.
CHU_L2_KHONG_XEM_LEAD = "Lead gắn với dự án chưa ở «Deal đã thắng»"


def _nguoi_xem(user: User) -> dict:
    """Ai đang xem trang chính và được làm gì — khoá `nguoi_xem` của GET.

    BGĐ: toàn quyền như cũ. Trưởng 4 phòng (`phong_truong_phong` — department nguyên
    gốc, phòng 'PM' cũ không tính): chỉ xem, không tiền, không thao tác. Còn lại 403.
    """
    if user.role in VAI_TRO_BGD:
        return {"loai": "bgd", "phong": None, "xem_tien": True, "thao_tac": True}
    phong = phong_truong_phong(user)
    if phong is None:
        raise HTTPException(status_code=403,
                            detail="Trang «Dữ liệu chung» chỉ dành cho Ban Giám đốc và trưởng phòng.")
    return {"loai": "truong_phong", "phong": phong, "xem_tien": False, "thao_tac": False}


async def _pham_vi_xem(db: AsyncSession, user: User) -> tuple[set[str] | None, set[str]]:
    """(id dự án đang chạy người này thấy — None = thấy hết, id lead người này thấy).

    CÙNG luật trang Dự án (`dieu_kien_pham_vi_du_an`) và trang Lead (`_loc_pham_vi_lead`
    — đã gồm chặn cứng «chỉ KD + BGĐ thấy lead»), mỗi tập đúng 1 câu SQL. Luật
    'phong_ban' hiện cho trưởng phòng thấy MỌI dự án (cột PIC phòng mình là người phòng
    mình, HOẶC còn trống/trỏ người ngoài phòng); vẫn lọc qua đây để khi trang Dự án siết
    lại thì trang này siết theo.
    """
    from app.api.leads import _loc_pham_vi_lead
    from app.api.projects import dieu_kien_pham_vi_du_an

    du_an: set[str] | None = None
    dk = dieu_kien_pham_vi_du_an(user)
    if dk is not None:
        du_an = set((await db.execute(
            select(Project.id).where(Project.status.in_(TRANG_THAI_CHAY), dk)
        )).scalars().all())
    lead: set[str] = set()
    if duoc_xem_lead(user):
        lead = set((await db.execute(_loc_pham_vi_lead(select(Lead.id), user))).scalars().all())
    return du_an, lead


def _an_tien(obj) -> None:
    """Mọi khoá tiền ở MỌI tầng → None, giữ khoá (giao diện nhận `number | null`)."""
    if isinstance(obj, dict):
        for k in obj:
            if k in KHOA_TIEN:
                obj[k] = None
            else:
                _an_tien(obj[k])
    elif isinstance(obj, list):
        for x in obj:
            _an_tien(x)


def _the_hom_nay_truong_phong(kq: dict, phong: str) -> list[dict]:
    """Tối đa 2 thẻ MỞ trang đối chiếu phòng mình — không có thẻ nhắc của BGĐ."""
    the: list[dict] = []
    x = next(p for p in kq["phong"] if p["ma"] == phong)
    so = x["trang_thai"]["chua_ro"] + x["trang_thai"]["lech"]
    if so:
        the.append({
            "ma": f"phong_{phong}", "phong": phong,
            "tieu_de": f"{x['ten']}: {so} hồ sơ chưa rõ hoặc lệch trên CRM",
            "so_luong": so,
            "nut": {"nhan": "Mở đối chiếu", "hanh_dong": "mo", "phong": phong,
                    "link": f"/doi-chieu?phong={phong}"},
            "da_nhac": None,
        })
    so_cu = kq["ngoai_dai"]["chua_xep"]["so_luong"]
    # Chỉ 3 phòng có giai đoạn dự án mới nhận dự án cũ về được (KD đối chiếu lead).
    if phong in GIAI_DOAN_CUA_PHONG and so_cu:
        the.append({
            "ma": "chua_xep", "phong": "chua_xep",
            "tieu_de": f"{so_cu} dự án cũ chưa xếp giai đoạn",
            "so_luong": so_cu,
            "nut": {"nhan": "Nhận dự án về phòng", "hanh_dong": "mo", "phong": "chua_xep",
                    "link": f"/doi-chieu?phong={phong}&tab=chua_xep"},
            "da_nhac": None,
        })
    return the


def _loc_cho_truong_phong(kq: dict, d: _DuLieu, phong: str,
                          du_an_thay: set[str] | None, lead_thay: set[str]) -> dict:
    """Bản «chỉ xem» cho trưởng phòng `phong`, LỌC từ bản BGĐ `kq` (cần `_tinh(d)` đã chạy)
    — không tính lại số nào.

    Giữ nguyên nên giống hệt BGĐ: phan_anh, dai_quy_trinh (trừ tiền), ngoai_dai, phong[],
    tin_hieu_30_ngay, cau_hinh, các số đếm của kenh_thong_bao. Chỉ đổi:
      • tiền (`tong_tien`, `gia_tri`) → None ở mọi tầng — như /doi-chieu;
      • dòng chi tiết chỉ còn hồ sơ người này VỐN ĐÃ THẤY: dự án trong `du_an_thay`
        (None = mọi dự án), lead trong `lead_thay`. «Hồ sơ cần xem» lọc trên danh sách
        ứng viên CHƯA cắt (`d.can_xem_theo_phong`) rồi mới cắt 50/phòng, 200 tổng — lọc
        sau khi BGĐ đã cắt thì hồ sơ ngoài phạm vi chiếm hết suất, danh sách ra trống;
      • thứ tự KHÔNG theo tiền: can_xem theo `_khoa_can_xem_khong_tien` (chọn 50 dòng
        đầu cũng theo khoá đó), du_lieu_cu theo mã — tiền ẩn mà vẫn xếp theo tiền là lộ;
      • L2 mà người này không được xem lead đó → bỏ chữ giai đoạn lead;
      • `kenh_thong_bao.chua_bat` chỉ người cùng phòng — lọc phòng rồi mới cắt 200;
      • `hom_nay` = thẻ mở trang đối chiếu phòng mình (_the_hom_nay_truong_phong).
    Trả bản sao, không đụng `kq` (dòng ứng viên dùng chung đối tượng với `kq["can_xem"]`).
    """
    out = copy.deepcopy(kq)

    def _thay(loai: str, rid: str) -> bool:
        if loai == "lead":
            return rid in lead_thay
        return du_an_thay is None or rid in du_an_thay

    out["lech"] = [r for r in out["lech"] if _thay(r["loai"], r["id"])]
    for r in out["lech"]:
        if r["ma"] == "L2":
            p = d.pmap.get(r["id"])
            if p is None or p.lead_id not in lead_thay:
                r["crm_ghi"] = CHU_L2_KHONG_XEM_LEAD
    ung_vien = {ph: [x for x in d.can_xem_theo_phong[ph] if _thay(x[2]["loai"], x[2]["id"])]
                for ph in PHONG_4}
    out["can_xem"] = copy.deepcopy(_chon_can_xem(ung_vien, _khoa_can_xem_khong_tien))
    out["cho_bgd"] = [r for r in out["cho_bgd"] if _thay("du_an", r["id"])]
    out["du_lieu_cu"] = sorted((r for r in out["du_lieu_cu"] if _thay("du_an", r["id"])),
                               key=lambda r: ((r["ma"] or "").lower(), r["id"]))
    # Trưởng phòng có department nguyên gốc ∈ PHONG_4 nên phòng kênh của họ chính là
    # `phong` (người phòng 'PM' cũ đã được _phong_kenh tính vào OPS).
    out["kenh_thong_bao"]["chua_bat"] = _ds_chua_bat(d, phong)[:TOI_DA_CHUA_BAT]
    out["hom_nay"] = _the_hom_nay_truong_phong(out, phong)
    _an_tien(out)   # sau cùng — phủ cả các danh sách vừa dựng lại
    return out


# ─────────────────────────────────────────────────────────────────────────────
# GET /dashboard/du-lieu-chung
# ─────────────────────────────────────────────────────────────────────────────

def _khoa_cache_trang_chinh(*_a, **kw) -> list[str]:
    """BGĐ dùng chung một bản theo vai trò; trưởng phòng mỗi người một bản — phạm vi
    dự án/lead tính theo chính người đó. Kèm phòng: đổi phòng giữa chừng thì không
    ăn lại bản cũ (cache trúng là bỏ qua kiểm quyền, bản cũ có thể là bản lẽ ra 403)."""
    u = kw.get("current_user")
    if u is None:
        return ["anon"]
    return [u.role] if u.role in VAI_TRO_BGD else [u.role, u.id, phong_goc(u)]


@router.get("")
@cached(ttl=120, prefix="dashboard", key_fn=_khoa_cache_trang_chinh)
async def du_lieu_chung(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toàn bộ trang «Dữ liệu chung» trong MỘT lần gọi. Chỉ đọc — không ghi gì vào DB.

    BGĐ nhận bản đủ; trưởng 4 phòng nhận bản lọc từ chính bản đó (26/11/2026).
    """
    nguoi_xem = _nguoi_xem(current_user)
    d = await _nap(db)
    kq = _tinh(d)
    kq["tin_hieu_30_ngay"] = await _tin_hieu_30_ngay(db, d.cutoff30)
    if nguoi_xem["loai"] == "truong_phong":
        du_an_thay, lead_thay = await _pham_vi_xem(db, current_user)
        kq = _loc_cho_truong_phong(kq, d, nguoi_xem["phong"], du_an_thay, lead_thay)
    kq["nguoi_xem"] = nguoi_xem
    return kq


# ─────────────────────────────────────────────────────────────────────────────
# POST /dashboard/du-lieu-chung/nhac
# ─────────────────────────────────────────────────────────────────────────────

class NhacIn(BaseModel):
    phong: Literal["SALES", "DESIGN", "PURCHASING", "OPS", "chua_xep"]
    id: str | None = Field(None, max_length=64)
    loai: Literal["du_an", "lead"] | None = None


def _link_tuyet_doi(duong: str) -> str:
    from app.config import get_settings
    return get_settings().FRONTEND_URL.rstrip("/") + duong


def _link_cai_app() -> str:
    return f'<a href="{html.escape(_link_tuyet_doi(DUONG_CAI_APP), quote=True)}">Hướng dẫn 1 phút</a>'


def _dong_moi_cai_app() -> str:
    return f"Cài JAMA HOME lên điện thoại và bật thông báo để nhận nhắc ngay: {_link_cai_app()}"


async def _gui_nhac(
    db: AsyncSession, d: _DuLieu, nguoi, *, phong: str, ref_id: str, tieu_de: str,
    dong: list[str], link: str, reply_markup: dict | None,
    da_gui: list, bo_qua: list,
) -> None:
    """Gửi 1 tin nhắc cho 1 người — chặn trùng trong ngày VN và tối đa N tin/người/ngày."""
    from app.services.automation import _notify

    dau_ngay = _dau_ngay_vn_utc(d.hom_nay)
    trung = (await db.execute(select(func.count(Notification.id)).where(
        Notification.user_id == nguoi.id, Notification.type == LOAI_THONG_BAO,
        Notification.ref_id == ref_id, Notification.created_at >= dau_ngay,
    ))).scalar() or 0
    if trung:
        bo_qua.append({"phong": phong, "ly_do": "da_nhac_hom_nay"})
        return
    toi_da = int(d.ch.get("toi_da_tin_ngay") or 2)
    da_nhan = (await db.execute(select(func.count(Notification.id)).where(
        Notification.user_id == nguoi.id, Notification.type == LOAI_THONG_BAO,
        Notification.created_at >= dau_ngay,
    ))).scalar() or 0
    if da_nhan >= toi_da:
        bo_qua.append({"phong": phong, "ly_do": "vuot_2_tin"})
        return
    may = nguoi.id in d.co_push
    cuoi = [f'<a href="{html.escape(_link_tuyet_doi(link), quote=True)}">Mở danh sách đối chiếu (~2 phút)</a>']
    if not may:
        # Chưa bật thông báo trên máy → tin chỉ nằm trong chuông (và Telegram nếu có)
        # tới khi người đó tự mở app. Mời cài app + bật thông báo ngay trong tin.
        cuoi.append(_dong_moi_cai_app())
    noi_dung = "\n".join(dong + cuoi)
    gui = await _notify(
        db, nguoi, LOAI_THONG_BAO, tieu_de, noi_dung, link=link, ref_id=ref_id,
        reply_markup=reply_markup, body_html=True,
    )
    if gui:
        da_gui.append({"phong": phong, "nguoi": nguoi.full_name, "telegram": bool(nguoi.telegram_user_id),
                       "thong_bao_may": may})
    else:
        bo_qua.append({"phong": phong, "ly_do": "da_nhac_hom_nay"})


@router.post("/nhac")
async def nhac(
    body: NhacIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Nhắc trưởng phòng / nhờ nhận dự án cũ / hỏi lại 1 hồ sơ. Không có job tự động."""
    _chan_neu_khong_phai_bgd(current_user)
    await _xep_hang_gui(db, "du_lieu_chung:nhac")
    d = await _nap(db)
    kq = _tinh(d)
    ngay = d.hom_nay.isoformat()
    da_gui: list[dict] = []
    bo_qua: list[dict] = []
    nguoi_db = {u.id: u for u in (await db.execute(select(User).where(User.is_active.is_(True)))).scalars()}

    def _tp(phong: str) -> list[User]:
        return [u for u in nguoi_db.values() if la_truong_phong_cua(u, phong)]

    if body.phong == "chua_xep":
        if body.id:
            raise HTTPException(status_code=400, detail="Hỏi lại từng hồ sơ phải chọn phòng cụ thể")
        so = kq["ngoai_dai"]["chua_xep"]["so_luong"]
        for phong in ("DESIGN", "PURCHASING", "OPS"):
            ds = _tp(phong)
            if not ds:
                bo_qua.append({"phong": phong, "ly_do": "khong_co_truong_phong"})
                continue
            for u in ds:
                await _gui_nhac(
                    db, d, u, phong=phong, ref_id=f"dlc:chua_xep:{ngay}",
                    tieu_de="Nhờ nhận dự án cũ về phòng",
                    dong=[f"{so} dự án đang chạy chưa xếp giai đoạn trên CRM.",
                          f"Dự án nào phòng {TEN_PHONG[phong]} đang làm thì bấm nhận để về đúng phòng."],
                    link=f"/doi-chieu?phong={phong}&tab=chua_xep", reply_markup=None,
                    da_gui=da_gui, bo_qua=bo_qua,
                )
    elif body.id is None:
        phong = body.phong
        ds = _tp(phong)
        if not ds:
            bo_qua.append({"phong": phong, "ly_do": "khong_co_truong_phong"})
        else:
            x = next(p for p in kq["phong"] if p["ma"] == phong)
            tt = x["trang_thai"]
            diem = f"{x['diem']}/100" if x["diem"] is not None else "chưa đủ hồ sơ để chấm"
            for u in ds:
                await _gui_nhac(
                    db, d, u, phong=phong, ref_id=f"dlc:{phong}:{ngay}",
                    tieu_de=f"Nhờ đối chiếu dữ liệu phòng {TEN_PHONG[phong]}",
                    dong=[f"{x['so_ho_so']} hồ sơ: {tt['chua_ro']} chưa có dấu vết trên CRM, {tt['lech']} lệch.",
                          f"Mức phản ánh: {diem}. Chỉ đo, không tính thưởng/phạt."],
                    link=f"/doi-chieu?phong={phong}", reply_markup=None,
                    da_gui=da_gui, bo_qua=bo_qua,
                )
    else:
        phong = body.phong
        loai = body.loai or ("lead" if phong == "SALES" and body.id not in d.pmap else "du_an")
        if loai == "lead" and phong != "SALES":
            # Chỉ Kinh doanh và BGĐ được thấy lead — không gửi tên/giai đoạn lead
            # cho trưởng phòng Thiết kế / Thu mua / Giám sát.
            raise HTTPException(status_code=400, detail="Lead chỉ hỏi lại qua phòng Kinh doanh")
        reply_markup = None
        if loai == "lead":
            lead = await db.get(Lead, body.id)
            if lead is None:
                raise HTTPException(status_code=404, detail="Lead không tồn tại")
            pic_id = lead.assigned_to
            ten = html.escape(lead.name or "")
            # Tiêu đề để chữ thường (danh sách thông báo trong app hiện nguyên văn);
            # _notify tự escape khi bọc `<b>…</b>` gửi Telegram. Thân tin là HTML nên
            # tên khách (dữ liệu ngoài, form báo giá công khai) escape ở đây.
            tieu_de = f"Hỏi lại lead {lead.name or ''}"
            dong = [f"Lead {ten} — CRM ghi: «{NHAN_GIAI_DOAN_LEAD.get(lead.stage, lead.stage)}».",
                    "Chưa thấy cập nhật gần đây. Nếu vẫn đang chăm, ghi một dòng hoạt động hoặc xác nhận ở danh sách đối chiếu."]
        else:
            p = await db.get(Project, body.id)
            if p is None:
                raise HTTPException(status_code=404, detail="Dự án không tồn tại")
            cot = PIC_THEO_PHONG_BAN[phong]
            pic_id = getattr(p, cot, None)
            ten = html.escape(f"{p.code} — {p.client_name or p.name}")
            tieu_de = f"Hỏi lại hồ sơ {p.code or ''}"
            dong = [f"Dự án {ten} — CRM ghi: «{NHAN_GIAI_DOAN.get(p.stage, p.stage)}».",
                    "Chưa thấy dấu vết cập nhật gần đây. Nếu đang làm, bấm «Báo cáo hôm nay» hoặc xác nhận ở danh sách đối chiếu."]
            if phong == "OPS" and p.pm_id:
                reply_markup = {"inline_keyboard": [[
                    {"text": "Báo cáo hôm nay", "callback_data": f"nx:baocao:{p.code}"[:64]},
                    {"text": "Báo sự cố", "callback_data": f"nx:suco:{p.code}"[:64]},
                ]]}
        pic = nguoi_db.get(pic_id) if pic_id else None
        nhan = [pic] if pic is not None and la_nguoi_that(pic) and phong_goc(pic) == phong else _tp(phong)
        if not nhan:
            bo_qua.append({"phong": phong, "ly_do": "khong_co_truong_phong"})
        for u in nhan:
            await _gui_nhac(
                db, d, u, phong=phong, ref_id=f"dlc:hs:{body.id}:{ngay}",
                tieu_de=tieu_de,
                dong=dong, link=f"/doi-chieu?phong={phong}", reply_markup=reply_markup,
                da_gui=da_gui, bo_qua=bo_qua,
            )

    await db.commit()
    cache.clear_prefix("dashboard")
    return {"da_gui": da_gui, "bo_qua": bo_qua}


# ─────────────────────────────────────────────────────────────────────────────
# POST /dashboard/du-lieu-chung/nhac-cai-app
# ─────────────────────────────────────────────────────────────────────────────

class NhacCaiAppIn(BaseModel):
    phong: Literal["SALES", "DESIGN", "PURCHASING", "OPS"] | None = None
    # Có truyền (kể cả danh sách rỗng) là lọc theo ids — danh sách rỗng KHÔNG có
    # nghĩa «gửi tất cả», tránh lỡ tay nhắc cả công ty.
    ids: list[Annotated[str, Field(max_length=64)]] | None = Field(None, max_length=200)


@router.post("/nhac-cai-app")
async def nhac_cai_app(
    body: NhacCaiAppIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Nhắc người CHƯA bật thông báo trên máy: cài JAMA HOME lên điện thoại + bật
    thông báo. Mỗi người tối đa 1 tin loại này/ngày VN; không tính vào giới hạn
    2 tin «Dữ liệu chung». Tin đi chuông + Telegram (nếu có liên kết)."""
    from app.services.automation import _notify

    _chan_neu_khong_phai_bgd(current_user)
    # Xếp hàng TRƯỚC khi đọc «đã nhắc hôm nay» — xem _xep_hang_gui.
    await _xep_hang_gui(db, "du_lieu_chung:nhac_cai_app")
    hom_nay = vn_today()
    co_push = await _nguoi_co_push(db)
    nguoi = [
        u for u in (await db.execute(select(User).where(User.is_active.is_(True)))).scalars()
        if la_nguoi_that(u) and u.id not in co_push
    ]
    if body.phong:
        nguoi = [u for u in nguoi if phong_cua(u) == body.phong]
    if body.ids is not None:
        chon = set(body.ids)
        nguoi = [u for u in nguoi if u.id in chon]
    thu_tu = {p: i for i, p in enumerate(PHONG_KENH)}
    nguoi.sort(key=lambda u: (thu_tu[_phong_kenh(u)], (u.full_name or "").lower(), u.id))

    da_nhac: set[str] = set()
    if nguoi:
        # Chặn theo ngày VN bằng created_at (dedupe của _notify chỉ xét tin CHƯA ĐỌC)
        da_nhac = set((await db.execute(select(distinct(Notification.user_id)).where(
            Notification.type == LOAI_NHAC_CAI_APP,
            Notification.created_at >= _dau_ngay_vn_utc(hom_nay),
            Notification.user_id.in_([u.id for u in nguoi]),
        ))).scalars().all())

    noi_dung = "\n".join([
        "Anh/chị chưa bật thông báo JAMA HOME trên điện thoại nên dễ lỡ việc được giao và tin nhắc.",
        "Cài app lên màn hình chính rồi bật thông báo, mất khoảng 1 phút.",
        _link_cai_app(),
    ])
    da_gui = qua_telegram = bo_qua_da_nhac = 0
    for u in nguoi:
        if u.id in da_nhac:
            bo_qua_da_nhac += 1
            continue
        gui = await _notify(
            db, u, LOAI_NHAC_CAI_APP, "Cài JAMA HOME lên điện thoại", noi_dung,
            link=DUONG_CAI_APP, ref_id=f"cai_app:{hom_nay.isoformat()}", body_html=True,
        )
        if not gui:
            bo_qua_da_nhac += 1
            continue
        da_gui += 1
        qua_telegram += int(bool(u.telegram_user_id))

    await db.commit()
    cache.clear_prefix("dashboard")
    return {"da_gui": da_gui, "qua_telegram": qua_telegram, "bo_qua_da_nhac": bo_qua_da_nhac}


# ─────────────────────────────────────────────────────────────────────────────
# GET/POST /dashboard/du-lieu-chung/doi-chieu
# ─────────────────────────────────────────────────────────────────────────────

def _dong_doi_chieu(d: _DuLieu, p, phong: str, bgd: bool) -> dict:
    cot = PIC_THEO_PHONG_BAN.get(phong)
    pic_id = getattr(p, cot, None) if cot else None
    pic = {"id": pic_id, "ten": d.users[pic_id].full_name} if pic_id and _pic_hop_le(d, pic_id, phong) else None
    dong = {
        "id": p.id, "loai": "du_an", "ma": p.code, "ten": p.name, "khach": p.client_name,
        "dia_chi": p.address, "giai_doan": p.stage, "pic": pic,
        "han_ban_giao": _iso(p.target_end_date),
        "dau_vet_cuoi": _dau_vet_dict(d, d.ev.get((p.id, phong))),
        "doi_chieu_cuoi": _doi_chieu_cuoi(d, "du_an", p.id, phong),
    }
    if bgd:
        dong["gia_tri"] = float(p.total_value or 0)
    return dong


@router.get("/doi-chieu")
async def xem_doi_chieu(
    phong: str | None = Query(None),
    tab: str | None = Query(None, description="ho_so | chua_xep — FE tự chọn tab, API trả cả hai"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Danh sách hồ sơ của MỘT phòng để trưởng phòng xác nhận. Trưởng phòng không thấy tiền."""
    phong = _phong_doi_chieu(current_user, phong)
    bgd = current_user.role in VAI_TRO_BGD
    d = await _nap(db)
    ho_so: list[dict] = []
    chua_xep: list[dict] = []
    if phong == "SALES":
        if duoc_xem_lead(current_user):
            for l in d.leads:
                if l.stage not in LEAD_DOI_CHIEU:
                    continue
                # Cùng phạm vi với /leads (trưởng phòng KD: lead của người cùng bộ
                # phận hoặc của chính mình) — tránh «hiện ở đây mà mở ra 403».
                if not bgd and not await duoc_xem_lead_nay(db, current_user, l):
                    continue
                pic = ({"id": l.assigned_to, "ten": d.users[l.assigned_to].full_name}
                       if l.assigned_to and _pic_hop_le(d, l.assigned_to, "SALES") else None)
                dong = {
                    "id": l.id, "loai": "lead", "ma": None, "ten": l.name, "khach": l.name,
                    "dia_chi": l.address, "giai_doan": l.stage, "pic": pic, "han_ban_giao": None,
                    "dau_vet_cuoi": _dau_vet_dict(d, d.ev_lead.get(l.id)),
                    "doi_chieu_cuoi": _doi_chieu_cuoi(d, "lead", l.id, "SALES"),
                }
                if bgd:
                    dong["gia_tri"] = _gia_tri_lead(l)
                ho_so.append(dong)
    else:
        for p in d.projects:
            if p.stage in GIAI_DOAN_CUA_PHONG[phong]:
                ho_so.append(_dong_doi_chieu(d, p, phong, bgd))
            elif p.stage not in GIAI_DOAN_LAM:
                dong = _dong_doi_chieu(d, p, phong, bgd)
                dong["goi_y_giai_doan"], dong["ly_do_goi_y"] = _goi_y_giai_doan(d, p)
                chua_xep.append(dong)
    nguoi = sorted(
        # department nguyên gốc: đúng tập người mà luật gắn PIC (_kiem_quyen_phan_cong_pic)
        # chấp nhận — người phòng 'PM' cũ không được mời chọn rồi bị từ chối.
        ({"id": u.id, "ten": u.full_name} for u in d.users.values()
         if la_nguoi_that(u) and phong_goc(u) == phong),
        key=lambda x: x["ten"] or "",
    )
    return {"phong": phong, "ho_so": ho_so, "chua_xep": chua_xep, "nguoi_trong_phong": nguoi}


class MucDoiChieu(BaseModel):
    id: str = Field(max_length=64)
    loai: Literal["du_an", "lead"] = "du_an"
    ket_qua: Literal["dung", "sai_giai_doan", "tam_dung", "da_xong"]
    giai_doan_moi: str | None = Field(None, max_length=32)
    pic_id: str | None = Field(None, max_length=36)
    ly_do: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def _tam_dung_phai_co_ly_do(self):
        if self.ket_qua == "tam_dung" and not (self.ly_do or "").strip():
            raise ValueError("Tạm dừng phải ghi lý do")
        return self


# Trần kích thước: mỗi mục là vài lượt đọc DB + 1 dòng audit trong CÙNG một giao
# dịch — một request hàng chục nghìn id sẽ giữ giao dịch rất lâu và phình audit_logs.
# Phòng đông nhất prod (~490 lead KD, ~40 dự án OPS) vẫn nằm gọn trong trần này.
class DoiChieuIn(BaseModel):
    phong: Literal["SALES", "DESIGN", "PURCHASING", "OPS"]
    muc: list[MucDoiChieu] = Field(default_factory=list, max_length=500)
    tat_ca_con_lai_dung: bool = False
    ids_hien_thi: list[Annotated[str, Field(max_length=64)]] = Field(default_factory=list, max_length=1000)


@router.post("/doi-chieu")
async def gui_doi_chieu(
    body: DoiChieuIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ghi kết quả đối chiếu. Mỗi mục = 1 dòng audit `doi_chieu:<PHÒNG>`.

    sai_giai_doan đổi stage thật (helper dùng chung với PUT stage), tam_dung → status
    paused + lý do, da_xong chỉ ghi nhận rồi dồn về BGĐ, pic_id qua đúng luật gắn PIC.
    Lỗi từng mục không làm hỏng các mục khác — trả trong `loi`.
    """
    from app.api.leads import change_stage
    from app.api.projects import (
        _kiem_quyen_phan_cong_pic, _thong_bao_gan_pic, NHAN_PIC, doi_giai_doan_du_an,
        duoc_doi_giai_doan,
    )
    from app.schemas.lead import LeadStageChange
    from app.services.audit import log_action

    phong = _phong_doi_chieu(current_user, body.phong)
    bgd = current_user.role in VAI_TRO_BGD
    da_ghi = da_doi = 0
    loi: list[dict] = []
    da_xu_ly: set[str] = set()

    async def _ghi(loai: str, eid: str, sau: dict) -> None:
        nonlocal da_ghi
        await log_action(
            db, actor=current_user, action=f"doi_chieu:{phong}",
            entity_type="project" if loai == "du_an" else "lead", entity_id=eid, after=sau,
        )
        da_ghi += 1

    for m in body.muc:
        da_xu_ly.add(m.id)
        sau: dict = {"ket_qua": m.ket_qua}
        if m.loai == "lead":
            if phong != "SALES" or not duoc_xem_lead(current_user):
                loi.append({"id": m.id, "ly_do": "khong_phai_ho_so_cua_phong"})
                continue
            lead = await db.get(Lead, m.id)
            if lead is None:
                loi.append({"id": m.id, "ly_do": "khong_ton_tai"})
                continue
            # Chỉ lead đang hiện trên trang (deal chờ ký, trong phạm vi xem /leads) —
            # không ghi audit đối chiếu (vào điểm Đối chiếu) cho lead người này không thấy.
            if lead.stage not in LEAD_DOI_CHIEU or not await duoc_xem_lead_nay(db, current_user, lead):
                loi.append({"id": m.id, "ly_do": "khong_phai_ho_so_cua_phong"})
                continue
            if m.pic_id or m.ket_qua in ("tam_dung", "da_xong"):
                loi.append({"id": m.id, "ly_do": "khong_ap_dung_cho_lead"})
                continue
            if m.ket_qua == "sai_giai_doan":
                if m.giai_doan_moi not in LEAD_DOI_DUOC:
                    loi.append({"id": m.id, "ly_do": "giai_doan_khong_hop_le"})
                    continue
                if m.giai_doan_moi != lead.stage:
                    # Dùng lại nguyên PUT /leads/{id}/stage (quyền, luật chuyển, Activity
                    # stage_change). Hàm đó chặn TRƯỚC khi sửa gì nên lỗi không để lại rác.
                    try:
                        await change_stage(lead.id, LeadStageChange(new_stage=m.giai_doan_moi),
                                           db=db, current_user=current_user)
                    except HTTPException as e:
                        loi.append({"id": m.id, "ly_do": str(e.detail)})
                        continue
                    da_doi += 1
                sau["giai_doan_moi"] = m.giai_doan_moi
            await _ghi("lead", lead.id, sau)
            continue

        # ── Dự án ──
        if phong == "SALES" and not bgd:
            # Trưởng phòng KD chỉ đối chiếu lead (spec B1); dự án đã có PIC KD sửa ở /projects
            loi.append({"id": m.id, "ly_do": "khong_phai_ho_so_cua_phong"})
            continue
        p = await db.get(Project, m.id)
        if p is None:
            loi.append({"id": m.id, "ly_do": "khong_ton_tai"})
            continue
        chua_xep = p.status in TRANG_THAI_CHAY and p.stage not in GIAI_DOAN_LAM
        trong_pham_vi = (p.status in TRANG_THAI_CHAY
                         and (phong == "SALES" or p.stage in GIAI_DOAN_CUA_PHONG[phong]))
        if not bgd and not (trong_pham_vi or chua_xep):
            loi.append({"id": m.id, "ly_do": "khong_phai_ho_so_cua_phong"})
            continue
        if chua_xep and m.ket_qua != "sai_giai_doan" and not bgd:
            loi.append({"id": m.id, "ly_do": "chua_xep_chi_nhan_giai_doan"})
            continue

        # pic_id kiểm TRƯỚC khi ghi gì — sai thì bỏ cả mục
        cot = PIC_THEO_PHONG_BAN[phong]
        if m.pic_id is not None and m.pic_id != getattr(p, cot):
            # Với MỌI người gọi (kể cả BGĐ — _kiem_quyen_phan_cong_pic để BGĐ đi
            # thẳng): phải là người thật đang làm, đúng phòng theo department nguyên
            # gốc (= nguoi_trong_phong). Id không tồn tại sẽ vỡ khoá ngoại khi flush
            # trên Postgres → 500 và mất cả lô.
            u_pic = await db.get(User, m.pic_id)
            if not (la_nguoi_that(u_pic) and phong_goc(u_pic) == phong):
                loi.append({"id": m.id, "ly_do": "pic_khong_hop_le"})
                continue
            try:
                await _kiem_quyen_phan_cong_pic(db, current_user, p, {cot: m.pic_id})
            except HTTPException as e:
                loi.append({"id": m.id, "ly_do": str(e.detail)})
                continue

        if m.ket_qua == "sai_giai_doan":
            if m.giai_doan_moi not in GIAI_DOAN_LAM:
                loi.append({"id": m.id, "ly_do": "giai_doan_khong_hop_le"})
                continue
            if chua_xep and not bgd and m.giai_doan_moi not in GIAI_DOAN_CUA_PHONG.get(phong, ()):
                loi.append({"id": m.id, "ly_do": "chi_nhan_ve_giai_doan_cua_phong"})
                continue
            if not duoc_doi_giai_doan(current_user):
                loi.append({"id": m.id, "ly_do": "khong_co_quyen_doi_giai_doan"})
                continue
            if m.giai_doan_moi != p.stage or p.status == "paused":
                # Helper chặn (403/409) TRƯỚC khi sửa gì nên lỗi không để lại rác
                try:
                    await doi_giai_doan_du_an(db, p, m.giai_doan_moi, actor=current_user)
                except HTTPException as e:
                    loi.append({"id": m.id, "ly_do": str(e.detail)})
                    continue
                da_doi += 1
            sau["giai_doan_moi"] = m.giai_doan_moi
        elif m.ket_qua == "tam_dung":
            if not duoc_doi_giai_doan(current_user):
                loi.append({"id": m.id, "ly_do": "khong_co_quyen_doi_giai_doan"})
                continue
            ly_do = (m.ly_do or "").strip()
            await doi_giai_doan_du_an(db, p, "paused", actor=current_user, pause_reason=ly_do)
            # Đang tạm dừng sẵn thì helper giữ lý do cũ — ghi đè bằng lý do mới
            p.pause_reason = ly_do
            sau["ly_do"] = ly_do

        if m.pic_id is not None and m.pic_id != getattr(p, cot):
            pic_cu = {c: getattr(p, c, None) for c in NHAN_PIC}
            setattr(p, cot, m.pic_id)
            await db.flush()
            await _thong_bao_gan_pic(db, p, pic_cu, current_user)
            sau["pic_id"] = m.pic_id
        await _ghi("du_an", p.id, sau)

    if body.tat_ca_con_lai_dung:
        for eid in body.ids_hien_thi:
            if eid in da_xu_ly:
                continue
            da_xu_ly.add(eid)
            if phong == "SALES":
                lead = await db.get(Lead, eid) if duoc_xem_lead(current_user) else None
                if (lead is None or lead.stage not in LEAD_DOI_CHIEU
                        or not await duoc_xem_lead_nay(db, current_user, lead)):
                    loi.append({"id": eid, "ly_do": "khong_phai_ho_so_cua_phong"})
                    continue
                await _ghi("lead", eid, {"ket_qua": "dung"})
            else:
                p = await db.get(Project, eid)
                if (p is None or p.status not in TRANG_THAI_CHAY
                        or p.stage not in GIAI_DOAN_CUA_PHONG[phong]):
                    loi.append({"id": eid, "ly_do": "khong_phai_ho_so_cua_phong"})
                    continue
                await _ghi("du_an", eid, {"ket_qua": "dung"})

    await db.commit()
    cache.clear_prefix("dashboard")
    return {"da_ghi": da_ghi, "da_doi_giai_doan": da_doi, "loi": loi}
