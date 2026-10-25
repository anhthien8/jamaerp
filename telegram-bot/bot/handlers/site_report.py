"""/duan and /baocao handlers — project lookup + site reports with photos."""

import os

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from bot.api_client import api
from bot.keyboards import hien_ban_phim, nut_gui_anh, nut_huy

router = Router()

# Trang web ERP (bot dựng link «Xem trong ERP»)
WEB_URL = os.getenv("WEB_URL", "https://frontend-jet-two-86.vercel.app").rstrip("/")


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
# /baocao — Site report with optional photo / file attachment
# ---------------------------------------------------------------------------

# Gõ một trong các chữ này = bấm ✅ Gửi (trước đây "done" bị lấy làm nội dung)
_TU_XONG = {"done", "xong", "/done", "gui", "gửi", "ok"}
_LA_TEP = F.document | F.video | F.audio | F.voice | F.video_note


def _la_tu_xong(text: str | None) -> bool:
    return (text or "").strip().lower().split("@")[0] in _TU_XONG


def _link_tin(message: types.Message) -> str | None:
    """Link mở đúng tin trong nhóm (chat riêng với bot thì không có link)."""
    chat = message.chat
    if chat.type not in ("group", "supergroup"):
        return None
    if chat.username:
        return f"https://t.me/{chat.username}/{message.message_id}"
    cid = str(chat.id)
    if cid.startswith("-100"):
        return f"https://t.me/c/{cid[4:]}/{message.message_id}"
    return None  # nhóm thường (chưa lên supergroup) không có link tin


def _co_dung_luong(size: int | None) -> str | None:
    if not size:
        return None
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.1f} MB"
    return f"{max(size // 1024, 1)} KB"


def _tep(message: types.Message) -> dict:
    """Tệp không phải ảnh: chỉ giữ tên + dung lượng + link tin. Bot không tải
    được tệp > 20 MB, và bản vẽ/video vốn đã nằm sẵn trong nhóm."""
    f = message.document or message.video or message.audio or message.voice or message.video_note
    if message.document:
        ten = f.file_name or "Tệp"
    elif message.video:
        ten = f.file_name or "Video"
    elif message.audio:
        ten = f.file_name or f.title or "Âm thanh"
    else:
        ten = "Ghi âm" if message.voice else "Video tròn"
    return {"name": ten[:200], "size_text": _co_dung_luong(f.file_size), "link": _link_tin(message)}


async def _tep_vao_kho(message: types.Message, state: FSMContext) -> tuple[dict, str | None]:
    """Bản vẽ/PDF/video → chép (copyMessage, không giới hạn dung lượng) vào topic
    dự án trong nhóm Kho «JAMA Công trình» + ghi vào Tài liệu dự án. Link trong
    nhật ký trỏ về bản trong topic. Lỗi thì giữ link tin gốc và báo lý do."""
    tep = _tep(message)
    data = await state.get_data()
    f = message.document or message.video or message.audio or message.voice or message.video_note
    res = await api.document_from_telegram(message.from_user.id, {
        "project_code": data.get("project_code"),
        "from_chat_id": message.chat.id,
        "message_id": message.message_id,
        "thread_id": message.message_thread_id,
        "file_id": f.file_id,
        "file_name": tep["name"],
        "mime": getattr(f, "mime_type", None),
        "file_size": f.file_size,
        "caption": (message.caption or data.get("report_content") or "")[:300] or None,
    })
    if not res or res.get("error"):
        return tep, (res.get("error") if res else "Không kết nối được server")
    return {**tep, "link": res.get("link") or tep["link"], "in_storage": True}, None


