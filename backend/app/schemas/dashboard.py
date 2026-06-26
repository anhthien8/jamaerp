"""Dashboard schemas."""

from decimal import Decimal
from pydantic import BaseModel


class DashboardExecutive(BaseModel):
    """CEO/BGĐ dashboard data."""
    total_leads: int
    total_leads_month: int
    conversion_rate: float
    pipeline_value: Decimal
    total_contracts: int
    total_contract_value: Decimal
    active_projects: int
    avg_project_progress: float
    sla_compliance: float
    overdue_leads: int
    team_performance: list[dict]
    stage_funnel: dict[str, int]
    monthly_trend: list[dict]


class DashboardSalesTeam(BaseModel):
    """Sales team leader dashboard."""
    team_name: str
    total_leads: int
    unassigned: int
    sla_violations: int
    members: list[dict]
    conversion_by_source: dict[str, float]


class DashboardPersonal(BaseModel):
    """Individual sales rep dashboard — used for TG daily briefing."""
    user_name: str
    total_active_leads: int
    by_stage: dict[str, int]
    overdue_followup: list[dict]  # Leads needing contact
    today_appointments: list[dict]
    weekly_kpis: dict
    pipeline_value: Decimal
    ai_suggestions: list[dict]
