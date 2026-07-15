"""Leaves API — nghỉ phép: tạo đơn, duyệt qua approval engine, lịch team, số dư phép.

Luồng duyệt:
- ≤3 ngày: leader team duyệt (1 cấp)
- >3 ngày HOẶC người tạo là leader: thêm cấp admin
- Approve đủ cấp → trừ số dư + ghi bảng công các ngày nghỉ (phép năm = 8h công/ngày)
"""

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.approval import ApprovalRequest
from app.models.attendance import AttendanceRecord
from app.models.leave import LeaveBalance, LeaveRequest
from app.models.user import User, Team
from app.services import approval_engine
from app.services.approval_engine import ApprovalError
from app.services.attendance_service import STANDARD_HOURS_PER_DAY, is_period_locked, period_of
from app.services.audit import log_action

router = APIRouter(prefix="/leaves", tags=["leaves"])

VALID_LEAVE_TYPES = ("annual", "sick", "unpaid")
LEAVE_TYPE_LABELS = {"annual": "Phép năm", "sick": "Nghỉ ốm", "unpaid": "Không lương"}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LeaveCreateBody(BaseModel):
    leave_type: str = Field(default="annual", pattern=r"^(annual|sick|unpaid)$")
    start_date: date
    end_date: date
    half_day: bool = False  # chỉ hợp lệ khi start == end
    reason: str = Field(..., min_length=3, max_length=500)


def _serialize(r: LeaveRequest, extra: dict | None = None) -> dict:
    data = {
        "id": r.id,
        "user_id": r.user_id,
        "leave_type": r.leave_type,
        "leave_type_label": LEAVE_TYPE_LABELS.get(r.leave_type, r.leave_type),
        "start_date": str(r.start_date),
        "end_date": str(r.end_date),
        "days": r.days,
        "reason": r.reason,
        "status": r.status,
        "approval_id": r.approval_id,
        "created_at": str(r.created_at),
    }
    if extra:
        data.update(extra)
    return data


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def count_leave_days(start: date, end: date, half_day: bool = False) -> float:
    """Số ngày nghỉ — bỏ Chủ nhật (công ty làm T2-T7). half_day chỉ khi 1 ngày."""
    if half_day and start == end:
        return 0.5
    days = 0
    d = start
    while d <= end:
        if d.weekday() != 6:  # 6 = Chủ nhật
            days += 1
        d += timedelta(days=1)
    return float(days)


async def get_or_create_balance(db: AsyncSession, user_id: str, year: int) -> LeaveBalance:
    result = await db.execute(
        select(LeaveBalance).where(
            LeaveBalance.user_id == user_id, LeaveBalance.year == year
        )
    )
    balance = result.scalar_one_or_none()
    if not balance:
        balance = LeaveBalance(user_id=user_id, year=year)
        db.add(balance)
        await db.flush()
    return balance


async def _build_approver_chain(db: AsyncSession, requester: User, days: float) -> list[str]:
    """≤3 ngày: leader. >3 ngày hoặc requester là leader: thêm/thay admin."""
    chain: list[str] = []

    leader_id: str | None = None
    if requester.team_id:
        team = await db.get(Team, requester.team_id)
        if team and team.leader_id and team.leader_id != requester.id:
            leader = await db.get(User, team.leader_id)
            if leader and leader.is_active:
                leader_id = leader.id

    admin_result = await db.execute(
        select(User).where(User.role == "admin", User.is_active == True).limit(1)  # noqa: E712
    )
    admin = admin_result.scalar_one_or_none()

    if leader_id:
        chain.append(leader_id)
    if days > 3 or not leader_id or requester.role == "leader":
        if admin and admin.id not in chain:
            chain.append(admin.id)
    return chain


# ---------------------------------------------------------------------------
# Side-effects đăng ký với approval engine
# ---------------------------------------------------------------------------

async def _on_leave_approved(db: AsyncSession, request: ApprovalRequest) -> None:
    leave = await db.get(LeaveRequest, request.ref_id)
    if not leave or leave.status != "pending":
        return

    leave.status = "approved"
    leave.resolved_at = datetime.now(timezone.utc)

    # Trừ số dư phép
    balance = await get_or_create_balance(db, leave.user_id, leave.start_date.year)
    if leave.leave_type == "annual":
        balance.annual_used += leave.days
    elif leave.leave_type == "sick":
        balance.sick_used += leave.days
    else:
        balance.unpaid_used += leave.days

    # Ghi bảng công các ngày nghỉ (bỏ Chủ nhật) — phép năm được tính công
    paid = leave.leave_type == "annual"
    d = leave.start_date
    while d <= leave.end_date:
        if d.weekday() != 6:
            existing = await db.execute(
                select(AttendanceRecord).where(
                    AttendanceRecord.user_id == leave.user_id,
                    AttendanceRecord.work_date == d,
                )
            )
            record = existing.scalar_one_or_none()
            hours = STANDARD_HOURS_PER_DAY if paid else 0.0
            if leave.days == 0.5:
                hours = hours / 2
            if record:
                record.source = "leave"
                record.work_hours = hours
                record.note = ((record.note + " | ") if record.note else "") + f"Nghỉ {LEAVE_TYPE_LABELS[leave.leave_type]}"
            else:
                db.add(AttendanceRecord(
                    user_id=leave.user_id,
                    work_date=d,
                    source="leave",
                    work_hours=hours,
                    note=f"Nghỉ {LEAVE_TYPE_LABELS[leave.leave_type]}: {leave.reason}",
                ))
        d += timedelta(days=1)
    await db.flush()