async def _luu_anh(message: types.Message, state: FSMContext) -> str | None:
    """Ảnh → Kho ảnh (topic dự án). Trả câu lỗi nếu không lưu được."""
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
        return res.get("error") if res else "Không kết nối được server"
    if res["id"] not in media_ids:
        media_ids.append(res["id"])
    await state.update_data(media_ids=media_ids)
    return None


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
    await state.update_data(project_code=project_code, media_ids=[], attachments=[])
    if not content:
        await state.set_state(SiteReportState.waiting_content)
        await message.answer(
            f"📝 <b>Báo cáo cho dự án {project_code}</b>\n\n"
            "Gõ nội dung báo cáo (hôm nay làm được gì, vướng gì). "
            "Có ảnh/bản vẽ thì gửi kèm luôn.",
            reply_markup=nut_huy(),
        )
        return
    await _sang_buoc_gom(message, state, content, _link_tin(message))


async def _sang_buoc_gom(message: types.Message, state: FSMContext, content: str, link: str | None):
    await state.update_data(report_content=content, message_link=link)
    await state.set_state(SiteReportState.collecting_photos)
    data = await state.get_data()
    da_co = len(data.get("media_ids", [])) + len(data.get("attachments", []))
    them = f"\n📎 Đã nhận {da_co} ảnh/tệp." if da_co else ""
    await message.answer(
        f"📝 <b>Báo cáo cho dự án {data.get('project_code', '')}</b>\n"
        f"Nội dung: {content}{them}\n\n"
        "Gửi thêm ảnh/tệp nếu có, xong bấm <b>✅ Gửi</b> (hoặc gõ <b>xong</b>).",
        reply_markup=nut_gui_anh(),
    )


@router.message(SiteReportState.waiting_content, F.photo | _LA_TEP)
async def nhan_tep_khi_cho_noi_dung(message: types.Message, state: FSMContext):
    """Gửi ảnh/tệp trước khi gõ nội dung: vẫn nhận; có chú thích thì dùng làm nội dung."""
    if message.photo:
        loi = await _luu_anh(message, state)
        if loi:
            await message.answer(f"⚠️ Ảnh chưa lưu được: {loi}", reply_markup=nut_huy())
            return
        ten = "ảnh"
    else:
        tep, loi = await _tep_vao_kho(message, state)
        data = await state.get_data()
        await state.update_data(attachments=data.get("attachments", []) + [tep])
        ten = f"tệp <b>{tep['name']}</b>" + (f" ({tep['size_text']})" if tep["size_text"] else "")
        ten += " — đã chép vào topic dự án" if not loi else f"\n⚠️ Chưa chép được vào topic dự án ({loi}), báo cáo vẫn kèm link tin gốc"
    caption = (message.caption or "").strip()
    if caption and not caption.startswith("/"):
        await _sang_buoc_gom(message, state, caption, _link_tin(message))
        return
    await message.answer(
        f"✅ Đã nhận {ten}.\nGõ <b>nội dung báo cáo</b> (hôm nay làm được gì, vướng gì) để gửi.",
        reply_markup=nut_huy(),
    )


@router.message(SiteReportState.waiting_content, F.text)
async def process_report_content(message: types.Message, state: FSMContext):
    """Receive report content text."""
    text = message.text.strip()
    if _la_tu_xong(text) or text.startswith("/"):
        await message.answer(
            "✍️ Chưa có nội dung báo cáo. Gõ vài dòng mô tả (hôm nay làm được gì, vướng gì) rồi gửi.",
            reply_markup=nut_huy(),
        )
        return
    await _sang_buoc_gom(message, state, text, _link_tin(message))


@router.message(SiteReportState.collecting_photos, F.photo)
async def collect_photo(message: types.Message, state: FSMContext):
    """Nhận ảnh → lưu ngay vào Kho ảnh (topic dự án), giữ lại media_id."""
    loi = await _luu_anh(message, state)
    if loi:
        await message.answer(
            f"⚠️ Ảnh chưa lưu được: {loi}\nGửi lại ảnh, hoặc bấm ✅ Gửi để gửi báo cáo không ảnh.",
            reply_markup=nut_gui_anh(),
        )
        return
    data = await state.get_data()
    await message.answer(
        f"✅ Đã lưu ảnh ({len(data.get('media_ids', []))} ảnh). Gửi thêm hoặc bấm <b>✅ Gửi</b>.",
        reply_markup=nut_gui_anh(),
    )


