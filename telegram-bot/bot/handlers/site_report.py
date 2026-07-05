"""/duan and /baocao handlers — project lookup + site reports with photos."""

import re

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from bot.api_client import api

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
    """Look up project by code — show info + task progress."""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "🔍 <b>Tra cứu dự án</b>\n\n"
            "Cách dùng: <code>/duan [Mã dự án]</code>\n"
            "Ví dụ: <code>/duan JMH-0601</code>"
        )
        return

    project_code = args[1].strip().upper()
    await message.answer("🔄 Đang tra cứu dự án...")

    result = await api.get_project(message.from_user.id, project_code)

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
    """Start a site report — parse project code and content."""
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        await message.answer(
            "📝 <b>Báo cáo công trình</b>\n\n"
            "Cách dùng:\n"
            "<code>/baocao [Mã dự án] [Nội dung]</code>\n"
            "Ví dụ: <code>/baocao JMH-0601 Hoàn thành đổ móng block A</code>\n\n"
            "💡 Sau khi gửi nội dung, bạn có thể đính kèm ảnh (gửi lần lượt)."
        )
        return

    project_code = args[1].strip().upper()
    content = args[2].strip() if len(args) > 2 else ""

    if not content:
        await message.answer(
            f"📝 <b>Báo cáo cho dự án {project_code}</b>\n\n"
            "Vui lòng nhập nội dung báo cáo.\n"
            "💡 <i>Gửi /cancel để hủy</i>"
        )
        await state.update_data(project_code=project_code)
        await state.set_state(SiteReportState.waiting_content)
        return

    # Has content — start collecting photos
    await state.update_data(project_code=project_code, report_content=content, photos=[])
    await state.set_state(SiteReportState.collecting_photos)
    await message.answer(
        f"📝 <b>Báo cáo cho dự án {project_code}</b>\n\n"
        f"Nội dung: {content}\n\n"
        "📸 Gửi ảnh hiện trường (có thể gửi nhiều ảnh).\n"
        "Khi xong, gửi <code>/done</code> để hoàn tất.\n"
        "💡 <i>Gửi /cancel để hủy</i>"
    )


@router.message(SiteReportState.waiting_content, F.text)
async def process_report_content(message: types.Message, state: FSMContext):
    """Receive report content text."""
    text = message.text
    if text.startswith("/"):
        if text == "/cancel":
            await state.clear()
            await message.answer("🚫 Đã hủy báo cáo.")
        return

    await state.update_data(report_content=text, photos=[])
    await state.set_state(SiteReportState.collecting_photos)
    await message.answer(
        "📸 Gửi ảnh hiện trường (có thể gửi nhiều ảnh).\n"
        "Khi xong, gửi <code>/done</code> để hoàn tất.\n"
        "💡 <i>Gửi /cancel để hủy</i>"
    )


@router.message(SiteReportState.collecting_photos, F.photo)
async def collect_photo(message: types.Message, state: FSMContext):
    """Collect photos for the report."""
    data = await state.get_data()
    photos = data.get("photos", [])

    # Use the largest available photo size
    photo = message.photo[-1]
    photos.append(photo.file_id)

    await state.update_data(photos=photos)
    await message.answer(
        f"✅ Đã nhận ảnh ({len(photos)} ảnh).\n"
        "Gửi thêm ảnh hoặc gửi <code>/done</code> để hoàn tất."
    )


@router.message(SiteReportState.collecting_photos, Command("done"))
async def finish_site_report(message: types.Message, state: FSMContext):
    """Submit the site report with collected photos."""
    data = await state.get_data()
    project_code = data.get("project_code", "")
    content = data.get("report_content", "")
    photos = data.get("photos", [])

    if not content:
        await message.answer("❌ Nội dung báo cáo trống. Hãy thử lại.")
        await state.clear()
        return

    await message.answer("🔄 Đang gửi báo cáo...")

    report_data = {
        "project_code": project_code,
        "content": content,
        "photos": photos,
        "reporter_tg_id": message.from_user.id,
    }

    result = await api.create_site_report(message.from_user.id, report_data)

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
        "⚠️ Vui lòng gửi ảnh hoặc gõ <code>/done</code> để hoàn tất.\n"
        "💡 <i>Gửi /cancel để hủy</i>"
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    """Cancel any active FSM flow."""
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.clear()
    await message.answer("🚫 Đã hủy thao tác.")


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
