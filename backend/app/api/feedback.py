"""Feedback API — employee feedback from Telegram & web."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.feedback import Feedback

router = APIRouter(prefix="/feedback", tags=["feedback"])


class TelegramFeedbackCreate(BaseModel):
    telegram_user_id: int
    category: str = Field(..., pattern=r"^(bug|feature_request|workflow_improvement|other)$")
    content: str = Field(..., min_length=5, max_length=5000)


class FeedbackReply(BaseModel):
    status: str | None = Field(default=None, pattern=r"^(new|in_review|done|rejected)$")
    admin_reply: str | None = Field(default=None, max_length=5000)


# ── Telegram bot endpoint (no JWT — uses shared secret) ─────────────────

@router.post("/telegram", status_code=201)
async def create_feedback_from_telegram(
    data: TelegramFeedbackCreate,
    db: AsyncSession = Depends(get_db),
):
    """Submit feedback from Telegram bot."""
    user_result = await db.execute(
        select(User).where(User.telegram_user_id == data.telegram_user_id)
    )
    user = user_result.scalar_one_or_none()

    feedback = Feedback(
        user_id=user.id if user else None,
        telegram_user_id=data.telegram_user_id,
        category=data.category,
        content=data.content,
        status="new",
    )
    db.add(feedback)
    await db.flush()

    return {
        "id": feedback.id,
        "category": feedback.category,
        "status": feedback.status,
        "user_name": user.full_name if user else "Unknown",
        "created_at": feedback.created_at.isoformat(),
        "message": "Feedback đã được gửi thành công.",
    }


# ── Admin: list all feedback ────────────────────────────────────────────

@router.get("")
async def list_all_feedback(
    status: str | None = Query(None),
    category: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("admin", "executive"):
        raise HTTPException(status_code=403, detail="Chỉ admin/executive xem feedback")

    q = (
        select(Feedback, User.full_name.label("user_name"))
        .outerjoin(User, Feedback.user_id == User.id)
    )
    if status:
        q = q.where(Feedback.status == status)
    if category:
        q = q.where(Feedback.category == category)

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    q = q.order_by(Feedback.created_at.desc())
    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)

    items = []
    for fb, user_name in result.all():
        items.append({
            "id": fb.id, "user_id": fb.user_id, "user_name": user_name,
            "telegram_user_id": fb.telegram_user_id,
            "category": fb.category, "content": fb.content, "status": fb.status,
            "admin_reply": fb.admin_reply,
            "created_at": fb.created_at.isoformat(), "updated_at": fb.updated_at.isoformat(),
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size}


# ── User: list own feedback ─────────────────────────────────────────────

@router.get("/my")
async def list_my_feedback(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(Feedback).where(
        (Feedback.user_id == current_user.id)
        | (Feedback.telegram_user_id == current_user.telegram_user_id)
    )
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    q = q.order_by(Feedback.created_at.desc())
    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)

    items = []
    for fb in result.scalars().all():
        items.append({
            "id": fb.id, "category": fb.category, "content": fb.content,
            "status": fb.status, "admin_reply": fb.admin_reply,
            "created_at": fb.created_at.isoformat(),
        })

    return {"items": items, "total": total, "page": page}


# ── Admin: update status / reply ────────────────────────────────────────

@router.put("/{feedback_id}")
async def update_feedback(
    feedback_id: str,
    data: FeedbackReply,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("admin", "executive"):
        raise HTTPException(status_code=403, detail="Chỉ admin/executive quản lý feedback")

    result = await db.execute(select(Feedback).where(Feedback.id == feedback_id))
    fb = result.scalar_one_or_none()
    if not fb:
        raise HTTPException(status_code=404, detail="Feedback không tồn tại")

    if data.status:
        fb.status = data.status
    if data.admin_reply is not None:
        fb.admin_reply = data.admin_reply
    fb.updated_at = datetime.now(timezone.utc)
    await db.flush()

    # Push reply to Telegram if applicable
    if data.admin_reply and fb.telegram_user_id:
        from app.services.telegram_notify import send_telegram
        status_label = {"in_review": "Đang xem xét", "done": "Đã xử lý", "rejected": "Từ chối"}.get(fb.status, fb.status)
        msg = (
            f"📝 <b>Feedback cập nhật</b>\n"
            f"Trạng thái: <b>{status_label}</b>\n"
            f"Phản hồi: {data.admin_reply}"
        )
        await send_telegram(fb.telegram_user_id, msg)

    return {
        "id": fb.id, "status": fb.status, "admin_reply": fb.admin_reply,
        "updated_at": fb.updated_at.isoformat(),
    }