@router.message(SiteReportState.collecting_photos, _LA_TEP)
async def collect_file(message: types.Message, state: FSMContext):
    """Bản vẽ/video/tệp nặng: chép vào topic dự án, ghi link vào báo cáo."""
    tep, loi = await _tep_vao_kho(message, state)
    data = await state.get_data()
    ds = data.get("attachments", []) + [tep]
    await state.update_data(attachments=ds)
    co = f" ({tep['size_text']})" if tep["size_text"] else ""
    noi = " — đã chép vào topic dự án" if not loi else f"\n⚠️ Chưa chép được vào topic dự án ({loi}), báo cáo vẫn kèm link tin gốc"
    await message.answer(
        f"✅ Đã nhận tệp <b>{tep['name']}</b>{co}{noi}\n{len(ds)} tệp. Gửi thêm hoặc bấm <b>✅ Gửi</b>.",
        reply_markup=nut_gui_anh(),
    )


@router.message(SiteReportState.collecting_photos, Command("done"))
async def finish_site_report(message: types.Message, state: FSMContext):
    """/done — vẫn nhận cho người quen gõ lệnh."""
    await gui_bao_cao(message, state, message.from_user.id)


async def gui_bao_cao(message: types.Message, state: FSMContext, tg_id: int):
    """Gửi báo cáo kèm ảnh/tệp đã gom (nút ✅ Gửi, /done hoặc gõ "xong")."""
    data = await state.get_data()
    project_code = data.get("project_code", "")
    content = data.get("report_content", "")
    photos = data.get("media_ids", [])
    attachments = data.get("attachments", [])[:20]

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
        "attachments": attachments,
        "message_link": data.get("message_link"),
    }

    result = await api.create_site_report(tg_id, report_data)

    if result and not result.get("error"):
        code = result.get("project_code", project_code)
        task = result.get("task_title", "—")
        photo_info = f"\n📸 Ảnh: {len(photos)} ảnh (đã vào Kho ảnh)" if photos else ""
        kho = sum(1 for t in attachments if t.get("in_storage"))
        tep_info = (
            f"\n📎 Tệp: {len(attachments)} tệp"
            + (f" ({kho} đã vào topic dự án)" if kho else " (kèm link mở trong nhóm)")
            if attachments else ""
        )
        if result.get("notified"):
            tep_info += f"\n🔔 Đã báo {result['notified']} người phụ trách"
        crm = ""
        if result.get("crm_path"):
            crm = (
                f"\n\n🔎 <b>Xem trong ERP:</b> Dự án → {code} → đầu việc «{task}» → Nhật ký\n"
                f"{WEB_URL}{result['crm_path']}"
            )
        await message.answer(
            f"✅ <b>Báo cáo đã được lưu vào ERP!</b>\n\n"
            f"🏗 Dự án: <code>{code}</code>\n"
            f"📋 Đầu việc: {task}\n"
            f"👤 Người báo cáo: {result.get('reporter', '—')}\n"
            f"🕐 Thời gian: {result.get('created_at', '—')}"
            f"{photo_info}{tep_info}{crm}",
            disable_web_page_preview=True,
        )
    else:
        error_msg = result.get("error", "Không rõ lỗi") if result else "Không kết nối được server"
        await message.answer(f"❌ <b>Lỗi gửi báo cáo:</b> {error_msg}")

    await state.clear()


@router.message(SiteReportState.collecting_photos, F.text & ~F.command("done") & ~F.command("cancel"))
async def wrong_input_photos(message: types.Message, state: FSMContext):
    """Gõ "xong"/"done" = bấm ✅ Gửi; chữ khác thì nhắc."""
    if _la_tu_xong(message.text):
        await gui_bao_cao(message, state, message.from_user.id)
        return
    await message.answer(
        "⚠️ Gửi ảnh/tệp, hoặc bấm <b>✅ Gửi</b> (gõ <b>xong</b>) để hoàn tất.",
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
