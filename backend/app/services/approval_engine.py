"""Approval engine — luồng phê duyệt dùng chung cho phép, tạm ứng, lương, chi phí, OT.

Thiết kế:
- create_request(): tạo đơn với chuỗi duyệt (1-3 cấp), notify approver đầu (web + Telegram riêng).
- approve(): idempotent; đủ cấp → status=approved + chạy side-effect đã đăng ký theo type.
- Side-effect đăng ký qua register_side_effect(type, fn) — module leave/payroll tự đăng ký,
  tránh import vòng.
- Ủy quyền: approver đặt delegate_to/delegate_until trên User — người được ủy quyền
  duyệt thay trong thời hạn.
- escalate_overdue(): đơn quá 2×SLA → chuyển admin (chạy trong automation hằng ngày).

Bất biến (được test):
1. Side-effect chỉ chạy khi đủ total_steps approve.
2. Đơn đã resolve không thể approve/reject lần nữa (409).
3. Requester không thể tự duyệt đơn của mình.
4. Mọi chuyển trạng thái ghi AuditLog.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import ApprovalRequest
from app.models.user import User
from app.services.audit import log_action

logger = logging.getLogger(__name__)

# type -> async fn(db, request) chạy khi đơn được duyệt đủ cấp
_SIDE_EFFECTS: dict[str, Callable[[AsyncSession, ApprovalRequest], Awaitable[Any]]] = {}
# type -> async fn(db, request) chạy khi đơn bị từ chối/hủy (rollback trạng thái bản ghi gốc)
_REJECT_EFFECTS: dict[str, Callable[[AsyncSession, ApprovalRequest], Awaitable[Any]]] = {}

TYPE_LABELS = {
    "leave": "Nghỉ phép",
    "advance": "Tạm ứng",
    "payroll_period": "Bảng lương",
    "expense": "Chi phí",
    "overtime": "Tăng ca",
}


def register_side_effect(type_: str, fn: Callable[[AsyncSession, ApprovalRequest], Awaitable[Any]]) -> None:
    _SIDE_EFFECTS[type_] = fn


def register_reject_effect(type_: str, fn: Callable[[AsyncSession, ApprovalRequest], Awaitable[Any]]) -> None:
    _REJECT_EFFECTS[type_] = fn


class ApprovalError(Exception):
    """Lỗi nghiệp vụ phê duyệt — API dịch sang HTTPException."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def _notify_user(db: AsyncSession, user: User | None, title: str, body: str, link: str | None, ref_id: str) -> None:
    """Notify web + Telegram chat riêng (dedupe theo ref)."""
    if user is None:
        return
    from app.services.automation import _notify
    await _notify(db, user, type_="approval", title=title, body=body, link=link, ref_id=ref_id)


async def create_request(
    db: AsyncSession,
    *,
    type_: str,
    ref_id: str,
    title: str,
    requester: User,
    approver_ids: list[str],
    amount: float | None = None,
    sla_hours: int = 24,
) -> ApprovalRequest:
    if not approver_ids:
        raise ApprovalError(400, "Đơn phải có ít nhất 1 người duyệt")
    # Loại requester khỏi chuỗi duyệt (không tự duyệt đơn mình)
    chain = [a for a in approver_ids if a and a != requester.id]
    if not chain:
        raise ApprovalError(400, "Chuỗi duyệt không hợp lệ — người duyệt trùng người tạo")

    request = ApprovalRequest(
        type=type_,
        ref_id=ref_id,
        title=title,
        amount=amount,
        requester_id=requester.id,
        current_approver_id=chain[0],
        next_approvers_csv=",".join(chain[1:]) if len(chain) > 1 else None,
        step=1,
        total_steps=len(chain),
        due_at=datetime.now(timezone.utc) + timedelta(hours=sla_hours),
    )
    db.add(request)
    await db.flush()

    approver = await db.get(User, chain[0])
    label = TYPE_LABELS.get(type_, type_)
    await _notify_user(
        db, approver,
        title=f"[Chờ duyệt] {label}: {title}",
        body=f"Người tạo: {requester.full_name}. Vào mục Phê duyệt để xử lý.",
        link="/approvals",
        ref_id=request.id,
    )
    await log_action(
        db, actor=requester, action="approval.create", entity_type="approval",
        entity_id=request.id, after={"type": type_, "ref_id": ref_id, "title": title},
    )
    return request


