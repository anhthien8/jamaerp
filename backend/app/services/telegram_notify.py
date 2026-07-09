"""Push messages from backend → Telegram users (via Bot API).

No-op when TELEGRAM_BOT_TOKEN is empty, so local dev works without a bot.
"""

import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


async def send_telegram(chat_id: int, text: str, parse_mode: str = "HTML") -> bool:
    """Send a Telegram message. Returns True on success, False otherwise."""
    settings = get_settings()
    token = settings.TELEGRAM_BOT_TOKEN
    if not token or not chat_id:
        logger.debug("Telegram notify skipped (no token or chat_id)")
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _TELEGRAM_API.format(token=token),
                json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
            )
            if resp.status_code == 200:
                return True
            logger.warning("Telegram notify failed (%s): %s", resp.status_code, resp.text[:200])
            return False
    except Exception as exc:
        logger.warning("Telegram notify error: %s", exc)
        return False
