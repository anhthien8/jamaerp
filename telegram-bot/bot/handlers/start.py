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
            f"<b>Lệnh CRM:</b>\n"
            f"/lead — Nhập lead mới (copy từ Zalo)\n"
            f"/pipeline — Xem pipeline của bạn\n"
            f"/briefing — Briefing hàng ngày\n"
            f"/suggest — Gợi ý AI cho lead\n\n"
            f"<b>Lệnh công trình:</b>\n"
            f"/duan [Mã DA] — Tra cứu dự án\n"
            f"/baocao [Mã DA] [Nội dung] — Báo cáo công trình\n"
            f"/vatlieu [Mã DA] [Vật tư] - [SL] [Đơn vị] — Yêu cầu vật tư\n"
            f"/suco [Mã DA] [Mô tả] — Báo cáo sự cố\n"
            f"/checkin [Mã DA] — Điểm danh GPS\n"
            f"/checkout [Mã DA] — Tan ca GPS\n\n"
            f"💡 <i>Hoặc forward/paste tin nhắn Zalo trực tiếp để bot tự parse!</i>"
        )
    else:
        await message.answer(
            "❌ <b>Chưa liên kết tài khoản CRM</b>\n\n"
            "Telegram ID của bạn chưa được đăng ký trong hệ thống.\n"
            f"Telegram ID: <code>{tg_user.id}</code>\n\n"
            "Vui lòng liên hệ Admin để được liên kết."
        )
