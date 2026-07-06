"""/vatlieu handler — material purchase requests + approve/reject callbacks."""

import re

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from bot.api_client import api


class RejectState(StatesGroup):
    """FSM state for collecting reject reason."""
    waiting_reason = State()

router = Router()


# ---------------------------------------------------------------------------
# /vatlieu — Request material purchase
# ---------------------------------------------------------------------------

@router.message(Command("vatlieu"))
async def cmd_vatlieu(message: types.Message):
    """Submit a material request — parse from text arguments."""
    # Expected format: /vatlieu [Mã_dự_án] [Tên_vật_tư] - [Số_lượng] [Đơn_vị]
    text = message.text.replace("/vatlieu", "").strip()

    if not text:
        await message.answer(
            "🧱 <b>Yêu cầu vật tư</b>\n\n"
            "Cách dùng:\n"
            "<code>/vatlieu [Mã DA] [Tên vật tư] - [Số lượng] [Đơn vị]</code>\n\n"
            "Ví dụ:\n"
            "<code>/vatlieu JMH-0601 Xi mang Portland - 50 bao</code>\n"
            "<code>/vatlieu JMH-0601 Sat thep phi 12 - 200kg</code>\n\n"
            "💡 Sau khi gửi, yêu cầu sẽ được chuyển đến Thu mua/Kế toán duyệt."
        )
        return

    parsed = _parse_material_args(text)

    if not parsed:
        await message.answer(
            "⚠️ <b>Cú pháp không hợp lệ</b>\n\n"
            "Vui lòng nhập đúng format:\n"
            "<code>/vatlieu [Mã DA] [Tên vật tư] - [Số lượng] [Đơn vị]</code>\n\n"
            "Ví dụ: <code>/vatlieu JMH-0601 Xi mang Portland - 50 bao</code>"
        )
        return

    project_code = parsed["project_code"]
    material_name = parsed["material_name"]
    quantity = parsed["quantity"]
    unit = parsed["unit"]

    # Show confirmation
    await message.answer(
        f"🧱 <b>Yêu cầu vật tư</b>\n\n"
        f"🏗 Dự án: <code>{project_code}</code>\n"
        f"📦 Vật tư: <b>{material_name}</b>\n"
        f"📊 Số lượng: <b>{quantity} {unit}</b>\n\n"
        f"🔄 Đang gửi yêu cầu..."
    )

    request_data = {
        "project_code": project_code,
        "material_name": material_name,
        "quantity": quantity,
        "unit": unit,
        "requester_tg_id": message.from_user.id,
    }

    result = await api.create_material_request(message.from_user.id, request_data)

    if not result:
        await message.answer("❌ Không kết nối được server. Vui lòng thử lại.")
        return

    if result.get("error"):
        await message.answer(f"❌ <b>Lỗi:</b> {result['error']}")
        return

    # Build result message
    over_budget = result.get("over_budget", False)
    est_cost = result.get("estimated_cost", 0)
    budget_remaining = result.get("budget_remaining", 0)

    status_emoji = "⚠️" if over_budget else "✅"
    status_text = result.get("message", "")

    lines = [
        f"{status_emoji} <b>Yêu cầu vật tư đã gửi thành công!</b>\n",
        f"🆔 Mã yêu cầu: <code>{result.get('request_id', '')[:8]}</code>",
        f"🏗 Dự án: <code>{result.get('project_code', project_code)}</code>",
        f"📦 Vật tư: <b>{result.get('material_name', material_name)}</b>",
        f"📊 SL: {result.get('quantity', quantity)} {result.get('unit', unit)}",
        f"👤 Người yêu cầu: {result.get('requester', '—')}",
        f"💰 Chi phí dự kiến: {_format_value(est_cost)}",
        f"💵 Ngân sách còn lại: {_format_value(budget_remaining)}",
        f"📌 Trạng thái: <i>{result.get('status', 'pending')}</i>",
    ]

    if over_budget:
        lines.append("")
        lines.append("⚠️ <b>Yêu cầu vượt định mức!</b>")
        lines.append("Cần giải trình trước khi được duyệt.")

    lines.append(f"\n📝 {status_text}")

    keyboard = build_material_keyboard(result.get("request_id", ""))
    await message.answer("\n".join(lines), reply_markup=keyboard)

    # If over budget, add a note about requiring extra approval
    if over_budget:
        await message.answer(
            "💡 <i>Yêu cầu này vượt ngân sách dự án. "
            "Vui lòng liên hệ Kế toán để được xử lý.</i>"
        )


# ---------------------------------------------------------------------------
# Approve/Reject inline button callbacks
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("mat_approve:"))
async def callback_approve_material(callback: CallbackQuery):
    """Handle approve button press from Thu mua / Ke toan."""
    request_id = callback.data.split(":", 1)[1]

    result = await api.approve_material(callback.from_user.id, request_id)

    if not result:
        await callback.message.edit_text("❌ Lỗi kết nối server khi duyệt.")
        return

    if result.get("error"):
        await callback.message.edit_text(f"❌ <b>Lỗi:</b> {result['error']}")
        return

    # Update the original message
    old_text = callback.message.text or ""
    # Append approval status to the original message
    approval_info = (
        f"\n\n✅ <b>ĐÃ DUYỆT</b>\n"
        f"👤 Duyệt bởi: {result.get('approver', '—')}\n"
        f"🕐 Thời gian: {result.get('resolved_at', '—')}"
    )

    # Remove the inline keyboard and add approval info
    await callback.message.edit_text(
        old_text + approval_info,
        reply_markup=None,
    )

    # Notify the requester if possible
    await callback.answer("Đã duyệt vật tư!", show_alert=True)


