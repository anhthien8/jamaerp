"""Nút bấm dùng chung (Đợt 3, 23/10/2026).

- `pick:<lệnh>:<MÃ|VP>`: bấm chọn dự án từ bàn phím → vào thẳng luồng của lệnh.
- `cmd_duan`… từ menu /start → hiện bàn phím chọn dự án thay vì in cú pháp.
- `fsm:done` / `fsm:anh`: nút ✅ Gửi / 📷 Thêm ảnh khi đang gom ảnh.
(`fsm:cancel` nằm ở group_utils cùng /cancel.)

Trong callback, người bấm là `callback.from_user` — `callback.message.from_user`
là chính bot, nên các luồng nhận tg_id/user truyền vào thay vì tự đọc message.
"""

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from bot.handlers.checkin_out import tan_ca_van_phong, vao_ca_van_phong, xin_vi_tri
from bot.handlers.incident import IncidentState, bat_dau_su_co, gui_su_co
from bot.handlers.material_request import hoi_vat_tu
from bot.handlers.site_report import SiteReportState, bat_dau_bao_cao, gui_bao_cao, hien_du_an
from bot.keyboards import TEN_LENH, hien_ban_phim

router = Router()

_MENU = {
    "cmd_duan": "duan", "cmd_baocao": "baocao", "cmd_suco": "suco",
    "cmd_vatlieu": "vatlieu", "cmd_checkin": "checkin", "cmd_checkout": "checkout",
}


@router.callback_query(F.data.in_(set(_MENU)))
async def cb_menu(callback: types.CallbackQuery, state: FSMContext):
    cmd = _MENU[callback.data]
    await callback.answer()
    if await hien_ban_phim(callback.message, callback.from_user.id, cmd, van_phong=cmd in ("checkin", "checkout")):
        return
    # Không phụ trách dự án nào → chấm công văn phòng luôn
    if cmd == "checkin":
        await vao_ca_van_phong(callback.message, state, callback.from_user)
    else:
        await tan_ca_van_phong(callback.message, callback.from_user)


@router.callback_query(F.data.startswith("pick:"))
async def cb_pick(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer()
        return
    _, cmd, code = parts
    await callback.answer()
    nhan = "🏢 Văn phòng" if code == "VP" else code
    try:  # gỡ bàn phím để không bấm lại lần hai
        await callback.message.edit_text(f"{TEN_LENH.get(cmd, cmd)} — <b>{nhan}</b>")
    except Exception:
        pass

    await state.clear()  # bấm dự án mới = bỏ luồng dở dang trước đó
    m, user = callback.message, callback.from_user
    if cmd == "duan":
        await hien_du_an(m, user.id, code)
    elif cmd == "baocao":
        await bat_dau_bao_cao(m, state, code)
    elif cmd == "suco":
        await bat_dau_su_co(m, state, code)
    elif cmd == "vatlieu":
        await hoi_vat_tu(m, state, code)
    elif cmd == "checkin":
        if code == "VP":
            await vao_ca_van_phong(m, state, user)
        else:
            await xin_vi_tri(m, state, code)
    elif cmd == "checkout":
        if code == "VP":
            await tan_ca_van_phong(m, user)
        else:
            await xin_vi_tri(m, state, code, ra_ca=True)


@router.callback_query(F.data == "fsm:anh")
async def cb_them_anh(callback: types.CallbackQuery):
    await callback.answer("Bấm 📎 (ghim) → Ảnh hoặc Camera, gửi bao nhiêu ảnh cũng được.", show_alert=True)


@router.callback_query(F.data == "fsm:done")
async def cb_gui(callback: types.CallbackQuery, state: FSMContext):
    hien_tai = await state.get_state()
    if hien_tai == SiteReportState.collecting_photos.state:
        await callback.answer("Đang gửi…")
        await gui_bao_cao(callback.message, state, callback.from_user.id)
    elif hien_tai == IncidentState.collecting_photos.state:
        await callback.answer("Đang gửi…")
        await gui_su_co(callback.message, state, callback.from_user.id)
    else:
        await callback.answer("Không có báo cáo nào đang chờ gửi.", show_alert=True)
