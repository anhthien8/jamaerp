"""Lead intake handler — parse Zalo messages + confirm + save."""

import json
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from bot.api_client import api

router = Router()

STAGE_LABELS = {
    "new": "Mới tiếp nhận",
    "interested": "Có nhu cầu",
    "survey_scheduled": "Đã hẹn khảo sát",
    "potential": "KH tiềm năng",
    "signed_design": "Ký thiết kế",
}


class LeadIntakeState(StatesGroup):
    waiting_text = State()
    confirming = State()


@router.message(Command("lead"))
async def cmd_lead(message: types.Message, state: FSMContext):
    """Start lead intake — ask for Zalo text."""
    await state.set_state(LeadIntakeState.waiting_text)
    await message.answer(
        "📝 <b>Nhập lead mới</b>\n\n"
        "Copy/paste tin nhắn khách hàng từ Zalo vào đây.\n"
        "Bot sẽ tự động phân tích và trích xuất thông tin.\n\n"
        "💡 <i>Gửi /cancel để hủy</i>"
    )


@router.message(LeadIntakeState.waiting_text, F.text)
async def process_lead_text(message: types.Message, state: FSMContext):
    """Receive raw text → parse via AI → show confirmation."""
    raw_text = message.text
    if raw_text.startswith("/"):
        await state.clear()
        return

    await message.answer("🔄 Đang phân tích tin nhắn...")

    # Parse via AI
    parsed = await api.parse_lead(message.from_user.id, raw_text)

    if not parsed:
        await message.answer("❌ Không thể phân tích. Vui lòng thử lại hoặc nhập thủ công.")
        return

    # Store parsed data for confirmation
    await state.update_data(parsed_lead=parsed, raw_text=raw_text)
    await state.set_state(LeadIntakeState.confirming)

    # Build confirmation message
    confidence_emoji = "🟢" if parsed.get("confidence", 0) >= 0.7 else "🟡" if parsed.get("confidence", 0) >= 0.4 else "🔴"

    confirm_text = (
        f"{confidence_emoji} <b>Kết quả phân tích</b> (Độ chính xác: {parsed.get('confidence', 0):.0%})\n\n"
        f"👤 Tên: <b>{parsed.get('name') or '—'}</b>\n"
        f"📱 SĐT: <b>{parsed.get('phone') or '—'}</b>\n"
        f"👋 Người LH: {parsed.get('contact_person') or '—'}\n"
        f"📍 Địa chỉ: {parsed.get('address') or '—'}\n"
        f"🏠 Loại: {parsed.get('property_type') or '—'}\n"
        f"📐 Diện tích: {parsed.get('area_sqm') or '—'} m²\n"
        f"💰 Ngân sách: {_format_budget(parsed.get('estimated_budget'))}\n"
        f"📋 Nhu cầu: {parsed.get('needs') or '—'}\n"
        f"📢 Nguồn: {parsed.get('source') or '—'}\n\n"
        f"<i>Tin nhắn gốc đã lưu</i>"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Xác nhận lưu", callback_data="lead_confirm"),
            InlineKeyboardButton(text="✏️ Sửa", callback_data="lead_edit"),
        ],
        [
            InlineKeyboardButton(text="❌ Hủy", callback_data="lead_cancel"),
        ],
    ])

    await message.answer(confirm_text, reply_markup=keyboard)


@router.callback_query(F.data == "lead_confirm")
async def confirm_lead(callback: types.CallbackQuery, state: FSMContext):
    """Save confirmed lead to CRM."""
    data = await state.get_data()
    parsed = data.get("parsed_lead", {})

    if not parsed:
        await callback.answer("Không tìm thấy dữ liệu lead.")
        return

    # Create lead via API
    lead_data = {
        "name": parsed.get("name") or "KH chưa có tên",
        "phone": parsed.get("phone") or "N/A",
        "contact_person": parsed.get("contact_person"),
        "address": parsed.get("address"),
        "needs": parsed.get("needs"),
        "source": parsed.get("source"),
        "property_type": parsed.get("property_type"),
        "area_sqm": float(parsed["area_sqm"]) if parsed.get("area_sqm") else None,
        "estimated_budget": float(parsed["estimated_budget"]) if parsed.get("estimated_budget") else None,
    }

    result = await api.create_lead(callback.from_user.id, lead_data)

    if result:
        await callback.message.edit_text(
            f"✅ <b>Lead đã lưu thành công!</b>\n\n"
            f"👤 {result.get('name')}\n"
            f"📱 {result.get('phone')}\n"
            f"🏷 Giai đoạn: {STAGE_LABELS.get(result.get('stage'), result.get('stage'))}\n"
            f"🆔 ID: <code>{result.get('id', '')[:8]}</code>\n\n"
            f"→ Đã sync lên CRM ✓"
        )
    else:
        await callback.message.edit_text("❌ Lỗi khi lưu lead. Vui lòng thử lại.")

    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "lead_cancel")
async def cancel_lead(callback: types.CallbackQuery, state: FSMContext):
    """Cancel lead intake."""
    await state.clear()
    await callback.message.edit_text("🚫 Đã hủy. Gửi /lead để nhập lead mới.")
    await callback.answer()


@router.callback_query(F.data == "lead_edit")
async def edit_lead(callback: types.CallbackQuery, state: FSMContext):
    """Allow manual editing."""
    await callback.message.edit_text(
        "✏️ <b>Chỉnh sửa thủ công</b>\n\n"
        "Tính năng này đang phát triển.\n"
        "Vui lòng gửi /lead để nhập lại từ đầu."
    )
    await state.clear()
    await callback.answer()


# Also catch forwarded/pasted messages (non-command) as lead intake
@router.message(F.text & ~F.text.startswith("/"))
async def auto_parse_message(message: types.Message, state: FSMContext):
    """Auto-detect lead info from any non-command text message."""
    current_state = await state.get_state()
    if current_state is not None:
        return  # Already in a flow

    # Check if message looks like a lead (has phone or name patterns)
    text = message.text
    import re
    has_phone = bool(re.search(r'0\d{9,10}', text))
    has_name = bool(re.search(r'(?:Anh|Chị|A\.|C\.)', text))

    if has_phone or (has_name and len(text) > 30):
        await state.update_data(raw_text=text)
        await state.set_state(LeadIntakeState.waiting_text)
        # Trigger the parse flow
        await process_lead_text(message, state)
    else:
        await message.answer(
            "💬 Tin nhắn không nhận diện được là lead.\n"
            "Sử dụng /lead để nhập lead hoặc /help để xem lệnh."
        )


def _format_budget(budget) -> str:
    """Format budget VND."""
    if not budget:
        return "—"
    b = float(budget)
    if b >= 1_000_000_000:
        return f"{b / 1_000_000_000:.1f} tỷ"
    elif b >= 1_000_000:
        return f"{b / 1_000_000:.0f} triệu"
    return f"{b:,.0f} VND"