async def _get_pending(db: AsyncSession, request_id: str) -> ApprovalRequest:
    result = await db.execute(
        select(ApprovalRequest)
        .where(ApprovalRequest.id == request_id)
        .with_for_update()  # Row-level lock: prevents concurrent approve/reject
    )
    request = result.scalar_one_or_none()
    if not request:
        raise ApprovalError(404, "Đơn phê duyệt không tồn tại")
    if request.status not in ("pending", "changes_requested"):
        raise ApprovalError(409, f"Đơn đã được xử lý (trạng thái: {request.status})")
    return request


async def _authorize_actor(db: AsyncSession, request: ApprovalRequest, actor: User) -> None:
    """Actor hợp lệ: approver hiện tại, người được approver ủy quyền (còn hạn), hoặc admin."""
    if actor.id == request.requester_id:
        raise ApprovalError(403, "Không thể tự duyệt đơn của chính mình")
    if actor.role == "admin":
        return
    if actor.id == request.current_approver_id:
        return
    approver = await db.get(User, request.current_approver_id) if request.current_approver_id else None
    if approver and approver.delegate_to == actor.id:
        until = approver.delegate_until
        if until and until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        if until and until >= datetime.now(timezone.utc):
            return
    raise ApprovalError(403, "Bạn không phải người duyệt của đơn này")


async def approve(
    db: AsyncSession, request_id: str, actor: User, *, via: str = "web", sla_hours: int = 24
) -> ApprovalRequest:
    request = await _get_pending(db, request_id)
    if request.status == "changes_requested":
        raise ApprovalError(409, "Đơn đang chờ người tạo sửa lại")
    await _authorize_actor(db, request, actor)

    label = TYPE_LABELS.get(request.type, request.type)
    requester = await db.get(User, request.requester_id)

    if request.step < request.total_steps:
        # Chuyển cấp kế tiếp
        next_ids = (request.next_approvers_csv or "").split(",")
        next_id = next_ids[0] if next_ids and next_ids[0] else None
        request.next_approvers_csv = ",".join(next_ids[1:]) if len(next_ids) > 1 else None
        request.current_approver_id = next_id
        request.step += 1
        request.due_at = datetime.now(timezone.utc) + timedelta(hours=sla_hours)
        request.acted_via = via
        await db.flush()

        next_approver = await db.get(User, next_id) if next_id else None
        await _notify_user(
            db, next_approver,
            title=f"[Chờ duyệt] {label}: {request.title}",
            body=f"Cấp {request.step}/{request.total_steps} — đã qua duyệt cấp trước.",
            link="/approvals",
            ref_id=f"{request.id}-step{request.step}",
        )
        await log_action(
            db, actor=actor, action="approval.approve_step", entity_type="approval",
            entity_id=request.id, after={"step": request.step, "via": via},
        )
        return request

    # Cấp cuối — chốt duyệt rồi chạy side-effect
    request.status = "approved"
    request.acted_via = via
    request.resolved_at = datetime.now(timezone.utc)
    await db.flush()

    side_effect = _SIDE_EFFECTS.get(request.type)
    if side_effect:
        await side_effect(db, request)

    await _notify_user(
        db, requester,
        title=f"✅ {label} đã được duyệt",
        body=f"{request.title} — duyệt bởi {actor.full_name}.",
        link="/approvals",
        ref_id=f"{request.id}-approved",
    )
    await log_action(
        db, actor=actor, action="approval.approve", entity_type="approval",
        entity_id=request.id, after={"type": request.type, "ref_id": request.ref_id, "via": via},
    )
    return request


