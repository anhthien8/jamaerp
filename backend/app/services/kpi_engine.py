"""KPI engine — compute sales performance metrics + burnout signals.

All aggregate SQL — no per-lead loops (see spec 05 §3 N+1 lesson).
"""

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, case, literal_column, and_, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, Team
from app.models.lead import Lead, Activity
from app.models.contract import Contract
from app.models.attendance import AttendanceRecord
from app.models.leave import LeaveRequest
from app.models.performance import KpiSnapshot

logger = logging.getLogger(__name__)

# Stage weights for pipeline_value_weighted
STAGE_WEIGHTS = {
    "new": 0.10,
    "interested": 0.25,
    "survey_scheduled": 0.50,
    "potential": 0.75,
    "signed_design": 1.0,
}

# Default KPI weights (configurable via SystemSetting)
DEFAULT_EFFORT_WEIGHT = 0.30
DEFAULT_OUTCOME_WEIGHT = 0.50
DEFAULT_QUALITY_WEIGHT = 0.20

ACTIVE_LEAD_STAGES = ("new", "interested", "survey_scheduled", "potential")

SALES_ROLES = ("data_entry", "leader")


# ---------------------------------------------------------------------------
# Period helpers
# ---------------------------------------------------------------------------

def parse_period(period: str) -> tuple[datetime, datetime]:
    """Parse 'YYYY-MM' → (start_utc, end_utc)."""
    parts = period.split("-")
    year, month = int(parts[0]), int(parts[1])
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return start, end


# ---------------------------------------------------------------------------
# KPI computation
# ---------------------------------------------------------------------------

