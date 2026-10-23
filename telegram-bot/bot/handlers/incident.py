"""/suco handler — incident reporting with photo evidence."""

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from bot.api_client import api
from bot.keyboards import hien_ban_phim, nut_gui_anh, nut_huy

router = Router()


class IncidentState(StatesGroup):
    """FSM states for incident report with photo evidence."""
    waiting_description = State()
    collecting_photos = State()


# ---------------------------------------------------------------------------
# /suco — Report incident
# ---------------------------------------------------------------------------

@router.message(Command("suco"))
async def cmd_suco(message: types.Message, state: FSMContext):
    """Không tham số → bàn phím chọn dự án; kèm mã (+ mô tả) → vào luồng."""
    args = (message.text or message.caption or "").split(maxsplit=2)
    if len(args) < 2:
        await hien_ban_phim(message, message.from_user.id, "suco")
        return
    await bat_dau_su_co(
        message, state, args[1].strip().upper(), args[2].strip() if len(args) > 2 else "",
    )


async def bat_dau_su_co(message: types.Message, state: FSMContext, project_code: str, description: str = ""):
    if not description:
        await state.update_data(project_code=project_code)
        await state.set_state(IncidentState.waiting_description)
        await message.answer(
            f"🚨 <b>Báo cáo sự cố — {project_code}</b>\n\n"
            "Gõ mô tả sự cố (ở đâu, hư hỏng gì).",
            reply_markup=nut_huy(),
        )
        return
    await _xin_anh(message, state, project_code, description)


async def _xin_anh(message: types.Message, state: FSMContext, project_code: str, description: str):
    await state.update_data(project_code=project_code, incident_description=description, photos=[])
    await state.set_state(IncidentState.collecting_photos)
    await message.answer(
        f"🚨 <b>Báo cáo sự cố — {project_code}</b>\n\n"
        f"Mô tả: {description}\n"
        f"Mức độ: <b>Cao</b> (mặc định)\n\n"
        "📸 Gửi ảnh bằng chứng (gửi nhiều ảnh được), xong bấm <b>✅ Gửi</b>.",
        reply_markup=nut_gui_anh(),
    )


@router.message(IncidentState.waiting_description, F.text)
async def process_incident_description(message: types.Message, state: FSMContext):
    """Receive incident description text."""
    text = message.text
    if text.startswith("/"):
        return
    data = await state.get_data()
    await _xin_anh(message, state, data.get("project_code", ""), text)


@router.message(IncidentState.collecting_photos, F.photo)
async def collect_incident_photo(message: types.Message, state: FSMContext):
    """Ảnh bằng chứng → Kho ảnh (nội bộ, không chia sẻ khách); giữ media_id."""
    data = await state.get_data()
    photos = data.get("photos", [])  # media_id trong Kho ảnh
    photo = message.photo[-1]  # cỡ lớn nhất
    res = await api.media_from_telegram(message.from_user.id, {
        "file_id": photo.file_id,
        "file_unique_id": photo.file_unique_id,
        "project_code": data.get("project_code"),
        "kind": "su_co",
        "caption": (message.caption or data.get("incident_description") or "")[:300] or None,
    })
    if not res or res.get("error"):
        loi = res.get("error") if res else "Không kết nối được server"
        await message.answer(
            f"⚠️ Ảnh chưa lưu được: {loi}\nGửi lại ảnh, hoặc bấm ✅ Gửi để báo không ảnh.",
            reply_markup=nut_gui_anh(),
        )
        return
    if res["id"] not in photos:
        photos.append(res["id"])

    await state.update_data(photos=photos)
    await message.answer(
        f"✅ Đã nhận ảnh bằng chứng ({len(photos)} ảnh). Gửi thêm hoặc bấm <b>✅ Gửi</b>.",
        reply_markup=nut_gui_anh(),
    )


@router.message(IncidentState.collecting_photos, Command("done"))
async def finish_incident_report(message: types.Message, state: FSMContext):
    """/done — vẫn nhận cho người quen gõ lệnh."""
    await gui_su_co(message, state, message.from_user.id)


async def gui_su_co(message: types.Message, state: FSMContext, tg_id: int):
    """Gửi báo cáo sự cố (nút ✅ Gửi hoặc /done)."""
    data = await state.get_data()
    project_code = data.get("project_code", "")
    description = data.get("incident_description", "")
    photos = data.get("photos", [])

    if not description:
        await message.answer("❌ Mô tả sự cố trống. Hãy thử lại.")
        await state.clear()
        return

    await message.answer("🔄 Đang gửi báo cáo sự cố...")

    incident_data = {
        "project_code": project_code,
        "description": description,
        "severity": "high",
        "reporter_tg_id": tg_id,
        "media_ids": photos,
    }

    result = await api.report_incident(tg_id, incident_data)

    if not result:
        await message.answer("❌ Không kết nối được server. Vui lòng thử lại.")
        await state.clear()
        return

    if result.get("error"):
        await message.answer(f"❌ <b>Lỗi:</b> {result['error']}")
        await state.clear()
        return

    # Build success message
    severity = result.get("severity", "high")
    severity_labels = {
        "low": "Thap",
        "medium": "Trung binh",
        "high": "Cao",
        "critical": "Khan cap",
    }
    severity_label = severity_labels.get(severity, severity)

    assigned = result.get("assigned_to")
    photo_info = f"\n📸 Ảnh bằng chứng: {len(photos)} ảnh" if photos else ""

    lines = [
        f"🚨 <b>Sự cố đã được ghi nhận!</b>\n",
        f"🏗 Dự án: <code>{result.get('project_code', project_code)}</code>",
        f"📋 Đầu việc: {result.get('task_title', '—')}",
        f"⚡ Mức độ: <b>{severity_label}</b>",
        f"👤 Người phát hiện: {result.get('reporter', '—')}",
        f"🕐 Thời gian: {result.get('created_at', '—')}",
    ]

    if assigned:
        lines.append("👨‍💻 <b>Thiết kế đã được tag trực tiếp.</b>")

    if photos:
        lines.append(photo_info)

    lines.append(f"\n📝 {result.get('message', '')}")

    await message.answer("\n".join(lines))
    await state.clear()


@router.message(IncidentState.collecting_photos, F.text & ~F.command("done") & ~F.command("cancel"))
async def wrong_input_incident(message: types.Message):
    """Handle wrong input during photo collection."""
    await message.answer(
        "⚠️ Gửi ảnh bằng chứng, hoặc bấm <b>✅ Gửi</b> để hoàn tất.",
        reply_markup=nut_gui_anh(),
    )
