"""/dutoan handlers — estimation (du toan) workflow for field workers."""

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from bot.api_client import api

router = Router()


class DutoanState(StatesGroup):
    """FSM states for estimation workflow."""
    choosing_method = State()
    input_so_lieu = State()
    input_mo_ta = State()
    input_hinh_anh = State()
    confirming = State()


# ---------------------------------------------------------------------------
# /dutoan — Entry point: list, detail, or start new
# ---------------------------------------------------------------------------

@router.message(Command("dutoan"))
async def cmd_dutoan(message: types.Message, state: FSMContext):
    """Entry: /dutoan, /dutoan list, /dutoan [id]."""
    args = message.text.split(maxsplit=1)

    # /dutoan list
    if len(args) > 1 and args[1].strip().lower() == "list":
        await _list_estimations(message)
        return

    # /dutoan [id]
    if len(args) > 1:
        est_id = args[1].strip()
        await _get_estimation(message, est_id)
        return

    # Start new estimation workflow
    await message.answer(
        "📐 <b>Tạo dự toán mới</b>\n\n"
        "Bước 1: Nhập mã dự án.\n"
        "Ví dụ: <code>JMH-0601</code>\n\n"
        "💡 <i>Gửi /cancel để hủy</i>"
    )
    await state.set_state(DutoanState.choosing_method)
    # We'll collect project_code first, then move to choosing_method
    await state.update_data(_step="project_code")


# ---------------------------------------------------------------------------
# Step 1: Collect project code
# ---------------------------------------------------------------------------

@router.message(DutoanState.choosing_method, F.text)
async def process_project_code(message: types.Message, state: FSMContext):
    """Collect project code, then ask for input method."""
    text = message.text.strip()
    if text.startswith("/"):
        if text == "/cancel":
            await state.clear()
            await message.answer("Da huy tao du toan.")
        return

    data = await state.get_data()
    step = data.get("_step")

    if step == "project_code":
        project_code = text.upper()
        await state.update_data(project_code=project_code, _step="method")
        await message.answer(
            f"📐 <b>Du toan cho: {project_code}</b>\n\n"
            "Chon cach nhap du lieu:\n"
            "1️⃣ <b>So lieu</b> — Nhap chi tiet so luong tung mon\n"
            "2️⃣ <b>Mo ta</b> — Mo ta bang van ban\n"
            "3️⃣ <b>Hinh anh</b> — Gui anh minh hoa + van ban\n\n"
            "Gui so <code>1</code>, <code>2</code>, hoac <code>3</code>.\n"
            "💡 <i>Gửi /cancel để hủy</i>"
        )
        return

    if step == "method":
        choice = text.strip()
        if choice == "1":
            await state.set_state(DutoanState.input_so_lieu)
            await state.update_data(input_method="so_lieu", items=[])
            await message.answer(
                "📊 <b>Nhap so lieu du toan</b>\n\n"
                "Nhap tung mon theo dinh dang:\n"
                "<code>Go Oc Cho 20m2, Kinh 15m2, Da 30m2</code>\n\n"
                "Hoac nhap tung dong:\n"
                "<code>Go Oc Cho 20m2</code>\n"
                "<code>Kinh 15m2</code>\n\n"
                "Gửi /done khi xong.\n"
                "💡 <i>Gửi /cancel để hủy</i>"
            )
        elif choice == "2":
            await state.set_state(DutoanState.input_mo_ta)
            await state.update_data(input_method="mo_ta")
            await message.answer(
                "📝 <b>Nhap mo ta du toan</b>\n\n"
                "Viet mo ta chi tiet ve hang muc can du toan.\n\n"
                "💡 <i>Gửi /cancel để hủy</i>"
            )
        elif choice == "3":
            await state.set_state(DutoanState.input_hinh_anh)
            await state.update_data(input_method="hinh_anh", photos=[], text_description="")
            await message.answer(
                "📸 <b>Gui hinh anh du toan</b>\n\n"
                "Gui anh minh hoa hang muc can du toan.\n"
                "Co the gui nhieu anh, sau do gui van ban mo ta.\n\n"
                "💡 <i>Gửi /cancel để hủy</i>"
            )
        else:
            await message.answer("Vui long chon 1, 2, hoac 3.")


# ---------------------------------------------------------------------------
# Step 3a: So lieu — collect quantities
# ---------------------------------------------------------------------------

