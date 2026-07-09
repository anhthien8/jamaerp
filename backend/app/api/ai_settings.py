"""AI Settings API — admin cấu hình LLM model (free) + fallback cho toàn hệ thống.

Áp dụng cho tất cả AI agents và Telegram bot (bot gọi AI qua backend API),
mọi role đều hưởng cấu hình này. Chỉ admin được thay đổi.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.services.automation import set_automation_setting
from app.services.llm_config import (
    FREE_MODEL_PRESETS,
    LLM_SETTING_KEYS,
    get_llm_config,
    invalidate_llm_cache,
    llm_complete,
)

router = APIRouter(prefix="/ai-settings", tags=["ai-settings"])


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return current_user


def _mask(key: str) -> str:
    """Mask API key for display: 'gsk_abc...xyz' → 'gsk_****xyz'."""
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}****{key[-4:]}"


class AISettingsUpdate(BaseModel):
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_fallback_model: str | None = None
    llm_fallback_api_key: str | None = None


async def _settings_response(db: AsyncSession) -> dict:
    config = await get_llm_config(db)
    return {
        "llm_model": config.get("llm_model", ""),
        "llm_api_key_masked": _mask(config.get("llm_api_key", "")),
        "llm_api_key_set": bool(config.get("llm_api_key")),
        "llm_fallback_model": config.get("llm_fallback_model", ""),
        "llm_fallback_api_key_masked": _mask(config.get("llm_fallback_api_key", "")),
        "llm_fallback_api_key_set": bool(config.get("llm_fallback_api_key")),
        "presets": FREE_MODEL_PRESETS,
    }


@router.get("")
async def read_ai_settings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    return await _settings_response(db)


@router.put("")
async def update_ai_settings(
    payload: AISettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No settings provided")

    for key, value in updates.items():
        if key not in LLM_SETTING_KEYS:
            raise HTTPException(status_code=400, detail=f"Unknown setting: {key}")
        await set_automation_setting(db, key, str(value).strip())

    await db.commit()
    invalidate_llm_cache()
    return await _settings_response(db)


@router.post("/test")
async def test_ai_connection(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    """Gửi 1 câu test đến LLM để kiểm tra model + key hoạt động."""
    invalidate_llm_cache()
    try:
        response = await llm_complete(
            messages=[
                {"role": "system", "content": "Bạn là trợ lý JAMA HOME. Trả lời đúng 1 câu ngắn."},
                {"role": "user", "content": "Chào bạn, hệ thống hoạt động chứ?"},
            ],
            temperature=0.1,
            max_tokens=50,
        )
        reply = response.choices[0].message.content
        model_used = getattr(response, "model", "unknown")
        return {"status": "ok", "model": model_used, "reply": reply}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)[:300]}
