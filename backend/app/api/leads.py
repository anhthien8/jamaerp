"""Leads API — CRUD, pipeline, activities."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User, Team
from app.models.lead import Lead, Activity, VALID_STAGE_TRANSITIONS, LEAD_STAGES
from app.schemas.lead import (
    LeadCreate, LeadUpdate, LeadResponse, LeadStageChange, LeadAssign,
    ActivityCreate, ActivityResponse, PipelineStats, PipelineKanban,
)

router = APIRouter(prefix="/leads", tags=["leads"])

STAGE_LABELS = {
    "new": "Mới", "interested": "Quan tâm", "survey_scheduled": "Hẹn khảo sát",
    "potential": "Tiềm năng", "signed_design": "Ký HĐ TK", "lost": "Mất", "dormant": "Ngủ đông",
}


def _lead_response(lead: Lead, user_name: str = None, team_name: str = None, act_count: int = 0) -> LeadResponse:
    return LeadResponse(
        id=lead.id, name=lead.name, phone=lead.phone, email=lead.email,
        contact_person=lead.contact_person, address=lead.address, needs=lead.needs,
        source=lead.source, property_type=lead.property_type,
        area_sqm=lead.area_sqm, estimated_budget=lead.estimated_budget,
        stage=lead.stage, priority=lead.priority,
        assigned_to=lead.assigned_to, team_id=lead.team_id,
        ai_score=lead.ai_score, ai_notes=lead.ai_notes,
        design_contract_value=lead.design_contract_value,
        notes=lead.notes, created_at=lead.created_at, updated_at=lead.updated_at,
        last_contacted_at=lead.last_contacted_at,
        assigned_user_name=user_name, team_name=team_name,
        activity_count=act_count,
    )


@router.get("", response_model=list[LeadResponse])
async def list_leads(
    stage: str | None = None,
    source: str | None = None,
    priority: str | None = None,
    assigned_to: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List leads with optional filters."""
    q = (
        select(
            Lead,
            User.full_name.label("user_name"),
            Team.name.label("team_name"),
        )
        .outerjoin(User, Lead.assigned_to == User.id)
        .outerjoin(Team, Lead.team_id == Team.id)
    )

    # RBAC filter
    if current_user.role == "data_entry":
        q = q.where(Lead.assigned_to == current_user.id)
    elif current_user.role == "leader":
        q = q.where(Lead.team_id == current_user.team_id)

    if stage:
        q = q.where(Lead.stage == stage)
    if source:
        q = q.where(Lead.source == source)
    if priority:
        q = q.where(Lead.priority == priority)
    if assigned_to:
        q = q.where(Lead.assigned_to == assigned_to)
    if search:
        q = q.where(
            Lead.name.ilike(f"%{search}%")
            | Lead.phone.ilike(f"%{search}%")
            | Lead.address.ilike(f"%{search}%")
        )

    q = q.order_by(Lead.updated_at.desc())
    result = await db.execute(q)
    rows = result.all()

    leads = []
    for lead, user_name, team_name in rows:
        # Count activities
        act_q = select(func.count(Activity.id)).where(Activity.lead_id == lead.id)
        act_result = await db.execute(act_q)
        act_count = act_result.scalar() or 0
        leads.append(_lead_response(lead, user_name, team_name, act_count))

    return leads


@router.get("/pipeline/stats", response_model=PipelineStats)
async def pipeline_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pipeline summary stats."""
    q = select(Lead.stage, func.count(Lead.id), func.sum(Lead.estimated_budget))
    if current_user.role == "data_entry":
        q = q.where(Lead.assigned_to == current_user.id)
    elif current_user.role == "leader":
        q = q.where(Lead.team_id == current_user.team_id)
    q = q.group_by(Lead.stage)

    result = await db.execute(q)
    rows = result.all()

    by_stage = {}
    total = 0
    pipeline_value = 0
    signed = 0
    for stage, count, budget_sum in rows:
        by_stage[stage] = count
        total += count
        pipeline_value += (budget_sum or 0)
        if stage == "signed_design":
            signed = count

    conversion_rate = (signed / total * 100) if total > 0 else 0

    return PipelineStats(
        total_leads=total,
        by_stage=by_stage,
        conversion_rate=round(conversion_rate, 1),
        pipeline_value=pipeline_value,
    )


@router.get("/pipeline/kanban", response_model=list[PipelineKanban])
async def pipeline_kanban(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Kanban board data — leads grouped by stage."""
    stages = ["new", "interested", "survey_scheduled", "potential", "signed_design"]
    kanban = []

    for stage in stages:
        q = (
            select(Lead, User.full_name.label("user_name"), Team.name.label("team_name"))
            .outerjoin(User, Lead.assigned_to == User.id)
            .outerjoin(Team, Lead.team_id == Team.id)
            .where(Lead.stage == stage)
            .order_by(Lead.updated_at.desc())
        )
        if current_user.role == "data_entry":
            q = q.where(Lead.assigned_to == current_user.id)
        elif current_user.role == "leader":
            q = q.where(Lead.team_id == current_user.team_id)

        result = await db.execute(q)
        rows = result.all()
        leads = [_lead_response(lead, un, tn) for lead, un, tn in rows]

        kanban.append(PipelineKanban(
            stage=stage,
            stage_label=STAGE_LABELS.get(stage, stage),
            leads=leads,
            count=len(leads),
        ))

    return kanban


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get single lead with details."""
    q = (
        select(Lead, User.full_name.label("user_name"), Team.name.label("team_name"))
        .outerjoin(User, Lead.assigned_to == User.id)
        .outerjoin(Team, Lead.team_id == Team.id)
        .where(Lead.id == lead_id)
    )
    result = await db.execute(q)
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Lead không tồn tại")

    lead, user_name, team_name = row
    act_q = select(func.count(Activity.id)).where(Activity.lead_id == lead.id)
    act_count = (await db.execute(act_q)).scalar() or 0
    return _lead_response(lead, user_name, team_name, act_count)


@router.post("", response_model=LeadResponse)
async def create_lead(
    data: LeadCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create new lead."""
    lead = Lead(
        name=data.name, phone=data.phone, email=data.email,
        contact_person=data.contact_person, address=data.address,
        needs=data.needs, source=data.source,
        property_type=data.property_type, area_sqm=data.area_sqm,
        estimated_budget=data.estimated_budget, priority=data.priority,
        notes=data.notes,
        assigned_to=current_user.id, team_id=current_user.team_id,
    )
    db.add(lead)
    await db.flush()

    # Activity log
    db.add(Activity(
        lead_id=lead.id, user_id=current_user.id,
        type="note", content=f"Tạo lead mới: {lead.name} — {lead.phone}",
    ))
    await db.flush()

    return _lead_response(lead, current_user.full_name, None, 1)