@router.callback_query(F.data.startswith("mat_reject:"))
async def callback_reject_material(callback: CallbackQuery, state: FSMContext):
    """Handle reject button press from Thu mua / Ke toan."""
    request_id = callback.data.split(":", 1)[1]

    # Store request_id in FSM state and ask for reason
    await state.update_data(reject_request_id=request_id)
    await state.set_state(RejectState.waiting_reason)

    await callback.message.answer(
        f"❌ <b>Từ chối yêu cầu</b>\n\n"
        f"Gửi lý do từ chối (hoặc gửi <code>/skip</code> để bỏ qua):\n"
        f"Mã yêu cầu: <code>{request_id[:8]}</code>"
    )

    await callback.answer()


@router.message(Command("skip"), RejectState.waiting_reason)
async def cmd_skip(message: types.Message, state: FSMContext):
    """Skip providing reject reason — reject without a reason."""
    data = await state.get_data()
    request_id = data.get("reject_request_id")
    await state.clear()

    if not request_id:
        await message.answer("Không tìm thấy yêu cầu để từ chối.")
        return

    result = await api.reject_material(message.from_user.id, request_id, reason=None)

    if not result:
        await message.answer("❌ Lỗi kết nối server khi từ chối.")
        return
    if result.get("error"):
        await message.answer(f"❌ <b>Lỗi:</b> {result['error']}")
        return

    await message.answer(
        f"❌ <b>Đã từ chối yêu cầu vật tư</b>\n\n"
        f"🆔 Mã: <code>{request_id[:8]}</code>\n"
        f"👤 Xử lý bởi: {result.get('approver', '—')}\n"
        f"🕐 Thời gian: {result.get('resolved_at', '—')}"
    )


@router.message(RejectState.waiting_reason)
async def process_reject_reason(message: types.Message, state: FSMContext):
    """Catch the reject reason text, call API, show confirmation."""
    data = await state.get_data()
    request_id = data.get("reject_request_id")
    reason = message.text.strip() if message.text else None
    await state.clear()

    if not request_id:
        await message.answer("Không tìm thấy yêu cầu để từ chối.")
        return

    result = await api.reject_material(message.from_user.id, request_id, reason=reason)

    if not result:
        await message.answer("❌ Lỗi kết nối server khi từ chối.")
        return
    if result.get("error"):
        await message.answer(f"❌ <b>Lỗi:</b> {result['error']}")
        return

    reason_line = f"\n📝 Lý do: {reason}" if reason else ""
    await message.answer(
        f"❌ <b>Đã từ chối yêu cầu vật tư</b>\n\n"
        f"🆔 Mã: <code>{request_id[:8]}</code>\n"
        f"👤 Xử lý bởi: {result.get('approver', '—')}\n"
        f"🕐 Thời gian: {result.get('resolved_at', '—')}"
        f"{reason_line}"
    )


# ---------------------------------------------------------------------------
# Helper: Build approve/reject keyboard for material requests
# ---------------------------------------------------------------------------

def build_material_keyboard(request_id: str) -> InlineKeyboardMarkup:
    """Build inline keyboard with approve/reject buttons for a material request."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Duyệt",
                callback_data=f"mat_approve:{request_id}",
            ),
            InlineKeyboardButton(
                text="❌ Từ chối",
                callback_data=f"mat_reject:{request_id}",
            ),
        ],
    ])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_material_args(text: str) -> dict | None:
    """
    Parse material request arguments from text.

    Expected format: [Mã DA] [Tên vật tư] - [Số lượng] [Đơn vị]
    Examples:
        JMH-0601 Xi mang Portland - 50 bao
        JMH-0601 Sat thep phi 12 - 200kg
        JMH-0601 Da 4x6 - 10m3
    """
    # Use regex that captures the project code as a token (letters+digits+dash+digits),
    # avoiding splitting on dashes inside the project code like JMH-0601.
    # Try " - " separator first (space-dash-space), then fall back to bare "-".
    match = re.match(
        r'^([A-Za-z][\w]*-\d+)\s+'  # project code
        r'(.+?)\s+-\s+'             # material name + " - " separator
        r'(\d+(?:[.,]\d+)?)'        # quantity
        r'\s*(.*?)$',                # unit (optional)
        text,
    )
    if not match:
        match = re.match(
            r'^([A-Za-z][\w]*-\d+)\s+'  # project code
            r'(.+?)'                     # material name
            r'-\s*'                      # bare "-" separator
            r'(\d+(?:[.,]\d+)?)'         # quantity
            r'\s*(.*?)$',                # unit (optional)
            text,
        )
    if not match:
        return None

    project_code = match.group(1).upper()
    material_name = match.group(2).strip()
    quantity_str = match.group(3).replace(",", ".")
    unit = match.group(4).strip()

    if not material_name:
        return None

    try:
        quantity = float(quantity_str)
    except ValueError:
        return None

    if quantity <= 0:
        return None

    if not unit:
        unit = "cai"  # Default unit

    return {
        "project_code": project_code,
        "material_name": material_name,
        "quantity": quantity,
        "unit": unit,
    }


def _format_value(value) -> str:
    """Format VND currency."""
    if not value:
        return "0 VND"
    v = float(value)
    if v >= 1_000_000_000:
        return f"{v / 1_000_000_000:.1f} ty"
    elif v >= 1_000_000:
        return f"{v / 1_000_000:.0f} trieu"
    return f"{v:,.0f} VND"
