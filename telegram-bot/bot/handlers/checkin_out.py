"""/checkin and /checkout handlers — GPS location-based attendance."""

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from bot.api_client import api

router = Router()


class CheckinState(StatesGroup):
    """FSM states for GPS check-in flow."""
    waiting_location = State()


class CheckoutState(StatesGroup):
    """FSM states for GPS check-out flow."""
    waiting_location = State()


@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Đã hủy. Gõ lệnh để bắt đầu lại.")


# ---------------------------------------------------------------------------
# /checkin — GPS check-in at project site
# ---------------------------------------------------------------------------

@router.message(Command("checkin"))
async def cmd_checkin(message: types.Message, state: FSMContext):
    """Điểm danh: không tham số = văn phòng; kèm mã dự án = công trình (GPS)."""
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        # Chấm công văn phòng — không cần GPS
        await api.authenticate(message.from_user.id, message.from_user.username)
        result = await api.office_checkin(message.from_user.id)
        if not result:
            await message.answer("❌ Không kết nối được server. Vui lòng thử lại.")
            return
        if result.get("error"):
            await message.answer(f"❌ {result['error']}")
            return
        await message.answer(
            f"✅ <b>{result.get('message', 'Điểm danh thành công!')}</b>\n\n"
            f"👤 {result.get('user', '—')} · 🕐 {str(result.get('checkin_time', ''))[:16]}\n\n"
            f"💡 Tại công trình? Dùng <code>/checkin [Mã dự án]</code> để điểm danh kèm GPS."
        )
        return

    project_code = args[1].strip().upper()

    await state.update_data(project_code=project_code)
    await state.set_state(CheckinState.waiting_location)

    # Build keyboard with location request
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [
                types.KeyboardButton(
                    text="📍 Gửi vị trí hiện tại",
                    request_location=True,
                ),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

    await message.answer(
        f"📍 <b>Điểm danh — {project_code}</b>\n\n"
        "Vui lòng chia sẻ vị trí GPS của bạn.\n"
        "Nhấn nút <b>\"Gửi vị trí hiện tại\"</b> bên dưới.\n\n"
        "💡 <i>Gửi /cancel để hủy</i>",
        reply_markup=keyboard,
    )


@router.message(CheckinState.waiting_location, F.location)
async def process_checkin_location(message: types.Message, state: FSMContext):
    """Receive GPS location and submit check-in."""
    data = await state.get_data()
    project_code = data.get("project_code", "")

    latitude = message.location.latitude
    longitude = message.location.longitude

    await message.answer(
        "🔄 Đang điểm danh...",
        reply_markup=types.ReplyKeyboardRemove(),
    )

    checkin_data = {
        "project_code": project_code,
        "latitude": latitude,
        "longitude": longitude,
        "user_tg_id": message.from_user.id,
    }

    result = await api.checkin(message.from_user.id, checkin_data)

    if not result:
        await message.answer("❌ Không kết nối được server. Vui lòng thử lại.")
        await state.clear()
        return

    if result.get("error"):
        await message.answer(f"❌ <b>Lỗi điểm danh:</b> {result['error']}")
        await state.clear()
        return

    await message.answer(
        f"✅ <b>Điểm danh thành công!</b>\n\n"
        f"🏗 Dự án: <code>{result.get('project_code', project_code)}</code>\n"
        f"👤 Nhân viên: {result.get('user', '—')}\n"
        f"📍 Vị trí: ({result.get('latitude', latitude)}, {result.get('longitude', longitude)})\n"
        f"🕐 Thời gian: {result.get('checkin_time', '—')}\n\n"
        f"📝 {result.get('message', '')}"
    )
    await state.clear()


@router.message(CheckinState.waiting_location, F.text & ~F.command("cancel"))
async def wrong_input_checkin(message: types.Message):
    """Handle wrong input during location request."""
    await message.answer(
        "⚠️ Vui lòng nhấn nút <b>\"Gửi vị trí hiện tại\"</b> để chia sẻ GPS.\n"
        "💡 <i>Gửi /cancel để hủy</i>"
    )


# ---------------------------------------------------------------------------
# /checkout — GPS check-out from project site
# ---------------------------------------------------------------------------

@router.message(Command("checkout"))
async def cmd_checkout(message: types.Message, state: FSMContext):
    """Tan ca: không tham số = văn phòng; kèm mã dự án = công trình."""
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        await api.authenticate(message.from_user.id, message.from_user.username)
        result = await api.office_checkout(message.from_user.id)
        if not result:
            await message.answer("❌ Không kết nối được server. Vui lòng thử lại.")
            return
        if result.get("error"):
            await message.answer(f"❌ {result['error']}")
            return
        ot_line = ""
        if result.get("ot_hours"):
            ot_line = f"\n⏰ OT chờ duyệt: {result['ot_hours']}h"
        await message.answer(
            f"✅ <b>Tan ca thành công!</b>\n\n"
            f"👤 {result.get('user', '—')} · Giờ công hôm nay: <b>{result.get('work_hours', 0)}h</b>{ot_line}"
        )
        return

    project_code = args[1].strip().upper()

    await state.update_data(project_code=project_code)
    await state.set_state(CheckoutState.waiting_location)

    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [
                types.KeyboardButton(
                    text="📍 Gửi vị trí hiện tại",
                    request_location=True,
                ),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

    await message.answer(
        f"📍 <b>Tan ca — {project_code}</b>\n\n"
        "Vui lòng chia sẻ vị trí GPS khi rời công trình.\n"
        "Nhấn nút <b>\"Gửi vị trí hiện tại\"</b> bên dưới.\n\n"
        "💡 <i>Gửi /cancel để hủy</i>",
        reply_markup=keyboard,
    )


@router.message(CheckoutState.waiting_location, F.location)
async def process_checkout_location(message: types.Message, state: FSMContext):
    """Receive GPS location and submit check-out."""
    data = await state.get_data()
    project_code = data.get("project_code", "")

    await message.answer(
        "🔄 Đang tan ca...",
        reply_markup=types.ReplyKeyboardRemove(),
    )

    checkout_data = {
        "project_code": project_code,
        "user_tg_id": message.from_user.id,
    }

    result = await api.checkout(message.from_user.id, checkout_data)

    if not result:
        await message.answer("❌ Không kết nối được server. Vui lòng thử lại.")
        await state.clear()
        return

    if result.get("error"):
        await message.answer(f"❌ <b>Lỗi tan ca:</b> {result['error']}")
        await state.clear()
        return

    await message.answer(
        f"✅ <b>Tan ca thành công!</b>\n\n"
        f"🏗 Dự án: <code>{result.get('project_code', project_code)}</code>\n"
        f"👤 Nhân viên: {result.get('user', '—')}\n"
        f"🕐 Thời gian: {result.get('checkout_time', '—')}\n\n"
        f"📝 {result.get('message', '')}"
    )
    await state.clear()


@router.message(CheckoutState.waiting_location, F.text & ~F.command("cancel"))
async def wrong_input_checkout(message: types.Message):
    """Handle wrong input during location request."""
    await message.answer(
        "⚠️ Vui lòng nhấn nút <b>\"Gửi vị trí hiện tại\"</b> để chia sẻ GPS.\n"
        "💡 <i>Gửi /cancel để hủy</i>"
    )
