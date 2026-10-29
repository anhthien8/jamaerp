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
        "<b>chưa ghi gì</b> cho tới khi bạn bấm Ghi.\n\n"
        "📑 Gửi <b>báo giá phát sinh JAMA gửi khách</b> cũng được — bot tự nhận ra và chuyển sang tạo phụ lục.",
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
    if res.get("la_bao_gia_khach"):
        # Tệp là báo giá JAMA gửi khách chứ không phải báo giá NCC → tự chuyển luồng phát sinh
        await state.clear()
        await state.update_data(ps_project_id=data["bg_project_id"], ps_project_code=data.get("bg_project_code"))
        await state.set_state(PhatSinhState.cho_tep)
        await cho.edit_text(f"📑 <b>{ten}</b> là báo giá JAMA gửi khách — bot xử lý như <b>phát sinh</b>: "
                            "tạo phụ lục nháp trên hợp đồng + thêm hạng mục vào phiếu vật tư.")
        cho = await message.answer("⏳ Đang đọc các hạng mục…")
        await xem_truoc_phat_sinh(cho, state, message.from_user.id, data["bg_project_id"], payload, ten)
        return
    khop = res.get("khop") or []
    khong = res.get("khong_khop") or []
    tao_moi = res.get("tao_moi") or []
    ncc = res.get("ncc_ten")
    if tao_moi or (not khop and res.get("so_dong_phieu") == 0):
        await _xem_truoc_tao_dong(cho, state, res, ten, tao_moi, khong)
        return
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


def _sl(v) -> str:
    return (f"{v:g}" if isinstance(v, (int, float)) else "") or "1"


async def _xem_truoc_tao_dong(cho: types.Message, state: FSMContext, res: dict, ten: str,
                              tao_moi: list[dict], khong: list[dict]):
    """Dự án chưa có phiếu: xem trước các dòng phiếu sẽ TẠO từ tệp + báo giá đi kèm."""
    ncc = res.get("ncc_ten")
    code = res.get("project_code")
    dong = [f"📄 <b>{ten}</b> · dự án <b>{code}</b>"
            + (f" · NCC: <b>{ncc}</b>" if ncc else " · <i>không thấy tên NCC trong tệp</i>")
            + (f" · MST {res['ncc_mst']}" if res.get("ncc_mst") else ""),
            f"ℹ️ Dự án <b>chưa có phiếu vật tư</b> — bot sẽ <b>tạo {len(tao_moi)} dòng phiếu</b> từ tệp này "
            "và ghi giá NCC vào từng dòng."]
    if tao_moi:
        dong.append("\n<b>Dòng sẽ tạo:</b>")
        for k in tao_moi[:15]:
            dm = "" if k.get("co_trong_danh_muc") else " · <i>mã ngoài danh mục</i>"
            tt = "" if k.get("con_hang", True) else " · ⛔ hết hàng"
            dong.append(f"• {k.get('phong') or 'Chung'} · <code>{k['ma']}</code> · SL {_sl(k.get('so_luong'))} "
                        f"{k.get('don_vi') or ''} → {_tien(k.get('gia'))}{dm}{tt}")
        if len(tao_moi) > 15:
            dong.append(f"… và {len(tao_moi) - 15} dòng nữa")
        if any(not k.get("so_luong") for k in tao_moi):
            dong.append("\n<i>Dòng nào tệp không ghi số lượng sẽ để SL 1 — sửa lại trên web sau.</i>")
    if khong:
        dong.append("\n<i>Không có giá (bỏ qua):</i> " + ", ".join(f"<code>{k['ma']}</code>" for k in khong[:8])
                    + (" …" if len(khong) > 8 else ""))
    if not tao_moi:
        dong.append("\n❌ Không đọc được mã nào có giá trong tệp — kiểm tra lại tệp hoặc gửi tệp khác.")
        await cho.edit_text("\n".join(dong), reply_markup=nut_huy())
        return
    if not ncc:
        dong.append("\n✍️ Gõ <b>tên nhà cung cấp</b> rồi bấm Ghi, hoặc bấm Ghi luôn để ghi là «NCC chưa rõ».")
    await state.update_data(bg_khop=[], bg_tao=tao_moi, bg_ncc=ncc, bg_nguon=f"tệp {ten}",
                            bg_mst=res.get("ncc_mst"), bg_dia_chi=res.get("ncc_dia_chi"))
    await state.set_state(BaoGiaState.cho_xac_nhan)
    await cho.edit_text("\n".join(dong), reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[
        types.InlineKeyboardButton(text=f"✅ Tạo {len(tao_moi)} dòng + ghi giá", callback_data="bg:ghi"), NUT_HUY,
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
        f"NCC: <b>{ten}</b>. Bấm Ghi để ghi {len(data.get('bg_khop') or []) + len(data.get('bg_tao') or [])} báo giá.",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[
            types.InlineKeyboardButton(text="✅ Ghi", callback_data="bg:ghi"), NUT_HUY,
        ]]),
    )