async def _on_leave_rejected(db: AsyncSession, request: ApprovalRequest) -> None:
    leave = await db.get(LeaveRequest, request.ref_id)
    if not leave or leave.status != "pending":
        return
    leave.status = "rejected" if request.status == "rejected" else "cancelled"
    leave.resolved_at = datetime.now(timezone.utc)
    await db.flush()


approval_engine.register_side_effect("leave", _on_leave_approved)
approval_engine.register_reject_effect("leave", _on_leave_rejected)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("")
async def create_leave(
    body: LeaveCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.end_date < body.start_date:
        raise HTTPException(status_code=400, detail="Ngày kết thúc phải sau ngày bắt đầu")
    if body.half_day and body.start_date != body.end_date:
        raise HTTPException(status_code=400, detail="Nghỉ nửa ngày chỉ áp dụng cho 1 ngày")

    days = count_leave_days(body.start_date, body.end_date, body.half_day)
    if days <= 0:
        raise HTTPException(status_code=400, detail="Khoảng nghỉ không có ngày làm việc nào (chỉ Chủ nhật)")

    # Kỳ lương đã khóa → không cho xin nghỉ lùi ngày vào kỳ đó
    if await is_period_locked(db, period_of(body.start_date)):
        raise HTTPException(status_code=409, detail=f"Kỳ {period_of(body.start_date)} đã khóa lương — không thể tạo đơn lùi ngày")

    # Kiểm tra số dư phép năm
    if body.leave_type == "annual":
        balance = await get_or_create_balance(db, current_user.id, body.start_date.year)
        remaining = balance.annual_total - balance.annual_used
        if days > remaining:
            raise HTTPException(
                status_code=400,
                detail=f"Không đủ phép năm: còn {remaining:.1f} ngày, xin {days:.1f} ngày",
            )

    # Chống trùng đơn pending/approved giao nhau về ngày
    overlap = await db.execute(
        select(LeaveRequest).where(
            LeaveRequest.user_id == current_user.id,
            LeaveRequest.status.in_(("pending", "approved")),
            LeaveRequest.start_date <= body.end_date,
            LeaveRequest.end_date >= body.start_date,
        ).limit(1)
    )
    if overlap.first():
        raise HTTPException(status_code=409, detail="Bạn đã có đơn nghỉ trùng khoảng ngày này")

    chain = await _build_approver_chain(db, current_user, days)
    if not chain:
        raise HTTPException(status_code=400, detail="Không tìm được người duyệt (team chưa có leader và hệ thống chưa có admin)")

    leave = LeaveRequest(
        user_id=current_user.id,
        leave_type=body.leave_type,
        start_date=body.start_date,
        end_date=body.end_date,
        days=days,
        reason=body.reason,
    )
    db.add(leave)
    await db.flush()

    try:
        approval = await approval_engine.create_request(
            db,
            type_="leave",
            ref_id=leave.id,
            title=f"{LEAVE_TYPE_LABELS[body.leave_type]} {days:g} ngày ({body.start_date} → {body.end_date}) — {current_user.full_name}",
            requester=current_user,
            approver_ids=chain,
            sla_hours=24,
        )
    except ApprovalError as err:
        raise HTTPException(status_code=err.status_code, detail=err.detail)

    leave.approval_id = approval.id
    await db.flush()
    return {"leave": _serialize(leave), "approval_id": approval.id}


@router.get("/me")
async def my_leaves(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(LeaveRequest)
        .where(LeaveRequest.user_id == current_user.id)
        .order_by(LeaveRequest.created_at.desc())
        .limit(50)
    )
    return {"items": [_serialize(r) for r in result.scalars().all()]}


@router.get("/balance/me")
async def my_balance(
    year: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.attendance_service import vn_today
    year = year or vn_today().year
    balance = await get_or_create_balance(db, current_user.id, year)
    return {
        "year": year,
        "annual_total": balance.annual_total,
        "annual_used": balance.annual_used,
        "annual_remaining": balance.annual_total - balance.annual_used,
        "sick_used": balance.sick_used,
        "unpaid_used": balance.unpaid_used,
    }


@router.get("/calendar")
async def team_calendar(
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    team_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lịch nghỉ đã duyệt trong tháng (leader: team mình; admin/accountant: chọn team hoặc toàn bộ)."""
    if current_user.role == "leader":
        team_id = current_user.team_id
    elif current_user.role not in ("admin", "accountant", "executive", "pm"):
        # nhân viên thường: chỉ xem team mình để sắp việc
        team_id = current_user.team_id
        if not team_id:
            raise HTTPException(status_code=403, detail="Bạn chưa thuộc team nào")

    from app.services.attendance_service import period_bounds
    start, end = period_bounds(month)

    q = (
        select(LeaveRequest, User.full_name, User.team_id)
        .join(User, User.id == LeaveRequest.user_id)
        .where(
            LeaveRequest.status == "approved",
            LeaveRequest.start_date < end,
            LeaveRequest.end_date >= start,
        )
    )
    if team_id:
        q = q.where(User.team_id == team_id)

    result = await db.execute(q.order_by(LeaveRequest.start_date))
    items = [
        _serialize(leave, {"full_name": full_name, "team_id": tid})
        for leave, full_name, tid in result.all()
    ]
    return {"month": month, "team_id": team_id, "items": items}
