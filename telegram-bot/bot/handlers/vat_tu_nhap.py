"""Nhập dữ liệu Vật tư qua bot (25/10/2026) — chỉ bộ phận Thu mua.

    /nhapmau <link Google Sheet>  — nhập danh mục mẫu (thêm mẫu mới, không ghi đè)
    /baogia [MÃ DỰ ÁN]            — gửi tệp báo giá NCC (Excel/CSV/PDF/ảnh)
                                    → bot đọc, khớp mã với phiếu dự án,
                                    hiện bản xem trước → bấm «Ghi» mới ghi.

Nguyên tắc: bot đọc → bản xem trước → người xác nhận → mới ghi. Quyền do
backend gác (sale/thiết kế bị 403 như trên web).
"""

import re

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.api_client import api
from bot.handlers.site_report import WEB_URL
from bot.keyboards import NUT_HUY, hien_ban_phim, nut_huy

router = Router()

_LINK_SHEET = re.compile(r"https?://docs\.google\.com/spreadsheets/\S+")


class BaoGiaState(StatesGroup):
    cho_tep = State()      # đã chọn dự án, chờ tệp báo giá
    cho_xac_nhan = State()  # đã có bản xem trước, chờ bấm Ghi / Hủy


def _tien(v: float | None) -> str:
    return f"{int(v):,}đ".replace(",", ".") if v else "—"


def _loi(res: dict | None, mac_dinh: str) -> str:
    if res is None:
        return "Không kết nối được máy chủ ERP, thử lại sau ít phút"
    return res.get("error") or mac_dinh


# ── /nhapmau ───────────────────────────────────────────────────────────────

@router.message(Command("nhapmau"))
async def cmd_nhapmau(message: types.Message):
    text = message.text or message.caption or ""
    m = _LINK_SHEET.search(text)
    if not m:
        await message.answer(
            "📋 <b>Nhập danh mục mẫu vật tư từ Google Sheet</b>\n\n"
            "Gõ: <code>/nhapmau &lt;link Google Sheet&gt;</code>\n"
            "Sheet phải để chế độ «Bất kỳ ai có liên kết đều xem được». "
            "Bot chỉ THÊM mẫu mới, không sửa mẫu đã có (muốn ghi đè thì dùng web: Vật tư → Danh mục).\n"
            "Chỉ bộ phận Thu mua làm được."
        )
        return
    cho = await message.answer("⏳ Đang đọc Google Sheet…")
    res = await api.vat_tu_import_sheet(message.from_user.id, m.group(0))
    if not res or res.get("error"):
        await cho.edit_text(f"❌ {_loi(res, 'Không nhập được danh mục')}")
        return
    await cho.edit_text(
        f"✅ Đã đọc <b>{res.get('doc_duoc', 0)}</b> dòng · thêm <b>{res.get('them', 0)}</b> mẫu mới"
        + (f" · bỏ qua {res['doc_duoc'] - res['them'] - res.get('sua', 0)} mẫu đã có" if res.get("doc_duoc") else "")
        + f".\nXem tại {WEB_URL}/vat-tu?tab=danh-muc — nhớ cài % lãi cho nhóm mới (Admin)."
    )


# ── /baogia ────────────────────────────────────────────────────────────────

@router.message(Command("baogia"))
async def cmd_baogia(message: types.Message, state: FSMContext):
    args = (message.text or message.caption or "").split(maxsplit=1)
    if len(args) < 2:
        await hien_ban_phim(message, message.from_user.id, "baogia")
        return
    await bat_dau_bao_gia(message, state, args[1].strip().upper(), message.from_user.id)


async def bat_dau_bao_gia(message: types.Message, state: FSMContext, project_code: str, tg_id: int):
    """Chọn dự án xong → chờ tệp. Dùng chung cho lệnh gõ tay và nút bấm."""
    kq = await api.get_project(tg_id, project_code)
    if not kq or not kq.get("project", {}).get("id"):
        await message.answer(f"❌ Không tìm thấy dự án <code>{project_code}</code>.")
        return
    p = kq["project"]
    await state.clear()
    await state.update_data(bg_project_id=p["id"], bg_project_code=p["code"])
    await state.set_state(BaoGiaState.cho_tep)
    await message.answer(
        f"💰 <b>Nhập báo giá NCC cho dự án {p['code']}</b> — {p.get('name', '')}\n\n"
        "Gửi <b>tệp báo giá</b> của nhà cung cấp: Excel (.xlsx), CSV, PDF hoặc ảnh chụp bảng giá.\n"
        "Bot sẽ đọc, khớp mã với phiếu vật tư của dự án và hiện bản xem trước — "
        "<b>chưa ghi gì</b> cho tới khi bạn bấm Ghi.",
        reply_markup=nut_huy(),
    )