@router.message(DutoanState.input_so_lieu, F.text)
async def process_so_lieu(message: types.Message, state: FSMContext):
    """Collect quantity items."""
    text = message.text.strip()
    if text.startswith("/"):
        if text == "/cancel":
            await state.clear()
            await message.answer("Da huy tao du toan.")
            return
        if text == "/done":
            data = await state.get_data()
            items = data.get("items", [])
            if not items:
                await message.answer("Chua co mon nao. Vui long nhap it nhat 1 mon.")
                return
            await _show_preview(message, state, data)
            return

    # Parse items — "Go Oc Cho 20m2, Kinh 15m2" or one per line
    raw_items = text.replace("\n", ",").split(",")
    data = await state.get_data()
    items = data.get("items", [])

    for raw in raw_items:
        raw = raw.strip()
        if raw:
            items.append(raw)

    await state.update_data(items=items)
    count = len(items)
    await message.answer(
        f"Da nhan {count} mon. Gui them hoac gui <code>/done</code> de xem preview."
    )


# ---------------------------------------------------------------------------
# Step 3b: Mo ta — text description
# ---------------------------------------------------------------------------

@router.message(DutoanState.input_mo_ta, F.text)
async def process_mo_ta(message: types.Message, state: FSMContext):
    """Collect text description."""
    text = message.text.strip()
    if text.startswith("/"):
        if text == "/cancel":
            await state.clear()
            await message.answer("Da huy tao du toan.")
            return

    await state.update_data(description=text)
    data = await state.get_data()
    await _show_preview(message, state, data)


# ---------------------------------------------------------------------------
# Step 3c: Hinh anh — photos + text
# ---------------------------------------------------------------------------

@router.message(DutoanState.input_hinh_anh, F.photo)
async def collect_hinh_anh(message: types.Message, state: FSMContext):
    """Collect photos for estimation."""
    data = await state.get_data()
    photos = data.get("photos", [])
    photo = message.photo[-1]
    photos.append(photo.file_id)
    await state.update_data(photos=photos)
    await message.answer(
        f"Da nhan anh ({len(photos)} anh). Gui them anh hoac gui van ban mo ta."
    )


@router.message(DutoanState.input_hinh_anh, F.text)
async def process_hinh_anh_text(message: types.Message, state: FSMContext):
    """Receive text description after photos."""
    text = message.text.strip()
    if text.startswith("/"):
        if text == "/cancel":
            await state.clear()
            await message.answer("Da huy tao du toan.")
            return
        if text == "/done":
            data = await state.get_data()
            if not data.get("photos"):
                await message.answer("Vui long gui it nhat 1 anh truoc.")
                return
            await _show_preview(message, state, data)
            return

    await state.update_data(text_description=text)
    data = await state.get_data()
    photos = data.get("photos", [])
    if not photos:
        await message.answer("Vui long gui it nhat 1 anh truoc, hoac gui <code>/done</code> neu chi co van ban.")
        return
    await _show_preview(message, state, data)


# ---------------------------------------------------------------------------
# Step 4: Preview + Confirm
# ---------------------------------------------------------------------------

async def _show_preview(message: types.Message, state: FSMContext, data: dict):
    """Show estimation preview and ask for confirmation."""
    project_code = data.get("project_code", "?")
    method = data.get("input_method", "?")

    method_labels = {"so_lieu": "So lieu", "mo_ta": "Mo ta", "hinh_anh": "Hinh anh"}
    method_label = method_labels.get(method, method)

    lines = [
        "📋 <b>Preview du toan</b>",
        f"🏗 Du an: <code>{project_code}</code>",
        f"📝 Phuong phap: {method_label}",
        "",
    ]

    if method == "so_lieu":
        items = data.get("items", [])
        lines.append("📊 Hang muc:")
        for i, item in enumerate(items, 1):
            lines.append(f"  {i}. {item}")
    elif method == "mo_ta":
        lines.append(f"📝 Mo ta:\n{data.get('description', '')}")
    elif method == "hinh_anh":
        photos = data.get("photos", [])
        lines.append(f"📸 So anh: {len(photos)}")
        desc = data.get("text_description", "")
        if desc:
            lines.append(f"📝 Mo ta: {desc}")

    lines.extend([
        "",
        "Gui <code>/confirm</code> de gui du toan.\n"
        "Gui <code>/cancel</code> de huy.",
    ])

    await state.set_state(DutoanState.confirming)
    await message.answer("\n".join(lines))


