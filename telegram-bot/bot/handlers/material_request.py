"""/vatlieu handler — material purchase requests + approve/reject callbacks."""

import re
from html import escape

from aiogram import Router, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from bot.api_client import api
from bot.keyboards import NUT_HUY, hien_ban_phim, nut_huy


class RejectState(StatesGroup):
    """FSM state for collecting reject reason."""
    waiting_reason = State()


class VatTuState(StatesGroup):
    """Đã bấm chọn dự án, chờ gõ «Tên vật tư - SL đơn vị» (một hoặc nhiều dòng)."""
    waiting_item = State()
    confirm_batch = State()  # đã xem trước danh sách nhiều dòng, chờ bấm «Gửi N dòng»


MAX_DONG = 20  # một lần dán tối đa bấy nhiêu vật tư

router = Router()


# ---------------------------------------------------------------------------
# /vatlieu — Request material purchase
# ---------------------------------------------------------------------------

@router.message(Command("vatlieu"))
async def cmd_vatlieu(message: types.Message):
    """Submit a material request — parse from text arguments."""
    # Expected format: /vatlieu [Mã_dự_án] [Tên_vật_tư] - [Số_lượng] [Đơn_vị]
    parts = (message.text or message.caption or "").split(maxsplit=1)
    text = parts[1].strip() if len(parts) > 1 else ""

    if not text:
        await hien_ban_phim(message, message.from_user.id, "vatlieu")
        return
    await gui_vat_tu(message, message.from_user.id, text)


async def hoi_vat_tu(message: types.Message, state: FSMContext, project_code: str):
    """Sau khi bấm chọn dự án: hỏi tên vật tư + số lượng."""
    await state.update_data(project_code=project_code)
    await state.set_state(VatTuState.waiting_item)
    await message.answer(
        f"📦 <b>Yêu cầu vật tư — {project_code}</b>\n\n"
        "Gõ theo mẫu <code>Tên vật tư - Số lượng Đơn vị</code>\n"
        "Cần nhiều món thì gõ mỗi dòng một vật tư rồi gửi một lần:\n"
        "<code>Xi măng Portland - 50 bao\n"
        "Sắt phi 12 - 200 kg</code>",
        reply_markup=nut_huy(),
    )


def _bo_dau_dong(dong: str) -> str:
    """Bỏ gạch đầu dòng / số thứ tự người dùng hay dán kèm («- », «• », «1. »)."""
    return re.sub(r"^\s*(?:[-–•*+]\s+|\d+[.)]\s+)", "", dong).strip()


def _so(x: float) -> str:
    return f"{x:g}"


@router.message(
    StateFilter(VatTuState.waiting_item, VatTuState.confirm_batch),
    F.text & ~F.text.startswith("/"),
)
async def nhan_vat_tu(message: types.Message, state: FSMContext):
    """Một dòng → gửi luôn như cũ. Nhiều dòng → xem trước rồi bấm «Gửi N dòng»
    (đang ở bước xem trước mà gõ lại = thay cả danh sách)."""
    data = await state.get_data()
    code = data.get("project_code", "")
    dong = [d for d in (_bo_dau_dong(x) for x in message.text.splitlines()) if d]

    if len(dong) <= 1:
        text = f"{code} {dong[0] if dong else ''}"
        if not _parse_material_args(text):
            await message.answer(
                "⚠️ Chưa đúng mẫu. Gõ lại: <code>Tên vật tư - Số lượng Đơn vị</code>\n"
                "Ví dụ: <code>Sắt phi 12 - 200 kg</code>",
                reply_markup=nut_huy(),
            )
            return
        await state.clear()
        await gui_vat_tu(message, message.from_user.id, text)
        return

    if len(dong) > MAX_DONG:
        await message.answer(
            f"⚠️ Danh sách có {len(dong)} dòng — mỗi lần gửi tối đa {MAX_DONG} dòng. Tách ra rồi gửi lại.",
            reply_markup=nut_huy(),
        )
        return

    items, sai = [], []
    for d in dong:
        p = _parse_material_args(f"{code} {d}")
        if p:
            items.append({"material_name": p["material_name"], "quantity": p["quantity"], "unit": p["unit"]})
        else:
            sai.append(d)
    if not items:
        await message.answer(
            "⚠️ Chưa dòng nào đúng mẫu <code>Tên vật tư - Số lượng Đơn vị</code>. Gõ lại cả danh sách.",
            reply_markup=nut_huy(),
        )
        return

    await state.update_data(items=items)
    await state.set_state(VatTuState.confirm_batch)
    lines = [f"📦 <b>Yêu cầu vật tư — {escape(code)}</b>", "", f"Đọc được {len(items)} dòng:"]
    lines += [
        f"{i}. <b>{escape(it['material_name'])}</b> — {_so(it['quantity'])} {escape(it['unit'])}"
        for i, it in enumerate(items, 1)
    ]
    if sai:
        lines += ["", f"⚠️ {len(sai)} dòng sai mẫu, sẽ KHÔNG gửi:"]
        lines += [f"• {escape(d[:80])}" for d in sai]
    lines += ["", "Kiểm tra tên và số lượng. Sai thì gõ lại cả danh sách."]
    await message.answer(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=f"Gửi {len(items)} dòng", callback_data="vt_batch:send"),
            NUT_HUY,
        ]]),
    )


