"""SLA & nhắc hạn cho ĐẦU VIỆC của dự án (13/10/2026).

Yêu cầu chủ dự án: «đảm bảo thông báo công việc được gửi đi cho từng nhân sự /
tài khoản khi (1) gắn tag, PIC công việc, (2) task quá hạn, (3) task vi phạm SLA
đã thống nhất».

Đo trước khi làm — trạng thái cũ của hệ thống báo cáo:
- Giao việc: chỉ endpoint `PATCH /tasks/{id}/assign` gửi thông báo; 3 đường còn
  lại (`create_task`, `update_task`, `bulk_assign_tasks`) im lặng hoàn toàn.
- Quá hạn: `tasks.due_date` gần như luôn NULL (19 đầu việc mẫu sinh lúc «Deal
  thắng» không đặt hạn; chỉ AI `task_coordinator` mới ghi hạn, mà agent đó chỉ
  chạy cho dự án CHƯA có task nào ⇒ thực tế không bao giờ chạy). Hệ quả: ô «việc
  quá hạn» trên Tổng quan luôn bằng 0 dù việc trễ cả tháng.
- SLA: KHÔNG tồn tại cho đầu việc. SLA cũ chỉ có ở phê duyệt (24/48/72 giờ) và
  lead (3 ngày).

Hai mốc KHÁC NHAU, cố ý không gộp:
- `due_date`   — HẠN THOẢ THUẬN với khách/nội bộ cho riêng đầu việc đó. Người
                 phụ trách tự đặt. Trễ mốc này ⇒ "quá hạn".
- `sla_due_at` — CHUẨN NỘI BỘ = `started_at` + số ngày SLA của đầu việc, tính tự
                 động. Trễ mốc này ⇒ "vi phạm SLA".
Một việc trễ cả hai mốc trong cùng một ngày thì CHỈ gửi thông báo "quá hạn":
cùng một sự thật mà bắn hai thông báo thì người ta tắt cả hai.

Ai nhận (chốt với chủ dự án): người đảm nhận trước; để quá lâu thì leo thang lên
trưởng phòng + PM dự án. Kênh: trong app + Telegram (dùng chung `_notify`).
"""

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.middleware.rbac import VAI_TRO_TRUONG_PHONG
from app.models.notification import SystemSetting
from app.models.project import Project, Task, TaskAssignee, task_department_for_stage
from app.models.user import User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cấu hình SLA — lưu JSON trong `system_settings`, sửa được ở trang Cài đặt
# ---------------------------------------------------------------------------

KEY_SLA_DAU_VIEC = "task_sla_days"          # {"2D Concept": 3, ...}
KEY_SLA_PHONG_BAN = "task_sla_dept_days"    # {"design": 5, ...}
KEY_SLA_LEO_THANG = "task_sla_escalate_days"  # trễ bao nhiêu ngày thì báo cấp trên
KEY_SLA_BAT = "task_sla_enabled"

# Số ngày chuẩn cho 19 đầu việc mẫu. Đề xuất ban đầu dựa trên khối lượng thực tế
# của từng đầu việc (thi công thô dài nhất, báo giá ngắn nhất); chủ dự án sửa lại
# trong Cài đặt khi có số liệu thật, KHÔNG phải sửa code.
SLA_MAC_DINH_DAU_VIEC: dict[str, int] = {
    "2D Concept": 3,
    "3D Demo": 4,
    "3D Render": 5,
    "Triển khai bản vẽ kỹ thuật": 7,
    "Thiết kế Final": 3,
    "Báo giá 2D": 2,
    "Báo giá 3D": 2,
    "Báo giá Nội thất": 3,
    "Báo giá chốt khách (Final)": 2,
    "Chuẩn bị vật liệu": 5,
    "Hoàn thành SPECS": 4,
    "Đặt hàng": 3,
    "Xin phép (nếu có)": 5,
    "Lập bảng tiến độ": 2,
    "Thi công thô": 20,
    "Thi công nội thất": 15,
    "Bàn giao công trình": 3,
    "Nghiệm thu khối lượng": 3,
    "Bảo hành – Bảo trì": 7,
}

# Việc tạo tay có tiêu đề tự do → không khớp bảng trên, rơi về chuẩn của phòng.
SLA_MAC_DINH_PHONG_BAN: dict[str, int] = {
    "design": 5,
    "quotation": 3,
    "procurement": 5,
    "construction": 15,
    "accounting": 3,
    "sales": 3,
}