@router.callback_query(F.data == "bg:ghi")
async def cb_ghi(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    khop = data.get("bg_khop") or []
    tao = data.get("bg_tao") or []
    if await state.get_state() != BaoGiaState.cho_xac_nhan.state or not (khop or tao):
        await callback.answer("Không có bản xem trước nào đang chờ. Gõ /baogia để bắt đầu.", show_alert=True)
        return
    await callback.answer("Đang ghi…")
    ncc = data.get("bg_ncc") or "NCC chưa rõ"
    items = [{"dong_id": k["dong_id"], "ncc_ten": ncc, "gia": k["gia"], "con_hang": k.get("con_hang", True),
              "ghi_chu": k.get("ghi_chu")} for k in khop if k.get("gia")]
    tao_dong = [{"ma": k["ma"], "phong": k.get("phong"), "so_luong": k.get("so_luong"), "don_vi": k.get("don_vi"),
                 "ncc_ten": ncc, "gia": k["gia"], "con_hang": k.get("con_hang", True), "ghi_chu": k.get("ghi_chu")}
                for k in tao if k.get("gia")]
    res = await api.vat_tu_ghi_bao_gia(callback.from_user.id, items, data.get("bg_nguon"),
                                       data.get("bg_mst"), data.get("bg_dia_chi"),
                                       project_id=data.get("bg_project_id"), tao_dong=tao_dong)
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
        (f"🆕 Đã tạo <b>{res['tao']}</b> dòng phiếu vật tư.\n" if res.get("tao") else "")
        + f"✅ Đã ghi <b>{res.get('ghi', 0)}</b> báo giá của <b>{ncc}</b> vào phiếu dự án {data.get('bg_project_code')}."
        + (f"\n⚠️ {len(res['loi'])} dòng lỗi." if res.get("loi") else "")
        + f"\nSo giá & chốt tại {WEB_URL}/vat-tu?project={pid} hoặc tab «Cần hỏi giá»."
    )


# ── /phatsinh: báo giá phát sinh JAMA gửi khách (30/10/2026) ───────────────
# Tệp → xem trước → Ghi = (A) phụ lục NHÁP dưới HĐ gốc (khách chốt thì ký trên web)
# + (B) dòng phiếu vật tư cho hạng mục cần mua (SL dương) để Thu mua hỏi NCC.

class PhatSinhState(StatesGroup):
    cho_tep = State()
    cho_xac_nhan = State()


def _so(v) -> str:
    return "" if v is None else (f"{v:g}" if isinstance(v, (int, float)) else str(v))


@router.message(Command("phatsinh"))
async def cmd_phatsinh(message: types.Message, state: FSMContext):
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await hien_ban_phim(message, message.from_user.id, "phatsinh")
        return
    await bat_dau_phat_sinh(message, state, args[1].strip().upper(), message.from_user.id)


