"""Audit API — admin tra cứu lịch sử thao tác nhạy cảm."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.services.audit import query_logs

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("")
async def list_audit_logs(
    entity_type: str | None = None,
    entity_id: str | None = None,
    actor_id: str | None = None,
    action: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Danh sách audit log (chỉ admin)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới được xem audit log")

    logs = await query_logs(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        action=action,
        page=page,
        page_size=page_size,
    )
    return {
        "items": [
            {
                "id": l.id,
                "actor_id": l.actor_id,
                "actor_name": l.actor_name,
                "action": l.action,
                "entity_type": l.entity_type,
                "entity_id": l.entity_id,
                "before": l.before_json,
                "after": l.after_json,
                "note": l.note,
                "created_at": str(l.created_at),
            }
            for l in logs
        ],
        "page": page,
        "page_size": page_size,
    }
