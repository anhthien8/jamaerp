"""Lead intake handler — parse Zalo messages + confirm + save."""

from aiogram import Router, types, F
from aiogram.filters import Command, StateFilter
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
    editing_field = State()


TRUONG_SUA = {"name": "Tên", "phone": "SĐT", "address": "Địa chỉ", "needs": "Nhu cầu", "area_sqm": "Diện tích (m²)"}


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
    await _hien_xac_nhan(message, state, parsed)


async def _hien_xac_nhan(message: types.Message, state: FSMContext, parsed: dict):
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
    """Save confirmed lead to ERP."""
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

    if result and result.get("error"):
        await callback.message.edit_text(f"⚠️ {result['error']}")
    elif result:
        await callback.message.edit_text(
            f"✅ <b>Lead đã lưu thành công!</b>\n\n"
            f"👤 {result.get('name')}\n"
            f"📱 {result.get('phone')}\n"
            f"🏷 Giai đoạn: {STAGE_LABELS.get(result.get('stage'), result.get('stage'))}\n"
            f"🆔 ID: <code>{result.get('id', '')[:8]}</code>\n\n"
            f"→ Đã sync lên ERP ✓"
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
    """Chọn trường cần sửa (trước đây báo «đang phát triển» rồi xoá luôn dữ liệu đã phân tích)."""
    if not (await state.get_data()).get("parsed_lead"):
        await callback.answer("Phiên đã hết, gửi /lead lại nhé.")
        return
    nut = [[InlineKeyboardButton(text=nhan, callback_data=f"lead_f:{k}")] for k, nhan in TRUONG_SUA.items()]
    await callback.message.edit_text("✏️ Sửa trường nào?", reply_markup=InlineKeyboardMarkup(inline_keyboard=nut))
    await callback.answer()


@router.callback_query(F.data.startswith("lead_f:"))
async def chon_truong_sua(callback: types.CallbackQuery, state: FSMContext):
    k = callback.data.split(":", 1)[1]
    if k not in TRUONG_SUA:
        await callback.answer()
        return
    await state.update_data(truong_sua=k)
    await state.set_state(LeadIntakeState.editing_field)
    await callback.message.edit_text(f"Gõ {TRUONG_SUA[k]} mới:")
    await callback.answer()


@router.message(LeadIntakeState.editing_field, F.text)
async def nhan_gia_tri_sua(message: types.Message, state: FSMContext):
    data = await state.get_data()
    parsed = dict(data.get("parsed_lead") or {})
    k = data.get("truong_sua")
    gia_tri = message.text.strip()
    if k == "area_sqm":
        try:
            gia_tri = float(gia_tri.replace(",", "."))
        except ValueError:
            await message.answer("Diện tích phải là số, VD 85")
            return
    parsed[k] = gia_tri
    await state.update_data(parsed_lead=parsed)
    await _hien_xac_nhan(message, state, parsed)


# Also catch forwarded/pasted messages (non-command) as lead intake
# CHỈ trong chat riêng — tránh parse nhầm tin nhắn trò chuyện trong nhóm công ty
# StateFilter(None): đang trong luồng khác (gõ nội dung /baocao, mô tả /suco,
# vật tư...) thì để tin rơi xuống handler của luồng đó — trước đây handler này
# khớp trước rồi return, nuốt mất tin của các luồng đăng ký sau nó.
@router.message(StateFilter(None), F.chat.type == "private", F.text & ~F.text.startswith("/"))
async def auto_parse_message(message: types.Message, state: FSMContext):
    """Auto-detect lead info from any non-command text message."""

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
