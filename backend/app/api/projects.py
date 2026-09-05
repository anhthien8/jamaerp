"""Projects API — CRUD, tasks."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, case, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.project import Project, Task, TaskActivity, task_department_for_stage
from app.middleware.rbac import (
    PIC_THEO_PHONG_BAN, la_pic_du_an, la_truong_phong, pham_vi_du_an,
)
from app.models.notification import Notification
from app.cache import cache
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, TaskResponse,
    TaskActivityCreate, TaskActivityResponse
)
from pydantic import BaseModel

_PHONE_UNMASK_ROLES = {"admin", "leader", "data_entry"}


def _mask_phone(phone: str | None, current_user=None) -> str | None:
    """Mask phone for non-privileged roles: show first 3 digits + '***'."""
    if not phone or not current_user or current_user.role in _PHONE_UNMASK_ROLES:
        return phone
    return phone[:3] + "***" if len(phone) >= 3 else "***"


def _mask_project_response(proj_resp, current_user=None):
    """Mask client_phone in a ProjectResponse dict."""
    d = proj_resp.model_dump() if not isinstance(proj_resp, dict) else proj_resp
    d["client_phone"] = _mask_phone(d.get("client_phone"), current_user)
    return d


# ── RBAC dependency ──────────────────────────────────────────────────────────

async def require_project_access(
    project_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Role-based access guard for project endpoints.

    - admin / executive: full access everywhere.
    - For list endpoints (project_id is None): all authenticated users can read.
    - For detail / update endpoints the user must be:
        * the assigned PM,
        * the assigned designer,
        * the assigned sales person, OR
        * a team leader (leader role), OR
        * accountant / purchasing (read-only — enforced at the endpoint level).
    """
    if current_user.role in ("admin", "executive"):
        return current_user
    # For list endpoints, all authenticated users can read
    if project_id is None:
        return current_user
    # For detail/update, check ownership
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    pham_vi = pham_vi_du_an(current_user)
    if pham_vi == "tat_ca":
        return current_user
    if la_pic_du_an(current_user, project):
        return current_user
    if pham_vi == "phong_ban":
        # Trưởng phòng: dự án nào có PIC thuộc bộ phận mình thì xem được.
        cot = PIC_THEO_PHONG_BAN.get((current_user.department or "").upper())
        if cot and getattr(project, cot, None):
            nguoi = await db.get(User, getattr(project, cot))
            if nguoi and (nguoi.department or "").upper() == (current_user.department or "").upper():
                return current_user
    # Được giao đầu việc trong dự án cũng phải xem được dự án đó
    co_task = (await db.execute(
        select(func.count(Task.id)).where(
            Task.project_id == project.id, Task.assigned_to == current_user.id
        )
    )).scalar() or 0
    if co_task:
        return current_user
    if await _chua_phan_cong_pic(db, project):
        return current_user
    raise HTTPException(status_code=403, detail="Bạn không phụ trách dự án này")


# ── «Chưa phân công PIC» — lối thoát để không tắt trắng màn hình Dự án ───────
# Đo prod ngay sau khi bật lọc phạm vi (05/09): 113 dự án nhưng pm_id/
# designer_id/purchasing_id đều = 0, 108/113 sales_id trỏ vào tài khoản admin
# (dấu vết lúc import), và 0 đầu việc nào được giao người. Hệ quả: 50 nhân sự
# mở mục Dự án thấy màn hình trống. Chốt với chủ dự án: dự án CHƯA phân công
# thì giữ nguyên như cũ (ai cũng xem được); vừa gắn PIC là nó tự động chỉ còn
# người phụ trách + trưởng phòng thấy.
#
# «Chưa phân công» tính theo BỘ PHẬN chứ không theo NULL — nếu chỉ xét NULL thì
# 108 dự án có sales_id=admin vẫn biến mất khỏi màn hình cả công ty. Một cột chỉ
# tính là ĐÃ phân công khi người trong đó đúng là nhân sự của bộ phận tương ứng.
# Cố ý KHÔNG dọn 108 giá trị sales_id đó về NULL: cột này còn được hợp đồng/hoa
# hồng (contracts.py), portal khách hàng và bot Telegram dùng.