async def bat_dau_phat_sinh(message: types.Message, state: FSMContext, project_code: str, tg_id: int):
    kq = await api.get_project(tg_id, project_code)
    if not kq or not kq.get("project", {}).get("id"):
        await message.answer(f"❌ Không tìm thấy dự án <code>{project_code}</code>.")
        return
    p = kq["project"]
    await state.clear()
    await state.update_data(ps_project_id=p["id"], ps_project_code=p["code"])
    await state.set_state(PhatSinhState.cho_tep)
    await message.answer(
        f"📑 <b>Nhập phát sinh cho dự án {p['code']}</b> — {p.get('name', '')}\n\n"
        "Gửi <b>tệp báo giá phát sinh</b> JAMA gửi khách (Excel, PDF hoặc ảnh chụp).\n"
        "Bot đọc rồi cho xem trước. Khi bạn bấm Ghi, bot sẽ:\n"
        "1️⃣ Tạo <b>phụ lục nháp</b> trên hợp đồng của khách (khách chốt thì ký phụ lục trên web)\n"
        "2️⃣ Thêm các hạng mục cần mua vào <b>phiếu vật tư</b> để Thu mua hỏi giá NCC\n"
        "<i>Dòng giảm trừ (SL âm, chủ nhà tự cấp) chỉ trừ tiền, không thêm vào phiếu mua.</i>",
        reply_markup=nut_huy(),
    )


@router.message(PhatSinhState.cho_tep, F.document | F.photo)
async def nhan_tep_phat_sinh(message: types.Message, state: FSMContext):
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
        await message.answer("⚠️ Tệp quá 20 MB — bot không tải được.", reply_markup=nut_huy())
        return
    cho = await message.answer(f"⏳ Đang đọc {ten}…")
    await xem_truoc_phat_sinh(cho, state, message.from_user.id, data["ps_project_id"], payload, ten)


async def xem_truoc_phat_sinh(cho: types.Message, state: FSMContext, tg_id: int, project_id: str,
                              payload: dict, ten: str):
    """Đọc tệp phát sinh → sửa tin «cho» thành bản xem trước. Dùng chung /phatsinh và /baogia (tự nhận)."""
    res = await api.vat_tu_trich_phat_sinh(tg_id, {"project_id": project_id, **payload})
    if not res or res.get("error"):
        await cho.edit_text(f"❌ {_loi(res, 'Không đọc được tệp')}\nGửi tệp khác hoặc bấm Hủy.", reply_markup=nut_huy())
        return
    items = res.get("items") or []
    hd = res.get("hop_dong") or []
    if not items:
        await cho.edit_text("❌ Không thấy hạng mục nào có giá trong tệp. Kiểm tra lại tệp hoặc bấm Hủy.",
                            reply_markup=nut_huy())
        return
    if not hd:
        await cho.edit_text(
            f"❌ Dự án {res.get('project_code')} chưa có hợp đồng nào để gắn phụ lục.\n"
            f"Tạo hợp đồng trước trên web: {WEB_URL}/contracts — rồi gửi lại tệp.", reply_markup=nut_huy())
        return
    tieu_de = res.get("tieu_de") or "Phát sinh"
    dong = [f"📄 <b>{ten}</b> · dự án <b>{res.get('project_code')}</b> — khách {res.get('client_name') or '?'}"]
    if res.get("khop_khach") is False:
        dong.append(f"⚠️ <b>Tên khách trong tệp không giống khách của dự án này</b>"
                    f" (tệp: {res.get('khach_trong_tep') or ten}). Kiểm tra có chọn nhầm dự án không!")
    dong.append(f"\n<b>{tieu_de}</b> — {len(items)} hạng mục:")
    for it in items[:20]:
        so = " × ".join(_so(v) for v in (it.get("kl"), it.get("sl")) if v is not None)
        dong.append(f"• {it['hang_muc']}" + (f" ({so} {it.get('dvt') or ''})".replace(" )", ")") if so else "")
                    + f" → <b>{_tien(abs(it['thanh_tien']))}</b>" + (" ➖ giảm trừ" if it["thanh_tien"] < 0 else ""))
    if len(items) > 20:
        dong.append(f"… và {len(items) - 20} hạng mục nữa")
    dong.append(f"\n💵 Tổng phụ lục: <b>{'-' if res['tong'] < 0 else ''}{_tien(abs(res['tong']))}</b>")
    if res.get("lech_tong"):
        dong.append(f"⚠️ Tổng in trong tệp là {_tien(res.get('tong_file'))} — <b>khác</b> tổng bot tự cộng "
                    "(KL × SL × đơn giá). Kiểm tra lại tệp trước khi ghi.")
    dong.append(f"📦 Thêm <b>{res.get('so_dong_mua', 0)}</b> dòng vào phiếu vật tư (mục «Phát sinh») cho Thu mua hỏi giá.")
    hd_chon = hd[0]
    if len(hd) > 1:
        dong.append("\n📌 Dự án có nhiều hợp đồng — chọn hợp đồng để gắn phụ lục:")
    else:
        dong.append(f"\n📌 Phụ lục sẽ gắn vào hợp đồng <b>{hd_chon['code']}</b> (nháp, chưa ký).")
    await state.update_data(ps_items=items, ps_tieu_de=tieu_de[:255], ps_nguon=ten, ps_hd=hd_chon["id"])
    await state.set_state(PhatSinhState.cho_xac_nhan)
    if len(hd) > 1:
        nut = [[types.InlineKeyboardButton(text=f"✅ Ghi vào {c['code']}"[:60], callback_data=f"ps:ghi:{i}")]
               for i, c in enumerate(hd[:6])]
        await state.update_data(ps_ds_hd=[c["id"] for c in hd[:6]])
    else:
        nut = [[types.InlineKeyboardButton(text="✅ Tạo phụ lục + phiếu vật tư", callback_data="ps:ghi:0")]]
        await state.update_data(ps_ds_hd=[hd_chon["id"]])
    nut.append([NUT_HUY])
    await cho.edit_text("\n".join(dong), reply_markup=types.InlineKeyboardMarkup(inline_keyboard=nut))