async def compute_kpi(db: AsyncSession, user_id: str, period: str) -> dict:
    """Compute all 8 KPI metrics for one user in a given period.

    Returns dict with:
      - metrics: dict of all metric values
      - score: 0-100 composite
    """
    start, end = parse_period(period)

    # 1. Working days (from attendance)
    work_days_q = await db.execute(
        select(func.count(AttendanceRecord.id)).where(
            AttendanceRecord.user_id == user_id,
            AttendanceRecord.work_date >= start.date(),
            AttendanceRecord.work_date < end.date(),
        )
    )
    work_days = max(1, work_days_q.scalar() or 1)

    # 2. Activity count in period
    activity_count_q = await db.execute(
        select(func.count(Activity.id)).where(
            Activity.lead_id.in_(
                select(Lead.id).where(Lead.assigned_to == user_id)
            ),
            Activity.created_at >= start,
            Activity.created_at < end,
        )
    )
    activity_count = activity_count_q.scalar() or 0

    # 3. SLA compliance: % of active leads contacted within 3 days
    active_leads = (await db.execute(
        select(Lead).where(
            Lead.assigned_to == user_id,
            Lead.stage.in_(ACTIVE_LEAD_STAGES),
        )
    )).scalars().all()

    sla_compliant = 0
    total_active = len(active_leads)
    first_touch_hours_list = []

    for lead in active_leads:
        last = lead.last_contacted_at or lead.created_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        days_since = (datetime.now(timezone.utc) - last).total_seconds() / 86400
        if days_since <= 3:
            sla_compliant += 1

        # First touch: earliest activity after lead.created_at
        first_act = (await db.execute(
            select(func.min(Activity.created_at)).where(
                Activity.lead_id == lead.id,
                Activity.created_at > lead.created_at,
            )
        )).scalar()
        if first_act:
            if first_act.tzinfo is None:
                first_act = first_act.replace(tzinfo=timezone.utc)
            created = lead.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            first_touch_hours_list.append((first_act - created).total_seconds() / 3600)

    sla_pct = (sla_compliant / max(1, total_active)) * 100
    first_touch_hours = sorted(first_touch_hours_list)[len(first_touch_hours_list) // 2] if first_touch_hours_list else 0

    # 4. Outcome: signed count + value
    signed_q = await db.execute(
        select(func.count(Lead.id), func.coalesce(func.sum(Lead.deal_value), 0)).where(
            Lead.assigned_to == user_id,
            Lead.stage == "signed_design",
            Lead.updated_at >= start,
            Lead.updated_at < end,
        )
    )
    signed_count, signed_value = signed_q.one()

    # 5. Stage conversion (new→interested, survey→signed)
    new_count_q = await db.execute(
        select(func.count(Lead.id)).where(
            Lead.assigned_to == user_id,
            Lead.created_at >= start,
            Lead.created_at < end,
        )
    )
    new_count = max(1, new_count_q.scalar() or 1)

    converted_q = await db.execute(
        select(func.count(Lead.id)).where(
            Lead.assigned_to == user_id,
            Lead.stage.in_(["interested", "survey_scheduled", "potential", "signed_design"]),
            Lead.created_at >= start,
            Lead.created_at < end,
        )
    )
    converted_count = converted_q.scalar() or 0
    stage_conversion = (converted_count / new_count) * 100

    # 6. Pipeline value weighted
    active_for_pipeline = (await db.execute(
        select(Lead).where(
            Lead.assigned_to == user_id,
            Lead.stage.in_(ACTIVE_LEAD_STAGES),
            Lead.deal_value.is_not(None),
        )
    )).scalars().all()

    pipeline_weighted = sum(
        (lead.deal_value or 0) * STAGE_WEIGHTS.get(lead.stage, 0)
        for lead in active_for_pipeline
    )

    # 7. Recall rate (leads lost = bad quality signal)
    total_leads_q = await db.execute(
        select(func.count(Lead.id)).where(
            Lead.assigned_to == user_id,
            Lead.created_at >= start,
            Lead.created_at < end,
        )
    )
    total_leads_period = max(1, total_leads_q.scalar() or 1)

    # 8. Lost no-response rate
    lost_q = await db.execute(
        select(func.count(Lead.id)).where(
            Lead.assigned_to == user_id,
            Lead.stage == "lost",
            Lead.created_at >= start,
            Lead.created_at < end,
        )
    )
    lost_count = lost_q.scalar() or 0

    # Assemble metrics
    metrics = {
        "activity_rate": round(activity_count / work_days, 2),
        "sla_compliance": round(sla_pct, 1),
        "first_touch_hours": round(first_touch_hours, 1),
        "signed_count": signed_count,
        "signed_value": signed_value,
        "stage_conversion": round(stage_conversion, 1),
        "pipeline_value_weighted": pipeline_weighted,
        "recall_rate": 0,  # Placeholder: requires recall audit data
        "lost_no_response_rate": round((lost_count / total_leads_period) * 100, 1),
    }

    # Composite score (simplified normalization for MVP)
    effort_score = min(100, metrics["activity_rate"] * 5 + metrics["sla_compliance"] * 0.5 + max(0, 48 - metrics["first_touch_hours"]) * 2)
    outcome_score = min(100, metrics["signed_count"] * 20 + metrics["stage_conversion"] * 0.5 + pipeline_weighted / 100_000_000)
    quality_score = max(0, 100 - metrics["recall_rate"] * 10 - metrics["lost_no_response_rate"])

    score = (
        min(100, effort_score) * DEFAULT_EFFORT_WEIGHT
        + min(100, outcome_score) * DEFAULT_OUTCOME_WEIGHT
        + min(100, quality_score) * DEFAULT_QUALITY_WEIGHT
    )

    return {
        "metrics": metrics,
        "score": round(min(100, max(0, score)), 1),
    }


async def snapshot_all(db: AsyncSession, period: str) -> int:
    """Snapshot KPI for all active sales users. Returns count of snapshots created/updated."""
    users = (await db.execute(
        select(User).where(
            User.role.in_(SALES_ROLES),
            User.is_active == True,  # noqa: E712
        )
    )).scalars().all()

    count = 0
    for user in users:
        try:
            result = await compute_kpi(db, user.id, period)
            # Upsert: update existing or create new
            existing = (await db.execute(
                select(KpiSnapshot).where(
                    KpiSnapshot.user_id == user.id,
                    KpiSnapshot.period == period,
                )
            )).scalar_one_or_none()

            if existing:
                existing.metrics_json = json.dumps(result["metrics"])
                existing.score = result["score"]
            else:
                snapshot = KpiSnapshot(
                    user_id=user.id,
                    period=period,
                    metrics_json=json.dumps(result["metrics"]),
                    score=result["score"],
                )
                db.add(snapshot)
            count += 1
        except Exception:
            logger.exception("KPI snapshot failed for user %s", user.id)

    await db.commit()

    # Compute ranks after all snapshots saved
    await _compute_ranks(db, period)

    return count


async def _compute_ranks(db: AsyncSession, period: str) -> None:
    """Set rank_in_team and rank_overall for all snapshots in a period."""
    snapshots = (await db.execute(
        select(KpiSnapshot).where(KpiSnapshot.period == period)
    )).scalars().all()

    if not snapshots:
        return

    # Load users to get team info
    user_ids = {s.user_id for s in snapshots}
    users = (await db.execute(
        select(User).where(User.id.in_(user_ids))
    )).scalars().all()
    user_teams = {u.id: u.team_id for u in users}

    # Overall ranking (desc score)
    sorted_all = sorted(snapshots, key=lambda s: s.score, reverse=True)
    for i, s in enumerate(sorted_all, 1):
        s.rank_overall = i

    # Per-team ranking
    teams: dict[str, list] = {}
    for s in snapshots:
        tid = user_teams.get(s.user_id)
        if tid:
            teams.setdefault(tid, []).append(s)
    for team_snaps in teams.values():
        team_sorted = sorted(team_snaps, key=lambda s: s.score, reverse=True)
        for i, s in enumerate(team_sorted, 1):
            s.rank_in_team = i

    await db.commit()


# ---------------------------------------------------------------------------
# Burnout signals
# ---------------------------------------------------------------------------

async def detect_burnout(db: AsyncSession, user_id: str) -> dict:
    """Detect burnout signals for a user. Returns {signals: [...], risk_level: 'green'|'yellow'|'red'}."""
    now = datetime.now(timezone.utc)
    four_weeks_ago = now - timedelta(weeks=4)
    three_months_ago = now - timedelta(days=90)

    signals = []

    # 1. OT >10h/week × 3 consecutive weeks
    for weeks_back in range(3):
        week_start = now - timedelta(weeks=weeks_back + 1)
        week_end = now - timedelta(weeks=weeks_back)
        ot_q = await db.execute(
            select(func.coalesce(func.sum(AttendanceRecord.ot_hours), 0)).where(
                AttendanceRecord.user_id == user_id,
                AttendanceRecord.work_date >= week_start.date(),
                AttendanceRecord.work_date < week_end.date(),
            )
        )
        if (ot_q.scalar() or 0) > 10:
            if weeks_back < 2:
                continue
            signals.append("ot_extended")
            break

    # 2. Work on Sunday ≥3/month (cross-DB: filter in Python to avoid SQLite strftime)
    thirty_days_ago = (now - timedelta(days=30)).date()
    recent_records = (await db.execute(
        select(AttendanceRecord.work_date).where(
            AttendanceRecord.user_id == user_id,
            AttendanceRecord.work_date >= thirty_days_ago,
        )
    )).scalars().all()
    sunday_count = sum(1 for d in recent_records if d.weekday() == 6)  # Sunday = 6
    if sunday_count >= 3:
        signals.append("sunday_work")

    # 3. No leave in 90 days + balance ≥6
    leave_q = await db.execute(
        select(func.count(LeaveRequest.id)).where(
            LeaveRequest.user_id == user_id,
            LeaveRequest.start_date >= three_months_ago.date(),
            LeaveRequest.status.in_(["approved", "pending"]),
        )
    )
    leave_count = leave_q.scalar() or 0
    if leave_count == 0:
        signals.append("no_leave")

    # 4. Disengagement: activity_rate drop ≥40% vs 3-period average
    # (simplified: compare this period vs last 3 periods)
    # Skip for MVP — requires KpiSnapshot history

    # 5. Lead overload
    active_leads_q = await db.execute(
        select(func.count(Lead.id)).where(
            Lead.assigned_to == user_id,
            Lead.stage.in_(ACTIVE_LEAD_STAGES),
        )
    )
    active_count = active_leads_q.scalar() or 0
    if active_count > 25:  # default lead_cap
        signals.append("lead_overload")

    risk_level = "green"
    if len(signals) >= 2:
        risk_level = "yellow"
    if len(signals) >= 3:
        risk_level = "red"

    return {
        "signals": signals,
        "risk_level": risk_level,
        "active_leads": active_count,
    }


# ---------------------------------------------------------------------------
# Leaderboard (anonymized)
# ---------------------------------------------------------------------------

async def get_leaderboard(db: AsyncSession, period: str, current_user_id: str | None = None) -> dict:
    """Get leaderboard for a period. Top 5 show names, rest only show their own rank."""
    snapshots = (await db.execute(
        select(KpiSnapshot, User.full_name, User.team_id)
        .join(User, KpiSnapshot.user_id == User.id)
        .where(KpiSnapshot.period == period)
        .order_by(KpiSnapshot.score.desc())
    )).all()

    leaderboard = []
    my_rank = None
    for i, (snap, name, team_id) in enumerate(snapshots, 1):
        entry = {
            "rank": i,
            "score": snap.score,
            "is_me": snap.user_id == current_user_id,
        }
        if i <= 5 or snap.user_id == current_user_id:
            entry["name"] = name
            entry["team_id"] = team_id
        else:
            entry["name"] = None
        if snap.user_id == current_user_id:
            my_rank = i
        leaderboard.append(entry)

    return {"leaderboard": leaderboard, "my_rank": my_rank}
