"""Pydantic schemas for projects."""

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


class ProjectUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    progress: int | None = None
    spent: float | None = None
    pm_id: str | None = None
    designer_id: str | None = None


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
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskResponse(BaseModel):
    id: str
    project_id: str
    title: str
    description: str | None = None
    status: str
    assigned_to: str | None = None
    order: int
    due_date: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
