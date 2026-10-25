"""Bàn phím bấm-chọn dùng chung (Đợt 3, 23/10/2026).

Nhân viên hiện trường không phải nhớ/gõ mã dự án: lệnh không tham số hiện
danh sách dự án đang chạy trong phạm vi của họ, bấm một nút là vào luồng.
Gõ mã tay (/baocao JMH-0601 ...) vẫn chạy như cũ.
"""

from aiogram import types

from bot.api_client import api

TEN_LENH = {
    "duan": "🏗 Xem dự án",
    "baocao": "📝 Báo cáo công trình",
    "suco": "🚨 Báo sự cố",
    "vatlieu": "📦 Yêu cầu vật tư",
    "checkin": "⏰ Vào ca",
    "checkout": "🕐 Tan ca",
    "baogia": "💰 Nhập báo giá NCC",
}

NUT_HUY = types.InlineKeyboardButton(text="❌ Hủy", callback_data="fsm:cancel")


def ban_phim_du_an(cmd: str, projects: list[dict], van_phong: bool = False) -> types.InlineKeyboardMarkup:
    """Mỗi dự án một nút `pick:<cmd>:<MÃ>` (≤64 byte), 2 nút/hàng."""
    nut = []
    for p in projects:
        ten = (p.get("name") or "")[:18]
        nut.append(types.InlineKeyboardButton(
            text=f"{p['code']} · {ten}" if ten else p["code"],
            callback_data=f"pick:{cmd}:{p['code']}"[:64],
        ))
    hang = [nut[i:i + 2] for i in range(0, len(nut), 2)]
    if van_phong:
        hang.insert(0, [types.InlineKeyboardButton(text="🏢 Văn phòng", callback_data=f"pick:{cmd}:VP")])
    hang.append([NUT_HUY])
    return types.InlineKeyboardMarkup(inline_keyboard=hang)


def nut_gui_anh(nhan_gui: str = "✅ Gửi") -> types.InlineKeyboardMarkup:
    """Nút cho bước gom ảnh: thêm ảnh (nhắc cách gửi) / gửi / hủy."""
    return types.InlineKeyboardMarkup(inline_keyboard=[[
        types.InlineKeyboardButton(text="📷 Thêm ảnh", callback_data="fsm:anh"),
        types.InlineKeyboardButton(text=nhan_gui, callback_data="fsm:done"),
        NUT_HUY,
    ]])


def nut_huy() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[[NUT_HUY]])


async def hien_ban_phim(message: types.Message, tg_id: int, cmd: str, van_phong: bool = False) -> bool:
    """Gửi bàn phím chọn dự án. Trả False khi người này không có dự án nào
    (để lệnh chấm công rơi về vào ca văn phòng)."""
    ds = await api.my_projects(tg_id)
    if not isinstance(ds, list):
        if van_phong:
            return False  # lỗi tra dự án không được chặn việc vào ca văn phòng
        if api.chua_lien_ket(tg_id):
            await message.answer(
                "🔗 Telegram của bạn chưa liên kết tài khoản CRM.\n"
                "Nhờ Admin vào <b>CRM → Tài khoản → «Telegram chưa gán»</b> bấm <b>Gán</b>.\n"
                f"Telegram ID: <code>{tg_id}</code>"
            )
            return True
        loi = ds.get("error") if isinstance(ds, dict) else "Máy chủ CRM đang bận, thử lại sau ít phút"
        await message.answer(f"❌ {loi}")
        return True
    if not ds and not van_phong:
        await message.answer(
            "📭 Bạn chưa phụ trách dự án nào đang chạy.\n"
            f"Gõ kèm mã nếu cần: <code>/{cmd} JMH-0601</code>"
        )
        return True
    if not ds:
        return False
    await message.answer(
        f"<b>{TEN_LENH.get(cmd, cmd)}</b> — chọn dự án:",
        reply_markup=ban_phim_du_an(cmd, ds, van_phong=van_phong),
    )
    return True
