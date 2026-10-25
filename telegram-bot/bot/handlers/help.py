"""/help — sổ tay dùng bot, hiện theo vai trò/phòng ban của người hỏi (25/10/2026).

Ai cũng thấy phần chung; thêm phần riêng cho Kinh doanh, Thu mua, Thiết kế/Giám sát,
Trưởng phòng/BGĐ. Người chưa gán tài khoản cũng xem được (/help nằm trong lệnh tự do).
"""

import os

from aiogram import Router, types
from aiogram.filters import Command

from bot.api_client import api

router = Router()

WEB_URL = os.getenv("WEB_URL", "https://crm.jamahome.vn").rstrip("/")

_CHUNG = (
    "📖 <b>Hướng dẫn dùng bot JAMA</b>\n"
    "Bấm nút hoặc gõ lệnh. Đang làm dở muốn thoát: /cancel.\n\n"
    "<b>Chấm công</b>\n"
    "• /checkin — vào ca. Chọn <i>Văn phòng</i> (cần bật GPS, trong 20 m) hoặc chọn dự án rồi gửi vị trí.\n"
    "• /checkout — tan ca.\n"
    "• /congcuatoi — công & giờ làm tháng này.\n\n"
    "<b>Công trình</b>\n"
    "• /duan — xem nhanh dự án (bấm chọn, không cần nhớ mã).\n"
    "• /baocao — báo cáo công trình: chọn dự án → gõ nội dung → gửi ảnh/bản vẽ/PDF → bấm ✅ Gửi. "
    "Ảnh vào Kho ảnh, tệp vào topic dự án.\n"
    "• /suco — báo sự cố kèm ảnh.\n"
    "• /vatlieu — yêu cầu vật tư cho công trình.\n\n"
    "<b>Cá nhân</b>\n"
    "• /nghiphep 12/11 13/11 lý do — xin nghỉ phép.\n"
    "• /tamung 2000000 lý do — xin tạm ứng (chat riêng).\n"
    "• /phieuluong — phiếu lương gần nhất (chỉ chat riêng với bot).\n"
    "• /choduyet — việc đang chờ bạn duyệt, bấm ✅/❌ ngay trên tin.\n"
    "• /feedback — góp ý về app/bot.\n"
    "• /id — Telegram ID / Chat ID (để Admin gán tài khoản hoặc cài nhóm).\n"
)

_KINH_DOANH = (
    "\n<b>Kinh doanh</b>\n"
    "• /lead — dán tin Zalo của khách, bot tự tách tên/SĐT/nhu cầu rồi tạo lead.\n"
    "• /pipeline — phễu lead của bạn. /briefing — việc cần làm hôm nay.\n"
    "• /dutoan — dự toán nhanh cải tạo.\n"
)

_THU_MUA = (
    "\n<b>Thu mua — nhập dữ liệu vật tư</b>\n"
    "• /baogia — chọn dự án → gửi <b>tệp báo giá NCC</b> (Excel/CSV/PDF/ảnh). "
    "Bot đọc, khớp mã với phiếu vật tư, hiện bản xem trước; bạn bấm <b>Ghi</b> mới lưu. "
    "Chốt giá & so NCC làm trên web.\n"
    "• /nhapmau &lt;link Google Sheet&gt; — thêm mẫu vào Danh mục (chỉ thêm mới, không ghi đè).\n"
    "• Không nhập từ Word (hợp đồng, biên bản) hay bảng giá tự do — chỉ bảng giá có mã sản phẩm.\n"
)

_QUAN_LY = (
    "\n<b>Trưởng phòng / Ban giám đốc</b>\n"
    "• /choduyet — duyệt nghỉ phép, tạm ứng, yêu cầu vật tư, hợp đồng ngay trên Telegram.\n"
    "• Kho ảnh: thả ảnh vào topic dự án trong nhóm «JAMA Công trình», bot tự ghi vào dự án.\n"
)

_CUOI = (
    f"\n🌐 Web: {WEB_URL} · Sổ tay đầy đủ: {WEB_URL}/huong-dan\n"
    "Bot bảo «chưa liên kết tài khoản»: nhờ Admin vào Tài khoản → «Telegram chưa gán» → Gán."
)

_PHONG_KD = {"SALES", "MARKETING", "BUSINESS", "KINH_DOANH"}
_PHONG_THU_MUA = {"PURCHASING", "PROCUREMENT"}
_VAI_QUAN_LY = {"admin", "executive", "accountant"}


def noi_dung_help(user: dict | None) -> str:
    """Ghép sổ tay theo vai; không rõ vai thì hiện hết (người mới chưa gán)."""
    phan = [_CHUNG]
    if not user:
        return "".join(phan + [_KINH_DOANH, _THU_MUA, _QUAN_LY, _CUOI])
    role = (user.get("role") or "").lower()
    dept = (user.get("department") or "").upper()
    la_quan_ly = role in _VAI_QUAN_LY or "leader" in role or role.endswith("_manager")
    if dept in _PHONG_KD or role.startswith("sale") or la_quan_ly:
        phan.append(_KINH_DOANH)
    if dept in _PHONG_THU_MUA or role == "admin" or "thumua" in role:
        phan.append(_THU_MUA)
    if la_quan_ly:
        phan.append(_QUAN_LY)
    phan.append(_CUOI)
    return "".join(phan)


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    user = await api.thong_tin(message.from_user.id)
    await message.answer(noi_dung_help(user or None), disable_web_page_preview=True)
