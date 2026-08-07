"""Backup API — admin bật/tắt sao lưu tự động, retention ≤180 ngày, gửi qua Telegram."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.services.backup_service import (
    MAX_RETENTION_DAYS,
    get_backup_settings,
    get_setting,
    has_telegram_token,
    run_backup,
    set_setting,
)

router = APIRouter(prefix="/backup", tags=["backup"])
logger = logging.getLogger(__name__)


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return current_user


class BackupSettingsUpdate(BaseModel):
    enabled: bool | None = None
    hour: int | None = None
    retention_days: int | None = None
    telegram_chat_id: str | None = None  # "" để gỡ nhóm nhận backup


async def _settings_response(db: AsyncSession) -> dict:
    """Trả về cấu hình sao lưu theo hợp đồng API (kiểu dữ liệu đã chuẩn hóa)."""
    cfg = await get_backup_settings(db)
    chat_id = cfg.get("backup_telegram_chat_id", "")

    last_status = await get_setting(db, "backup_last_status") or "never"
    last_run_at = await get_setting(db, "backup_last_run_at") or None
    last_detail = await get_setting(db, "backup_last_detail")

    last_size_raw = await get_setting(db, "backup_last_size_mb")
    try:
        last_size_mb: float | None = float(last_size_raw) if last_size_raw else None
    except ValueError:
        last_size_mb = None

    return {
        "enabled": cfg["backup_enabled"] == "true",
        "hour": int(cfg["backup_hour"]),
        "retention_days": int(cfg["backup_retention_days"]),
        "telegram_chat_id": chat_id,
        "telegram_configured": bool(chat_id) and has_telegram_token(),
        "last_run_at": last_run_at,
        "last_status": last_status,
        "last_detail": last_detail,
        "last_size_mb": last_size_mb,
    }


@router.get("/settings")
async def read_backup_settings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    return await _settings_response(db)


@router.put("/settings")
async def update_backup_settings(
    payload: BackupSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Không có thay đổi nào được gửi lên")

    if updates.get("enabled") is not None:
        await set_setting(db, "backup_enabled", "true" if updates["enabled"] else "false")

    if updates.get("hour") is not None:
        hour = int(updates["hour"])
        if not (0 <= hour <= 23):
            raise HTTPException(status_code=400, detail="Giờ chạy phải trong khoảng 0-23")
        await set_setting(db, "backup_hour", str(hour))

    if updates.get("retention_days") is not None:
        days = int(updates["retention_days"])
        if not (1 <= days <= MAX_RETENTION_DAYS):
            raise HTTPException(
                status_code=400,
                detail=f"Số ngày giữ bản sao phải trong khoảng 1-{MAX_RETENTION_DAYS}",
            )
        await set_setting(db, "backup_retention_days", str(days))

    if updates.get("telegram_chat_id") is not None:
        await set_setting(db, "backup_telegram_chat_id", str(updates["telegram_chat_id"]).strip())

    await db.commit()
    return await _settings_response(db)


@router.post("/run")
async def trigger_backup(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_admin),
):
    """Sao lưu ngay (chạy tay) — trả kết quả THẬT theo hợp đồng API."""
    result = await run_backup(db)

    # Ghi audit log cho lần chạy tay (best-effort, không chặn kết quả)
    try:
        from app.services.audit import log_action

        await log_action(
            db,
            actor=current_user,
            action="backup_run",
            entity_type="backup",
            entity_id=result.get("file_name"),
            after=result,
        )
        await db.commit()
    except Exception as exc:  # audit hỏng không được làm hỏng backup
        logger.warning("Không ghi được audit log backup_run: %s", exc)

    return result
