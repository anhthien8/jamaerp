"""/start handler — welcome + authentication."""

from aiogram import Router, types
from aiogram.filters import CommandStart

from bot.api_client import api

router = Router()


@router.message(CommandStart())
async def cmd_start(message: types.Message):
    """Handle /start — authenticate user via TG ID."""
    tg_user = message.from_user
    auth_result = await api.authenticate(tg_user.id, tg_user.username)

    if auth_result:
        user = auth_result["user"]
        await message.answer(
            f"🏠 <b>Chào mừng {user['full_name']}!</b>\n\n"
            f"Bạn đã đăng nhập vào <b>JAMA HOME CRM</b>\n"
            f"📋 Vai trò: <code>{user['role']}</code>\n"
            f"👥 Phòng ban: <code>{user['department']}</code>\n\n"
            f"<b>Lệnh có sẵn:</b>\n"
            f"/lead — Nhập lead mới (copy từ Zalo)\n"
            f"/pipeline — Xem pipeline của bạn\n"
            f"/briefing — Briefing hàng ngày\n"
            f"/suggest — Gợi ý AI cho lead\n\n"
            f"💡 <i>Hoặc forward/paste tin nhắn Zalo trực tiếp để bot tự parse!</i>"
        )
    else:
        await message.answer(
            "❌ <b>Chưa liên kết tài khoản CRM</b>\n\n"
            "Telegram ID của bạn chưa được đăng ký trong hệ thống.\n"
            f"Telegram ID: <code>{tg_user.id}</code>\n\n"
            "Vui lòng liên hệ Admin để được liên kết."
        )