@router.put("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: str,
    data: LeadUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update lead fields."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead không tồn tại")

    update_fields = data.model_dump(exclude_unset=True)
    for k, v in update_fields.items():
        setattr(lead, k, v)
    lead.updated_at = datetime.now(timezone.utc)
    await db.flush()

    return _lead_response(lead)


@router.put("/{lead_id}/stage", response_model=LeadResponse)
async def change_stage(
    lead_id: str,
    data: LeadStageChange,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Move lead to new pipeline stage."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead không tồn tại")

    valid = VALID_STAGE_TRANSITIONS.get(lead.stage, [])
    if data.new_stage not in valid:
        raise HTTPException(
            status_code=400,
            detail=f"Không thể chuyển từ {lead.stage} sang {data.new_stage}",
        )

    old_stage = lead.stage
    lead.stage = data.new_stage
    if data.design_contract_value:
        lead.design_contract_value = data.design_contract_value
    lead.updated_at = datetime.now(timezone.utc)
    await db.flush()

    # Log activity
    content = f"Chuyển stage: {STAGE_LABELS.get(old_stage)} → {STAGE_LABELS.get(data.new_stage)}"
    if data.note:
        content += f" — {data.note}"
    db.add(Activity(
        lead_id=lead.id, user_id=current_user.id,
        type="stage_change", content=content,
    ))
    await db.flush()

    return _lead_response(lead)


@router.post("/{lead_id}/assign", response_model=LeadResponse)
async def assign_lead(
    lead_id: str,
    data: LeadAssign,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Assign lead to a user."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead không tồn tại")

    # Get target user
    target = await db.execute(select(User).where(User.id == data.user_id))
    target_user = target.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User không tồn tại")

    lead.assigned_to = data.user_id
    lead.team_id = target_user.team_id
    lead.updated_at = datetime.now(timezone.utc)
    await db.flush()

    content = f"Phân công cho {target_user.full_name}"
    if data.note:
        content += f" — {data.note}"
    db.add(Activity(
        lead_id=lead.id, user_id=current_user.id,
        type="assignment", content=content,
    ))
    await db.flush()

    return _lead_response(lead, target_user.full_name, None)


# ── Activities ──

@router.get("/{lead_id}/activities", response_model=list[ActivityResponse])
async def list_activities(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get activity history for a lead."""
    q = (
        select(Activity, User.full_name.label("user_name"))
        .outerjoin(User, Activity.user_id == User.id)
        .where(Activity.lead_id == lead_id)
        .order_by(Activity.created_at.desc())
    )
    result = await db.execute(q)
    rows = result.all()

    return [
        ActivityResponse(
            id=act.id, lead_id=act.lead_id, user_id=act.user_id,
            type=act.type, content=act.content, created_at=act.created_at,
            user_name=user_name,
        )
        for act, user_name in rows
    ]


@router.post("/{lead_id}/activities", response_model=ActivityResponse)
async def create_activity(
    lead_id: str,
    data: ActivityCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add activity to lead."""
    # Verify lead exists
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead không tồn tại")

    activity = Activity(
        lead_id=lead_id, user_id=current_user.id,
        type=data.type, content=data.content,
    )
    db.add(activity)

    # Update last contacted
    lead.last_contacted_at = datetime.now(timezone.utc)
    lead.updated_at = datetime.now(timezone.utc)
    await db.flush()

    return ActivityResponse(
        id=activity.id, lead_id=activity.lead_id, user_id=activity.user_id,
        type=activity.type, content=activity.content, created_at=activity.created_at,
        user_name=current_user.full_name,
    )
