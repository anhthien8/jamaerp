"""Pydantic schemas for leads & activities."""

from pydantic import BaseModel
from datetime import datetime


class LeadCreate(BaseModel):
    name: str
    phone: str
    email: str | None = None
    contact_person: str | None = None
    address: str | None = None
    needs: str | None = None
    source: str | None = None
    property_type: str | None = None
    area_sqm: float | None = None
    estimated_budget: float | None = None
    property_class: str | None = None
    price_per_sqm: float | None = None
    region: str | None = None
    segment: str | None = None
    plan_type: str | None = None
    tags: str | None = None
    deal_value: float | None = None
    priority: str = "medium"
    notes: str | None = None


class LeadUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    contact_person: str | None = None
    address: str | None = None
    needs: str | None = None
    source: str | None = None
    property_type: str | None = None
    area_sqm: float | None = None
    estimated_budget: float | None = None
    property_class: str | None = None
    price_per_sqm: float | None = None
    region: str | None = None
    segment: str | None = None
    plan_type: str | None = None
    tags: str | None = None
    deal_value: float | None = None
    priority: str | None = None
    notes: str | None = None


class LeadResponse(BaseModel):
    id: str
    name: str
    phone: str
    email: str | None = None
    contact_person: str | None = None
    address: str | None = None
    needs: str | None = None
    source: str | None = None
    property_type: str | None = None
    area_sqm: float | None = None
    estimated_budget: float | None = None
    property_class: str | None = None
    price_per_sqm: float | None = None
    region: str | None = None
    segment: str | None = None
    plan_type: str | None = None
    tags: str | None = None
    deal_value: float | None = None
    stage: str
    priority: str
    assigned_to: str | None = None
    team_id: str | None = None
    ai_score: float | None = None
    ai_notes: str | None = None
    design_contract_value: float | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    last_contacted_at: datetime | None = None
    # Joined fields
    assigned_user_name: str | None = None
    team_name: str | None = None
    activity_count: int | None = None

    model_config = {"from_attributes": True}


class LeadStageChange(BaseModel):
    new_stage: str
    design_contract_value: float | None = None
    note: str | None = None


class LeadAssign(BaseModel):
    user_id: str
    note: str | None = None


class ActivityCreate(BaseModel):
    type: str
    content: str


class ActivityResponse(BaseModel):
    id: str
    lead_id: str
    user_id: str
    type: str
    content: str
    created_at: datetime
    user_name: str | None = None

    model_config = {"from_attributes": True}


class PipelineStats(BaseModel):
    total_leads: int
    by_stage: dict[str, int]
    conversion_rate: float
    pipeline_value: float


class PipelineKanban(BaseModel):
    stage: str
    stage_label: str
    leads: list[LeadResponse]
    count: int
