"""Central LLM configuration + completion helper.

Admin có thể cấu hình model chính (free) + model fallback qua UI Settings,
lưu vào bảng system_settings — áp dụng ngay cho toàn bộ AI agents và
Telegram bot (bot gọi qua backend API) mà không cần restart.

Thứ tự ưu tiên cấu hình hệ thống: DB SystemSetting > biến môi trường (.env) > default.
Thứ tự ưu tiên API key khi gọi (13/08/2026): key CÁ NHÂN của user đang request
(users.llm_api_key, auth set vào contextvar) > key hệ thống. Key cá nhân lỗi
(sai/hết quota) thì tự rơi về key hệ thống — user không bị kẹt. Key cá nhân là
key Groq nên CHỈ dùng khi model là groq/ — không gửi sang provider khác.
Fallback flow: model chính lỗi → thử model fallback → raise để agent
dùng rule-based fallback của riêng nó.
"""

import logging
import time
from typing import Any

from litellm import acompletion
from sqlalchemy import select

from app.config import get_settings
from app.services.llm_user_key import current_user_llm_key

logger = logging.getLogger(__name__)

settings = get_settings()

# Keys lưu trong system_settings
LLM_SETTING_KEYS = (
    "llm_model",
    "llm_api_key",
    "llm_fallback_model",
    "llm_fallback_api_key",
)

# Gợi ý model free (hiển thị trong UI)
FREE_MODEL_PRESETS = [
    {"label": "Groq — Llama 3.3 70B (free tier)", "model": "groq/llama-3.3-70b-versatile"},
    {"label": "Groq — Llama 3.1 8B (free, nhanh)", "model": "groq/llama-3.1-8b-instant"},
    {"label": "Google Gemini 2.0 Flash (free tier)", "model": "gemini/gemini-2.0-flash"},
    {"label": "OpenRouter — Llama 3.3 70B (free)", "model": "openrouter/meta-llama/llama-3.3-70b-instruct:free"},
    {"label": "Ollama — Llama 3.2 (local, không cần key)", "model": "ollama/llama3.2"},
]

# ---------------------------------------------------------------------------
# Config cache (tránh query DB mỗi lần gọi LLM)
# ---------------------------------------------------------------------------

_CACHE_TTL = 60.0  # seconds
_cache: dict[str, str] = {}
_cache_at: float = 0.0


def invalidate_llm_cache() -> None:
    global _cache_at
    _cache_at = 0.0


def _env_defaults() -> dict[str, str]:
    return {
        "llm_model": settings.LLM_MODEL,
        "llm_api_key": settings.LLM_API_KEY,
        "llm_fallback_model": settings.LLM_FALLBACK_MODEL,
        "llm_fallback_api_key": "",
    }


async def get_llm_config(db=None) -> dict[str, str]:
    """Return merged LLM config. Pass a session to bypass cache freshness."""
    global _cache, _cache_at

    if db is None and _cache and (time.time() - _cache_at) < _CACHE_TTL:
        return _cache

    config = _env_defaults()
    try:
        from app.models.notification import SystemSetting

        if db is not None:
            result = await db.execute(
                select(SystemSetting).where(SystemSetting.key.in_(LLM_SETTING_KEYS))
            )
            rows = result.scalars().all()
        else:
            from app.database import async_session

            async with async_session() as session:
                result = await session.execute(
                    select(SystemSetting).where(SystemSetting.key.in_(LLM_SETTING_KEYS))
                )
                rows = result.scalars().all()

        for row in rows:
            if row.value:  # empty string → keep env default
                config[row.key] = row.value
    except Exception as exc:
        logger.warning("Could not load LLM settings from DB, using env: %s", exc)

    _cache = config
    _cache_at = time.time()
    return config


def _needs_no_key(model: str) -> bool:
    """Local models (ollama) don't need an API key."""
    return model.startswith("ollama")


def _user_key_applies(model: str) -> bool:
    """Key cá nhân là key GROQ (UI chỉ nhận gsk_) — tuyệt đối không gửi nó
    sang provider khác (Gemini/OpenRouter...) khi admin đổi model hệ thống;
    gửi nhầm là lộ key cho bên thứ ba ngay cả khi họ trả 401."""
    return model.startswith("groq/")


async def llm_available() -> bool:
    """True when a usable model is configured (has key or is local)."""
    config = await get_llm_config()
    model = config.get("llm_model", "")
    if not model:
        return False
    return (
        bool(config.get("llm_api_key"))
        or (bool(current_user_llm_key.get()) and _user_key_applies(model))
        or _needs_no_key(model)
    )


async def llm_complete(
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 800,
    response_format: dict | None = None,
    **kwargs: Any,
):
    """Central completion call: primary model → fallback model → raise.

    Agents should catch the exception and use their own rule-based fallback.
    """
    config = await get_llm_config()

    attempts: list[tuple[str, str]] = []
    primary_model = config.get("llm_model", "")
    system_key = config.get("llm_api_key", "")
    user_key = current_user_llm_key.get()
    if primary_model:
        # Key cá nhân của user đang request đứng TRƯỚC key hệ thống —
        # trùng nhau thì khỏi thử hai lần, model không phải Groq thì không dùng
        if user_key and user_key != system_key and _user_key_applies(primary_model):
            attempts.append((primary_model, user_key))
        if system_key or _needs_no_key(primary_model):
            attempts.append((primary_model, system_key))

    fallback_model = config.get("llm_fallback_model", "")
    if fallback_model and fallback_model != primary_model:
        fb_key = config.get("llm_fallback_api_key") or config.get("llm_api_key", "")
        if fb_key or _needs_no_key(fallback_model):
            attempts.append((fallback_model, fb_key))

    if not attempts:
        raise RuntimeError("No LLM model configured (missing API key)")

    last_error: Exception | None = None
    for model, api_key in attempts:
        try:
            params: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                **kwargs,
            }
            if api_key:
                params["api_key"] = api_key
            if response_format:
                params["response_format"] = response_format
            return await acompletion(**params)
        except Exception as exc:
            logger.warning("LLM call failed on %s: %s — trying next", model, exc)
            last_error = exc

    raise last_error  # type: ignore[misc]