@router.callback_query(F.data == "vt_batch:send", VatTuState.confirm_batch)
async def cb_gui_nhieu_dong(callback: CallbackQuery, state: FSMContext):
    """Gửi lần lượt từng dòng qua đúng API một-món; một tin tổng kết, không in số tiền."""
    data = await state.get_data()
    await state.clear()  # xoá trước khi gọi API → bấm đúp không gửi hai lần
    await callback.answer("Đang gửi…")
    code, items = data.get("project_code", ""), data.get("items") or []
    tg_id = callback.from_user.id

    xong, loi, vuot = [], [], False
    for it in items:
        ten = f"{escape(it['material_name'])} — {_so(it['quantity'])} {escape(it['unit'])}"
        result = await api.create_material_request(tg_id, {
            "project_code": code, **it, "requester_tg_id": tg_id,
        })
        if not result:
            loi.append(f"• {ten}: không kết nối được server")
        elif result.get("error"):
            loi.append(f"• {ten}: {escape(str(result['error']))}")
        else:
            vuot = vuot or bool(result.get("over_budget"))
            xong.append(f"• {ten}" + (" — ⚠️ vượt định mức" if result.get("over_budget") else ""))

    lines = [f"📦 <b>Yêu cầu vật tư — {escape(code)}</b>", ""]
    if xong:
        lines += [f"✅ Đã gửi {len(xong)}/{len(items)} dòng cho Thu mua:", *xong]
    if loi:
        lines += ["", f"❌ {len(loi)} dòng CHƯA gửi được (gõ lại các dòng này):", *loi]
    if vuot:
        lines += ["", "Dòng vượt định mức cần giải trình trước khi được duyệt."]
    ban_phim = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"Thêm vật tư cho {code}", callback_data=f"vt_more:{code}"[:64]),
    ]])
    try:
        await callback.message.edit_text("\n".join(lines), reply_markup=ban_phim)
    except Exception:
        await callback.message.answer("\n".join(lines), reply_markup=ban_phim)


@router.callback_query(F.data == "vt_batch:send")
async def cb_gui_nhieu_dong_cu(callback: CallbackQuery):
    """Nút trên tin cũ: danh sách đã gửi / đã hủy / đã bị thay."""
    await callback.answer("Danh sách này đã gửi hoặc đã hủy. Gõ /vatlieu để tạo lại.", show_alert=True)


@router.callback_query(F.data.startswith("vt_more:"))
async def cb_them_vat_tu(callback: CallbackQuery, state: FSMContext):
    """«Thêm vật tư cho <MÃ>» — hỏi tiếp cho đúng dự án, khỏi chọn lại."""
    code = callback.data.split(":", 1)[1]
    await callback.answer()
    if not code:
        return
    await state.clear()
    await hoi_vat_tu(callback.message, state, code)


async def gui_vat_tu(message: types.Message, tg_id: int, text: str):
    """Gửi yêu cầu vật tư từ chuỗi «MÃ Tên - SL đơn vị»."""
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
        "requester_tg_id": tg_id,
    }

    result = await api.create_material_request(tg_id, request_data)

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