def _dieu_kien_chua_phan_cong():
    """Điều kiện SQL: dự án chưa có PIC đúng bộ phận ở bất kỳ vai nào."""
    da_phan_cong = []
    for dept, cot in PIC_THEO_PHONG_BAN.items():
        nhan_su_phong = select(User.id).where(
            func.upper(func.coalesce(User.department, "")) == dept
        )
        # coalesce để cột NULL cho ra FALSE thay vì NULL — thiếu nó thì `~or_(...)`
        # ra NULL và dự án trống PIC bị loại sạch, đúng cái đang muốn tránh.
        da_phan_cong.append(func.coalesce(getattr(Project, cot), "").in_(nhan_su_phong))
    return ~or_(*da_phan_cong)


async def _chua_phan_cong_pic(db: AsyncSession, project: Project) -> bool:
    """Bản kiểm trên 1 dự án — dùng cho guard chi tiết, khớp với điều kiện SQL trên."""
    for dept, cot in PIC_THEO_PHONG_BAN.items():
        uid = getattr(project, cot, None)
        if not uid:
            continue
        nguoi = await db.get(User, uid)
        if nguoi and (nguoi.department or "").upper() == dept:
            return False
    return True

class ProjectStageUpdate(BaseModel):
    stage: str
    pause_reason: str | None = None

class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    stage: str = "design"
    department: str | None = None
    assigned_to: str | None = None
    order: int = 0
    status: str = "not_started"


class TaskStatusUpdate(BaseModel):
    status: str


class TaskAssignUpdate(BaseModel):
    """Body của PUT .../assign — phải khai báo assigned_to.

    Trước 12/08/2026 endpoint này dùng TaskStatusUpdate (chỉ có `status`), nên
    Pydantic loại bỏ `assigned_to` do FE gửi mà không báo lỗi: API trả 200, giao
    diện hiện "Đã giao việc cho X" nhưng task vẫn chưa có người làm.
    """
    assigned_to: str
    status: str | None = None

class TaskFileUpdate(BaseModel):
    final_file_url: str | None = None
    version_label: str | None = None

class BulkTaskAssign(BaseModel):
    assignments: list[dict]  # each dict: {"task_id": str, "assigned_to": str}

class ProjectKanbanStage(BaseModel):
    stage: str
    stage_label: str
    projects: list[ProjectResponse]
    count: int

router = APIRouter(prefix="/projects", tags=["projects"])


# ── Ưu tiên nguồn lực (docs/specs/07 Phần B) ─────────────────────────────────
# Sort mặc định: quá hạn → còn ≤14 ngày → còn ≤30 ngày → còn lại;
# trong cùng nhóm: hợp đồng giá trị lớn trước. Completed/cancelled chìm cuối.
# Ngưỡng 14/30 ngày chỉnh được qua SystemSetting (project_urgent_days/project_warning_days).

_RUNNING_STATUSES = ("active", "paused")


async def _priority_thresholds(db: AsyncSession) -> tuple[int, int]:
    from app.services.automation import get_automation_settings
    settings = await get_automation_settings(db)
    try:
        urgent = max(1, int(settings.get("project_urgent_days", "14")))
        warning = max(urgent, int(settings.get("project_warning_days", "30")))
    except (TypeError, ValueError):
        urgent, warning = 14, 30
    return urgent, warning


def _priority_order(urgent_days: int, warning_days: int) -> list:
    now = datetime.now(timezone.utc)
    running = Project.status.in_(_RUNNING_STATUSES)
    has_deadline = Project.target_end_date.is_not(None)
    bucket = case(
        (and_(running, has_deadline, Project.target_end_date < now), 0),                                   # quá hạn
        (and_(running, has_deadline, Project.target_end_date <= now + timedelta(days=urgent_days)), 1),    # cận hạn
        (and_(running, has_deadline, Project.target_end_date <= now + timedelta(days=warning_days)), 2),   # sắp tới hạn
        (running, 3),                                                                                       # đang chạy, còn xa/chưa đặt hạn
        else_=4,                                                                                            # completed/cancelled
    )
    return [
        bucket.asc(),
        Project.total_value.desc().nulls_last(),
        Project.target_end_date.asc().nulls_last(),
    ]


