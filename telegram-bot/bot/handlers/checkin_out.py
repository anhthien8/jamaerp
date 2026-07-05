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


# ---------------------------------------------------------------------------
# /checkin — GPS check-in at project site
# ---------------------------------------------------------------------------

@router.message(Command("checkin"))
async def cmd_checkin(message: types.Message, state: FSMContext):
    """Start GPS check-in — request location from user."""
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        await message.answer(
            "📍 <b>Check-in công trình</b>\n\n"
            "Cách dùng:\n"
            "<code>/checkin [Mã dự án]</code>\n\n"
            "Ví dụ: <code>/checkin JMH-0601</code>\n\n"
            "💡 Bot sẽ yêu cầu vị trí GPS để check-in."
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
        f"📍 <b>Check-in — {project_code}</b>\n\n"
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
        "🔄 Đang check-in...",
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
        await message.answer(f"❌ <b>Lỗi check-in:</b> {result['error']}")
        await state.clear()
        return

    await message.answer(
        f"✅ <b>Check-in thành công!</b>\n\n"
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
    """Start GPS check-out — request location from user."""
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        await message.answer(
            "📍 <b>Check-out công trình</b>\n\n"
            "Cách dùng:\n"
            "<code>/checkout [Mã dự án]</code>\n\n"
            "Ví dụ: <code>/checkout JMH-0601</code>\n\n"
            "💡 Bot sẽ ghi nhận thời gian check-out."
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
        f"📍 <b>Check-out — {project_code}</b>\n\n"
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
        "🔄 Đang check-out...",
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
        await message.answer(f"❌ <b>Lỗi check-out:</b> {result['error']}")
        await state.clear()
        return

    await message.answer(
        f"✅ <b>Check-out thành công!</b>\n\n"
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
