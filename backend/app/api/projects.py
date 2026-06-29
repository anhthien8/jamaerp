"""Projects API — CRUD, tasks."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.project import Project, Task, TaskActivity
from app.cache import cache
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, TaskResponse,
    TaskActivityCreate, TaskActivityResponse
)
from pydantic import BaseModel


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
    if current_user.role == "accountant":
        return current_user  # read-only for accounting
    if current_user.role == "purchasing":
        return current_user  # read-only for purchasing
    if project.pm_id == current_user.id:
        return current_user
    if project.designer_id == current_user.id:
        return current_user
    if project.sales_id == current_user.id:
        return current_user
    if current_user.role == "leader":
        return current_user  # team leaders can view all
    raise HTTPException(status_code=403, detail="No access to this project")

class ProjectStageUpdate(BaseModel):
    stage: str

class TaskStatusUpdate(BaseModel):
    status: str

class TaskFileUpdate(BaseModel):
    final_file_url: str | None = None

class ProjectKanbanStage(BaseModel):
    stage: str
    stage_label: str
    projects: list[ProjectResponse]
    count: int

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
async def list_projects(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_project_access),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """List projects."""
    q = select(Project).order_by(Project.created_at.desc())
    if status:
        q = q.where(Project.status == status)

    # Count total (before pagination)
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    projects = result.scalars().all()

    return {
        "items": [ProjectResponse.model_validate(p) for p in projects],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


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
    return ProjectResponse.model_validate(project)


@router.post("", response_model=ProjectResponse)
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create new project — admin, leader, pm only."""
    if current_user.role not in ("admin", "leader", "pm"):
        raise HTTPException(status_code=403, detail="Không có quyền tạo dự án")
    project = Project(**data.model_dump())
    db.add(project)
    await db.flush()
    return ProjectResponse.model_validate(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_project_access),
):
    """Update project."""
    if current_user.role in ("accountant", "purchasing", "sales"):
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

    return ProjectResponse.model_validate(project)


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


@router.get("/pipeline/kanban", response_model=list[ProjectKanbanStage])
async def project_kanban(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_project_access),
):
    """Kanban board data — projects grouped by stage."""
    stages = ["design", "quotation", "procurement", "construction", "acceptance", "completed"]
    stage_labels = {
        "design": "Thiết kế",
        "quotation": "Báo giá",
        "procurement": "Thu mua",
        "construction": "Thi công",
        "acceptance": "Nghiệm thu",
        "completed": "Hoàn thành",
    }
    kanban = []

    for stage in stages:
        q = select(Project).where(Project.stage == stage).order_by(Project.updated_at.desc())
        result = await db.execute(q)
        projects = result.scalars().all()
        responses = [ProjectResponse.model_validate(p) for p in projects]

        kanban.append(ProjectKanbanStage(
            stage=stage,
            stage_label=stage_labels.get(stage, stage),
            projects=responses,
            count=len(responses),
        ))

    return kanban


@router.put("/{project_id}/stage", response_model=ProjectResponse)
async def update_project_stage(
    project_id: str,
    data: ProjectStageUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_project_access),
):
    """Update project current stage — admin, pm, leader only."""
    if current_user.role not in ("admin", "pm", "leader"):
        raise HTTPException(status_code=403, detail="Không có quyền cập nhật giai đoạn dự án")
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Dự án không tồn tại")

    project.stage = data.stage
    project.updated_at = datetime.now(timezone.utc)
    await db.flush()

    # Invalidate caches affected by project stage changes
    cache.clear_prefix("pl")
    cache.clear_prefix("dashboard")

    return ProjectResponse.model_validate(project)


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
    """Set the final result file for a task."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Đầu việc không tồn tại")

    task.final_file_url = data.final_file_url
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

    # Recalculate project progress
    proj_result = await db.execute(select(Project).where(Project.id == task.project_id))
    project = proj_result.scalar_one_or_none()
    if project:
        tasks_q = select(Task).where(Task.project_id == project.id)
        tasks_res = await db.execute(tasks_q)
        all_tasks = tasks_res.scalars().all()
        if all_tasks:
            done_tasks = [t for t in all_tasks if t.status in ("done", "completed")]
            project.progress = int((len(done_tasks) / len(all_tasks)) * 100)
            project.updated_at = datetime.now(timezone.utc)
            await db.flush()

    return TaskResponse.model_validate(task)