async def _stage_progress_map(db: AsyncSession, project_ids: list[str]) -> dict[str, dict[str, dict]]:
    """1 aggregate query: {project_id: {stage: {done, total}}} — cho thanh 5 khối trên thẻ."""
    if not project_ids:
        return {}
    result = await db.execute(
        select(
            Task.project_id,
            Task.stage,
            func.count(Task.id).label("total"),
            func.sum(case((Task.status == "done", 1), else_=0)).label("done"),
        )
        .where(Task.project_id.in_(project_ids))
        .group_by(Task.project_id, Task.stage)
    )
    progress: dict[str, dict[str, dict]] = {}
    for project_id, stage, total, done in result.all():
        progress.setdefault(project_id, {})[stage] = {"done": int(done or 0), "total": int(total or 0)}
    return progress


@router.get("")
async def list_projects(
    status: str | None = None,
    sort: str = Query("priority", pattern=r"^(priority|newest)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_project_access),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """List projects — mặc định sắp theo ưu tiên nguồn lực (spec 07B)."""
    if sort == "priority":
        urgent, warning = await _priority_thresholds(db)
        q = select(Project).order_by(*_priority_order(urgent, warning))
    else:
        q = select(Project).order_by(Project.created_at.desc())
    if status:
        q = q.where(Project.status == status)

    # ── Phạm vi theo bộ phận (05/09/2026) ────────────────────────────────
    # Trước đây endpoint này KHÔNG lọc gì: mọi tài khoản thấy toàn bộ dự án.
    pham_vi = pham_vi_du_an(current_user)
    if pham_vi != "tat_ca":
        # Dự án mình là PIC, hoặc mình được giao ít nhất 1 đầu việc trong đó.
        du_an_co_task = select(Task.project_id).where(Task.assigned_to == current_user.id)
        dieu_kien = [
            Project.pm_id == current_user.id,
            Project.designer_id == current_user.id,
            Project.sales_id == current_user.id,
            Project.purchasing_id == current_user.id,
            Project.id.in_(du_an_co_task),
            # Dự án chưa phân công PIC nào: giữ nguyên như trước, ai cũng xem được.
            _dieu_kien_chua_phan_cong(),
        ]
        if pham_vi == "phong_ban":
            # Trưởng phòng: thêm mọi dự án có PIC thuộc bộ phận mình.
            dept = (current_user.department or "").upper()
            cot = PIC_THEO_PHONG_BAN.get(dept)
            if cot:
                nguoi_cung_phong = select(User.id).where(
                    func.upper(func.coalesce(User.department, "")) == dept
                )
                dieu_kien.append(getattr(Project, cot).in_(nguoi_cung_phong))
        q = q.where(or_(*dieu_kien))

    # Count total (before pagination)
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    projects = result.scalars().all()

    return {
        "items": [_mask_project_response(ProjectResponse.model_validate(p), current_user) for p in projects],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/pipeline/kanban", response_model=list[ProjectKanbanStage])
async def project_kanban(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_project_access),
):
    """Kanban board data — projects grouped by stage."""
    stages = ["design", "quotation", "procurement", "construction", "acceptance", "paused", "completed"]
    stage_labels = {
        "design": "Thiết kế",
        "quotation": "Báo giá",
        "procurement": "Thu mua",
        "construction": "Thi công",
        "acceptance": "Nghiệm thu",
        "paused": "Tạm dừng",
        "completed": "Hoàn thành",
    }
    kanban = []
    urgent, warning = await _priority_thresholds(db)
    priority = _priority_order(urgent, warning)

    # Lấy toàn bộ 1 lượt rồi group theo stage (tránh 6 query) + đổ tiến độ đầu việc (1 aggregate)
    result = await db.execute(select(Project).order_by(*priority))
    all_projects = result.scalars().all()
    progress_map = await _stage_progress_map(db, [p.id for p in all_projects])

    by_stage: dict[str, list] = {s: [] for s in stages}
    for p in all_projects:
        if p.stage in by_stage:
            response = ProjectResponse.model_validate(p)
            response.stage_progress = progress_map.get(p.id)
            by_stage[p.stage].append(_mask_project_response(response, current_user))

    for stage in stages:
        kanban.append(ProjectKanbanStage(
            stage=stage,
            stage_label=stage_labels.get(stage, stage),
            projects=by_stage[stage],
            count=len(by_stage[stage]),
        ))

    return kanban


# ── Dự án đang đến phòng bạn (spec 07 A3) ────────────────────────────────────

STAGE_DEPARTMENTS = {
    "design": "DESIGN",
    "quotation": "DESIGN",
    "procurement": "PURCHASING",
    "construction": "PM",
    "acceptance": "PM",
}


@router.get("/by-department")
async def projects_by_department(
    dept: str = Query(..., pattern=r"^(DESIGN|PURCHASING|PM)$"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dự án đang ở giai đoạn thuộc phòng `dept`, sắp theo ưu tiên nguồn lực.

    Dùng cho khối "Dự án đang đến phòng bạn" trên trang Tổng quan của
    designer / pm / purchasing.
    """
    dept_stages = [s for s, d in STAGE_DEPARTMENTS.items() if d == dept]
    urgent, warning = await _priority_thresholds(db)

    q = (
        select(Project)
        .where(Project.status.in_(_RUNNING_STATUSES), Project.stage.in_(dept_stages))
        .order_by(*_priority_order(urgent, warning))
        .limit(limit)
    )
    projects = (await db.execute(q)).scalars().all()

    # Số đầu việc chưa xong của phòng trong các dự án này — 1 aggregate
    pending_map: dict[str, int] = {}
    if projects:
        pending_result = await db.execute(
            select(Task.project_id, func.count(Task.id))
            .where(
                Task.project_id.in_([p.id for p in projects]),
                Task.status != "done",
                (Task.department == dept) | (Task.department.is_(None) & Task.stage.in_(dept_stages)),
            )
            .group_by(Task.project_id)
        )
        pending_map = {pid: int(n) for pid, n in pending_result.all()}

    now = datetime.now(timezone.utc)
    items = []
    for p in projects:
        end = p.target_end_date
        if end is not None and end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        days_left = (end - now).days if end else None
        items.append({
            **_mask_project_response(ProjectResponse.model_validate(p), current_user),
            "pending_tasks": pending_map.get(p.id, 0),
            "days_left": days_left,
        })
    return {"department": dept, "items": items}


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_project_access),
):
    """Get project details."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Dự án không tồn tại")
    return _mask_project_response(ProjectResponse.model_validate(project), current_user)


@router.post("", response_model=ProjectResponse)
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create new project — admin, leader, pm only."""
    if current_user.role not in ("admin", "leader", "supervisor"):
        raise HTTPException(status_code=403, detail="Không có quyền tạo dự án")
    project = Project(**data.model_dump())
    db.add(project)
    await db.flush()
    return _mask_project_response(ProjectResponse.model_validate(project), current_user)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_project_access),
):
    """Update project."""
    if current_user.role in ("accountant", "data_entry"):
        raise HTTPException(status_code=403, detail="Không có quyền chỉnh sửa dự án")
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Dự án không tồn tại")

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(project, k, v)
    project.updated_at = datetime.now(timezone.utc)
    await db.flush()

    # Invalidate caches if stage or status was changed
    update_fields = data.model_dump(exclude_unset=True)
    if "stage" in update_fields or "status" in update_fields:
        cache.clear_prefix("pl")
        cache.clear_prefix("dashboard")

    return _mask_project_response(ProjectResponse.model_validate(project), current_user)


