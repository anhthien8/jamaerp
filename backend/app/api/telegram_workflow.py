"""Telegram Bot workflow API endpoints for JAMA HOME CRM.

Provides the backend for Telegram Bot commands:
  /duan, /baocao, /vatlieu, /suco, /checkin, /checkout
plus material approve/reject via inline buttons.

All endpoints are called by the Telegram Bot webhook handler.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.project import Project, Task, TaskActivity
from app.models.inventory import Material

# ---------------------------------------------------------------------------
# SQLAlchemy model: MaterialRequest (pending approval workflow)
# ---------------------------------------------------------------------------
# Defined here so the table is created when this module is imported.
# Move to app/models/inventory.py once the workflow is stable.
from sqlalchemy import String, Float, ForeignKey, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MaterialRequest(Base):
    __tablename__ = "material_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    material_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    estimated_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # Statuses: pending, approved, rejected
    requester_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    approver_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_material_requests_project", "project_id"),
        Index("ix_material_requests_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<MaterialRequest {self.id} [{self.status}]>"


# ---------------------------------------------------------------------------
# Pydantic request / response schemas
# ---------------------------------------------------------------------------

class SiteReportRequest(BaseModel):
    project_code: str
    content: str = Field(..., min_length=1, max_length=5000)
    photos: list[str] = Field(default_factory=list, description="List of photo URLs or base64 strings")
    reporter_tg_id: int = Field(..., description="Telegram user ID of the reporter")


class MaterialRequestPayload(BaseModel):
    project_code: str
    material_name: str = Field(..., min_length=1, max_length=255)
    quantity: float = Field(..., gt=0)
    unit: str = Field(..., min_length=1, max_length=20)
    requester_tg_id: int = Field(..., description="Telegram user ID of the requester")


class IncidentRequest(BaseModel):
    project_code: str
    description: str = Field(..., min_length=1, max_length=5000)
    severity: str = Field(default="high", pattern=r"^(low|medium|high|critical)$")
    reporter_tg_id: int = Field(..., description="Telegram user ID of the reporter")


class CheckinRequest(BaseModel):
    project_code: str
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    user_tg_id: int = Field(..., description="Telegram user ID")


class CheckoutRequest(BaseModel):
    project_code: str
    user_tg_id: int = Field(..., description="Telegram user ID")


class ApproveRejectRequest(BaseModel):
    approver_tg_id: int = Field(..., description="Telegram user ID of the approver")
    reason: str | None = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

async def _resolve_user_by_tg(tg_id: int, db: AsyncSession) -> User:
    """Look up a User by their Telegram user ID."""
    result = await db.execute(
        select(User).where(User.telegram_user_id == tg_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy nhân viên với Telegram ID {tg_id}",
        )
    return user


async def _resolve_project(code: str, db: AsyncSession) -> Project:
    """Look up a Project by its short code (e.g. JMH-0601)."""
    result = await db.execute(
        select(Project).where(Project.code == code)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy dự án với mã '{code}'",
        )
    return project


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/telegram", tags=["telegram"])


# ── 1. GET /project/{project_code} ─────────────────────────────────────────

@router.get("/project/{project_code}")
async def quick_project_lookup(
    project_code: str,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Quick project lookup by code — returns project info, task progress,
    and assigned team members.

    Used by the /duan Telegram command.
    """
    project = await _resolve_project(project_code, db)

    # Gather tasks summary
    tasks_result = await db.execute(
        select(Task).where(Task.project_id == project.id).order_by(Task.order)
    )
    tasks = tasks_result.scalars().all()

    total_tasks = len(tasks)
    done_tasks = sum(1 for t in tasks if t.status == "done")
    in_progress_tasks = sum(1 for t in tasks if t.status == "in_progress")

    # Gather assigned team
    team: dict[str, str | None] = {
        "pm_id": project.pm_id,
        "pm_name": None,
        "designer_id": project.designer_id,
        "designer_name": None,
        "sales_id": project.sales_id,
        "sales_name": None,
    }

    user_ids = [uid for uid in (project.pm_id, project.designer_id, project.sales_id) if uid]
    if user_ids:
        users_result = await db.execute(
            select(User).where(User.id.in_(user_ids))
        )
        users_map = {u.id: u.full_name for u in users_result.scalars().all()}
        team["pm_name"] = users_map.get(project.pm_id)
        team["designer_name"] = users_map.get(project.designer_id)
        team["sales_name"] = users_map.get(project.sales_id)

    return {
        "project": {
            "id": project.id,
            "code": project.code,
            "name": project.name,
            "client_name": project.client_name,
            "client_phone": project.client_phone,
            "address": project.address,
            "status": project.status,
            "stage": project.stage,
            "progress": project.progress,
            "total_value": project.total_value,
            "spent": project.spent,
            "start_date": project.start_date.isoformat() if project.start_date else None,
            "target_end_date": project.target_end_date.isoformat() if project.target_end_date else None,
        },
        "tasks_summary": {
            "total": total_tasks,
            "done": done_tasks,
            "in_progress": in_progress_tasks,
            "remaining": total_tasks - done_tasks - in_progress_tasks,
        },
        "team": team,
    }