async def reject(
    db: AsyncSession, request_id: str, actor: User, *, reason: str, via: str = "web"
) -> ApprovalRequest:
    request = await _get_pending(db, request_id)
    await _authorize_actor(db, request, actor)

    request.status = "rejected"
    request.reason = reason
    request.acted_via = via
    request.resolved_at = datetime.now(timezone.utc)
    await db.flush()

    reject_effect = _REJECT_EFFECTS.get(request.type)
    if reject_effect:
        await reject_effect(db, request)

    label = TYPE_LABELS.get(request.type, request.type)
    requester = await db.get(User, request.requester_id)
    await _notify_user(
        db, requester,
        title=f"❌ {label} bị từ chối",
        body=f"{request.title} — lý do: {reason}",
        link="/approvals",
        ref_id=f"{request.id}-rejected",
    )
    await log_action(
        db, actor=actor, action="approval.reject", entity_type="approval",
        entity_id=request.id, after={"reason": reason, "via": via},
    )
    return request


async def request_changes(
    db: AsyncSession, request_id: str, actor: User, *, reason: str, via: str = "web"
) -> ApprovalRequest:
    request = await _get_pending(db, request_id)
    if request.status == "changes_requested":
        raise ApprovalError(409, "Đơn đã ở trạng thái chờ sửa")
    await _authorize_actor(db, request, actor)

    request.status = "changes_requested"
    request.reason = reason
    request.acted_via = via
    await db.flush()

    requester = await db.get(User, request.requester_id)
    await _notify_user(
        db, requester,
        title=f"✏️ Cần sửa lại: {request.title}",
        body=f"Yêu cầu từ {actor.full_name}: {reason}",
        link="/approvals",
        ref_id=f"{request.id}-changes",
    )
    await log_action(
        db, actor=actor, action="approval.request_changes", entity_type="approval",
        entity_id=request.id, after={"reason": reason},
    )
    return request


async def resubmit(db: AsyncSession, request_id: str, actor: User) -> ApprovalRequest:
    """Người tạo nộp lại đơn sau khi sửa — quay về pending ở cấp hiện tại."""
    result = await db.execute(
        select(ApprovalRequest).where(ApprovalRequest.id == request_id).with_for_update()
    )
    request = result.scalar_one_or_none()
    if not request:
        raise ApprovalError(404, "Đơn phê duyệt không tồn tại")
    if request.status != "changes_requested":
        raise ApprovalError(409, "Chỉ nộp lại được đơn đang chờ sửa")
    if actor.id != request.requester_id:
        raise ApprovalError(403, "Chỉ người tạo mới được nộp lại đơn")

    request.status = "pending"
    request.reason = None
    request.due_at = datetime.now(timezone.utc) + timedelta(hours=24)
    await db.flush()

    approver = await db.get(User, request.current_approver_id) if request.current_approver_id else None
    await _notify_user(
        db, approver,
        title=f"[Chờ duyệt] (đã sửa) {request.title}",
        body=f"{actor.full_name} đã cập nhật đơn.",
        link="/approvals",
        ref_id=f"{request.id}-resubmit",
    )
    await log_action(db, actor=actor, action="approval.resubmit", entity_type="approval", entity_id=request.id)
    return request


