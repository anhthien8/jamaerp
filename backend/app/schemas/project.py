"""Pydantic schemas for projects, tasks, and task activities."""

from pydantic import BaseModel
from datetime import datetime


class ProjectCreate(BaseModel):
    code: str
    name: str
    lead_id: str | None = None
    client_name: str
    client_phone: str | None = None
    address: str | None = None
    project_type: str = "design_build"
    design_value: float | None = None
    construction_value: float | None = None
    total_value: float | None = None
    pm_id: str | None = None
    designer_id: str | None = None
    sales_id: str | None = None
    start_date: datetime | None = None
    target_end_date: datetime | None = None
    stage: str = "design"


class ProjectUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    stage: str | None = None
    progress: int | None = None
    spent: float | None = None
    pm_id: str | None = None
    designer_id: str | None = None
    budget_total: float | None = None
    handover_date: datetime | None = None
    warranty_months: int | None = None


class ProjectResponse(BaseModel):
    id: str
    code: str
    name: str
    lead_id: str | None = None
    client_name: str
    client_phone: str | None = None
    address: str | None = None
    project_type: str
    status: str
    stage: str
    design_value: float | None = None
    construction_value: float | None = None
    total_value: float | None = None
    spent: float
    progress: int
    pm_id: str | None = None
    designer_id: str | None = None
    sales_id: str | None = None
    start_date: datetime | None = None
    target_end_date: datetime | None = None
    budget_total: float | None = None
    handover_date: datetime | None = None
    warranty_months: int = 12
    pause_reason: str | None = None
    paused_at: datetime | None = None
    stage_acceptances: dict | None = None
    created_at: datetime
    updated_at: datetime
    # Tiến độ đầu việc theo giai đoạn: {"design": {"done": 3, "total": 5}, ...}
    # Chỉ được đổ ở endpoint kanban (aggregate 1 query) — nơi khác để None
    stage_progress: dict[str, dict] | None = None

    model_config = {"from_attributes": True}


class TaskResponse(BaseModel):
    id: str
    project_id: str
    title: str
    description: str | None = None
    status: str
    stage: str
    department: str | None = None
    final_file_url: str | None = None
    assigned_to: str | None = None
    order: int
    due_date: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskActivityCreate(BaseModel):
    content: str
    media_url: str | None = None


class TaskActivityResponse(BaseModel):
    id: str
    task_id: str
    user_id: str
    user_name: str | None = None
    content: str
    media_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