@router.message(DutoanState.confirming, Command("confirm"))
async def confirm_estimation(message: types.Message, state: FSMContext):
    """Submit estimation to backend."""
    data = await state.get_data()

    payload = {
        "project_code": data.get("project_code"),
        "input_method": data.get("input_method"),
        "reporter_tg_id": message.from_user.id,
    }

    method = data.get("input_method")
    if method == "so_lieu":
        payload["items"] = data.get("items", [])
    elif method == "mo_ta":
        payload["description"] = data.get("description", "")
    elif method == "hinh_anh":
        payload["photos"] = data.get("photos", [])
        payload["text_description"] = data.get("text_description", "")

    await message.answer("Dang gui du toan...")

    result = await api.create_estimation(message.from_user.id, payload)

    if result and not result.get("error"):
        est_id = result.get("id", "?")
        await message.answer(
            f"✅ <b>Du toan da duoc gui thanh cong!</b>\n\n"
            f"🆔 Ma: <code>{est_id}</code>\n"
            f"🏗 Du an: <code>{data.get('project_code')}</code>\n"
            f"📝 Phuong phap: {result.get('input_method', method)}\n"
            f"🕐 Thoi gian: {result.get('created_at', '?')}\n\n"
            f"Xem lai: <code>/dutoan {est_id}</code>"
        )
    else:
        error_msg = result.get("error", "Khong ro loi") if result else "Khong ket noi duoc server"
        await message.answer(f"❌ <b>Loi gui du toan:</b> {error_msg}")

    await state.clear()


# ---------------------------------------------------------------------------
# /dutoan list — list recent estimations
# ---------------------------------------------------------------------------

async def _list_estimations(message: types.Message):
    """List recent estimations for current user."""
    result = await api.list_estimations(message.from_user.id)

    if not result:
        await message.answer("Khong the lay danh sach du toan. Vui long thu lai.")
        return

    estimations = result if isinstance(result, list) else result.get("items", [])

    if not estimations:
        await message.answer(
            "📋 <b>Chua co du toan nao.</b>\n\n"
            "Gui <code>/dutoan</code> de tao du toan moi."
        )
        return

    lines = ["📋 <b>Du toan gan day</b>\n"]
    for est in estimations[:10]:
        est_id = est.get("id", "?")
        project = est.get("project_code", "?")
        method = est.get("input_method", "?")
        created = est.get("created_at", "?")
        lines.append(
            f"• <code>{est_id}</code> | {project} | {method} | {created}"
        )

    lines.append("\nXem chi tiet: <code>/dutoan [ma]</code>")
    await message.answer("\n".join(lines))


# ---------------------------------------------------------------------------
# /dutoan [id] — view detail
# ---------------------------------------------------------------------------

async def _get_estimation(message: types.Message, est_id: str):
    """View estimation detail."""
    result = await api.get_estimation(message.from_user.id, est_id)

    if not result:
        await message.answer(
            f"Khong tim thay du toan <code>{est_id}</code>."
        )
        return

    project = result.get("project_code", "?")
    method = result.get("input_method", "?")
    created = result.get("created_at", "?")
    reporter = result.get("reporter", "?")
    status = result.get("status", "?")

    lines = [
        f"📐 <b>Chi tiet du toan</b>",
        f"🆔 Ma: <code>{result.get('id', est_id)}</code>",
        f"🏗 Du an: <code>{project}</code>",
        f"📝 Phuong phap: {method}",
        f"👤 Nguoi tao: {reporter}",
        f"📊 Trang thai: {status}",
        f"🕐 Tao luc: {created}",
        "",
    ]

    if method == "so_lieu":
        items = result.get("items", [])
        if items:
            lines.append("📊 Hang muc:")
            for i, item in enumerate(items, 1):
                if isinstance(item, dict):
                    lines.append(f"  {i}. {item.get('name', '?')} — {item.get('quantity', '?')}")
                else:
                    lines.append(f"  {i}. {item}")
    elif method == "mo_ta":
        desc = result.get("description", "")
        if desc:
            lines.append(f"📝 Mo ta:\n{desc}")
    elif method == "hinh_anh":
        photos = result.get("photos", [])
        lines.append(f"📸 So anh: {len(photos)}")
        text_desc = result.get("text_description", "")
        if text_desc:
            lines.append(f"📝 Mo ta: {text_desc}")

    await message.answer("\n".join(lines))
