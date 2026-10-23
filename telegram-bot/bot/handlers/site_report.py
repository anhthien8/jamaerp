"""/duan and /baocao handlers — project lookup + site reports with photos."""

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from bot.api_client import api
from bot.keyboards import hien_ban_phim, nut_gui_anh, nut_huy

router = Router()


class SiteReportState(StatesGroup):
    """FSM states for multi-step site report flow."""
    waiting_content = State()
    collecting_photos = State()


# ---------------------------------------------------------------------------
# /duan — Quick project lookup
# ---------------------------------------------------------------------------

@router.message(Command("duan"))
async def cmd_duan(message: types.Message):
    """Không tham số → bàn phím chọn dự án; kèm mã → tra luôn."""
    args = (message.text or message.caption or "").split(maxsplit=1)
    if len(args) < 2:
        await hien_ban_phim(message, message.from_user.id, "duan")
        return
    await hien_du_an(message, message.from_user.id, args[1].strip().upper())


async def hien_du_an(message: types.Message, tg_id: int, project_code: str):
    """Thông tin + tiến độ dự án (dùng chung cho lệnh gõ tay và nút bấm)."""
    await message.answer("🔄 Đang tra cứu dự án...")

    result = await api.get_project(tg_id, project_code)

    if not result:
        await message.answer(
            f"❌ Không tìm thấy dự án <code>{project_code}</code>.\n"
            "Vui lòng kiểm tra lại mã dự án."
        )
        return

    project = result.get("project", {})
    tasks = result.get("tasks_summary", {})
    team = result.get("team", {})

    # Format status labels
    status_map = {
        "planning": "Chuan bi",
        "in_progress": "Dang thuc hien",
        "completed": "Hoan thanh",
        "on_hold": "Tam dung",
    }
    status_label = status_map.get(project.get("status", ""), project.get("status", "—"))

    # Format currency
    total_value = project.get("total_value") or 0
    spent = project.get("spent") or 0
    budget_text = _format_value(total_value)
    spent_text = _format_value(spent)

    # Task progress bar
    total_tasks = tasks.get("total", 0)
    done_tasks = tasks.get("done", 0)
    in_progress = tasks.get("in_progress", 0)
    progress_pct = project.get("progress") or 0
    bar_len = min(int(progress_pct / 10), 10)
    progress_bar = f"{'█' * bar_len}{'░' * (10 - bar_len)} {progress_pct}%"

    lines = [
        f"🏗 <b>{project.get('code', '')} — {project.get('name', '')}</b>\n",
        f"👤 Khách hàng: <b>{project.get('client_name', '—')}</b>",
        f"📱 SĐT: {project.get('client_phone', '—')}",
        f"📍 Địa chỉ: {project.get('address', '—')}",
        f"📌 Trạng thái: <b>{status_label}</b>",
        f"🏗 Giai đoạn: {project.get('stage', '—')}",
        "",
        f"📊 <b>Tiến độ:</b>",
        f"<code>{progress_bar}</code>",
        f"• Tổng đầu việc: {total_tasks}",
        f"• Đã hoàn thành: {done_tasks}",
        f"• Đang thực hiện: {in_progress}",
        f"• Còn lại: {tasks.get('remaining', 0)}",
        "",
        f"💰 <b>Ngân sách:</b>",
        f"• Tổng: {budget_text}",
        f"• Đã sử dụng: {spent_text}",
    ]

    # Team info
    pm_name = team.get("pm_name")
    designer_name = team.get("designer_name")
    sales_name = team.get("sales_name")
    if any([pm_name, designer_name, sales_name]):
        lines.append("")
        lines.append("👥 <b>Đội ngũ:</b>")
        if pm_name:
            lines.append(f"• PM: {pm_name}")
        if designer_name:
            lines.append(f"• Thiết kế: {designer_name}")
        if sales_name:
            lines.append(f"• Kinh doanh: {sales_name}")

    await message.answer("\n".join(lines))


# ---------------------------------------------------------------------------
# /baocao — Site report with optional photo attachment
# ---------------------------------------------------------------------------

@router.message(Command("baocao"))
async def cmd_baocao(message: types.Message, state: FSMContext):
    """Không tham số → bàn phím chọn dự án; kèm mã (+ nội dung) → vào luồng."""
    # Gửi ảnh kèm chú thích "/baocao ..." thì text rỗng, lệnh nằm ở caption
    args = (message.text or message.caption or "").split(maxsplit=2)
    if len(args) < 2:
        await hien_ban_phim(message, message.from_user.id, "baocao")
        return
    await bat_dau_bao_cao(
        message, state, args[1].strip().upper(), args[2].strip() if len(args) > 2 else "",
    )


