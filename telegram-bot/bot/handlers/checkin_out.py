"""/checkin and /checkout handlers — GPS location-based attendance."""

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from bot.api_client import api
from bot.keyboards import hien_ban_phim

router = Router()


def _ban_phim_vi_tri() -> types.ReplyKeyboardMarkup:
    return types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="📍 Gửi vị trí hiện tại", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _can_gps(loi) -> bool:
    """Backend báo thiếu GPS khi vào ca văn phòng (bán kính VP)."""
    return "Cần bật vị trí" in str(loi or "")


async def _bao_vao_ca_van_phong(message: types.Message, result: dict) -> None:
    await message.answer(
        f"✅ <b>{result.get('message', 'Điểm danh thành công!')}</b>\n\n"
        f"👤 {result.get('user', '—')} · 🕐 {str(result.get('checkin_time', ''))[:16]}\n\n"
        f"💡 Tại công trình? Dùng <code>/checkin [Mã dự án]</code> để điểm danh kèm GPS."
    )


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
    """Không tham số: có dự án → bàn phím (🏢 Văn phòng + dự án), không có → vào
    ca văn phòng luôn; kèm mã dự án = công trình (GPS)."""
    args = (message.text or message.caption or "").split(maxsplit=1)

    if len(args) < 2:
        if not await hien_ban_phim(message, message.from_user.id, "checkin", van_phong=True):
            await vao_ca_van_phong(message, state, message.from_user)
        return
    await xin_vi_tri(message, state, args[1].strip().upper())


async def vao_ca_van_phong(message: types.Message, state: FSMContext, user: types.User):
    """Chấm công văn phòng — thử trước không GPS; backend đòi thì xin vị trí."""
    await api.authenticate(user.id, user.username)
    result = await api.office_checkin(user.id)
    if not result:
        await message.answer("❌ Không kết nối được server. Vui lòng thử lại.")
        return
    if result.get("error"):
        if _can_gps(result["error"]):
            await state.update_data(project_code="")
            await state.set_state(CheckinState.waiting_location)
            await message.answer(
                "📍 <b>Vào ca văn phòng</b>\n\n"
                "Cần vị trí GPS để xác nhận bạn đang ở văn phòng.\n"
                "Nhấn nút <b>\"Gửi vị trí hiện tại\"</b> bên dưới.\n\n"
                "💡 <i>Gửi /cancel để hủy</i>",
                reply_markup=_ban_phim_vi_tri(),
            )
            return
        await message.answer(f"❌ {result['error']}")
        return
    await _bao_vao_ca_van_phong(message, result)


async def xin_vi_tri(message: types.Message, state: FSMContext, project_code: str, ra_ca: bool = False):
    """Điểm danh / tan ca tại công trình: xin GPS bằng nút gửi vị trí."""
    await state.update_data(project_code=project_code)
    keyboard = _ban_phim_vi_tri()
    if ra_ca:
        await state.set_state(CheckoutState.waiting_location)
        await message.answer(
            f"📍 <b>Tan ca — {project_code}</b>\n\n"
            "Vui lòng chia sẻ vị trí GPS khi rời công trình.\n"
            "Nhấn nút <b>\"Gửi vị trí hiện tại\"</b> bên dưới.\n\n"
            "💡 <i>Gửi /cancel để hủy</i>",
            reply_markup=keyboard,
        )
        return

    await state.set_state(CheckinState.waiting_location)
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

    if not project_code:
        # Vào ca văn phòng kèm GPS (backend kiểm bán kính)
        result = await api.office_checkin(message.from_user.id, latitude, longitude)
        await state.clear()
        if not result:
            await message.answer("❌ Không kết nối được server. Vui lòng thử lại.")
            return
        if result.get("error"):
            await message.answer(f"❌ {result['error']}")
            return
        await _bao_vao_ca_van_phong(message, result)
        return

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
    """Tan ca: không tham số = bàn phím (hoặc văn phòng); kèm mã dự án = công trình."""
    args = (message.text or message.caption or "").split(maxsplit=1)

    if len(args) < 2:
        if not await hien_ban_phim(message, message.from_user.id, "checkout", van_phong=True):
            await tan_ca_van_phong(message, message.from_user)
        return
    await xin_vi_tri(message, state, args[1].strip().upper(), ra_ca=True)


async def tan_ca_van_phong(message: types.Message, user: types.User):
    await api.authenticate(user.id, user.username)
    result = await api.office_checkout(user.id)
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
