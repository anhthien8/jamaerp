"""Automation API — settings + manual triggers (admin/executive only)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.notification import DEFAULT_AUTOMATION_SETTINGS
from app.services.automation import (
    get_automation_settings,
    set_automation_setting,
    run_followup_reminders,
    run_lead_recall,
    run_payment_reminders,
    run_all_automation,
)
from app.services.bod_report import send_bod_report, build_bod_report, send_group_briefing

router = APIRouter(prefix="/automation", tags=["automation"])

_ADMIN_ROLES = ("admin", "executive")


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin or executive role required")
    return current_user


class SettingsUpdate(BaseModel):
    followup_reminder_days: int | None = None
    lead_recall_days: int | None = None
    lead_recall_enabled: bool | None = None
    payment_reminder_days: int | None = None
    bod_report_enabled: bool | None = None
    bod_report_hour: int | None = None
    telegram_group_chat_id: str | None = None
    group_briefing_enabled: bool | None = None


@router.get("/settings")
async def read_settings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    return await get_automation_settings(db)


@router.put("/settings")
async def update_settings(
    payload: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No settings provided")

    for key, value in updates.items():
        if key not in DEFAULT_AUTOMATION_SETTINGS:
            raise HTTPException(status_code=400, detail=f"Unknown setting: {key}")
        if isinstance(value, bool):
            str_value = "true" if value else "false"
        elif key == "telegram_group_chat_id":
            str_value = str(value).strip()
            if str_value and not str_value.lstrip("-").isdigit():
                raise HTTPException(
                    status_code=400,
                    detail="telegram_group_chat_id must be a number (e.g. -100123456789)",
                )
        else:
            if key.endswith("_days") and not (1 <= int(value) <= 90):
                raise HTTPException(status_code=400, detail=f"{key} must be 1-90")
            if key == "bod_report_hour" and not (0 <= int(value) <= 23):
                raise HTTPException(status_code=400, detail="bod_report_hour must be 0-23")
            str_value = str(value)
        await set_automation_setting(db, key, str_value)

    await db.commit()
    return await get_automation_settings(db)


# ---------------------------------------------------------------------------
# Manual triggers (testing / on-demand)
# ---------------------------------------------------------------------------

@router.post("/run/followups")
async def trigger_followups(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    result = await run_followup_reminders(db)
    await db.commit()
    return result


@router.post("/run/recall")
async def trigger_recall(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    result = await run_lead_recall(db)
    await db.commit()
    return result


@router.post("/run/payments")
async def trigger_payments(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    result = await run_payment_reminders(db)
    await db.commit()
    return result


@router.post("/run/all")
async def trigger_all(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    return await run_all_automation(db)


@router.post("/run/bod-report/{period}")
async def trigger_bod_report(
    period: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    if period not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="period must be daily|weekly|monthly")
    return await send_bod_report(db, period)


@router.post("/run/group-briefing")
async def trigger_group_briefing(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    """Gửi thử briefing vào nhóm Telegram công ty (kiểm tra sau khi cài đặt)."""
    return await send_group_briefing(db)


@router.get("/bod-report/{period}/preview")
async def preview_bod_report(
    period: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    if period not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="period must be daily|weekly|monthly")
    return await build_bod_report(db, period)
