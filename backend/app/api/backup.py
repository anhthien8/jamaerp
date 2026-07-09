"""Backup API — admin bật/tắt sao lưu 5h sáng, retention ≤180 ngày, Google Drive OAuth."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.services.backup_service import (
    MAX_RETENTION_DAYS,
    build_gdrive_auth_url,
    get_backup_settings,
    get_setting,
    handle_gdrive_callback,
    list_local_backups,
    run_backup,
    set_setting,
)

router = APIRouter(prefix="/backup", tags=["backup"])
settings = get_settings()


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return current_user


class BackupSettingsUpdate(BaseModel):
    backup_enabled: bool | None = None
    backup_hour: int | None = None
    backup_retention_days: int | None = None
    backup_gdrive_enabled: bool | None = None
    gdrive_client_id: str | None = None
    gdrive_client_secret: str | None = None


async def _settings_response(db: AsyncSession) -> dict:
    cfg = await get_backup_settings(db)
    last_status_raw = await get_setting(db, "backup_last_status")
    try:
        last_status = json.loads(last_status_raw) if last_status_raw else None
    except json.JSONDecodeError:
        last_status = None

    backups = list_local_backups()
    return {
        **cfg,
        "max_retention_days": MAX_RETENTION_DAYS,
        "gdrive_connected": bool(await get_setting(db, "gdrive_refresh_token")),
        "gdrive_account_email": await get_setting(db, "gdrive_account_email"),
        "gdrive_client_id_set": bool(await get_setting(db, "gdrive_client_id")),
        "last_run": await get_setting(db, "backup_last_run"),
        "last_status": last_status,
        "local_backup_count": len(backups),
        "local_backups": backups[:10],  # 10 bản gần nhất
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
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No settings provided")

    for key, value in updates.items():
        if isinstance(value, bool):
            str_value = "true" if value else "false"
        elif key == "backup_hour":
            if not (0 <= int(value) <= 23):
                raise HTTPException(status_code=400, detail="backup_hour must be 0-23")
            str_value = str(value)
        elif key == "backup_retention_days":
            if not (1 <= int(value) <= MAX_RETENTION_DAYS):
                raise HTTPException(
                    status_code=400,
                    detail=f"backup_retention_days must be 1-{MAX_RETENTION_DAYS}",
                )
            str_value = str(value)
        else:  # gdrive_client_id / gdrive_client_secret
            str_value = str(value).strip()
        await set_setting(db, key, str_value)

    await db.commit()
    return await _settings_response(db)


@router.post("/run")
async def trigger_backup(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    """Sao lưu ngay (test hoặc trước khi update hệ thống)."""
    return await run_backup(db)


# ---------------------------------------------------------------------------
# Google Drive OAuth flow
# ---------------------------------------------------------------------------

@router.get("/gdrive/auth-url")
async def gdrive_auth_url(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    try:
        url = await build_gdrive_auth_url(db)
        await db.commit()
        return {"auth_url": url}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/gdrive/callback")
async def gdrive_callback(
    code: str = Query(""),
    state: str = Query(""),
    error: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    """Google redirect về đây sau khi admin đồng ý — không yêu cầu JWT,
    bảo vệ bằng state token 1 lần."""
    frontend = settings.FRONTEND_URL.rstrip("/")
    if error or not code:
        return RedirectResponse(f"{frontend}/settings?gdrive=error")
    try:
        await handle_gdrive_callback(db, code, state)
        await db.commit()
        return RedirectResponse(f"{frontend}/settings?gdrive=connected")
    except ValueError:
        await db.rollback()
        return RedirectResponse(f"{frontend}/settings?gdrive=error")


@router.post("/gdrive/disconnect")
async def gdrive_disconnect(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    for key in ("gdrive_refresh_token", "gdrive_folder_id", "gdrive_account_email"):
        await set_setting(db, key, "")
    await set_setting(db, "backup_gdrive_enabled", "false")
    await db.commit()
    return {"status": "disconnected"}
