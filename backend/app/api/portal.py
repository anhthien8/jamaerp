"""Customer Portal — public read-only access for customers."""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.customer import Customer
from app.models.project import Project, Task, TaskActivity
from app.models.user import User

router = APIRouter(prefix="/portal", tags=["portal"])


async def _get_customer_by_token(token: str, db: AsyncSession) -> Customer:
    """Look up customer by portal token."""
    result = await db.execute(
        select(Customer).where(Customer.portal_token == token, Customer.portal_enabled == True)
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Liên kết không hợp lệ hoặc đã hết hạn")
    return customer


@router.get("/{token}")
async def portal_profile(token: str, db: AsyncSession = Depends(get_db)):
    """Customer profile + list of projects."""
    customer = await _get_customer_by_token(token, db)

    # Get all projects for this customer
    result = await db.execute(
        select(Project).where(
            or_(Project.customer_id == customer.id, Project.lead_id == customer.lead_id)
        ).order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()

    return {
        "customer": {
            "name": customer.name,
            "phone": customer.phone,
            "email": customer.email,
            "address": customer.address,
            "type": customer.type,
            "company_name": customer.company_name,
        },
        "projects": [
            {
                "id": p.id, "code": p.code, "name": p.name,
                "status": p.status, "stage": p.stage,
                "progress": p.progress, "total_value": p.total_value,
                "created_at": p.created_at.isoformat(),
            }
            for p in projects
        ],
        "project_count": len(projects),
    }


@router.get("/{token}/projects/{project_id}")
async def portal_project_detail(token: str, project_id: str, db: AsyncSession = Depends(get_db)):
    """Project detail with tasks."""
    customer = await _get_customer_by_token(token, db)

    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Dự án không tồn tại")

    # Verify customer owns this project
    if project.customer_id != customer.id and project.lead_id != customer.lead_id:
        raise HTTPException(status_code=403, detail="Không có quyền xem dự án này")

    # Get tasks
    tasks_result = await db.execute(
        select(Task).where(Task.project_id == project.id).order_by(Task.order)
    )
    tasks = tasks_result.scalars().all()

    task_status = {"done": 0, "in_progress": 0, "not_started": 0}
    for t in tasks:
        if t.status in task_status:
            task_status[t.status] += 1

    STAGE_LABELS = {
        "design": "Thiết kế", "quotation": "Báo giá", "procurement": "Thu mua",
        "construction": "Thi công", "acceptance": "Nghiệm thu", "completed": "Hoàn thành",
    }

    return {
        "project": {
            "id": project.id, "code": project.code, "name": project.name,
            "status": project.status, "stage": project.stage,
            "stage_label": STAGE_LABELS.get(project.stage, project.stage),
            "progress": project.progress,
            "start_date": project.start_date.isoformat() if project.start_date else None,
            "target_end_date": project.target_end_date.isoformat() if project.target_end_date else None,
        },
        "tasks": [
            {"id": t.id, "title": t.title, "status": t.status, "stage": t.stage}
            for t in tasks
        ],
        "task_summary": task_status,
        "total_tasks": len(tasks),
    }


@router.get("/{token}/projects/{project_id}/activities")
async def portal_activities(token: str, project_id: str, db: AsyncSession = Depends(get_db)):
    """Activity feed for a project (last 20 items)."""
    customer = await _get_customer_by_token(token, db)

    # Verify ownership
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project or (project.customer_id != customer.id and project.lead_id != customer.lead_id):
        raise HTTPException(status_code=403, detail="Không có quyền")

    # Get activities from all tasks in this project
    tasks_result = await db.execute(select(Task.id).where(Task.project_id == project.id))
    task_ids = [t[0] for t in tasks_result.all()]

    if not task_ids:
        return {"activities": []}

    act_result = await db.execute(
        select(TaskActivity, User.full_name.label("user_name"))
        .outerjoin(User, TaskActivity.user_id == User.id)
        .where(TaskActivity.task_id.in_(task_ids))
        .order_by(desc(TaskActivity.created_at))
        .limit(20)
    )

    activities = []
    for act, user_name in act_result.all():
        activities.append({
            "id": act.id, "content": act.content,
            "media_url": act.media_url,
            "user_name": user_name or "Nhân viên JAMA",
            "created_at": act.created_at.isoformat(),
        })

    return {"activities": activities}
