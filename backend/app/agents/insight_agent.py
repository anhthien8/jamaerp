"""Insight Agent — generate weekly business insights from CRM data.

Uses litellm acompletion for LLM-powered narrative analysis with a
rule-based fallback when the LLM is unavailable or the API key is blank.
"""

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, case, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services.llm_config import llm_available, llm_complete
from app.models.lead import Lead, Activity
from app.models.project import Project
from app.models.contract import Contract
from app.models.payroll import Transaction
from app.models.user import User

settings = get_settings()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM system prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are a senior business analyst for JAMA HOME, a premium interior design
and construction company in Vietnam.

You will receive structured CRM metrics for a given reporting period.
Analyse the data and produce a JSON object with exactly these keys:

{
  "summary": "2-4 sentence executive summary of the period",
  "key_metrics": [
    {"label": "metric name", "value": "formatted value", "trend": "up|down|flat"}
  ],
  "alerts": [
    {"severity": "critical|warning|info", "message": "what is wrong or notable"}
  ],
  "recommendations": [
    {"action": "specific recommended action", "priority": "high|medium|low"}
  ]
}

Rules:
- All text must be in Vietnamese.
- key_metrics must contain at least 5 entries covering: pipeline value,
  conversion rate, new leads, revenue, project progress.
- alerts must flag concrete problems (SLA breach, pipeline stall, low
  conversion, budget overrun, etc.).  Empty list only if everything is fine.
