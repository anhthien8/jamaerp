"""Attendance API — chấm công web, bảng công cá nhân/team, duyệt OT, sửa công."""

from datetime import datetime, date, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.attendance import AttendanceRecord
from app.models.user import User
from app.services.attendance_service import (
    _empty_summary,
    is_period_locked,
    month_records,
    month_summary,
    period_bounds,
    period_of,
    record_checkin,
    record_checkout,
    team_month_summary,
    vn_today,
)
from app.services.audit import log_action

router = APIRouter(prefix="/attendance", tags=["attendance"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CheckinBody(BaseModel):
    project_id: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class EditAttendanceBody(BaseModel):
    check_in: datetime | None = None
    check_out: datetime | None = None
    work_hours: float | None = Field(default=None, ge=0, le=24)
    note: str = Field(..., min_length=3, max_length=500)  # bắt buộc ghi lý do sửa


def _serialize(r: AttendanceRecord) -> dict:
    return {
        "id": r.id,
        "user_id": r.user_id,
        "work_date": str(r.work_date),
        "check_in": str(r.check_in) if r.check_in else None,
        "check_out": str(r.check_out) if r.check_out else None,
        "project_id": r.project_id,
        "source": r.source,
        "work_hours": r.work_hours,
        "ot_hours": r.ot_hours,
        "ot_status": r.ot_status,
        "needs_review": r.needs_review,
        "note": r.note,
    }


async def _get_record(db: AsyncSession, record_id: str) -> AttendanceRecord:
    record = await db.get(AttendanceRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Bản ghi chấm công không tồn tại")
    return record


async def _require_unlocked(db: AsyncSession, work_date: date) -> None:
    if await is_period_locked(db, period_of(work_date)):
        raise HTTPException(
            status_code=409,
            detail=f"Kỳ lương {period_of(work_date)} đã khóa — không thể sửa chấm công",
        )


async def _require_team_scope(db: AsyncSession, current_user: User, target_user_id: str) -> User:
    """Leader chỉ thao tác trong team mình; admin/accountant toàn quyền."""
    target = await db.get(User, target_user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Nhân viên không tồn tại")
    if current_user.role in ("admin", "accountant"):
        return target
    if current_user.role == "leader" and current_user.team_id and target.team_id == current_user.team_id:
        return target
    raise HTTPException(status_code=403, detail="Không có quyền thao tác chấm công của nhân viên này")


# ---------------------------------------------------------------------------
# Check-in / Check-out (web — mọi role)
# ---------------------------------------------------------------------------

@router.post("/checkin")
async def checkin(
    body: CheckinBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record, created = await record_checkin(
        db, current_user, source="web",
        project_id=body.project_id, lat=body.latitude, lng=body.longitude,
    )
    return {
        "record": _serialize(record),
        "created": created,
        "message": "Check-in thành công" if created else "Hôm nay bạn đã check-in rồi",
    }


@router.post("/checkout")
async def checkout(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = await record_checkout(db, current_user)
    if not record:
        raise HTTPException(status_code=400, detail="Hôm nay bạn chưa check-in")
    return {"record": _serialize(record), "message": "Check-out thành công"}


@router.get("/today")
async def today_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trạng thái chấm công hôm nay của chính mình (cho nút checkin/checkout trên UI)."""
    result = await db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.user_id == current_user.id,
            AttendanceRecord.work_date == vn_today(),
        )
    )
    record = result.scalar_one_or_none()
    return {"record": _serialize(record) if record else None}


# ---------------------------------------------------------------------------
# Bảng công
# ---------------------------------------------------------------------------

@router.get("/me")
async def my_attendance(
    period: str = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    period = period or period_of(vn_today())
    records = await month_records(db, current_user.id, period)
    summary = await month_summary(db, current_user.id, period)
    return {"summary": summary, "records": [_serialize(r) for r in records]}


@router.get("/team")
async def team_attendance(
    period: str = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    team_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bảng công team (leader: team mình; admin/accountant: mọi team hoặc toàn công ty)."""
    if current_user.role == "leader":
        team_id = current_user.team_id
        if not team_id:
            raise HTTPException(status_code=400, detail="Bạn chưa thuộc team nào")
    elif current_user.role not in ("admin", "accountant"):
        raise HTTPException(status_code=403, detail="Không có quyền xem bảng công team")

    period = period or period_of(vn_today())

    q = select(User).where(User.is_active == True)  # noqa: E712
    if team_id:
        q = q.where(User.team_id == team_id)
    users = (await db.execute(q.order_by(User.full_name))).scalars().all()

    # 1 aggregate cho cả team thay vì N query per-user (spec 05 Track B)
    summaries = await team_month_summary(db, [u.id for u in users], period)
    rows = [
        {
            "user_id": u.id,
            "full_name": u.full_name,
            "role": u.role,
            "team_id": u.team_id,
            **(summaries.get(u.id) or _empty_summary(period)),
        }
        for u in users
    ]
    return {"period": period, "items": rows}


# ---------------------------------------------------------------------------
# Sửa công (quên chấm) — bắt buộc note, ghi audit, chặn kỳ khóa
# ---------------------------------------------------------------------------

@router.patch("/{record_id}")
async def edit_attendance(
    record_id: str,
    body: EditAttendanceBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = await _get_record(db, record_id)
    await _require_team_scope(db, current_user, record.user_id)
    await _require_unlocked(db, record.work_date)

    before = {
        "check_in": str(record.check_in), "check_out": str(record.check_out),
        "work_hours": record.work_hours,
    }
    if body.check_in is not None:
        record.check_in = body.check_in
    if body.check_out is not None:
        record.check_out = body.check_out
    if body.work_hours is not None:
        record.work_hours = body.work_hours
    record.needs_review = False
    record.note = ((record.note + " | ") if record.note else "") + f"Sửa bởi {current_user.full_name}: {body.note}"
    await db.flush()

    await log_action(
        db, actor=current_user, action="attendance.edit", entity_type="attendance",
        entity_id=record.id, before=before,
        after={"check_in": str(record.check_in), "check_out": str(record.check_out), "work_hours": record.work_hours},
        note=body.note,
    )
    return {"record": _serialize(record)}


# ---------------------------------------------------------------------------
# Duyệt OT
# ---------------------------------------------------------------------------

@router.get("/ot/pending")
async def pending_ot(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("admin", "leader", "accountant"):
        raise HTTPException(status_code=403, detail="Không có quyền duyệt OT")

    # Join + lọc team trong SQL — không N+1, không lọc Python (spec 05 Track B)
    q = (
        select(AttendanceRecord, User.full_name)
        .join(User, User.id == AttendanceRecord.user_id)
        .where(AttendanceRecord.ot_status == "pending")
    )
    if current_user.role == "leader":
        q = q.where(User.team_id == current_user.team_id)
    result = await db.execute(q.order_by(AttendanceRecord.work_date.desc()))

    items = [
        {**_serialize(record), "full_name": full_name}
        for record, full_name in result.all()
    ]
    return {"items": items}


@router.post("/{record_id}/ot-approve")
async def approve_ot(
    record_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = await _get_record(db, record_id)
    target = await _require_team_scope(db, current_user, record.user_id)
    if current_user.id == record.user_id:
        raise HTTPException(status_code=403, detail="Không thể tự duyệt OT của chính mình")
    if record.ot_status != "pending":
        raise HTTPException(status_code=409, detail="OT này đã được xử lý")
    await _require_unlocked(db, record.work_date)

    record.ot_status = "approved"
    await db.flush()
    await log_action(
        db, actor=current_user, action="ot.approve", entity_type="attendance",
        entity_id=record.id, after={"ot_hours": record.ot_hours, "user": target.full_name},
    )
    return {"record": _serialize(record)}


@router.post("/{record_id}/ot-reject")
async def reject_ot(
    record_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = await _get_record(db, record_id)
    target = await _require_team_scope(db, current_user, record.user_id)
    if current_user.id == record.user_id:
        raise HTTPException(status_code=403, detail="Không thể tự xử lý OT của chính mình")
    if record.ot_status != "pending":
        raise HTTPException(status_code=409, detail="OT này đã được xử lý")
    await _require_unlocked(db, record.work_date)

    record.ot_status = "rejected"
    await db.flush()
    await log_action(
        db, actor=current_user, action="ot.reject", entity_type="attendance",
        entity_id=record.id, after={"ot_hours": record.ot_hours, "user": target.full_name},
    )
    return {"record": _serialize(record)}
