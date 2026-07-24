"""/start handler — welcome + authentication with inline buttons."""

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
            f"📋 Vai trò: <code>{user['role']}</code> · 👥 Phòng ban: <code>{user['department']}</code>\n\n"
            f"Chọn chức năng bên dưới:",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [
                    types.InlineKeyboardButton(text="🔄 Pipeline", callback_data="cmd_pipeline"),
                    types.InlineKeyboardButton(text="📋 Briefing", callback_data="cmd_briefing"),
                ],
                [
                    types.InlineKeyboardButton(text="🏗️ Dự án", callback_data="cmd_duan"),
                    types.InlineKeyboardButton(text="📝 Báo cáo", callback_data="cmd_baocao"),
                ],
                [
                    types.InlineKeyboardButton(text="📦 Vật tư", callback_data="cmd_vatlieu"),
                    types.InlineKeyboardButton(text="🚨 Sự cố", callback_data="cmd_suco"),
                ],
                [
                    types.InlineKeyboardButton(text="⏰ Check-in", callback_data="cmd_checkin"),
                    types.InlineKeyboardButton(text="🕐 Check-out", callback_data="cmd_checkout"),
                ],
                [
                    types.InlineKeyboardButton(text="💬 Feedback", callback_data="cmd_feedback"),
                    types.InlineKeyboardButton(text="📐 Dự toán", callback_data="cmd_dutoan"),
                ],
                [
                    types.InlineKeyboardButton(text="👤 Nhập lead", callback_data="cmd_lead"),
                ],
            ]),
        )
    else:
        await message.answer(
            "❌ <b>Chưa liên kết tài khoản CRM</b>\n\n"
            "Telegram ID của bạn chưa được đăng ký trong hệ thống.\n"
            f"Telegram ID: <code>{tg_user.id}</code>\n\n"
            "Vui lòng liên hệ Admin để được liên kết."
        )


# ── Callback handlers for inline buttons ────────────────────────────────

@router.callback_query(lambda c: c.data == "cmd_pipeline")
async def cb_pipeline(callback: types.CallbackQuery):
    await callback.message.edit_text("📊 Đang tải pipeline...")
    result = await api.get_pipeline(callback.from_user.id)
    if result:
        lines = ["📊 <b>Pipeline của bạn:</b>\n"]
        for col in result:
            count = col.get("count", 0)
            if count > 0:
                lines.append(f"• {col.get('stage_label', col.get('stage'))}: {count} leads")
        await callback.message.edit_text("\n".join(lines) if lines else "Không có lead nào trong pipeline")
    else:
        await callback.message.edit_text("❌ Không thể tải pipeline")
    await callback.answer()


@router.callback_query(lambda c: c.data == "cmd_briefing")
async def cb_briefing(callback: types.CallbackQuery):
    await callback.message.edit_text("📋 Đang tạo briefing...")
    result = await api.get_personal_dashboard(callback.from_user.id)
    if result:
        lines = [
            "📋 <b>Briefing hôm nay:</b>\n",
            f"👥 Leads đang quản lý: {result.get('total_active_leads', 0)}",
            f"💰 Giá trị pipeline: {result.get('pipeline_value', 0):,}đ",
        ]
        overdue = result.get("overdue_followup", [])
        if overdue:
            lines.append(f"\n⚠️ <b>Cần follow-up ({len(overdue)} leads):</b>")
            for item in overdue[:3]:
                lines.append(f"  • {item['name']} — {item.get('phone', '')}")
        await callback.message.edit_text("\n".join(lines))
    else:
        await callback.message.edit_text("❌ Không thể tải briefing")
    await callback.answer()


@router.callback_query(lambda c: c.data == "cmd_duan")
async def cb_duan(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🏗️ <b>Tra cứu dự án</b>\n\n"
        "Nhập lệnh: <code>/duan [Mã dự án]</code>\n"
        "Ví dụ: <code>/duan JMH-2026-001</code>"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "cmd_baocao")
async def cb_baocao(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📝 <b>Báo cáo công trình</b>\n\n"
        "Nhập lệnh: <code>/baocao [Mã DA] [Nội dung]</code>\n"
        "Ví dụ: <code>/baocao JMH-2026-001 Hoàn thành phần thô tầng 1</code>"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "cmd_vatlieu")
async def cb_vatlieu(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📦 <b>Yêu cầu vật tư</b>\n\n"
        "Nhập lệnh: <code>/vatlieu [Mã DA] [Tên vật tư] - [SL] [Đơn vị]</code>\n"
        "Ví dụ: <code>/vatlieu JMH-2026-001 Da op lat - 10 m2</code>"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "cmd_suco")
async def cb_suco(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🚨 <b>Báo cáo sự cố</b>\n\n"
        "Nhập lệnh: <code>/suco [Mã DA] [Mô tả]</code>\n"
        "Ví dụ: <code>/suco JMH-2026-001 Ro nuoc tu bep</code>"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "cmd_checkin")
async def cb_checkin(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "⏰ <b>Điểm danh GPS</b>\n\n"
        "Nhập lệnh: <code>/checkin [Mã DA]</code>\n"
        "Bot sẽ tự động ghi nhận vị trí GPS của bạn"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "cmd_checkout")
async def cb_checkout(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🕐 <b>Tan ca GPS</b>\n\n"
        "Nhập lệnh: <code>/checkout [Mã DA]</code>\n"
        "Bot sẽ ghi nhận thời gian kết thúc ca làm"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "cmd_feedback")
async def cb_feedback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "💬 <b>Gửi Feedback</b>\n\n"
        "Nhập lệnh: <code>/feedback</code>\n"
        "Hoặc: <code>/feedback bug Mô tả...</code>"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "cmd_dutoan")
async def cb_dutoan(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📐 <b>Dự toán cải tạo</b>\n\n"
        "Nhập lệnh: <code>/dutoan</code>\n"
        "Chọn phương án: Số liệu / Mô tả / Hình ảnh"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "cmd_lead")
async def cb_lead(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "👤 <b>Nhập lead mới</b>\n\n"
        "Forward hoặc paste tin nhắn Zalo của khách hàng vào đây.\n"
        "Bot sẽ tự động parse thông tin và tạo lead."
    )
    await callback.answer()
