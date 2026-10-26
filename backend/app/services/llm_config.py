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

import json
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
    "llm_fallbacks",  # JSON [{model, api_key}] — chuỗi nhiều dự phòng (26/10/2026)
)

MAX_FALLBACKS = 5

# Gợi ý model free (hiển thị trong UI)
FREE_MODEL_PRESETS = [
    {"label": "Groq — GPT-OSS 120B (free tier)", "model": "groq/openai/gpt-oss-120b"},
    {"label": "Groq — GPT-OSS 20B (free, nhanh)", "model": "groq/openai/gpt-oss-20b"},
    {"label": "OpenCode — DeepSeek V4.1 Flash (free có thời hạn)", "model": "opencode/deepseek-v4.1-flash-free"},
    {"label": "OpenCode — DeepSeek V4.1 Flash (trả phí, rẻ)", "model": "opencode/deepseek-v4.1-flash"},
    {"label": "OpenCode — DeepSeek V4 Pro (trả phí)", "model": "opencode/deepseek-v4-pro"},
    {"label": "Google Gemini 2.0 Flash (free tier)", "model": "gemini/gemini-2.0-flash"},
    {"label": "OpenRouter — Llama 3.3 70B (free)", "model": "openrouter/meta-llama/llama-3.3-70b-instruct:free"},
    {"label": "Ollama — Llama 3.2 (local, không cần key)", "model": "ollama/llama3.2"},
]

# Groq đã tắt các model này (07–08/2026) — cấu hình cũ trong DB/env tự đổi sang model thay thế Groq khuyên dùng
MODEL_DA_TAT = {
    "groq/llama-3.1-8b-instant": "groq/openai/gpt-oss-20b",
    "groq/llama-3.3-70b-versatile": "groq/openai/gpt-oss-120b",
    "groq/meta-llama/llama-4-scout-17b-16e-instruct": "groq/qwen/qwen3.8-27b",
    "groq/qwen/qwen3-32b": "groq/openai/gpt-oss-120b",
    "groq/qwen/qwen3.6-27b": "groq/qwen/qwen3.8-27b",
}

# OpenCode Zen: API kiểu OpenAI — "opencode/<id>" → litellm "openai/<id>" + api_base
OPENCODE_API_BASE = "https://opencode.ai/inference/openai/v1"


def chuan_model(model: str) -> str:
    return MODEL_DA_TAT.get((model or "").strip(), (model or "").strip())


def tham_so_model(model: str) -> dict[str, str]:
    """Tham số litellm cho một model đã cấu hình (đổi model đã tắt, nối OpenCode)."""
    model = chuan_model(model)
    if model.startswith("opencode/"):
        return {"model": "openai/" + model.removeprefix("opencode/"), "api_base": OPENCODE_API_BASE}
    return {"model": model}


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
        "llm_fallbacks": "",
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

    for k in ("llm_model", "llm_fallback_model"):
        config[k] = chuan_model(config.get(k, ""))
    _cache = config
    _cache_at = time.time()
    return config


def nha_cung_cap(model: str) -> str:
    return (model or "").split("/")[0]


def ds_du_phong(config: dict) -> list[dict[str, str]]:
    """Chuỗi model dự phòng theo thứ tự. Cấu hình cũ (1 model) vẫn đọc được."""
    try:
        ds = json.loads(config.get("llm_fallbacks") or "[]")
    except ValueError:
        ds = []
    kq = [
        {"model": chuan_model(str(x.get("model") or "")), "api_key": str(x.get("api_key") or "")}
        for x in ds if isinstance(x, dict) and x.get("model")
    ]
    if not kq and config.get("llm_fallback_model"):
        kq = [{"model": config["llm_fallback_model"], "api_key": config.get("llm_fallback_api_key") or ""}]
    return kq[:MAX_FALLBACKS]


def _needs_no_key(model: str) -> bool:
    """Local models (ollama) don't need an API key."""
    return model.startswith("ollama")


def _khoa_hop(model: str, key: str) -> bool:
    """Chặn rõ ràng nhất: khoá Groq (gsk_) chỉ đi với model groq/ và ngược lại."""
    return key.startswith("gsk_") == model.startswith("groq/")


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
        if system_key and not _khoa_hop(primary_model, system_key):
            logger.warning("Khoá chính không hợp model %s (khác nhà cung cấp) — bỏ qua", primary_model)
        elif system_key or _needs_no_key(primary_model):
            attempts.append((primary_model, system_key))

    du_phong = ds_du_phong(config)
    # Khoá đã nhập theo nhà cung cấp — dự phòng bỏ trống khoá thì mượn khoá CÙNG nhà cung cấp,
    # không bao giờ gửi khoá Groq sang OpenCode và ngược lại
    khoa_ncc: dict[str, str] = {}
    for m, k in [(primary_model, system_key)] + [(x["model"], x["api_key"]) for x in du_phong]:
        if k and _khoa_hop(m, k):
            khoa_ncc.setdefault(nha_cung_cap(m), k)
    for x in du_phong:
        fb_key = x["api_key"] if x["api_key"] and _khoa_hop(x["model"], x["api_key"]) else ""
        fb_key = fb_key or khoa_ncc.get(nha_cung_cap(x["model"]), "")
        if (fb_key or _needs_no_key(x["model"])) and (x["model"], fb_key) not in attempts:
            attempts.append((x["model"], fb_key))

    if not attempts:
        raise RuntimeError("No LLM model configured (missing API key)")

    last_error: Exception | None = None
    for model, api_key in attempts:
        try:
            params: dict[str, Any] = {
                **tham_so_model(model),
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