@router.message(BaoGiaState.cho_tep, F.document | F.photo)
async def nhan_tep_bao_gia(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if message.document:
        f = message.document
        payload = {"file_id": f.file_id, "file_name": f.file_name, "mime": f.mime_type}
        ten = f.file_name or "tệp"
    else:
        f = message.photo[-1]
        payload = {"file_id": f.file_id, "file_name": "anh.jpg", "mime": "image/jpeg"}
        ten = "ảnh"
    if (f.file_size or 0) > 20 * 1024 * 1024:
        await message.answer("⚠️ Tệp quá 20 MB — bot không tải được. Xuất lại bảng giá gọn hơn rồi gửi.", reply_markup=nut_huy())
        return
    cho = await message.answer(f"⏳ Đang đọc {ten} và khớp mã với phiếu dự án {data.get('bg_project_code')}…")
    res = await api.vat_tu_trich_bao_gia(message.from_user.id, {"project_id": data["bg_project_id"], **payload})
    if not res or res.get("error"):
        await cho.edit_text(f"❌ {_loi(res, 'Không đọc được tệp')}\nGửi tệp khác hoặc bấm Hủy.", reply_markup=nut_huy())
        return
    khop = res.get("khop") or []
    khong = res.get("khong_khop") or []
    ncc = res.get("ncc_ten")
    dong = [f"📄 <b>{ten}</b> · dự án <b>{res.get('project_code')}</b>"
            + (f" · NCC: <b>{ncc}</b>" if ncc else " · <i>không thấy tên NCC trong tệp</i>"),
            f"Đọc được {res.get('so_doc_duoc', 0)} mã · khớp <b>{len(khop)}</b> dòng phiếu"
            + (f" · {len(khong)} mã không có trong phiếu" if khong else "")]
    if khop:
        dong.append("\n<b>Sẽ ghi báo giá:</b>")
        for k in khop[:15]:
            tt = "" if k.get("con_hang", True) else " · ⛔ hết hàng"
            dong.append(f"• {k.get('phong', '')} · <code>{k.get('ma_phieu') or k['ma']}</code> → {_tien(k.get('gia'))}/{k.get('don_vi') or k.get('don_vi_phieu') or ''}{tt}")
        if len(khop) > 15:
            dong.append(f"… và {len(khop) - 15} dòng nữa")
    if khong:
        dong.append("\n<i>Không khớp (bỏ qua):</i> " + ", ".join(f"<code>{k['ma']}</code>" for k in khong[:8])
                    + (" …" if len(khong) > 8 else ""))
    if not khop:
        dong.append("\n❌ Không có mã nào trùng với phiếu vật tư dự án — kiểm tra lại tệp hoặc mã trong phiếu.")
        await cho.edit_text("\n".join(dong), reply_markup=nut_huy())
        return
    if not ncc:
        dong.append("\n✍️ Gõ <b>tên nhà cung cấp</b> rồi bấm Ghi, hoặc bấm Ghi luôn để ghi là «NCC chưa rõ».")
    if res.get("ncc_mst"):
        dong[0] += f" · MST {res['ncc_mst']}"
    await state.update_data(bg_khop=khop, bg_ncc=ncc, bg_nguon=f"tệp {ten}",
                            bg_mst=res.get("ncc_mst"), bg_dia_chi=res.get("ncc_dia_chi"))
    await state.set_state(BaoGiaState.cho_xac_nhan)
    await cho.edit_text("\n".join(dong), reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[
        types.InlineKeyboardButton(text=f"✅ Ghi {len(khop)} báo giá", callback_data="bg:ghi"), NUT_HUY,
    ]]))


@router.message(BaoGiaState.cho_tep, F.text & ~F.text.startswith("/"))
async def nhac_gui_tep(message: types.Message):
    await message.answer("📎 Gửi tệp báo giá (Excel/CSV/PDF/ảnh) chứ không gõ chữ. Bấm Hủy để thoát.", reply_markup=nut_huy())


@router.message(BaoGiaState.cho_xac_nhan, F.text & ~F.text.startswith("/"))
async def doi_ten_ncc(message: types.Message, state: FSMContext):
    ten = message.text.strip()[:150]
    await state.update_data(bg_ncc=ten)
    data = await state.get_data()
    await message.answer(
        f"NCC: <b>{ten}</b>. Bấm Ghi để ghi {len(data.get('bg_khop', []))} báo giá.",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[
            types.InlineKeyboardButton(text="✅ Ghi", callback_data="bg:ghi"), NUT_HUY,
        ]]),
    )


@router.callback_query(F.data == "bg:ghi")
async def cb_ghi(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    khop = data.get("bg_khop") or []
    if await state.get_state() != BaoGiaState.cho_xac_nhan.state or not khop:
        await callback.answer("Không có bản xem trước nào đang chờ. Gõ /baogia để bắt đầu.", show_alert=True)
        return
    await callback.answer("Đang ghi…")
    ncc = data.get("bg_ncc") or "NCC chưa rõ"
    items = [{"dong_id": k["dong_id"], "ncc_ten": ncc, "gia": k["gia"], "con_hang": k.get("con_hang", True),
              "ghi_chu": k.get("ghi_chu")} for k in khop if k.get("gia")]
    res = await api.vat_tu_ghi_bao_gia(callback.from_user.id, items, data.get("bg_nguon"),
                                       data.get("bg_mst"), data.get("bg_dia_chi"))
    if not res or res.get("error"):
        await callback.message.answer(f"❌ {_loi(res, 'Không ghi được')}")
        return
    await state.clear()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    pid = data.get("bg_project_id")
    await callback.message.answer(
        f"✅ Đã ghi <b>{res.get('ghi', 0)}</b> báo giá của <b>{ncc}</b> vào phiếu dự án {data.get('bg_project_code')}."
        + (f"\n⚠️ {len(res['loi'])} dòng lỗi." if res.get("loi") else "")
        + f"\nSo giá & chốt tại {WEB_URL}/vat-tu?project={pid} hoặc tab «Cần hỏi giá»."
    )