SLA_MAC_DINH_CHUNG = 5
LEO_THANG_MAC_DINH = 2

# Phòng ban của ĐẦU VIỆC → phòng ban CÔNG TY (cột `users.department`). Soi gương
# `DEPT_TO_USER_DEPT` ở frontend/src/app/projects/page.tsx để hai bên không lệch:
# báo giá do phòng Dự toán–Thu mua làm, nghiệm thu do đội Giám sát (OPS).
PHONG_CONG_TY_THEO_PHONG_VIEC: dict[str, str] = {
    "design": "DESIGN",
    "quotation": "PURCHASING",
    "procurement": "PURCHASING",
    "construction": "OPS",
    "acceptance": "OPS",
    "accounting": "ACCT",
    "sales": "SALES",
}


def _doc_json(raw: str | None, mac_dinh: dict) -> dict:
    """Đọc cấu hình JSON; cấu hình gãy thì dùng mặc định chứ không làm sập worker."""
    if not raw:
        return dict(mac_dinh)
    try:
        du_lieu = json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("Cấu hình SLA không phải JSON hợp lệ — dùng mặc định")
        return dict(mac_dinh)
    if not isinstance(du_lieu, dict):
        return dict(mac_dinh)
    gop = dict(mac_dinh)
    for k, v in du_lieu.items():
        try:
            so = int(v)
        except (TypeError, ValueError):
            continue
        if so > 0:
            gop[str(k)] = so
    return gop


async def lay_cau_hinh_sla(db: AsyncSession) -> dict:
    """Cấu hình SLA hiệu lực = mặc định trong code ⊕ phần đã sửa trong Cài đặt."""
    rows = await db.execute(
        select(SystemSetting).where(
            SystemSetting.key.in_(
                [KEY_SLA_DAU_VIEC, KEY_SLA_PHONG_BAN, KEY_SLA_LEO_THANG, KEY_SLA_BAT]
            )
        )
    )
    luu = {s.key: s.value for s in rows.scalars().all()}
    try:
        leo_thang = max(0, int(luu.get(KEY_SLA_LEO_THANG, LEO_THANG_MAC_DINH)))
    except (TypeError, ValueError):
        leo_thang = LEO_THANG_MAC_DINH
    return {
        "dau_viec": _doc_json(luu.get(KEY_SLA_DAU_VIEC), SLA_MAC_DINH_DAU_VIEC),
        "phong_ban": _doc_json(luu.get(KEY_SLA_PHONG_BAN), SLA_MAC_DINH_PHONG_BAN),
        "leo_thang_ngay": leo_thang,
        "bat": (luu.get(KEY_SLA_BAT, "true") or "true").lower() != "false",
    }


async def luu_cau_hinh_sla(
    db: AsyncSession,
    dau_viec: dict | None = None,
    phong_ban: dict | None = None,
    leo_thang_ngay: int | None = None,
    bat: bool | None = None,
) -> dict:
    """Ghi cấu hình SLA. Chỉ lưu phần KHÁC mặc định để bảng settings không phình."""
    async def _ghi(key: str, value: str) -> None:
        s = await db.get(SystemSetting, key)
        if s:
            s.value = value
        else:
            db.add(SystemSetting(key=key, value=value))

    if dau_viec is not None:
        khac = {
            k: int(v) for k, v in dau_viec.items()
            if int(v) > 0 and SLA_MAC_DINH_DAU_VIEC.get(k) != int(v)
        }
        await _ghi(KEY_SLA_DAU_VIEC, json.dumps(khac, ensure_ascii=False))
    if phong_ban is not None:
        khac = {
            k: int(v) for k, v in phong_ban.items()
            if int(v) > 0 and SLA_MAC_DINH_PHONG_BAN.get(k) != int(v)
        }
        await _ghi(KEY_SLA_PHONG_BAN, json.dumps(khac, ensure_ascii=False))
    if leo_thang_ngay is not None:
        await _ghi(KEY_SLA_LEO_THANG, str(max(0, int(leo_thang_ngay))))
    if bat is not None:
        await _ghi(KEY_SLA_BAT, "true" if bat else "false")
    await db.flush()
    return await lay_cau_hinh_sla(db)


