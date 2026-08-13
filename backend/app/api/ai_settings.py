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
from app.services.llm_user_key import current_user_llm_key

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


# ---------------------------------------------------------------------------
# Khóa AI CÁ NHÂN (13/08/2026) — mọi vai trò đăng nhập đều quản lý key của mình.
# Có key riêng thì AI ưu tiên dùng trước key hệ thống (xem llm_config).
# Không bao giờ trả key đầy đủ — chỉ dạng che.
# ---------------------------------------------------------------------------


class MyLlmKeyUpdate(BaseModel):
    api_key: str = ""  # rỗng = xóa key


def _my_key_response(user: User) -> dict:
    return {
        "set": bool(user.llm_api_key),
        "masked": _mask(user.llm_api_key or ""),
    }


@router.get("/my-key")
async def read_my_llm_key(current_user: User = Depends(get_current_user)):
    return _my_key_response(current_user)


@router.put("/my-key")
async def update_my_llm_key(
    payload: MyLlmKeyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    key = payload.api_key.strip()
    # Chỉ nhận key Groq — llm_complete cũng chỉ dùng key cá nhân với model groq/,
    # tránh gửi nhầm key sang provider khác.
    if key and not key.startswith("gsk_"):
        raise HTTPException(
            status_code=400, detail="Chỉ nhận khóa Groq (bắt đầu bằng gsk_)"
        )
    if key and len(key) < 12:
        raise HTTPException(status_code=400, detail="Khóa API không hợp lệ (quá ngắn)")
    current_user.llm_api_key = key or None
    await db.commit()
    return _my_key_response(current_user)


@router.post("/my-key/test")
async def test_my_llm_key(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Kiểm tra ĐÚNG key cá nhân (không rơi về key hệ thống như llm_complete)."""
    if not current_user.llm_api_key:
        raise HTTPException(status_code=400, detail="Bạn chưa lưu khóa API cá nhân")
    config = await get_llm_config(db)
    model = config.get("llm_model", "")
    if not model.startswith("groq/"):
        # Key cá nhân là key Groq — model hệ thống đang không phải Groq thì
        # test bằng model Groq nhanh, không gửi key sang provider khác.
        model = "groq/llama-3.1-8b-instant"
    try:
        from litellm import acompletion

        response = await acompletion(
            model=model,
            messages=[
                {"role": "system", "content": "Bạn là trợ lý JAMA HOME. Trả lời đúng 1 câu ngắn."},
                {"role": "user", "content": "Khóa cá nhân của tôi hoạt động chứ?"},
            ],
            temperature=0.1,
            max_tokens=50,
            api_key=current_user.llm_api_key,
        )
        return {"status": "ok", "model": getattr(response, "model", model),
                "reply": response.choices[0].message.content}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)[:300]}


@router.post("/test")
async def test_ai_connection(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    """Gửi 1 câu test đến LLM để kiểm tra model + key HỆ THỐNG hoạt động.

    Bỏ key cá nhân của admin khỏi request này: công cụ chẩn đoán phải chạy
    đúng key chung mà nhân viên không có key riêng (và worker nền) đang dùng —
    không thì key chung chết mà nút test vẫn báo "ok" bằng key riêng của admin.
    """
    invalidate_llm_cache()
    khoa_ca_nhan = current_user_llm_key.set("")
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
    finally:
        current_user_llm_key.reset(khoa_ca_nhan)