@router.message(PhatSinhState.cho_tep, F.text & ~F.text.startswith("/"))
async def nhac_gui_tep_ps(message: types.Message):
    await message.answer("📎 Gửi tệp báo giá phát sinh (Excel/PDF/ảnh) chứ không gõ chữ. Bấm Hủy để thoát.",
                         reply_markup=nut_huy())


@router.callback_query(F.data.startswith("ps:ghi:"))
async def cb_ghi_phat_sinh(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    ds_hd = data.get("ps_ds_hd") or []
    try:
        i = int(callback.data.split(":")[2])
    except ValueError:
        i = -1
    if await state.get_state() != PhatSinhState.cho_xac_nhan.state or not data.get("ps_items") or not 0 <= i < len(ds_hd):
        await callback.answer("Không có bản xem trước nào đang chờ. Gõ /phatsinh để bắt đầu.", show_alert=True)
        return
    await callback.answer("Đang ghi…")
    res = await api.vat_tu_ghi_phat_sinh(callback.from_user.id, {
        "project_id": data["ps_project_id"], "contract_id": ds_hd[i], "tieu_de": data["ps_tieu_de"],
        "items": data["ps_items"], "nguon": data.get("ps_nguon"),
    })
    if not res or res.get("error"):
        await callback.message.answer(f"❌ {_loi(res, 'Không ghi được')}")
        return
    await state.clear()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    pl = res.get("phu_luc") or {}
    await callback.message.answer(
        f"✅ Đã tạo phụ lục nháp <b>{pl.get('code')}</b> · {_tien(abs(pl.get('total_value') or 0))}"
        + (" (giảm trừ)" if (pl.get("total_value") or 0) < 0 else "") + "\n"
        f"📦 Đã thêm <b>{res.get('tao_dong', 0)}</b> dòng vào phiếu vật tư dự án {data.get('ps_project_code')}.\n\n"
        f"Bước tiếp:\n• Gửi khách xem; khách chốt thì mở {WEB_URL}/contracts, tìm <b>{pl.get('code')}</b> và chuyển sang Đã ký\n"
        f"• Thu mua hỏi giá NCC tại {WEB_URL}/vat-tu?project={data.get('ps_project_id')}"
    )