@router.get("/{project_id}/tasks", response_model=list[TaskResponse])
async def list_tasks(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_project_access),
):
    """List tasks for project."""
    q = select(Task).where(Task.project_id == project_id).order_by(Task.order)
    result = await db.execute(q)
    tasks = result.scalars().all()
    return [TaskResponse.model_validate(t) for t in tasks]


@router.post("/{project_id}/tasks", response_model=TaskResponse)
async def create_task(
    project_id: str,
    data: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new task under a project — admin, leader, supervisor only."""
    if current_user.role not in ("admin", "leader", "supervisor"):
        raise HTTPException(status_code=403, detail="Không có quyền tạo đầu việc")
    # Verify project exists
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Dự án không tồn tại")
    task = Task(
        project_id=project_id,
        title=data.title,
        description=data.description,
        stage=data.stage,
        # Form bỏ trống phòng ban → suy từ giai đoạn, KHÔNG để NULL (NULL làm dropdown
        # «Đảm nhận» FE hiện toàn bộ nhân sự — QC 05/09).
        department=data.department or task_department_for_stage(data.stage),
        assigned_to=data.assigned_to,
        order=data.order,
        status=data.status,
    )
    db.add(task)
    await db.flush()
    return TaskResponse.model_validate(task)


@router.put("/{project_id}/stage", response_model=ProjectResponse)
async def update_project_stage(
    project_id: str,
    data: ProjectStageUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_project_access),
):
    """Update project current stage — admin, supervisor, leader only."""
    if current_user.role not in ("admin", "supervisor", "leader"):
        raise HTTPException(status_code=403, detail="Không có quyền cập nhật giai đoạn dự án")
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Dự án không tồn tại")

    project.stage = data.stage
    project.updated_at = datetime.now(timezone.utc)
    if data.stage == "paused" and hasattr(data, 'pause_reason') and data.pause_reason:
        project.pause_reason = data.pause_reason
        project.paused_at = datetime.now(timezone.utc)
    elif data.stage != "paused":
        project.pause_reason = None
        project.paused_at = None

    # ── Customer lifecycle: post-completion actions ────────────────────────
    if data.stage == "completed":
        project.status = "completed"
        # Calculate warranty_end_date from handover_date + warranty_months
        if project.handover_date is not None:
            hd = project.handover_date
            if hd.tzinfo is None:
                hd = hd.replace(tzinfo=timezone.utc)
            project.warranty_end_date = hd + timedelta(days=project.warranty_months * 30)
        # Notify admin to run satisfaction survey & set warranty reminder
        notif = Notification(
            user_id=current_user.id,
            type="system",
            title="Dự án đã hoàn thành",
            body=f"Dự án {project.code} đã hoàn thành. Cần survey满意度 và nhắc bảo hành.",
            link=f"/projects",
            ref_id=project.id,
        )
        db.add(notif)

    await db.flush()

    # Invalidate caches affected by project stage changes
    cache.clear_prefix("pl")
    cache.clear_prefix("dashboard")

    return _mask_project_response(ProjectResponse.model_validate(project), current_user)


@router.get("/tasks/{task_id}/activities", response_model=list[TaskActivityResponse])
async def list_task_activities(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get notes and media updates for a task."""
    q = (
        select(TaskActivity, User.full_name.label("user_name"))
        .outerjoin(User, TaskActivity.user_id == User.id)
        .where(TaskActivity.task_id == task_id)
        .order_by(TaskActivity.created_at.desc())
    )
    result = await db.execute(q)
    rows = result.all()

    responses = []
    for act, user_name in rows:
        responses.append(TaskActivityResponse(
            id=act.id,
            task_id=act.task_id,
            user_id=act.user_id,
            user_name=user_name,
            content=act.content,
            media_url=act.media_url,
            created_at=act.created_at,
        ))
    return responses


@router.post("/tasks/{task_id}/activities", response_model=TaskActivityResponse)
async def create_task_activity(
    task_id: str,
    data: TaskActivityCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a new note/media update to a task."""
    # Verify task exists
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Đầu việc không tồn tại")

    act = TaskActivity(
        task_id=task_id,
        user_id=current_user.id,
        content=data.content,
        media_url=data.media_url,
    )
    db.add(act)
    await db.flush()

    return TaskActivityResponse(
        id=act.id,
        task_id=act.task_id,
        user_id=act.user_id,
        user_name=current_user.full_name,
        content=act.content,
        media_url=act.media_url,
        created_at=act.created_at,
    )


@router.put("/tasks/{task_id}/final-file", response_model=TaskResponse)
async def update_task_final_file(
    task_id: str,
    data: TaskFileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set the final result file for a task, appending to version history."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Đầu việc không tồn tại")

    # Update the main field (always points to latest)
    task.final_file_url = data.final_file_url

    # Append to version history
    versions = list(task.final_file_versions or [])
    next_version = len(versions) + 1
    if data.final_file_url:
        versions.append({
            "url": data.final_file_url,
            "version": next_version,
            "label": data.version_label,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        })
    task.final_file_versions = versions
    await db.flush()
    return TaskResponse.model_validate(task)


@router.put("/tasks/{task_id}/status", response_model=TaskResponse)
async def update_task_status(
    task_id: str,
    data: TaskStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update task status and dynamically update project progress."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Đầu việc không tồn tại")

    old_status = task.status
    task.status = data.status
    if data.status in ("done", "completed"):
        task.completed_at = datetime.now(timezone.utc)
    else:
        task.completed_at = None

    await db.flush()

    # Recalculate project progress via SQL COUNT
    proj_result = await db.execute(select(Project).where(Project.id == task.project_id))
    project = proj_result.scalar_one_or_none()
    if project:
        count_q = select(
            func.count(Task.id).label("total"),
            func.count(Task.id).filter(Task.status.in_(["done", "completed"])).label("done"),
        ).where(Task.project_id == project.id)
        row = (await db.execute(count_q)).one()
        project.progress = int((row.done / row.total) * 100) if row.total else 0
        project.updated_at = datetime.now(timezone.utc)
        await db.flush()

    return TaskResponse.model_validate(task)


@router.put("/{project_id}/tasks/{task_id}/assign")
async def assign_task(
    project_id: str,
    task_id: str,
    data: TaskAssignUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Assign a task to a user."""
    result = await db.execute(select(Task).where(Task.id == task_id, Task.project_id == project_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Người nhận phải có thật — trước đây gán ID rác vẫn trả 200 rồi tạo thông báo mồ côi.
    assignee = (await db.execute(select(User).where(User.id == data.assigned_to))).scalar_one_or_none()
    if assignee is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhân sự được giao việc")

    task.assigned_to = assignee.id
    if data.status:
        task.status = data.status
    await db.flush()

    from app.models.notification import Notification
    notif = Notification(
        user_id=assignee.id,
        type="system",
        title="Bạn được giao task mới",
        body=f"Task: {task.title}",
        link="/projects",
    )
    db.add(notif)
    await db.flush()
    return TaskResponse.model_validate(task)


@router.put("/{project_id}/tasks/{task_id}")
async def update_task(
    project_id: str,
    task_id: str,
    data: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update task details (title, description, assigned_to)."""
    result = await db.execute(select(Task).where(Task.id == task_id, Task.project_id == project_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if data.title:
        task.title = data.title
    if data.description is not None:
        task.description = data.description
    if data.assigned_to:
        task.assigned_to = data.assigned_to
    if data.department:
        task.department = data.department
    await db.flush()
    return TaskResponse.model_validate(task)


@router.post("/{project_id}/tasks/bulk-assign")
async def bulk_assign_tasks(
    project_id: str,
    data: BulkTaskAssign,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bulk assign tasks to users — admin, supervisor, leader only."""
    if current_user.role not in ("admin", "supervisor", "leader"):
        raise HTTPException(status_code=403, detail="Không có quyền phân công đầu việc")

    # Verify project exists
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Dự án không tồn tại")

    # Collect task IDs from assignments
    task_ids = [a["task_id"] for a in data.assignments if "task_id" in a]
    if not task_ids:
        return {"updated": 0}

    # Fetch all target tasks in one query
    tasks_result = await db.execute(
        select(Task).where(Task.id.in_(task_ids), Task.project_id == project_id)
    )
    tasks_by_id = {t.id: t for t in tasks_result.scalars().all()}

    updated = 0
    for assignment in data.assignments:
        task_id = assignment.get("task_id")
        assigned_to = assignment.get("assigned_to")
        task = tasks_by_id.get(task_id)
        if task:
            task.assigned_to = assigned_to
            updated += 1

    await db.flush()
    return {"updated": updated}