async def cancel(db: AsyncSession, request_id: str, actor: User) -> ApprovalRequest:
    result = await db.execute(
        select(ApprovalRequest).where(ApprovalRequest.id == request_id).with_for_update()
    )
    request = result.scalar_one_or_none()
    if not request:
        raise ApprovalError(404, "Đơn phê duyệt không tồn tại")
    if request.status not in ("pending", "changes_requested"):
        raise ApprovalError(409, f"Đơn đã được xử lý (trạng thái: {request.status})")
    if actor.id != request.requester_id and actor.role != "admin":
        raise ApprovalError(403, "Chỉ người tạo (hoặc admin) mới được hủy đơn")

    request.status = "cancelled"
    request.resolved_at = datetime.now(timezone.utc)
    await db.flush()

    reject_effect = _REJECT_EFFECTS.get(request.type)
    if reject_effect:
        await reject_effect(db, request)

    await log_action(db, actor=actor, action="approval.cancel", entity_type="approval", entity_id=request.id)
    return request


async def escalate_overdue(db: AsyncSession) -> int:
    """Đơn pending quá hạn: lần 1 nhắc approver; quá 2×SLA → chuyển admin.

    Chạy trong automation hằng ngày (07:00 VN).
    """
    now = datetime.now(timezone.utc)
    # Lọc quá hạn ngay trong SQL — không quét toàn bộ pending rồi lọc Python (spec 05 Track B)
    result = await db.execute(
        select(ApprovalRequest).where(
            ApprovalRequest.status == "pending",
            ApprovalRequest.due_at.is_not(None),
            ApprovalRequest.due_at < now,
        )
    )
    escalated = 0
    for request in result.scalars().all():
        due = request.due_at
        if due and due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)

        label = TYPE_LABELS.get(request.type, request.type)
        overdue_hours = (now - due).total_seconds() / 3600

        if request.escalated == 0 or overdue_hours < 24:
            # Nhắc approver hiện tại
            approver = await db.get(User, request.current_approver_id) if request.current_approver_id else None
            await _notify_user(
                db, approver,
                title=f"⏰ Quá hạn duyệt: {label} — {request.title}",
                body=f"Đơn đã chờ quá SLA. Vui lòng xử lý.",
                link="/approvals",
                ref_id=f"{request.id}-overdue-{request.escalated}",
            )
            request.escalated += 1
            escalated += 1

        if overdue_hours >= 24 and request.escalated >= 1:
            # Quá 24h sau hạn → chuyển admin (nếu approver hiện tại chưa phải admin)
            admin_result = await db.execute(
                select(User).where(User.role == "admin", User.is_active == True).limit(1)  # noqa: E712
            )
            admin = admin_result.scalar_one_or_none()
            if admin and request.current_approver_id != admin.id and request.requester_id != admin.id:
                request.current_approver_id = admin.id
                request.escalated += 1
                await _notify_user(
                    db, admin,
                    title=f"🚨 Escalate: {label} — {request.title}",
                    body="Đơn quá hạn không được xử lý — chuyển lên admin.",
                    link="/approvals",
                    ref_id=f"{request.id}-escalated",
                )
                await log_action(
                    db, actor=None, action="approval.escalate", entity_type="approval",
                    entity_id=request.id, after={"to": admin.id},
                )
                escalated += 1
    await db.flush()
    return escalated


async def reassign_orphaned(db: AsyncSession) -> int:
    """Đơn có approver đã nghỉ việc → chuyển admin (job đêm)."""
    result = await db.execute(
        select(ApprovalRequest).where(ApprovalRequest.status == "pending")
    )
    moved = 0
    admin_result = await db.execute(
        select(User).where(User.role == "admin", User.is_active == True).limit(1)  # noqa: E712
    )
    admin = admin_result.scalar_one_or_none()
    if not admin:
        return 0
    for request in result.scalars().all():
        if not request.current_approver_id:
            request.current_approver_id = admin.id
            moved += 1
            continue
        approver = await db.get(User, request.current_approver_id)
        if approver and not approver.is_active and request.requester_id != admin.id:
            request.current_approver_id = admin.id
            moved += 1
            await log_action(
                db, actor=None, action="approval.reassign_orphan", entity_type="approval",
                entity_id=request.id, after={"to": admin.id},
            )
    await db.flush()
    return moved
