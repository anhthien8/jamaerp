"""/suco handler — incident reporting with photo evidence."""

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from bot.api_client import api

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
    """Report a construction incident — parse project code + description."""
    # Expected: /suco [Mã_dự_án] [Mô_tả]
    args = message.text.split(maxsplit=2)

    if len(args) < 2:
        await message.answer(
            "🚨 <b>Báo cáo sự cố</b>\n\n"
            "Cách dùng:\n"
            "<code>/suco [Mã dự án] [Mô tả sự cố]</code>\n\n"
            "Ví dụ:\n"
            "<code>/suco JMH-0601 Trần nhà bị nứt ở block A tầng 2</code>\n\n"
            "Mức độ mặc định: <b>Cao</b>\n"
            "💡 Sau khi gửi mô tả, bạn có thể đính kèm ảnh bằng chứng."
        )
        return

    project_code = args[1].strip().upper()
    description = args[2].strip() if len(args) > 2 else ""

    if not description:
        await state.update_data(project_code=project_code)
        await state.set_state(IncidentState.waiting_description)
        await message.answer(
            f"🚨 <b>Báo cáo sự cố — {project_code}</b>\n\n"
            "Vui lòng mô tả sự cố:\n"
            "💡 <i>Gửi /cancel để hủy</i>"
        )
        return

    # Has description — start collecting photos
    await state.update_data(
        project_code=project_code,
        incident_description=description,
        photos=[],
    )
    await state.set_state(IncidentState.collecting_photos)
    await message.answer(
        f"🚨 <b>Báo cáo sự cố — {project_code}</b>\n\n"
        f"Mô tả: {description}\n"
        f"Mức độ: <b>Cao</b> (mặc định)\n\n"
        "📸 Gửi ảnh bằng chứng (có thể gửi nhiều ảnh).\n"
        "Khi xong, gửi <code>/done</code> để hoàn tất.\n"
        "💡 <i>Gửi /cancel để hủy</i>"
    )


@router.message(IncidentState.waiting_description, F.text)
async def process_incident_description(message: types.Message, state: FSMContext):
    """Receive incident description text."""
    text = message.text
    if text.startswith("/"):
        if text == "/cancel":
            await state.clear()
            await message.answer("🚫 Đã hủy báo cáo sự cố.")
        return

    data = await state.get_data()
    project_code = data.get("project_code", "")

    await state.update_data(incident_description=text, photos=[])
    await state.set_state(IncidentState.collecting_photos)
    await message.answer(
        f"🚨 <b>Báo cáo sự cố — {project_code}</b>\n\n"
        f"Mô tả: {text}\n"
        f"Mức độ: <b>Cao</b> (mặc định)\n\n"
        "📸 Gửi ảnh bằng chứng (có thể gửi nhiều ảnh).\n"
        "Khi xong, gửi <code>/done</code> để hoàn tất.\n"
        "💡 <i>Gửi /cancel để hủy</i>"
    )


@router.message(IncidentState.collecting_photos, F.photo)
async def collect_incident_photo(message: types.Message, state: FSMContext):
    """Collect photos as evidence for the incident."""
    data = await state.get_data()
    photos = data.get("photos", [])

    # Use the largest available photo size
    photo = message.photo[-1]
    photos.append(photo.file_id)

    await state.update_data(photos=photos)
    await message.answer(
        f"✅ Đã nhận ảnh bằng chứng ({len(photos)} ảnh).\n"
        "Gửi thêm ảnh hoặc gửi <code>/done</code> để hoàn tất."
    )


@router.message(IncidentState.collecting_photos, Command("done"))
async def finish_incident_report(message: types.Message, state: FSMContext):
    """Submit the incident report to the backend."""
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
        "reporter_tg_id": message.from_user.id,
        "photos": photos,
    }

    result = await api.report_incident(message.from_user.id, incident_data)

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
        "⚠️ Vui lòng gửi ảnh bằng chứng hoặc gõ <code>/done</code> để hoàn tất.\n"
        "💡 <i>Gửi /cancel để hủy</i>"
    )
