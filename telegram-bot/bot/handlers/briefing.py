"""/briefing — bản tin «Hôm nay của bạn» (R00 mục 10, 21/11/2026).

Cùng nội dung tin bot gửi lúc 07:00 (server dựng: services/nhip_sale.dung_ban_tin):
hẹn hôm nay, hẹn hôm qua chưa có kết quả, khách cần gọi, đợt thu cần nhắc. Mỗi dòng một
nút: bấm là bot gửi thẻ khách có nút ghi việc (lead_nut: ld:bt / ld:bq).
"""

from aiogram import Router, types
from aiogram.filters import Command

from bot.api_client import api

router = Router()

KHONG_CO_VIEC = "Hôm nay chưa có hẹn, khách cần gọi hay đợt thu nào cần nhắc."
LOI_TAI = "Không tải được bản tin, thử lại sau ít phút (hoặc /start để đăng nhập lại)."


async def ban_tin_hom_nay(tg_user_id: int) -> tuple[str, types.InlineKeyboardMarkup | None]:
    """(chữ HTML, bàn phím) của bản tin — dùng cho /briefing và nút «Briefing» ở /start."""
    kq = await api.ban_tin(tg_user_id)
    if not kq or kq.get("error"):
        return LOI_TAI, None
    if not kq.get("text"):
        return KHONG_CO_VIEC, None
    mk = kq.get("reply_markup")
    return kq["text"], types.InlineKeyboardMarkup.model_validate(mk) if mk else None


CHI_CHAT_RIENG = "Bản tin có SĐT khách và tiền hợp đồng — chỉ xem trong chat riêng với bot, nhắn riêng /briefing nhé."


@router.message(Command("briefing"))
async def cmd_briefing(message: types.Message):
    if message.chat.type != "private":
        await message.answer(CHI_CHAT_RIENG)
        return
    text, mk = await ban_tin_hom_nay(message.from_user.id)
    await message.answer(text, reply_markup=mk)


@router.message(Command("suggest"))
async def cmd_suggest(message: types.Message):
    """Get AI suggestion — placeholder until lead selection UI."""
    await message.answer(
        "🤖 <b>AI Gợi ý</b>\n\n"
        "Sử dụng lệnh:\n"
        "<code>/suggest [ID lead]</code>\n\n"
        "Ví dụ: <code>/suggest abc12345</code>\n\n"
        "Bot sẽ phân tích và đề xuất hành động tiếp theo."
    )
