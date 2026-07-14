"""/feedback handler — employee feedback via Telegram with FSM."""

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from bot.api_client import api

router = Router()

CATEGORY_LABELS = {
    "bug": "🐛 Bug / Lỗi",
    "feature_request": "💡 Tính năng mới",
    "workflow_improvement": "⚡ Cải thiện workflow",
    "other": "📝 Khác",
}
CATEGORY_INLINE = list(CATEGORY_LABELS.keys())


class FeedbackState(StatesGroup):
    waiting_for_category = State()
    waiting_for_content = State()


@router.message(Command("feedback"))
async def cmd_feedback(message: types.Message, state: FSMContext):
    args = message.text.split(maxsplit=2)

    # Inline: /feedback bug <text>
    if len(args) >= 3 and args[1] in CATEGORY_INLINE:
        if len(args[2].strip()) < 5:
            await message.answer("⚠️ Nội dung quá ngắn. Vui lòng nhập ít nhất 5 ký tự.")
            return
        await _submit_feedback(message, args[1], args[2].strip())
        return

    # Category only: /feedback bug
    if len(args) == 2 and args[1] in CATEGORY_INLINE:
        await state.update_data(category=args[1])
        await state.set_state(FeedbackState.waiting_for_content)
        await message.answer(
            f"📝 <b>Feedback — {CATEGORY_LABELS.get(args[1], args[1])}</b>\n\n"
            "Nhập nội dung feedback:\n💡 <i>Gửi /cancel để hủy</i>"
        )
        return

    # Show category picker
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=label, callback_data=f"fb_cat:{cat}")]
        for cat, label in CATEGORY_LABELS.items()
    ])
    await state.set_state(FeedbackState.waiting_for_category)
    await message.answer("📝 <b>Gửi Feedback</b>\n\nChọn loại feedback:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("fb_cat:"), FeedbackState.waiting_for_category)
async def process_category_callback(callback: types.CallbackQuery, state: FSMContext):
    category = callback.data.split(":", 1)[1]
    if category not in CATEGORY_INLINE:
        await callback.answer("Loại feedback không hợp lệ")
        return
    await state.update_data(category=category)
    await state.set_state(FeedbackState.waiting_for_content)
    await callback.message.edit_text(
        f"📝 <b>Feedback — {CATEGORY_LABELS.get(category, category)}</b>\n\n"
        "Nhập nội dung feedback:\n💡 <i>Gửi /cancel để hủy</i>"
    )
    await callback.answer()


@router.message(FeedbackState.waiting_for_content, F.text)
async def process_content(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if text.startswith("/") and text == "/cancel":
        await state.clear()
        await message.answer("🚫 Đã hủy feedback.")
        return
    if len(text) < 5:
        await message.answer("⚠️ Nội dung quá ngắn. Vui lòng nhập ít nhất 5 ký tự.")
        return
    data = await state.get_data()
    category = data.get("category", "other")
    await _submit_feedback(message, category, text)
    await state.clear()


@router.message(Command("myfeedback"))
async def cmd_myfeedback(message: types.Message):
    result = await api.get_my_feedback(message.from_user.id)
    if not result:
        await message.answer("❌ Không kết nối được server. Vui lòng thử lại.")
        return
    items = result.get("items", [])
    if not items:
        await message.answer("📝 <b>Feedback của bạn</b>\n\nBạn chưa gửi feedback nào.\nGửi /feedback để bắt đầu.")
        return
    status_icons = {"new": "🆕", "in_review": "🔍", "done": "✅", "rejected": "❌"}
    lines = [f"📝 <b>Feedback của bạn</b> ({len(items)} lỗi)\n"]
    for fb in items[:10]:
        icon = status_icons.get(fb["status"], "?")
        cat_label = CATEGORY_LABELS.get(fb["category"], fb["category"])
        content_preview = fb["content"][:80] + ("..." if len(fb["content"]) > 80 else "")
        lines.append(f"{icon} <b>{cat_label}</b> — {fb['created_at'][:10]}")
        lines.append(f"   {content_preview}")
        if fb.get("admin_reply"):
            lines.append(f"   💬 Admin: {fb['admin_reply'][:60]}")
        lines.append("")
    await message.answer("\n".join(lines))


async def _submit_feedback(message: types.Message, category: str, content: str):
    await message.answer("🔄 Đang gửi feedback...")
    result = await api.submit_feedback(message.from_user.id, category, content)
    if not result:
        await message.answer("❌ Không kết nối được server. Vui lòng thử lại.")
        return
    if result.get("error"):
        await message.answer(f"❌ <b>Lỗi:</b> {result['error']}")
        return
    cat_label = CATEGORY_LABELS.get(category, category)
    await message.answer(
        f"✅ <b>Cảm ơn! Feedback đã được gửi thành công.</b>\n\n"
        f"Loại: {cat_label}\n"
        f"Nội dung: {content[:100]}{'...' if len(content) > 100 else ''}\n\n"
        f"Admin sẽ xem xét và phản hồi trong thời gian sớm nhất.\n"
        f"Theo dõi: /myfeedback"
    )
