"""KPI API — performance metrics, leaderboard, coaching notes, reviews."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.performance import KpiSnapshot, CoachingNote, ReviewCycle
from app.services.kpi_engine import compute_kpi, snapshot_all, get_leaderboard, detect_burnout
from app.services.audit import log_action

router = APIRouter(prefix="/kpi", tags=["kpi"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _current_period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


# ---------------------------------------------------------------------------
# GET /kpi/me — personal KPI
# ---------------------------------------------------------------------------

@router.get("/me")
async def get_my_kpi(
    period: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    period = period or _current_period()

    # Try existing snapshot first
    existing = (await db.execute(
        select(KpiSnapshot).where(
            KpiSnapshot.user_id == current_user.id,
            KpiSnapshot.period == period,
        )
    )).scalar_one_or_none()

    if existing:
        return {
            "period": period,
            "score": existing.score,
            "metrics": json.loads(existing.metrics_json),
            "rank_in_team": existing.rank_in_team,
            "rank_overall": existing.rank_overall,
        }

    # Compute on-the-fly if no snapshot yet
    result = await compute_kpi(db, current_user.id, period)
    return {
        "period": period,
        "score": result["score"],
        "metrics": result["metrics"],
        "rank_in_team": None,
        "rank_overall": None,
    }


# ---------------------------------------------------------------------------
# GET /kpi/team — team KPI (leader sees own team, admin/executive sees all)
# ---------------------------------------------------------------------------

@router.get("/team")
async def get_team_kpi(
    period: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    period = period or _current_period()

    if current_user.role not in ("admin", "leader", "executive"):
        raise HTTPException(403, "Chỉ admin/leader/executive xem KPI team")

    q = (
        select(KpiSnapshot, User.full_name, User.team_id)
        .join(User, KpiSnapshot.user_id == User.id)
        .where(KpiSnapshot.period == period)
    )

    if current_user.role == "leader" and current_user.team_id:
        q = q.where(User.team_id == current_user.team_id)

    rows = (await db.execute(q.order_by(KpiSnapshot.score.desc()))).all()

    return {
        "period": period,
        "members": [
            {
                "user_id": snap.user_id,
                "name": name,
                "team_id": team_id,
                "score": snap.score,
                "metrics": json.loads(snap.metrics_json),
                "rank_in_team": snap.rank_in_team,
            }
            for snap, name, team_id in rows
        ],
    }


# ---------------------------------------------------------------------------
# GET /kpi/leaderboard — anonymized (top 5 names, rest hidden)
# ---------------------------------------------------------------------------

@router.get("/leaderboard")
async def get_kpi_leaderboard(
    period: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    period = period or _current_period()
    return await get_leaderboard(db, period, current_user.id)


# ---------------------------------------------------------------------------
# POST /kpi/snapshot — trigger manual snapshot (admin only)
# ---------------------------------------------------------------------------

@router.post("/snapshot")
async def trigger_snapshot(
    period: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(403, "Chỉ admin chạy snapshot")

    period = period or _current_period()
    count = await snapshot_all(db, period)
    await log_action(db, actor=current_user, action="kpi_snapshot", entity_type="kpi", note=f"Snapshot KPI kỳ {period}: {count} users")
    return {"period": period, "users_snapshot": count}


# ---------------------------------------------------------------------------
# GET /kpi/burnout — personal burnout status
# ---------------------------------------------------------------------------

@router.get("/burnout")
async def get_my_burnout(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await detect_burnout(db, current_user.id)
    return result


# ---------------------------------------------------------------------------
# Coaching notes
# ---------------------------------------------------------------------------

class CoachingNoteCreate(BaseModel):
    user_id: str
    note: str
    kind: str = "one_on_one"


@router.post("/coaching-notes")
async def create_coaching_note(
    body: CoachingNoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("admin", "leader"):
        raise HTTPException(403, "Chỉ leader/admin tạo coaching note")

    # Leader can only note for their own team
    if current_user.role == "leader":
        target = await db.get(User, body.user_id)
        if not target or target.team_id != current_user.team_id:
            raise HTTPException(403, "Nhân viên không thuộc team của bạn")

    note = CoachingNote(
        user_id=body.user_id,
        coach_id=current_user.id,
        note=body.note,
        kind=body.kind,
    )
    db.add(note)
    await db.commit()
    await log_action(db, actor=current_user, action="coaching_note", entity_type="coaching", note=f"Note cho {body.user_id}: {body.kind}")
    return {"id": note.id, "created_at": str(note.created_at)}


@router.get("/coaching-notes")
async def list_coaching_notes(
    user_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(CoachingNote).order_by(CoachingNote.created_at.desc())

    if user_id:
        # Users can only see notes about themselves; leaders see team; admin sees all
        if current_user.role == "admin":
            q = q.where(CoachingNote.user_id == user_id)
        elif current_user.role == "leader":
            target = await db.get(User, user_id)
            if target and target.team_id == current_user.team_id:
                q = q.where(CoachingNote.user_id == user_id)
            else:
                raise HTTPException(403, "Không có quyền xem note của nhân viên này")
        else:
            if user_id != current_user.id:
                raise HTTPException(403, "Chỉ xem note của chính mình")
            q = q.where(CoachingNote.user_id == user_id)
    else:
        # Default: leader sees own team, admin sees all
        if current_user.role == "admin":
            pass
        elif current_user.role == "leader":
            team_users = (await db.execute(
                select(User.id).where(User.team_id == current_user.team_id)
            )).scalars().all()
            q = q.where(CoachingNote.user_id.in_(team_users))
        else:
            q = q.where(CoachingNote.user_id == current_user.id)

    notes = (await db.execute(q.limit(50))).scalars().all()
    return {
        "items": [
            {
                "id": n.id,
                "user_id": n.user_id,
                "coach_id": n.coach_id,
                "note": n.note,
                "kind": n.kind,
                "created_at": str(n.created_at),
            }
            for n in notes
        ]
    }


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------

class ReviewSelfSubmit(BaseModel):
    self_json: str  # JSON string with self-assessment answers


class ReviewLeaderSubmit(BaseModel):
    leader_json: str  # JSON string with leader assessment
    goals_json: str | None = None
    suggested_grade_change: str | None = None


@router.get("/reviews/me")
async def get_my_reviews(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reviews = (await db.execute(
        select(ReviewCycle).where(ReviewCycle.user_id == current_user.id)
        .order_by(ReviewCycle.created_at.desc()).limit(4)
    )).scalars().all()

    return {
        "items": [
            {
                "id": r.id,
                "period": r.period,
                "status": r.status,
                "self_json": r.self_json,
                "leader_json": r.leader_json,
                "goals_json": r.goals_json,
                "suggested_grade_change": r.suggested_grade_change,
            }
            for r in reviews
        ]
    }


@router.put("/reviews/me/{review_id}")
async def submit_self_review(
    review_id: str,
    body: ReviewSelfSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    review = await db.get(ReviewCycle, review_id)
    if not review or review.user_id != current_user.id:
        raise HTTPException(404, "Không tìm thấy review")
    if review.status != "pending_self":
        raise HTTPException(409, "Review không ở trạng thái chờ self-assessment")

    review.self_json = body.self_json
    review.status = "pending_leader"
    await db.commit()
    await log_action(db, actor=current_user, action="review_self", entity_type="review", note=f"Submit self review kỳ {review.period}")
    return {"status": review.status}


@router.put("/reviews/{review_id}/leader")
async def submit_leader_review(
    review_id: str,
    body: ReviewLeaderSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("admin", "leader"):
        raise HTTPException(403, "Chỉ leader/admin chấm review")

    review = await db.get(ReviewCycle, review_id)
    if not review:
        raise HTTPException(404, "Không tìm thấy review")
    if review.status != "pending_leader":
        raise HTTPException(409, "Review không ở trạng thái chờ leader")

    # Leader scope check
    if current_user.role == "leader":
        target = await db.get(User, review.user_id)
        if not target or target.team_id != current_user.team_id:
            raise HTTPException(403, "Nhân viên không thuộc team của bạn")

    review.leader_json = body.leader_json
    review.goals_json = body.goals_json
    review.suggested_grade_change = body.suggested_grade_change
    review.status = "done"
    await db.commit()
    await log_action(db, actor=current_user, action="review_leader", entity_type="review", note=f"Submit leader review kỳ {review.period}")
    return {"status": review.status}
