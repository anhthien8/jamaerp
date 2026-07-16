"""Approvals API — Trung tâm phê duyệt ("Chờ tôi duyệt")."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.approval import ApprovalRequest
from app.models.user import User
from app.services import approval_engine
from app.services.approval_engine import ApprovalError, TYPE_LABELS
from app.services.audit import log_action

router = APIRouter(prefix="/approvals", tags=["approvals"])


class ReasonBody(BaseModel):
    reason: str = Field(..., min_length=2, max_length=500)


class DelegateBody(BaseModel):
    delegate_to: str | None = None  # None = tắt ủy quyền
    until: datetime | None = None


class TelegramActBody(BaseModel):
    approver_tg_id: int | None = None  # Deprecated: backend uses JWT-authenticated user as actor
    reason: str | None = Field(default=None, max_length=500)


def _serialize(r: ApprovalRequest, extra: dict | None = None) -> dict:
    data = {
        "id": r.id,
        "type": r.type,
        "type_label": TYPE_LABELS.get(r.type, r.type),
        "ref_id": r.ref_id,
        "title": r.title,
        "amount": r.amount,
        "requester_id": r.requester_id,
        "current_approver_id": r.current_approver_id,
        "step": r.step,
        "total_steps": r.total_steps,
        "status": r.status,
        "reason": r.reason,
        "due_at": str(r.due_at) if r.due_at else None,
        "created_at": str(r.created_at),
        "resolved_at": str(r.resolved_at) if r.resolved_at else None,
    }
    if extra:
        data.update(extra)
    return data


def _raise(err: ApprovalError):
    raise HTTPException(status_code=err.status_code, detail=err.detail)


@router.get("/pending-for-me")
async def pending_for_me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Đơn đang chờ tôi duyệt (gồm cả đơn tôi được ủy quyền)."""
    # Đơn tôi là approver hiện tại
    conditions = [ApprovalRequest.current_approver_id == current_user.id]

    # Đơn của các approver đã ủy quyền cho tôi (còn hạn) — 1 query, lọc hạn trong SQL
    now = datetime.now(timezone.utc)
    valid_delegators = (await db.execute(
        select(User.id).where(
            User.delegate_to == current_user.id,
            User.delegate_until.is_not(None),
            User.delegate_until >= now,
        )
    )).scalars().all()
    if valid_delegators:
        conditions.append(ApprovalRequest.current_approver_id.in_(valid_delegators))

    # Join requester name — không N+1 (spec 05 Track B)
    result = await db.execute(
        select(ApprovalRequest, User.full_name)
        .join(User, User.id == ApprovalRequest.requester_id)
        .where(
            ApprovalRequest.status == "pending",
            or_(*conditions),
        )
        .order_by(ApprovalRequest.created_at)
    )
    items = [
        _serialize(request, {
            "requester_name": requester_name,
            "delegated": request.current_approver_id != current_user.id,
        })
        for request, requester_name in result.all()
    ]
    return {"items": items, "count": len(items)}


@router.get("/my-requests")
async def my_requests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Đơn tôi đã tạo."""
    result = await db.execute(
        select(ApprovalRequest)
        .where(ApprovalRequest.requester_id == current_user.id)
        .order_by(ApprovalRequest.created_at.desc())
        .limit(100)
    )
    return {"items": [_serialize(r) for r in result.scalars().all()]}


@router.get("/handled")
async def handled_by_me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Đơn đã xử lý gần đây (admin thấy tất cả, người khác thấy đơn liên quan)."""
    q = select(ApprovalRequest).where(
        ApprovalRequest.status.in_(("approved", "rejected", "cancelled"))
    )
    if current_user.role != "admin":
        q = q.where(or_(
            ApprovalRequest.requester_id == current_user.id,
            ApprovalRequest.current_approver_id == current_user.id,
        ))
    result = await db.execute(q.order_by(ApprovalRequest.resolved_at.desc()).limit(100))
    return {"items": [_serialize(r) for r in result.scalars().all()]}