async def bat_dau_bao_cao(message: types.Message, state: FSMContext, project_code: str, content: str = ""):
    if not content:
        await state.update_data(project_code=project_code)
        await state.set_state(SiteReportState.waiting_content)
        await message.answer(
            f"📝 <b>Báo cáo cho dự án {project_code}</b>\n\n"
            "Gõ nội dung báo cáo (hôm nay làm được gì, vướng gì).",
            reply_markup=nut_huy(),
        )
        return

    await state.update_data(project_code=project_code, report_content=content, photos=[], media_ids=[])
    await state.set_state(SiteReportState.collecting_photos)
    await message.answer(
        f"📝 <b>Báo cáo cho dự án {project_code}</b>\n\n"
        f"Nội dung: {content}\n\n"
        "📸 Gửi ảnh hiện trường (gửi nhiều ảnh được), xong bấm <b>✅ Gửi</b>.",
        reply_markup=nut_gui_anh(),
    )


@router.message(SiteReportState.waiting_content, F.text)
async def process_report_content(message: types.Message, state: FSMContext):
    """Receive report content text."""
    text = message.text
    if text.startswith("/"):
        return

    await state.update_data(report_content=text, photos=[], media_ids=[])
    await state.set_state(SiteReportState.collecting_photos)
    await message.answer(
        "📸 Gửi ảnh hiện trường (gửi nhiều ảnh được), xong bấm <b>✅ Gửi</b>.\n"
        "Không có ảnh thì bấm <b>✅ Gửi</b> luôn.",
        reply_markup=nut_gui_anh(),
    )


@router.message(SiteReportState.collecting_photos, F.photo)
async def collect_photo(message: types.Message, state: FSMContext):
    """Nhận ảnh → lưu ngay vào Kho ảnh (topic dự án), giữ lại media_id."""
    data = await state.get_data()
    media_ids = data.get("media_ids", [])
    photo = message.photo[-1]  # cỡ lớn nhất
    res = await api.media_from_telegram(message.from_user.id, {
        "file_id": photo.file_id,
        "file_unique_id": photo.file_unique_id,
        "project_code": data.get("project_code"),
        "kind": "tien_do",
        "caption": (message.caption or data.get("report_content") or "")[:300] or None,
    })
    if not res or res.get("error"):
        loi = res.get("error") if res else "Không kết nối được server"
        await message.answer(
            f"⚠️ Ảnh chưa lưu được: {loi}\nGửi lại ảnh, hoặc bấm ✅ Gửi để gửi báo cáo không ảnh.",
            reply_markup=nut_gui_anh(),
        )
        return
    if res["id"] not in media_ids:
        media_ids.append(res["id"])
    await state.update_data(media_ids=media_ids)
    await message.answer(
        f"✅ Đã lưu ảnh ({len(media_ids)} ảnh). Gửi thêm hoặc bấm <b>✅ Gửi</b>.",
        reply_markup=nut_gui_anh(),
    )


@router.message(SiteReportState.collecting_photos, Command("done"))
async def finish_site_report(message: types.Message, state: FSMContext):
    """/done — vẫn nhận cho người quen gõ lệnh."""
    await gui_bao_cao(message, state, message.from_user.id)


async def gui_bao_cao(message: types.Message, state: FSMContext, tg_id: int):
    """Gửi báo cáo kèm ảnh đã gom (nút ✅ Gửi hoặc /done)."""
    data = await state.get_data()
    project_code = data.get("project_code", "")
    content = data.get("report_content", "")
    photos = data.get("media_ids", [])

    if not content:
        await message.answer("❌ Nội dung báo cáo trống. Hãy thử lại.")
        await state.clear()
        return

    await message.answer("🔄 Đang gửi báo cáo...")

    report_data = {
        "project_code": project_code,
        "content": content,
        "media_ids": photos,
        "reporter_tg_id": tg_id,
    }

    result = await api.create_site_report(tg_id, report_data)

    if result and not result.get("error"):
        photo_info = f"\n📸 Ảnh đính kèm: {len(photos)} ảnh" if photos else ""
        await message.answer(
            f"✅ <b>Báo cáo đã được ghi nhận!</b>\n\n"
            f"🏗 Dự án: <code>{result.get('project_code', project_code)}</code>\n"
            f"📋 Đầu việc: {result.get('task_title', '—')}\n"
            f"👤 Người báo cáo: {result.get('reporter', '—')}\n"
            f"🕐 Thời gian: {result.get('created_at', '—')}"
            f"{photo_info}"
        )
    else:
        error_msg = result.get("error", "Không rõ lỗi") if result else "Không kết nối được server"
        await message.answer(f"❌ <b>Lỗi gửi báo cáo:</b> {error_msg}")

    await state.clear()


@router.message(SiteReportState.collecting_photos, F.text & ~F.command("done") & ~F.command("cancel"))
async def wrong_input_photos(message: types.Message):
    """Handle wrong input during photo collection."""
    await message.answer(
        "⚠️ Gửi ảnh, hoặc bấm <b>✅ Gửi</b> để hoàn tất.",
        reply_markup=nut_gui_anh(),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
