"""JAMA HOME ERP Telegram Bot — aiogram 3.x entry point."""

import asyncio
import logging
import os
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

from bot.api_client import api
from bot.handlers import (
    chon_du_an,
    start,
    lead_intake,
    pipeline,
    briefing,
    site_report,
    material_request,
    incident,
    checkin_out,
    group_utils,
    feedback,
    hr,
    estimation,
    kho_anh,
    help as help_cmd,
    vat_tu_nhap,
)

load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok","service":"telegram-bot"}')
    def log_message(self, *args):
        pass


# ── Đợt 3: tự đăng nhập + ghi nhận người Telegram ─────────────────────────
# Bot API không liệt kê được thành viên nhóm, nên mỗi người nhắn (nhóm/riêng)
# hoặc vừa vào nhóm được báo về backend để admin gán vào tài khoản ERP.
# Cần BotFather /setprivacy → Disable thì bot mới thấy tin thường trong nhóm.
_GIAN_CACH = 600  # giây — mỗi người tối đa 1 lần/10 phút
_lan_dang_nhap: dict[int, float] = {}
_lan_ghi_nhan: dict[int, float] = {}


def _bao_da_gap(user: types.User, chat: types.Chat | None) -> None:
    now = time.monotonic()
    if user.is_bot or now - _lan_ghi_nhan.get(user.id, -_GIAN_CACH) < _GIAN_CACH:
        return
    _lan_ghi_nhan[user.id] = now
    info = {
        "tg_user_id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }
    if chat is not None and chat.type in ("group", "supergroup"):
        info["chat_id"] = chat.id
        info["chat_title"] = chat.title
    asyncio.create_task(api.contact_seen(info))


# Lệnh dùng được khi Telegram chưa gán tài khoản ERP.
_LENH_TU_DO = {"start", "id", "cancel", "help"}


def _la_lenh_can_dang_nhap(event) -> bool:
    if isinstance(event, types.CallbackQuery):
        return True
    if isinstance(event, types.Message):
        text = (event.text or event.caption or "").strip()
        if text.startswith("/"):
            lenh = text[1:].split(maxsplit=1)[0].split("@")[0].lower() if len(text) > 1 else ""
            return lenh not in _LENH_TU_DO
    return False


def _huong_dan_lien_ket(user: types.User) -> str:
    ten = " ".join(x for x in (user.first_name, user.last_name) if x) or "bạn"
    return (
        f"🔗 <b>Telegram của {ten} chưa liên kết tài khoản ERP</b>\n\n"
        "Bot đã ghi nhận bạn. Nhờ Admin vào <b>ERP → Tài khoản → «Telegram chưa gán»</b>, "
        "chọn tên bạn rồi bấm <b>Gán</b>. Xong là dùng được ngay, không cần /start lại.\n"
        f"Telegram ID của bạn: <code>{user.id}</code>"
    )


async def nguoi_dung_middleware(handler, event, data):
    user: types.User | None = data.get("event_from_user")
    chat: types.Chat | None = data.get("event_chat")
    if user is not None and not user.is_bot and _la_lenh_can_dang_nhap(event) and user.id not in api._tokens:
        # Gõ lệnh/bấm nút: thử đăng nhập NGAY (không chờ 10 phút) để người vừa
        # được admin gán dùng được luôn; vẫn chưa gán thì hướng dẫn rõ ràng.
        _lan_dang_nhap[user.id] = time.monotonic()
        await api.authenticate(user.id, user.username)
        if api.chua_lien_ket(user.id):
            _bao_da_gap(user, chat)
            if isinstance(event, types.CallbackQuery):
                await event.answer("Telegram của bạn chưa liên kết tài khoản ERP", show_alert=True)
                if event.message:
                    await event.message.answer(_huong_dan_lien_ket(user))
            else:
                await event.answer(_huong_dan_lien_ket(user))
            return None
    if user is not None and not user.is_bot:
        # Bot khởi động lại thì cache JWT rỗng → tự đăng nhập bằng TG ID thay
        # vì bắt nhân viên /start lại. Người chưa gán: thử lại sau 10 phút.
        now = time.monotonic()
        if user.id not in api._tokens and now - _lan_dang_nhap.get(user.id, -_GIAN_CACH) >= _GIAN_CACH:
            _lan_dang_nhap[user.id] = now
            await api.authenticate(user.id, user.username)
        _bao_da_gap(user, chat)
    if isinstance(event, types.Message) and event.new_chat_members:
        for m in event.new_chat_members:
            _bao_da_gap(m, chat)
    return await handler(event, data)


LENH_GOI_Y = [
    ("start", "Menu chính"),
    ("help", "Hướng dẫn dùng bot"),
    ("checkin", "Vào ca (văn phòng / công trình)"),
    ("checkout", "Tan ca"),
    ("baocao", "Báo cáo công trình kèm ảnh"),
    ("suco", "Báo sự cố kèm ảnh"),
    ("vatlieu", "Yêu cầu vật tư"),
    ("duan", "Xem nhanh dự án"),
    ("choduyet", "Việc chờ tôi duyệt"),
    ("congcuatoi", "Công & giờ làm tháng này"),
    ("nghiphep", "Xin nghỉ phép"),
    ("dutoan", "Dự toán cải tạo"),
    ("lead", "Nhập lead mới"),
    ("baogia", "Thu mua: nhập báo giá NCC từ tệp"),
    ("nhapmau", "Thu mua: nhập danh mục mẫu từ Google Sheet"),
    ("cancel", "Hủy thao tác đang làm"),
    ("id", "Xem Telegram ID / Chat ID"),
]


def _start_health_server():
    port = int(os.getenv("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logger.info(f"Health server on port {port}")
    server.serve_forever()


async def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set!")
        sys.exit(1)

    # Start health server for Railway healthcheck
    threading.Thread(target=_start_health_server, daemon=True).start()

    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.message.outer_middleware(nguoi_dung_middleware)
    dp.callback_query.outer_middleware(nguoi_dung_middleware)

    # Register handlers
    dp.include_router(group_utils.router)  # /id, /cancel chung + group welcome (trước để ưu tiên)
    dp.include_router(chon_du_an.router)   # nút bấm chọn dự án / ✅ Gửi
    dp.include_router(start.router)
    dp.include_router(help_cmd.router)
    dp.include_router(vat_tu_nhap.router)  # /nhapmau, /baogia (Thu mua)
    dp.include_router(lead_intake.router)
    dp.include_router(pipeline.router)
    dp.include_router(briefing.router)
    dp.include_router(site_report.router)
    dp.include_router(material_request.router)
    dp.include_router(incident.router)
    dp.include_router(checkin_out.router)
    dp.include_router(feedback.router)
    dp.include_router(hr.router)
    dp.include_router(estimation.router)
    dp.include_router(kho_anh.router)  # ảnh thả vào topic nhóm Kho ảnh — cuối chuỗi

    try:  # menu «/» của Telegram liệt kê lệnh tiếng Việt
        await bot.set_my_commands([types.BotCommand(command=c, description=d) for c, d in LENH_GOI_Y])
    except Exception as e:
        logger.warning(f"set_my_commands lỗi: {e}")

    logger.info("JAMA HOME ERP Bot starting...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
