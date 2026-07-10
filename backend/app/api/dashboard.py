"""Dashboard API — executive & personal dashboards."""

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User, Team
from app.models.lead import Lead, Activity
from app.models.project import Project
from app.cache import cache, cached

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@cached(ttl=120, prefix="dashboard", key_fn=lambda *a, **kw: [kw.get("current_user").role if kw.get("current_user") else "anon"])
@router.get("/executive")
async def executive_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Executive dashboard with company-wide metrics."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Total leads
    total = (await db.execute(select(func.count(Lead.id)))).scalar() or 0
    total_month = (await db.execute(
        select(func.count(Lead.id)).where(Lead.created_at >= month_start)
    )).scalar() or 0

    # Pipeline value
    pipeline_value = (await db.execute(
        select(func.sum(Lead.estimated_budget)).where(
            Lead.stage.notin_(["lost", "dormant"])
        )
    )).scalar() or 0

    # Conversion
    signed = (await db.execute(
        select(func.count(Lead.id)).where(Lead.stage == "signed_design")
    )).scalar() or 0
    conversion_rate = round((signed / total * 100) if total > 0 else 0, 1)

    # Projects
    active_projects = (await db.execute(
        select(func.count(Project.id)).where(Project.status == "active")
    )).scalar() or 0
    avg_progress = (await db.execute(
        select(func.avg(Project.progress)).where(Project.status == "active")
    )).scalar() or 0

    # Stage funnel
    stage_q = select(Lead.stage, func.count(Lead.id)).group_by(Lead.stage)
    stage_result = await db.execute(stage_q)
    stage_funnel = {s: c for s, c in stage_result.all()}

    # Contract values
    total_contract_value = (await db.execute(
        select(func.sum(Project.total_value))
    )).scalar() or 0
    total_contracts = (await db.execute(
        select(func.count(Project.id))
    )).scalar() or 0

    # Team performance
    team_q = (
        select(
            Team.name,
            func.count(Lead.id).label("total"),
            func.sum(case((Lead.stage == "signed_design", 1), else_=0)).label("signed_count"),
        )
        .outerjoin(Lead, Lead.team_id == Team.id)
        .where(Team.department == "SALES")
        .group_by(Team.name)
    )
    try:
        team_result = await db.execute(team_q)
        team_perf = [
            {"team": name, "total_leads": t, "signed": s or 0,
             "conversion": round((s or 0) / t * 100, 1) if t else 0}
            for name, t, s in team_result.all()
        ]
    except Exception:
        team_perf = []

    # Overdue (no contact in 3 days for active leads)
    overdue_cutoff = now - timedelta(days=3)
    overdue = (await db.execute(
        select(func.count(Lead.id)).where(
            Lead.stage.notin_(["lost", "dormant", "signed_design"]),
            (Lead.last_contacted_at < overdue_cutoff) | (Lead.last_contacted_at.is_(None))
        )
    )).scalar() or 0

    return {
        "total_leads": total,
        "total_leads_month": total_month,
        "conversion_rate": conversion_rate,
        "pipeline_value": pipeline_value,
        "total_contracts": total_contracts,
        "total_contract_value": total_contract_value,
        "active_projects": active_projects,
        "avg_project_progress": round(avg_progress, 1),
        "sla_compliance": round(100 - (overdue / total * 100) if total > 0 else 100, 1),
        "overdue_leads": overdue,
        "stage_funnel": stage_funnel,
        "team_performance": team_perf,
        "monthly_trend": [],
    }


@router.get("/personal")
async def personal_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Personal dashboard for current user."""
    now = datetime.now(timezone.utc)

    q = select(Lead).where(
        Lead.assigned_to == current_user.id,
        Lead.stage.notin_(["lost", "dormant"]),
    )
    result = await db.execute(q)
    leads = result.scalars().all()

    by_stage = {}
    pipeline_value = 0
    for lead in leads:
        by_stage[lead.stage] = by_stage.get(lead.stage, 0) + 1
        pipeline_value += (lead.estimated_budget or 0)

    # Overdue followup
    overdue_cutoff = now - timedelta(days=3)
    overdue = [
        {"id": l.id, "name": l.name, "phone": l.phone, "stage": l.stage,
         "last_contacted_at": str(l.last_contacted_at) if l.last_contacted_at else None}
        for l in leads
        if (l.last_contacted_at and l.last_contacted_at.replace(tzinfo=timezone.utc) < overdue_cutoff)
           or l.last_contacted_at is None
    ]

    return {
        "user_name": current_user.full_name,
        "total_active_leads": len(leads),
        "by_stage": by_stage,
        "overdue_followup": overdue[:10],
        "today_appointments": [],
        "weekly_kpis": {
            "calls": 0, "meetings": 0, "surveys": 0, "new_leads": 0,
        },
        "pipeline_value": pipeline_value,
        "ai_suggestions": [],
    }
