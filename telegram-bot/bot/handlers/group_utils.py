"""Group utility handlers — /id, /cancel chung + welcome when added to a group."""

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

router = Router()


# /cancel và nút ❌ Hủy dùng chung cho mọi luồng (trước đây 3 file tự đăng ký
# /cancel, router đầu tiên thắng nên thông báo không nhất quán).
@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    if await state.get_state() is None:
        await message.answer("Không có thao tác nào đang mở.", reply_markup=types.ReplyKeyboardRemove())
        return
    await state.clear()
    await message.answer("🚫 Đã hủy. Gõ lệnh hoặc /start để bắt đầu lại.", reply_markup=types.ReplyKeyboardRemove())


@router.callback_query(F.data == "fsm:cancel")
async def cb_cancel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Đã hủy")
    try:
        await callback.message.edit_text("🚫 Đã hủy.")
    except Exception:
        pass


@router.message(Command("id"))
async def cmd_id(message: types.Message):
    """Reply with the current chat's ID — dùng để cấu hình nhóm công ty trong ERP."""
    chat = message.chat
    chat_type = {"private": "cá nhân", "group": "nhóm", "supergroup": "siêu nhóm", "channel": "kênh"}.get(
        chat.type, chat.type
    )
    lines = [
        f"🆔 <b>Chat ID:</b> <code>{chat.id}</code>",
        f"Loại: {chat_type}" + (f" — {chat.title}" if chat.title else ""),
    ]
    if chat.type in ("group", "supergroup"):
        lines += [
            "",
            "📋 Copy Chat ID ở trên và dán vào:",
            "ERP → Cài đặt → Tự động hóa → <b>Nhóm Telegram công ty</b>",
            "Bot sẽ gửi briefing công việc hàng ngày vào nhóm này.",
        ]
    if message.from_user:
        lines.append(f"\n👤 User ID của bạn: <code>{message.from_user.id}</code>")
    await message.answer("\n".join(lines))


@router.message(F.new_chat_members)
async def on_added_to_group(message: types.Message):
    """Welcome message when the bot is added to a group."""
    if not message.new_chat_members:
        return
    me = await message.bot.get_me()
    if not any(m.id == me.id for m in message.new_chat_members):
        return
    await message.answer(
        "🏠 <b>Xin chào JAMA HOME!</b>\n\n"
        "Tôi là trợ lý công việc của công ty. Để hoàn tất cài đặt:\n"
        "1️⃣ Gõ <b>/id</b> để lấy Chat ID của nhóm này\n"
        "2️⃣ Admin dán Chat ID vào ERP → Cài đặt → Tự động hóa\n\n"
        "Sau đó tôi sẽ gửi briefing công việc mỗi sáng 🌅\n"
        "Các lệnh dùng được trong nhóm: /duan · /baocao · /vatlieu · /suco · /checkin · /pipeline"
    )