@router.post("/{request_id}/approve")
async def approve(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        request = await approval_engine.approve(db, request_id, current_user, via="web")
    except ApprovalError as err:
        _raise(err)
    return {"request": _serialize(request)}


@router.post("/{request_id}/reject")
async def reject(
    request_id: str,
    body: ReasonBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        request = await approval_engine.reject(db, request_id, current_user, reason=body.reason, via="web")
    except ApprovalError as err:
        _raise(err)
    return {"request": _serialize(request)}


@router.post("/{request_id}/request-changes")
async def request_changes(
    request_id: str,
    body: ReasonBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        request = await approval_engine.request_changes(db, request_id, current_user, reason=body.reason)
    except ApprovalError as err:
        _raise(err)
    return {"request": _serialize(request)}


@router.post("/{request_id}/resubmit")
async def resubmit(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        request = await approval_engine.resubmit(db, request_id, current_user)
    except ApprovalError as err:
        _raise(err)
    return {"request": _serialize(request)}


@router.post("/{request_id}/cancel")
async def cancel(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        request = await approval_engine.cancel(db, request_id, current_user)
    except ApprovalError as err:
        _raise(err)
    return {"request": _serialize(request)}


# ---------------------------------------------------------------------------
# Telegram inline button callbacks (bot gọi với JWT-authenticated user)
# ---------------------------------------------------------------------------

@router.post("/{request_id}/tg-approve")
async def tg_approve(
    request_id: str,
    body: TelegramActBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # SECURITY: Use JWT-authenticated user as actor — prevents impersonation
    actor = current_user
    if body.approver_tg_id and current_user.telegram_user_id and body.approver_tg_id != current_user.telegram_user_id:
        raise HTTPException(status_code=403, detail="Telegram ID không khớp với tài khoản đang đăng nhập")
    try:
        request = await approval_engine.approve(db, request_id, actor, via="telegram")
    except ApprovalError as err:
        _raise(err)
    return {"request": _serialize(request), "actor": actor.full_name}


@router.post("/{request_id}/tg-reject")
async def tg_reject(
    request_id: str,
    body: TelegramActBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # SECURITY: Use JWT-authenticated user as actor — prevents impersonation
    actor = current_user
    if body.approver_tg_id and current_user.telegram_user_id and body.approver_tg_id != current_user.telegram_user_id:
        raise HTTPException(status_code=403, detail="Telegram ID không khớp với tài khoản đang đăng nhập")
    try:
        request = await approval_engine.reject(
            db, request_id, actor, reason=body.reason or "Từ chối qua Telegram", via="telegram"
        )
    except ApprovalError as err:
        _raise(err)
    return {"request": _serialize(request), "actor": actor.full_name}


# ---------------------------------------------------------------------------
# Ủy quyền duyệt khi vắng mặt
# ---------------------------------------------------------------------------

@router.post("/delegate")
async def set_delegate(
    body: DelegateBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Đặt/tắt ủy quyền duyệt (leader, accountant, pm, admin)."""
    if current_user.role not in ("admin", "leader", "accountant", "supervisor"):
        raise HTTPException(status_code=403, detail="Vai trò của bạn không có quyền duyệt để ủy quyền")

    if body.delegate_to:
        if body.delegate_to == current_user.id:
            raise HTTPException(status_code=400, detail="Không thể ủy quyền cho chính mình")
        target = await db.get(User, body.delegate_to)
        if not target or not target.is_active:
            raise HTTPException(status_code=404, detail="Người nhận ủy quyền không hợp lệ")
        if not body.until:
            raise HTTPException(status_code=400, detail="Cần thời hạn ủy quyền (until)")

    before = {"delegate_to": current_user.delegate_to}
    current_user.delegate_to = body.delegate_to
    current_user.delegate_until = body.until
    await db.flush()
    await log_action(
        db, actor=current_user, action="approval.delegate", entity_type="user",
        entity_id=current_user.id, before=before,
        after={"delegate_to": body.delegate_to, "until": str(body.until)},
    )
    return {"delegate_to": body.delegate_to, "until": str(body.until) if body.until else None}