- recommendations must be actionable, specific, and prioritised.
- Return ONLY valid JSON.  No markdown fences, no commentary.
"""

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_insights(db: AsyncSession, period_days: int = 7) -> dict:
    """Generate weekly (or custom-period) business insights.

    Parameters
    ----------
    db : AsyncSession
        Active SQLAlchemy async session.
    period_days : int
        Number of days to look back (default 7 = one week).

    Returns
    -------
    dict
        ``{"summary": str, "key_metrics": list, "alerts": list, "recommendations": list}``
    """
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=period_days)
    prev_period_start = period_start - timedelta(days=period_days)

    # ---- gather all metrics ----
    metrics = await _gather_metrics(db, now, period_start, prev_period_start)

    # ---- try LLM, fall back to rules ----
    if await llm_available():
        try:
            return await _llm_insights(metrics, period_days)
        except Exception:
            logger.warning("LLM insight generation failed, falling back to rules", exc_info=True)

    return _rule_based_insights(metrics, period_days)


# ---------------------------------------------------------------------------
# Data gathering
# ---------------------------------------------------------------------------

async def _gather_metrics(
    db: AsyncSession,
    now: datetime,
    period_start: datetime,
    prev_period_start: datetime,
) -> dict:
    """Collect every numeric metric the insight engine needs."""
    m: dict = {}

    # -- Lead counts (current period) --
    m["new_leads_period"] = _scalar(await db.execute(
        select(func.count(Lead.id)).where(Lead.created_at >= period_start)
    ))
    m["total_leads_all_time"] = _scalar(await db.execute(
        select(func.count(Lead.id))
    ))

    # -- Lead counts (previous period for trend) --
    m["new_leads_prev"] = _scalar(await db.execute(
        select(func.count(Lead.id)).where(
            and_(Lead.created_at >= prev_period_start, Lead.created_at < period_start)
        )
    ))

    # -- Pipeline value (active leads) --
    m["pipeline_value"] = _scalar(await db.execute(
        select(func.coalesce(func.sum(Lead.estimated_budget), 0)).where(
            Lead.stage.notin_(["lost", "dormant", "signed_design"])
        )
    ))

    # -- Pipeline value previous period --
    m["pipeline_value_prev"] = _scalar(await db.execute(
        select(func.coalesce(func.sum(Lead.estimated_budget), 0)).where(
            and_(
                Lead.stage.notin_(["lost", "dormant", "signed_design"]),
                Lead.created_at >= prev_period_start,
                Lead.created_at < period_start,
            )
        )
    ))

    # -- Stage funnel --
    stage_rows = (await db.execute(
        select(Lead.stage, func.count(Lead.id)).group_by(Lead.stage)
    )).all()
    m["stage_funnel"] = {s: c for s, c in stage_rows}

    # -- Conversion rate (signed / total) --
    m["signed_count"] = m["stage_funnel"].get("signed_design", 0)
    m["conversion_rate"] = (
        round(m["signed_count"] / m["total_leads_all_time"] * 100, 1)
        if m["total_leads_all_time"] else 0.0
    )

    # -- Conversion rate previous period --
    prev_signed = _scalar(await db.execute(
        select(func.count(Lead.id)).where(
            and_(Lead.stage == "signed_design", Lead.created_at < period_start)
        )
    ))
    prev_total = _scalar(await db.execute(
        select(func.count(Lead.id)).where(Lead.created_at < period_start)
    ))
    m["conversion_rate_prev"] = (
        round(prev_signed / prev_total * 100, 1) if prev_total else 0.0
    )

    # -- Lost leads this period --
    m["lost_leads_period"] = _scalar(await db.execute(
        select(func.count(Lead.id)).where(
            and_(Lead.stage == "lost", Lead.updated_at >= period_start)
        )
    ))

    # -- Revenue (income transactions this period) --
    m["revenue_period"] = _scalar(await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            and_(
                Transaction.type == "income",
                Transaction.status == "completed",
                Transaction.date >= period_start,
            )
        )
    ))
    m["revenue_prev"] = _scalar(await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            and_(
                Transaction.type == "income",
                Transaction.status == "completed",
                Transaction.date >= prev_period_start,
                Transaction.date < period_start,
            )
        )
    ))

    # -- Expenses this period --
    m["expenses_period"] = _scalar(await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            and_(
                Transaction.type == "expense",
                Transaction.status == "completed",
                Transaction.date >= period_start,
            )
        )
    ))

    # -- Net cash flow --
    m["net_cash_flow"] = m["revenue_period"] - m["expenses_period"]

    # -- Projects --
    m["active_projects"] = _scalar(await db.execute(
        select(func.count(Project.id)).where(Project.status == "active")
    ))
    m["avg_project_progress"] = round(
        _scalar(await db.execute(
            select(func.coalesce(func.avg(Project.progress), 0)).where(
                Project.status == "active"
            )
        )), 1,
    )
    m["completed_projects_period"] = _scalar(await db.execute(
        select(func.count(Project.id)).where(
            and_(Project.status == "completed", Project.updated_at >= period_start)
        )
    ))
    m["new_projects_period"] = _scalar(await db.execute(
        select(func.count(Project.id)).where(Project.created_at >= period_start)
    ))

    # -- Contracts signed this period --
    m["contracts_signed_period"] = _scalar(await db.execute(
        select(func.count(Contract.id)).where(
            and_(Contract.status == "signed", Contract.created_at >= period_start)
        )
    ))
    m["contract_value_period"] = _scalar(await db.execute(
        select(func.coalesce(func.sum(Contract.total_value), 0)).where(
            and_(Contract.status == "signed", Contract.created_at >= period_start)
        )
    ))

    # -- SLA: overdue leads (no contact in 3+ days, still active) --
    overdue_cutoff = now - timedelta(days=3)
    m["overdue_leads"] = _scalar(await db.execute(
        select(func.count(Lead.id)).where(
            Lead.stage.notin_(["lost", "dormant", "signed_design"]),
            or_(
                Lead.last_contacted_at < overdue_cutoff,
                Lead.last_contacted_at.is_(None),
            ),
        )
    ))

    # -- Activity volume this period --
    m["activities_period"] = _scalar(await db.execute(
        select(func.count(Activity.id)).where(Activity.created_at >= period_start)
    ))
    m["activities_prev"] = _scalar(await db.execute(
        select(func.count(Activity.id)).where(
            and_(Activity.created_at >= prev_period_start, Activity.created_at < period_start)
        )
    ))

    # -- Activity breakdown by type --
    act_type_rows = (await db.execute(
        select(Activity.type, func.count(Activity.id))
        .where(Activity.created_at >= period_start)
        .group_by(Activity.type)
    )).all()
    m["activity_types"] = {t: c for t, c in act_type_rows}

    # -- Lead source distribution (this period) --
    source_rows = (await db.execute(
        select(Lead.source, func.count(Lead.id))
        .where(Lead.created_at >= period_start)
        .group_by(Lead.source)
    )).all()
    m["lead_sources"] = {s: c for s, c in source_rows if s}

    # -- Average deal value --
    m["avg_deal_value"] = round(
        _scalar(await db.execute(
            select(func.coalesce(func.avg(Lead.deal_value), 0)).where(
                and_(
                    Lead.deal_value.isnot(None),
                    Lead.created_at >= period_start,
                )
            )
        )), 0,
    )

    # -- Average budget of new leads --
    m["avg_budget_new"] = round(
        _scalar(await db.execute(
            select(func.coalesce(func.avg(Lead.estimated_budget), 0)).where(
                Lead.created_at >= period_start
            )
        )), 0,
    )

    # -- Team performance (leads per sales person this period) --
    team_rows = (await db.execute(
        select(
            User.full_name,
            func.count(Lead.id).label("total"),
            func.sum(case((Lead.stage == "signed_design", 1), else_=0)).label("signed"),
        )
        .outerjoin(Lead, and_(Lead.assigned_to == User.id, Lead.created_at >= period_start))
        .where(User.department == "SALES")
        .group_by(User.full_name)
    )).all()
    m["team_performance"] = [
        {
            "name": name,
            "leads": t or 0,
            "signed": int(s or 0),
            "conversion": round((int(s or 0) / t * 100) if t else 0, 1),
        }
        for name, t, s in team_rows
    ]

    # -- Project budget utilisation --
    budget_rows = (await db.execute(
        select(
            Project.code,
            Project.total_value,
            Project.spent,
            Project.progress,
        ).where(Project.status == "active")
    )).all()
    m["project_budgets"] = [
        {
            "code": code,
            "total_value": total or 0,
            "spent": spent or 0,
            "utilisation": round((spent / total * 100) if total else 0, 1),
            "progress": progress or 0,
        }
        for code, total, spent, progress in budget_rows
    ]

    return m


# ---------------------------------------------------------------------------
# LLM-powered insights
# ---------------------------------------------------------------------------

async def _llm_insights(metrics: dict, period_days: int) -> dict:
    """Send metrics to LLM for narrative insight generation."""
    period_label = _period_label(period_days)

    user_msg = (
        f"Phép tính cho kỳ {period_label}.\n\n"
        f"Số liệu:\n{json.dumps(metrics, ensure_ascii=False, indent=2, default=str)}"
    )

    response = await llm_complete(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.3,
        max_tokens=1500,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content
    result = json.loads(content)
    return _validate_output(result, metrics, period_days)


# ---------------------------------------------------------------------------
# Rule-based fallback
# ---------------------------------------------------------------------------

def _rule_based_insights(metrics: dict, period_days: int) -> dict:
    """Produce insights entirely from business rules when LLM is unavailable."""
    period_label = _period_label(period_days)
    summary_parts: list[str] = []
    key_metrics: list[dict] = []
    alerts: list[dict] = []
    recommendations: list[dict] = []

    # ---- Summary ----
    summary_parts.append(
        f"Tổng quan kỳ {period_label}: "
        f"nhận {metrics['new_leads_period']} lead mới, "
        f"pipeline {format_vnd(metrics['pipeline_value'])}, "
        f"doanh thu {format_vnd(metrics['revenue_period'])}."
    )

    # ---- Key Metrics ----
    # 1. Pipeline value
    pipeline_trend = _trend(metrics["pipeline_value"], metrics["pipeline_value_prev"])
    key_metrics.append({
        "label": "Giá trị pipeline",
        "value": format_vnd(metrics["pipeline_value"]),
        "trend": pipeline_trend,
    })

    # 2. Conversion rate
    conv_trend = _trend(metrics["conversion_rate"], metrics["conversion_rate_prev"])
    key_metrics.append({
        "label": "Tỷ lệ chuyển đổi",
        "value": f"{metrics['conversion_rate']}%",
        "trend": conv_trend,
    })

    # 3. New leads
    leads_trend = _trend(metrics["new_leads_period"], metrics["new_leads_prev"])
    key_metrics.append({
        "label": "Lead mới",
        "value": str(metrics["new_leads_period"]),
        "trend": leads_trend,
    })

    # 4. Revenue
    rev_trend = _trend(metrics["revenue_period"], metrics["revenue_prev"])
    key_metrics.append({
        "label": "Doanh thu thuộc kỳ",
        "value": format_vnd(metrics["revenue_period"]),
        "trend": rev_trend,
    })

    # 5. Net cash flow
    key_metrics.append({
        "label": "Dòng tiền ròng",
        "value": format_vnd(metrics["net_cash_flow"]),
        "trend": "up" if metrics["net_cash_flow"] > 0 else "down",
    })

    # 6. Active projects
    key_metrics.append({
        "label": "Dự án đang hoạt động",
        "value": str(metrics["active_projects"]),
        "trend": "flat",
    })

    # 7. Contract value this period
    key_metrics.append({
        "label": "Giá trị hợp đồng ký kỳ này",
        "value": format_vnd(metrics["contract_value_period"]),
        "trend": "up" if metrics["contracts_signed_period"] > 0 else "flat",
    })

    # ---- Alerts ----
    # Overdue leads
    if metrics["overdue_leads"] > 0:
        severity = "critical" if metrics["overdue_leads"] >= 5 else "warning"
        alerts.append({
            "severity": severity,
            "message": (
                f"Có {metrics['overdue_leads']} lead chưa liên hệ "
                f"trên 3 ngày. Cần xử lý ngay."
            ),
        })

    # Low conversion rate
    if metrics["conversion_rate"] < 5 and metrics["total_leads_all_time"] >= 20:
        alerts.append({
            "severity": "warning",
            "message": (
                f"Tỷ lệ chuyển đổi chỉ "
                f"{metrics['conversion_rate']}%. Cần kiểm tra lại quy trình."
            ),
        })

    # Conversion declining
    if (
        metrics["conversion_rate_prev"] > 0
        and metrics["conversion_rate"] < metrics["conversion_rate_prev"] * 0.8
    ):
        alerts.append({
            "severity": "warning",
            "message": (
                f"Tỷ lệ chuyển đổi giảm từ "
                f"{metrics['conversion_rate_prev']}% xuống {metrics['conversion_rate']}%."
            ),
        })

    # Pipeline shrinking
    if (
        metrics["pipeline_value_prev"] > 0
        and metrics["pipeline_value"] < metrics["pipeline_value_prev"] * 0.85
    ):
        alerts.append({
            "severity": "warning",
            "message": (
                f"Pipeline giảm hơn 15% so với kỳ trước. "
                f"Cần tìm thêm lead mới."
            ),
        })

    # High project budget utilisation
    for p in metrics.get("project_budgets", []):
        if p["utilisation"] > 90 and p["progress"] < 80:
            alerts.append({
                "severity": "critical",
                "message": (
                    f"Dự án {p['code']}: đã dùng "
                    f"{p['utilisation']}% ngân sách nhưng tiến độ "
                    f"chưa đạt 80%. Nguy cơ vượt ngân sách."
                ),
            })

    # Revenue dropping
    if metrics["revenue_prev"] > 0 and metrics["revenue_period"] < metrics["revenue_prev"] * 0.7:
        alerts.append({
            "severity": "warning",
            "message": (
                f"Doanh thu giảm hơn 30%: từ "
                f"{format_vnd(metrics['revenue_prev'])} xuống "
                f"{format_vnd(metrics['revenue_period'])}."
            ),
        })

    # No new contracts
    if metrics["active_projects"] > 0 and metrics["contracts_signed_period"] == 0:
        alerts.append({
            "severity": "info",
            "message": "Kỳ này chưa ký hợp đồng mới.",
        })

    # ---- Recommendations ----
    if metrics["overdue_leads"] > 0:
        recommendations.append({
            "action": (
                f"Liên hệ ngay với {metrics['overdue_leads']} lead "
                f"quá hạn chưa tương tác."
            ),
            "priority": "high",
        })

    if metrics["conversion_rate"] < 10:
        recommendations.append({
            "action": (
                "Rà soát lại lead: loại bỏ lead "
                "kém chất lượng, cải thiện "
                "phương án tiếp cận cho lead tiềm năng."
            ),
            "priority": "high",
        })

    if metrics["activities_period"] < metrics["new_leads_period"]:
        recommendations.append({
            "action": (
                "Hoạt động tương tác chưa "
                "đầy đủ so với số lead mới. "
                "Tăng tần suất liên hệ."
            ),
            "priority": "medium",
        })

    # Lead source optimisation
    if metrics.get("lead_sources"):
        best_source = max(metrics["lead_sources"], key=metrics["lead_sources"].get)
        recommendations.append({
            "action": (
                f"Tối ưu nguồn {best_source} "
                f"(đóng góp {metrics['lead_sources'][best_source]} lead kỳ này). "
                f"Cân nhắc tăng ngân sách marketing cho kênh này."
            ),
            "priority": "medium",
        })

    # Low activity engagement
    if metrics["activities_period"] == 0 and metrics["new_leads_period"] > 0:
        recommendations.append({
            "action": (
                "Chưa có hoạt động nào được ghi nhận kỳ này. "
                "Yêu cầu sales team tổ chức cuộc gọi "
                "hoặc hẹn khảo sát cho các lead mới."
            ),
            "priority": "high",
        })

    # Team underperformance
    for member in metrics.get("team_performance", []):
        if member["leads"] >= 3 and member["signed"] == 0:
            recommendations.append({
                "action": (
                    f"{member['name']}: {member['leads']} lead nhưng chưa "
                    f"ký được. Cần review lại chiến lược."
                ),
                "priority": "medium",
            })

    # Project budget management
    for p in metrics.get("project_budgets", []):
        if p["utilisation"] > 80 and p["progress"] < 70:
            recommendations.append({
                "action": (
                    f"Dự án {p['code']}: kiểm tra chi phí "
                    f"đã tiêu thụ {p['utilisation']}% ngân sách "
                    f"nhưng tiến độ chưa đạt 70%."
                ),
                "priority": "high",
            })

    # ---- Build summary ----
    summary = " ".join(summary_parts)
    if alerts:
        critical = [a for a in alerts if a["severity"] == "critical"]
        if critical:
            summary += (
                f" CẦn xử lý ngay: {critical[0]['message']}"
            )

    return {
        "summary": summary,
        "key_metrics": key_metrics,
        "alerts": alerts,
        "recommendations": recommendations,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _scalar(result) -> float | int:
    """Extract scalar value from a SQLAlchemy result, defaulting to 0."""
    val = result.scalar()
    return val if val is not None else 0


def _trend(current: float, previous: float) -> str:
    """Classify movement as up / down / flat."""
    if previous == 0:
        return "up" if current > 0 else "flat"
    diff_pct = (current - previous) / abs(previous) * 100
    if diff_pct > 2:
        return "up"
    if diff_pct < -2:
        return "down"
    return "flat"


def format_vnd(value: float | int) -> str:
    """Format a number as Vietnamese Dong string."""
    v = int(value)
    if v >= 1_000_000_000:
        return f"{v / 1_000_000_000:,.1f} tỷ VND"
    if v >= 1_000_000:
        return f"{v / 1_000_000:,.0f} triệu VND"
    return f"{v:,} VND"


def _period_label(days: int) -> str:
    if days == 7:
        return "tuần này"
    if days == 14:
        return "2 tuần"
    if days == 30 or days == 31:
        return "tháng này"
    return f"{days} ngày vừa qua"


def _validate_output(result: dict, metrics: dict, period_days: int) -> dict:
    """Ensure LLM output matches the required schema; patch if needed."""
    output: dict = {
        "summary": result.get("summary", "Không có tổng quan."),
        "key_metrics": result.get("key_metrics", []),
        "alerts": result.get("alerts", []),
        "recommendations": result.get("recommendations", []),
    }

    # Guarantee at least 5 key_metrics
    if len(output["key_metrics"]) < 5:
        rule_output = _rule_based_insights(metrics, period_days)
        existing_labels = {m.get("label") for m in output["key_metrics"]}
        for km in rule_output["key_metrics"]:
            if km["label"] not in existing_labels:
                output["key_metrics"].append(km)
            if len(output["key_metrics"]) >= 7:
                break

    # Ensure correct types
    for key in ("key_metrics", "alerts", "recommendations"):
        if not isinstance(output[key], list):
            output[key] = []

    if not isinstance(output["summary"], str):
        output["summary"] = str(output["summary"])

    return output