# ---------------------------------------------------------------------------
# Tính mốc SLA
# ---------------------------------------------------------------------------

def _phong_cua_viec(task: Task) -> str:
    return (task.department or task_department_for_stage(task.stage) or "").lower()


def so_ngay_sla(task: Task, cau_hinh: dict) -> int:
    """Số ngày chuẩn cho một đầu việc: theo tên việc → theo phòng → chung."""
    theo_ten = cau_hinh["dau_viec"].get((task.title or "").strip())
    if theo_ten:
        return int(theo_ten)
    theo_phong = cau_hinh["phong_ban"].get(_phong_cua_viec(task))
    if theo_phong:
        return int(theo_phong)
    return SLA_MAC_DINH_CHUNG


def tinh_han_sla(task: Task, cau_hinh: dict) -> datetime | None:
    """Mốc SLA = `started_at` + số ngày chuẩn. Việc chưa bắt đầu thì chưa có mốc —
    SLA đo thời gian LÀM, không đo thời gian chờ tới lượt."""
    moc = task.started_at
    if moc is None:
        return None
    if moc.tzinfo is None:
        moc = moc.replace(tzinfo=timezone.utc)
    return moc + timedelta(days=so_ngay_sla(task, cau_hinh))


def _utc(dt: datetime | None) -> datetime | None:
    """Mốc đọc từ DB (SQLite trả naive) → luôn so sánh ở UTC."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Người nhận thông báo
# ---------------------------------------------------------------------------

async def nguoi_leo_thang(db: AsyncSession, task: Task) -> list[User]:
    """Trưởng phòng của phòng làm việc đó + PM dự án (bỏ trùng, bỏ người đã nghỉ)."""
    phong = PHONG_CONG_TY_THEO_PHONG_VIEC.get(_phong_cua_viec(task))
    nguoi: dict[str, User] = {}
    vai_tro = VAI_TRO_TRUONG_PHONG.get(phong or "", set())
    if vai_tro:
        rows = await db.execute(
            select(User).where(
                User.is_active == True,  # noqa: E712
                func.upper(func.coalesce(User.department, "")) == phong,
                User.role.in_(tuple(vai_tro)),
            )
        )
        for u in rows.scalars().all():
            nguoi[u.id] = u
    du_an = task.project
    if du_an is not None and du_an.pm_id:
        pm = await db.get(User, du_an.pm_id)
        if pm is not None and pm.is_active:
            nguoi[pm.id] = pm
    return list(nguoi.values())


def _nguoi_lam(task: Task) -> list[User]:
    """Người đảm nhận còn hiệu lực. `task_assignees` là nguồn sự thật; `assigned_to`
    chỉ là bản sao nên không đọc ở đây, tránh đếm hai lần."""
    return [a.user for a in (task.assignees or []) if a.user is not None and a.user.is_active]


# ---------------------------------------------------------------------------
# Hai job nhắc hạn
# ---------------------------------------------------------------------------

def _truy_van_task():
    """Việc chưa xong, nạp kèm nhóm đảm nhận + dự án.

    Phải là HÀM chứ không phải hằng số module: `selectinload` buộc SQLAlchemy cấu
    hình mapper ngay lúc import, mà lúc đó registry chưa có đủ model (Quotation,
    Contract…) nên app sập khi khởi động.
    """
    return (
        select(Task)
        .options(
            selectinload(Task.assignees).selectinload(TaskAssignee.user),
            selectinload(Task.project),
        )
        .where(Task.status != "done")
    )


async def dong_bo_han_sla(db: AsyncSession, cau_hinh: dict | None = None) -> int:
    """Điền `sla_due_at` cho việc đã bắt đầu mà còn thiếu mốc (dữ liệu cũ, hoặc
    chủ dự án vừa đổi số ngày SLA trong Cài đặt)."""
    cau_hinh = cau_hinh or await lay_cau_hinh_sla(db)
    rows = await db.execute(
        _truy_van_task().where(Task.started_at.is_not(None), Task.sla_due_at.is_(None))
    )
    dem = 0
    for task in rows.scalars().all():
        han = tinh_han_sla(task, cau_hinh)
        if han is not None:
            task.sla_due_at = han
            dem += 1
    if dem:
        await db.flush()
    return dem


async def _gui_canh_bao(
    db: AsyncSession,
    task: Task,
    loai: str,
    tieu_de: str,
    noi_dung: str,
    so_ngay_tre: int,
    leo_thang_ngay: int,
) -> int:
    """Gửi cho từng người đảm nhận; trễ quá `leo_thang_ngay` thì gửi thêm cấp trên."""
    # Import muộn: automation.py đã import nhiều model, import vòng ở module level
    # sẽ gãy khi worker nạp task_sla trước automation.
    from app.services.automation import _notify

    da_gui = 0
    lam_viec = _nguoi_lam(task)
    for nguoi in lam_viec:
        if await _notify(
            db, nguoi, loai, tieu_de, noi_dung,
            link=f"/projects?id={task.project_id}", ref_id=task.id,
        ):
            da_gui += 1

    if so_ngay_tre < max(1, leo_thang_ngay):
        return da_gui

    ten_nguoi_lam = ", ".join(n.full_name for n in lam_viec) or "CHƯA AI NHẬN"
    for cap_tren in await nguoi_leo_thang(db, task):
        if any(cap_tren.id == n.id for n in lam_viec):
            continue  # vừa nhận với vai người làm, khỏi gửi lần hai
        if await _notify(
            db, cap_tren, "task_escalated",
            f"Việc trễ {so_ngay_tre} ngày cần can thiệp: {task.title}",
            f"{noi_dung}\nNgười đảm nhận: {ten_nguoi_lam}",
            link=f"/projects?id={task.project_id}", ref_id=task.id,
        ):
            da_gui += 1
    return da_gui


async def run_task_overdue_alerts(db: AsyncSession) -> int:
    """(2) Việc quá HẠN THOẢ THUẬN (`due_date`)."""
    cau_hinh = await lay_cau_hinh_sla(db)
    bay_gio = datetime.now(timezone.utc)
    rows = await db.execute(_truy_van_task().where(Task.due_date.is_not(None)))
    dem = 0
    for task in rows.scalars().all():
        han = _utc(task.due_date)
        if han is None or han >= bay_gio:
            continue
        so_ngay_tre = max(1, (bay_gio - han).days)
        ten_du_an = task.project.name if task.project else ""
        dem += await _gui_canh_bao(
            db, task, "task_overdue",
            f"Việc quá hạn {so_ngay_tre} ngày: {task.title}",
            f"Dự án {ten_du_an} — hạn {han.strftime('%d/%m/%Y')}. "
            f"Vào cập nhật tiến độ hoặc đổi hạn nếu đã thống nhất lại.",
            so_ngay_tre, cau_hinh["leo_thang_ngay"],
        )
    return dem


async def run_task_sla_alerts(db: AsyncSession) -> int:
    """(3) Việc vượt CHUẨN NỘI BỘ (`sla_due_at`)."""
    cau_hinh = await lay_cau_hinh_sla(db)
    if not cau_hinh["bat"]:
        return 0
    await dong_bo_han_sla(db, cau_hinh)
    bay_gio = datetime.now(timezone.utc)
    rows = await db.execute(_truy_van_task().where(Task.sla_due_at.is_not(None)))
    dem = 0
    for task in rows.scalars().all():
        han = _utc(task.sla_due_at)
        if han is None or han >= bay_gio:
            continue
        han_thoa_thuan = _utc(task.due_date)
        if han_thoa_thuan is not None and han_thoa_thuan < bay_gio:
            continue  # đã báo "quá hạn" — không bắn hai thông báo cho một sự thật
        so_ngay_tre = max(1, (bay_gio - han).days)
        ten_du_an = task.project.name if task.project else ""
        dem += await _gui_canh_bao(
            db, task, "task_sla_breach",
            f"Vượt SLA {so_ngay_tre} ngày: {task.title}",
            f"Dự án {ten_du_an} — chuẩn nội bộ {so_ngay_sla(task, cau_hinh)} ngày "
            f"kể từ lúc bắt đầu, đã vượt mốc {han.strftime('%d/%m/%Y')}.",
            so_ngay_tre, cau_hinh["leo_thang_ngay"],
        )
    return dem


async def run_task_alerts(db: AsyncSession) -> dict[str, int]:
    """Gộp hai job cho worker gọi một lần mỗi ngày."""
    qua_han = await run_task_overdue_alerts(db)
    vuot_sla = await run_task_sla_alerts(db)
    await db.commit()
    return {"task_overdue": qua_han, "task_sla_breach": vuot_sla}