# ── 2. POST /site-report ──────────────────────────────────────────────────

@router.post("/site-report", status_code=status.HTTP_201_CREATED)
async def create_site_report(
    data: SiteReportRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Site report with photos — creates a TaskActivity entry.

    Used by the /baocao Telegram command.
    The reporter is resolved by their Telegram user ID.
    """
    project = await _resolve_project(data.project_code, db)
    reporter = await _resolve_user_by_tg(data.reporter_tg_id, db)

    # Find or use the first task for this project to attach the activity.
    # In practice the bot should resolve the correct task; we default to the
    # first active (in_progress) task, or fall back to the first task overall.
    tasks_result = await db.execute(
        select(Task)
        .where(Task.project_id == project.id)
        .order_by(Task.order)
    )
    tasks = tasks_result.scalars().all()
    if not tasks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dự án chưa có đầu việc nào để ghi nhật ký",
        )

    # Prefer an in_progress task
    target_task = next((t for t in tasks if t.status == "in_progress"), tasks[0])

    # Build content with photo references
    photo_refs = "\n".join(f"  [Anh {i+1}]: {url}" for i, url in enumerate(data.photos))
    full_content = data.content
    if photo_refs:
        full_content = f"{data.content}\n\nAnh di dong:\n{photo_refs}"

    # Store first photo URL as media_url for quick preview
    first_photo = data.photos[0] if data.photos else None

    activity = TaskActivity(
        task_id=target_task.id,
        user_id=reporter.id,
        content=full_content,
        media_url=first_photo,
    )
    db.add(activity)
    await db.flush()

    return {
        "activity_id": activity.id,
        "task_id": target_task.id,
        "task_title": target_task.title,
        "project_code": project.code,
        "reporter": reporter.full_name,
        "created_at": activity.created_at.isoformat(),
        "message": "Bao cao cong trinh da duoc ghi nhan thanh cong.",
    }


# ── 3. POST /material-request ─────────────────────────────────────────────

@router.post("/material-request", status_code=status.HTTP_201_CREATED)
async def create_material_request(
    data: MaterialRequestPayload,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Material request — checks budget limits and creates a pending approval.

    Used by the /vatlieu Telegram command.
    - If within budget: status = pending, ready for approve/reject.
    - If over budget: status = pending, flagged with warning.
    """
    project = await _resolve_project(data.project_code, db)
    requester = await _resolve_user_by_tg(data.requester_tg_id, db)

    # Budget check: compare against remaining budget
    budget_remaining = (project.total_value or 0) - project.spent
    estimated_cost = 0.0  # Could be enriched with material price lookup

    # Try to find matching material in catalog for price estimate
    mat_result = await db.execute(
        select(Material).where(Material.name.ilike(f"%{data.material_name}%"))
    )
    matched_material = mat_result.scalar_one_or_none()
    if matched_material:
        estimated_cost = matched_material.unit_price * data.quantity

    over_budget = False
    if project.total_value and estimated_cost > 0:
        if project.spent + estimated_cost > project.total_value:
            over_budget = True

    mat_request = MaterialRequest(
        project_id=project.id,
        material_name=data.material_name,
        quantity=data.quantity,
        unit=data.unit,
        estimated_cost=estimated_cost,
        status="pending",
        requester_id=requester.id,
    )
    db.add(mat_request)
    await db.flush()

    return {
        "request_id": mat_request.id,
        "project_code": project.code,
        "material_name": data.material_name,
        "quantity": data.quantity,
        "unit": data.unit,
        "estimated_cost": estimated_cost,
        "budget_remaining": budget_remaining,
        "over_budget": over_budget,
        "status": "pending",
        "requester": requester.full_name,
        "message": (
            "Yeu cau vat tu da vuot dinh muc. Can giai trinh."
            if over_budget
            else "Yeu cau vat tu nam trong dinh muc, dang cho duyet."
        ),
    }


# ── 4. POST /incident ─────────────────────────────────────────────────────

@router.post("/incident", status_code=status.HTTP_201_CREATED)
async def report_incident(
    data: IncidentRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Incident report — auto-creates an urgent Task on the project.

    Used by the /suco Telegram command.
    Severity mapping:
      - critical / high  -> urgent task, assigned to designer
      - medium / low     -> normal task
    """
    project = await _resolve_project(data.project_code, db)
    reporter = await _resolve_user_by_tg(data.reporter_tg_id, db)

    severity_label = {
        "low": "Thap",
        "medium": "Trung binh",
        "high": "Cao",
        "critical": "Khan cap",
    }.get(data.severity, data.severity)

    # Build the task
    task_title = f"[{severity_label}] Su co: {data.description[:100]}"
    task_description = (
        f"Mo ta: {data.description}\n"
        f"Muc do: {severity_label}\n"
        f"Nguoi phat hien: {reporter.full_name} (TG ID: {data.reporter_tg_id})\n"
        f"Thoi gian: {datetime.now(timezone.utc).isoformat()}"
    )

    task = Task(
        project_id=project.id,
        title=task_title,
        description=task_description,
        status="in_progress",
        stage=project.stage,
        department="design" if data.severity in ("high", "critical") else None,
        assigned_to=project.designer_id if data.severity in ("high", "critical") else None,
        order=0,
    )
    db.add(task)
    await db.flush()

    # Also log as activity for traceability
    activity = TaskActivity(
        task_id=task.id,
        user_id=reporter.id,
        content=f"[Bao cao su co - {severity_label}] {data.description}",
        media_url=None,
    )
    db.add(activity)
    await db.flush()

    return {
        "task_id": task.id,
        "task_title": task.title,
        "project_code": project.code,
        "severity": data.severity,
        "assigned_to": project.designer_id if data.severity in ("high", "critical") else None,
        "reporter": reporter.full_name,
        "created_at": task.created_at.isoformat(),
        "message": (
            f"Da tao su co khancap '{severity_label}'. "
            f"Thiet ke da duoc tag truc tiep."
            if data.severity in ("high", "critical")
            else f"Da ghi nhan su co muc do {severity_label}."
        ),
    }


# ── 5. POST /checkin ──────────────────────────────────────────────────────

@router.post("/checkin", status_code=status.HTTP_201_CREATED)
async def gps_checkin(
    data: CheckinRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """GPS check-in — records user location and start of work shift.

    Used by the /checkin Telegram command.
    Creates a TaskActivity on the project's first active task.
    """
    project = await _resolve_project(data.project_code, db)
    user = await _resolve_user_by_tg(data.user_tg_id, db)

    # Find or create a task for daily logging
    tasks_result = await db.execute(
        select(Task)
        .where(Task.project_id == project.id)
        .order_by(Task.order)
    )
    tasks = tasks_result.scalars().all()
    if not tasks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dua an chua co dau viec nao de ghi nhan check-in",
        )

    target_task = next((t for t in tasks if t.status == "in_progress"), tasks[0])

    content = (
        f"CHECK-IN tai cong trinh\n"
        f"Vi tri: ({data.latitude}, {data.longitude})\n"
        f"Thoi gian: {datetime.now(timezone.utc).isoformat()}"
    )

    activity = TaskActivity(
        task_id=target_task.id,
        user_id=user.id,
        content=content,
        media_url=None,
    )
    db.add(activity)
    await db.flush()

    return {
        "activity_id": activity.id,
        "task_id": target_task.id,
        "project_code": project.code,
        "user": user.full_name,
        "latitude": data.latitude,
        "longitude": data.longitude,
        "checkin_time": activity.created_at.isoformat(),
        "message": f"Check-in thanh cong tai du an {project.code}.",
    }


# ── 6. POST /checkout ─────────────────────────────────────────────────────

@router.post("/checkout", status_code=status.HTTP_201_CREATED)
async def gps_checkout(
    data: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """GPS check-out — records end of work shift.

    Used by the /checkout Telegram command.
    """
    project = await _resolve_project(data.project_code, db)
    user = await _resolve_user_by_tg(data.user_tg_id, db)

    tasks_result = await db.execute(
        select(Task)
        .where(Task.project_id == project.id)
        .order_by(Task.order)
    )
    tasks = tasks_result.scalars().all()
    if not tasks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dua an chua co dau viec nao de ghi nhan check-out",
        )

    target_task = next((t for t in tasks if t.status == "in_progress"), tasks[0])

    content = (
        f"CHECK-OUT tai cong trinh\n"
        f"Thoi gian: {datetime.now(timezone.utc).isoformat()}"
    )

    activity = TaskActivity(
        task_id=target_task.id,
        user_id=user.id,
        content=content,
        media_url=None,
    )
    db.add(activity)
    await db.flush()

    return {
        "activity_id": activity.id,
        "task_id": target_task.id,
        "project_code": project.code,
        "user": user.full_name,
        "checkout_time": activity.created_at.isoformat(),
        "message": f"Check-out thanh cong tai du an {project.code}.",
    }


# ── 7. POST /approve/{request_id} ────────────────────────────────────────

@router.post("/approve/{request_id}")
async def approve_material_request(
    request_id: str,
    data: ApproveRejectRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Approve a material request.

    Used by the approve inline button callback on Telegram.
    Only accountant / purchasing / admin roles may approve.
    """
    result = await db.execute(
        select(MaterialRequest).where(MaterialRequest.id == request_id)
    )
    mat_request = result.scalar_one_or_none()
    if not mat_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Yeu cau vat tu khong ton tai",
        )

    if mat_request.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Yeu cau da duoc xu ly truoc do (trang thai: {mat_request.status})",
        )

    approver = await _resolve_user_by_tg(data.approver_tg_id, db)

    # RBAC: only accountant, purchasing, or admin may approve
    if approver.role not in ("admin", "accountant", "purchasing"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chi ke toan / thu mua / admin moi co quyen duyet vat tu",
        )

    mat_request.status = "approved"
    mat_request.approver_id = approver.id
    mat_request.resolved_at = datetime.now(timezone.utc)
    await db.flush()

    return {
        "request_id": mat_request.id,
        "status": "approved",
        "approver": approver.full_name,
        "material_name": mat_request.material_name,
        "quantity": mat_request.quantity,
        "unit": mat_request.unit,
        "resolved_at": mat_request.resolved_at.isoformat(),
        "message": (
            f"Yeu cau mua {mat_request.quantity} {mat_request.unit} "
            f"{mat_request.material_name} da duoc duyet."
        ),
    }


