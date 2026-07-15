"""Audit service — ghi log thao tác nhạy cảm.

Dùng: await log_action(db, actor=current_user, action="payroll.approve",
                        entity_type="payroll", entity_id=p.id,
                        before={"status": "pending_approval"}, after={"status": "approved"})

Nguyên tắc: log là best-effort gắn cùng transaction của thao tác chính —
nếu thao tác rollback thì log cũng rollback (không log "ma").
"""

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.user import User


def _dump(data: Any) -> str | None:
    if data is None:
        return None
    try:
        return json.dumps(data, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(data)


async def log_action(
    db: AsyncSession,
    *,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    before: Any = None,
    after: Any = None,
    note: str | None = None,
) -> AuditLog:
    """Ghi một dòng audit log (flush, không commit — theo transaction hiện tại)."""
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        actor_name=actor.full_name if actor else "system",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_json=_dump(before),
        after_json=_dump(after),
        note=note,
    )
    db.add(entry)
    await db.flush()
    return entry


async def query_logs(
    db: AsyncSession,
    *,
    entity_type: str | None = None,
    entity_id: str | None = None,
    actor_id: str | None = None,
    action: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> list[AuditLog]:
    q = select(AuditLog).order_by(AuditLog.created_at.desc())
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)
    if entity_id:
        q = q.where(AuditLog.entity_id == entity_id)
    if actor_id:
        q = q.where(AuditLog.actor_id == actor_id)
    if action:
        q = q.where(AuditLog.action == action)
    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    return list(result.scalars().all())
