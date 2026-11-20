"""Push messages from backend → Telegram users (via Bot API).

No-op when TELEGRAM_BOT_TOKEN is empty, so local dev works without a bot.

13/11/2026:
- Nhóm được nâng lên supergroup → Telegram trả `migrate_to_chat_id`: gửi lại vào ID mới
  và tự thay ID cũ trong mọi cấu hình (nhóm công ty, Kho ảnh, sao lưu…), khỏi rớt tin âm thầm.
- Người chưa bấm Start / đã chặn bot / ID sai: ghi vào SystemSetting `telegram_gui_loi`
  để Admin xem ở «Tài khoản» ai đang không nhận được tin. Gửi được lại thì tự xoá.
"""

import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from app.config import get_settings

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
KHOA_LOI_GUI = "telegram_gui_loi"
# Bản nhớ các chat_id đang có dấu lỗi — gửi thành công khỏi phải mở DB mỗi tin (None = chưa nạp)
_loi_cache: set[str] | None = None


def ly_do_loi(desc: str) -> str | None:
    """Lỗi do phía người nhận (cần họ làm gì đó) → nhãn tiếng Việt; lỗi khác → None."""
    d = (desc or "").lower()
    if "can't initiate conversation" in d or "bot can't initiate" in d:
        return "Chưa bấm Start với bot"
    if "blocked by the user" in d:
        return "Đã chặn bot"
    if "user is deactivated" in d:
        return "Tài khoản Telegram đã xoá"
    if "chat not found" in d:
        return "Không tìm thấy chat (ID sai hoặc chưa từng nhắn bot)"
    return None


async def _doi_id_nhom(cu: int, moi: int) -> int:
    """Thay ID nhóm cũ bằng ID supergroup mới trong mọi SystemSetting đang trỏ tới nó."""
    from app.database import async_session
    from app.models.notification import SystemSetting

    async with async_session() as db:
        rows = (await db.execute(select(SystemSetting).where(SystemSetting.value == str(cu)))).scalars().all()
        for r in rows:
            r.value = str(moi)
        await db.commit()
    logger.warning("Telegram: nhóm %s đã lên supergroup %s — đã cập nhật %d cấu hình", cu, moi, len(rows))
    return len(rows)


async def _ghi_loi(chat_id: int, ly_do: str | None) -> None:
    """Ghi/xoá dấu «không gửi được» cho chat_id. Lỗi ghi không được làm hỏng việc gửi."""
    global _loi_cache
    k = str(chat_id)
    if ly_do is None and _loi_cache is not None and k not in _loi_cache:
        return
    try:
        from app.database import async_session
        from app.services.attendance_service import get_setting_json, set_setting_json

        async with async_session() as db:
            ds = await get_setting_json(db, KHOA_LOI_GUI)
            if ly_do is None:
                _loi_cache = set(ds)
                if k not in ds:
                    return
                ds.pop(k)
            else:
                ds[k] = {"ly_do": ly_do, "luc": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")}
            await set_setting_json(db, KHOA_LOI_GUI, ds)
            await db.commit()
            _loi_cache = set(ds)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Không ghi được trạng thái gửi Telegram: %s", exc)


_ERP_MAC_DINH = "https://crm.jamahome.vn"


def erp_url(link: str | None) -> str | None:
    """Link ERP tuyệt đối cho nút «Mở ERP». Telegram từ chối nút trỏ localhost/http,
    nên máy dev (FRONTEND_URL=localhost) vẫn trỏ về ERP thật."""
    if not link:
        return None
    if link.startswith("https://"):
        return link
    if link.startswith("http://"):
        return None
    base = (get_settings().FRONTEND_URL or "").rstrip("/")
    if not base.startswith("https://") or "localhost" in base or "127.0.0.1" in base:
        base = _ERP_MAC_DINH
    return f"{base}/{link.lstrip('/')}"


def nut_lead(lead_id: str) -> list[list[dict]]:
    """Hàng nút trên tin về MỘT lead gửi người đang phụ trách (R00 mục 6).

    Khớp `hang_nut_chinh()` của bot (telegram-bot/bot/handlers/lead_nut.py) — bot xử lý
    `ld:<việc>:<lead_id>`. SĐT khách để trong chữ của tin (nút url không nhận `tel:`).
    """
    return [
        [
            {"text": "Đã gọi", "callback_data": f"ld:goi:{lead_id}"},
            {"text": "Đã gặp/Zoom", "callback_data": f"ld:gz:{lead_id}"},
        ],
        [{"text": "Hẹn lại", "callback_data": f"ld:hl:{lead_id}"}],
    ]


def ban_phim(nut: list[list[dict]] | None = None, link: str | None = None) -> dict | None:
    """InlineKeyboardMarkup: các hàng nút `nut` + hàng «Mở ERP» cuối cùng (khi có link)."""
    hang = [list(h) for h in (nut or []) if h]
    url = erp_url(link)
    if url:
        hang.append([{"text": "Mở ERP", "url": url}])
    return {"inline_keyboard": hang} if hang else None


def _loi_do_nut(desc: str) -> bool:
    d = (desc or "").lower()
    return any(k in d for k in ("button", "markup", "keyboard"))


async def send_telegram(
    chat_id: int, text: str, parse_mode: str = "HTML", reply_markup: dict | None = None,
) -> bool:
    """Gửi 1 tin Telegram (kèm nút bấm `reply_markup` nếu có). True khi gửi được.

    `reply_markup`: bàn phím nút inline kiểu Bot API, ví dụ
    {"inline_keyboard": [[{"text": "...", "callback_data": "nx:baocao:PRJ-..."}]]}.
    Nút bị Telegram từ chối (URL/callback sai) thì gửi lại KHÔNG nút — tin vẫn phải tới.
    """
    settings = get_settings()
    token = settings.TELEGRAM_BOT_TOKEN
    if not token or not chat_id:
        logger.debug("Telegram notify skipped (no token or chat_id)")
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for _ in range(3):  # gửi lại khi nhóm vừa lên supergroup / nút bị từ chối
                payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
                if reply_markup:
                    payload["reply_markup"] = reply_markup
                resp = await client.post(_TELEGRAM_API.format(token=token), json=payload)
                if resp.status_code == 200:
                    if int(chat_id) > 0:
                        await _ghi_loi(chat_id, None)
                    return True
                try:
                    body = resp.json()
                except ValueError:
                    body = {}
                moi = (body.get("parameters") or {}).get("migrate_to_chat_id")
                if moi and int(moi) != int(chat_id):
                    await _doi_id_nhom(int(chat_id), int(moi))
                    chat_id = int(moi)
                    continue
                if reply_markup and resp.status_code == 400 and _loi_do_nut(body.get("description") or ""):
                    logger.warning("Telegram từ chối nút: %s — gửi lại không nút", body.get("description"))
                    reply_markup = None
                    continue
                break
            desc = body.get("description") or resp.text[:200]
            logger.warning("Telegram notify failed (%s) chat %s: %s", resp.status_code, chat_id, desc)
            ly_do = ly_do_loi(desc)
            if ly_do and int(chat_id) > 0:
                await _ghi_loi(chat_id, ly_do)
            return False
    except Exception as exc:
        logger.warning("Telegram notify error: %s", exc)
        return False


async def ds_loi_gui(db) -> dict:
    """{chat_id(str): {ly_do, luc}} — người đang không nhận được tin bot."""
    from app.services.attendance_service import get_setting_json
    return await get_setting_json(db, KHOA_LOI_GUI)