# ── 8. POST /reject/{request_id} ─────────────────────────────────────────

@router.post("/reject/{request_id}")
async def reject_material_request(
    request_id: str,
    data: ApproveRejectRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Reject a material request with optional reason.

    Used by the reject inline button callback on Telegram.
    """
    result = await db.execute(
        select(MaterialRequest).where(MaterialRequest.id == request_id)
    )
    mat_request = result.scalar_one_or_none()
    if not mat_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Yeu cau vat tu khong ton tai",
        )

    if mat_request.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Yeu cau da duoc xu ly truoc do (trang thai: {mat_request.status})",
        )

    approver = await _resolve_user_by_tg(data.approver_tg_id, db)

    if approver.role not in ("admin", "accountant", "purchasing"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chi ke toan / thu mua / admin moi co quyen tu choi vat tu",
        )

    mat_request.status = "rejected"
    mat_request.approver_id = approver.id
    mat_request.reject_reason = data.reason
    mat_request.resolved_at = datetime.now(timezone.utc)
    await db.flush()

    return {
        "request_id": mat_request.id,
        "status": "rejected",
        "approver": approver.full_name,
        "material_name": mat_request.material_name,
        "reject_reason": mat_request.reject_reason,
        "resolved_at": mat_request.resolved_at.isoformat(),
        "message": (
            f"Yeu cau mua {mat_request.material_name} da bi tu choi."
            + (f" Ly do: {data.reason}" if data.reason else "")
        ),
    }
