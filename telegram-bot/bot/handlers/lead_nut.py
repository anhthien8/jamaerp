"""Nút trên tin nhắc việc về lead (R00 mục 4, 14/11/2026).

Sale hiếm khi mở app: tin bot nhắc chăm khách / báo được giao lead kèm nút, một chạm là
ghi xong vào ERP — cùng lõi với web (POST /telegram/lead/{id}/touch, server chỉ nhận
lead người bấm đang phụ trách).

callback_data `ld:<việc>:<lead_id>` (≤64 byte):
  goi            Đã gọi
  gz             mở hàng con «Gặp trực tiếp / Zoom-online / Khách lên văn phòng»
  gap|zoom|vp    ghi lần gặp tương ứng
  hl             mở hàng con «Mai / 3 ngày / 1 tuần»
  h1|h3|h7       hẹn lại sau 1 / 3 / 7 ngày (09:00 giờ VN, server tính)
  kh             không hẹn — thu bàn phím về «Mở ERP»
  mat            mở danh sách lý do mất
  m0..m4         chuyển lead sang «Mất» với lý do tương ứng (PUT /leads/{id}/stage)
  bk             quay lại hàng nút chính
"""

import html
import logging
from datetime import datetime, timedelta, timezone

from aiogram import F, Router, types

from bot.api_client import api

logger = logging.getLogger(__name__)
router = Router()

VN = timezone(timedelta(hours=7))

# Khớp LOST_REASONS của web (frontend/src/app/leads/page.tsx).
LY_DO_MAT = [
    "Ngân sách không phù hợp",
    "Đã chọn đối thủ",
    "Không phản hồi",
    "Thay đổi kế hoạch",
    "Lý do khác",
]

HOI_HEN = "Hẹn lại khi nào?"
SO_NGAY_HEN = {"h1": 1, "h3": 3, "h7": 7}
VIEC_GHI = {"goi", "gap", "zoom", "vp"}

Hang = list[list[types.InlineKeyboardButton]]


def _nut(text: str, viec: str, lead_id: str) -> types.InlineKeyboardButton:
    return types.InlineKeyboardButton(text=text, callback_data=f"ld:{viec}:{lead_id}")


def hang_nut_chinh(lead_id: str) -> Hang:
    """Hàng nút chính trên tin về lead — khớp `nut_lead()` phía server."""
    return [
        [_nut("Đã gọi", "goi", lead_id), _nut("Đã gặp/Zoom", "gz", lead_id)],
        [_nut("Hẹn lại", "hl", lead_id)],
    ]


def hang_hen(lead_id: str, *, sau_khi_ghi: bool = False) -> Hang:
    """Chọn ngày hẹn. Ngay sau khi ghi một lần chạm: «Không hẹn» khép lại tin;
    mở từ hàng chính: «Quay lại» (chưa ghi gì, đổi ý thì về hàng chính)."""
    cuoi = _nut("Không hẹn", "kh", lead_id) if sau_khi_ghi else _nut("Quay lại", "bk", lead_id)
    return [
        [_nut("Mai", "h1", lead_id), _nut("3 ngày", "h3", lead_id), _nut("1 tuần", "h7", lead_id)],
        [cuoi],
    ]


def hang_gap(lead_id: str) -> Hang:
    return [
        [_nut("Gặp trực tiếp", "gap", lead_id), _nut("Zoom/online", "zoom", lead_id)],
        [_nut("Khách lên văn phòng", "vp", lead_id)],
        [_nut("Quay lại", "bk", lead_id)],
    ]


def hang_ly_do_mat(lead_id: str, quay_lai: str = "bk") -> Hang:
    hang = [[_nut(ly_do, f"m{i}", lead_id)] for i, ly_do in enumerate(LY_DO_MAT)]
    hang.append([_nut("Quay lại", quay_lai, lead_id)])
    return hang


HANG_CON = {"gz": hang_gap, "hl": hang_hen, "mat": hang_ly_do_mat, "bk": hang_nut_chinh}


def _nut_mo_erp(message: types.Message) -> Hang:
    """Giữ nút «Mở ERP» của tin gốc mỗi khi thay bàn phím."""
    mk = message.reply_markup
    for row in mk.inline_keyboard if mk else []:
        for b in row:
            if b.url and b.text == "Mở ERP":
                return [[b]]
    return []


def _ban_phim(message: types.Message, hang: Hang) -> types.InlineKeyboardMarkup | None:
    tat_ca = [*hang, *_nut_mo_erp(message)]
    return types.InlineKeyboardMarkup(inline_keyboard=tat_ca) if tat_ca else None


def _bo_cau_hoi_hen(goc: str) -> tuple[str, bool]:
    if goc.endswith(HOI_HEN):
        return goc[: -len(HOI_HEN)].rstrip(), True
    return goc, False


async def _sua_tin(message: types.Message, dong: str, hang: Hang, *, hoi_hen: bool = False) -> None:
    """Ghi thêm một dòng kết quả vào cuối tin + thay bàn phím.

    Dòng đầu tiên cách nội dung tin một dòng trống; dòng trả lời câu «Hẹn lại khi nào?»
    thì thay chỗ câu hỏi, nằm liền dưới dòng «Đã ghi …».
    """
    goc, vua_hoi = _bo_cau_hoi_hen(message.html_text or "")
    noi = "\n" if vua_hoi else "\n\n"
    text = f"{goc}{noi}{dong}"
    if hoi_hen:
        text += f"\n{HOI_HEN}"
    try:
        await message.edit_text(text, reply_markup=_ban_phim(message, hang))
    except Exception as e:  # tin quá cũ / không đổi gì — kết quả đã ghi, chỉ là không vẽ lại
        logger.info("Không sửa được tin lead: %s", e)


def _the_tg(message: types.Message | None) -> dict:
    if message is None:
        return {}
    return {"telegram_message_id": message.message_id, "telegram_chat_id": message.chat.id}


async def _bao_loi(callback: types.CallbackQuery, kq: dict | None) -> None:
    if kq is None:
        loi = "Không kết nối được ERP, thử lại sau ít phút"
    else:
        loi = kq.get("error")
        loi = loi if isinstance(loi, str) else "Không ghi được, mở ERP để làm tiếp"
    await callback.answer(loi[:190], show_alert=True)


def _gio_hen(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso).strftime("%H:%M %d/%m/%Y")
    except ValueError:
        return iso


async def _doi_ban_phim(callback: types.CallbackQuery, msg: types.Message | None, viec: str, lead_id: str):
    """Mở / đóng hàng nút con — chưa ghi gì vào ERP."""
    if msg is None:
        await callback.answer("Tin đã quá cũ, bấm «Mở ERP» để làm tiếp", show_alert=True)
        return
    try:
        if viec == "kh":
            # «Không hẹn» sau khi ghi: bỏ câu hỏi, chỉ còn «Mở ERP».
            goc, _ = _bo_cau_hoi_hen(msg.html_text or "")
            await msg.edit_text(goc, reply_markup=_ban_phim(msg, []))
        else:
            await msg.edit_reply_markup(reply_markup=_ban_phim(msg, HANG_CON[viec](lead_id)))
    except Exception as e:
        logger.info("Không đổi được bàn phím lead: %s", e)
    await callback.answer()


@router.callback_query(F.data.startswith("ld:"))
async def bam_nut_lead(callback: types.CallbackQuery):
    try:
        _, viec, lead_id = callback.data.split(":", 2)
    except ValueError:
        await callback.answer("Nút không hợp lệ", show_alert=True)
        return
    msg = callback.message if isinstance(callback.message, types.Message) else None
    tg_id = callback.from_user.id

    if viec in HANG_CON or viec == "kh":
        await _doi_ban_phim(callback, msg, viec, lead_id)
        return

    # Ghi một lần chạm khách → hỏi luôn hẹn lại khi nào.
    if viec in VIEC_GHI:
        kq = await api.lead_touch(tg_id, lead_id, {"viec": viec, **_the_tg(msg)})
        if not kq or kq.get("error"):
            await _bao_loi(callback, kq)
            return
        if not kq.get("moi_ghi"):
            await callback.answer("Đã ghi rồi")
            return
        await callback.answer("Đã ghi vào ERP")
        if msg:
            gio = datetime.now(VN).strftime("%H:%M")
            await _sua_tin(
                msg, f"<b>Đã ghi</b> {gio} · {html.escape(kq.get('noi_dung') or '')}",
                hang_hen(lead_id, sau_khi_ghi=True), hoi_hen=True,
            )
        return

    # Hẹn lại sau N ngày.
    if viec in SO_NGAY_HEN:
        kq = await api.lead_touch(
            tg_id, lead_id, {"viec": "hen", "hen_sau_ngay": SO_NGAY_HEN[viec], **_the_tg(msg)},
        )
        if not kq or kq.get("error"):
            await _bao_loi(callback, kq)
            return
        hen = _gio_hen((kq.get("lead") or {}).get("hen_tiep_luc"))
        await callback.answer(f"Đã hẹn lại {hen}")
        if msg:
            await _sua_tin(msg, f"<b>Đã hẹn lại</b> {hen}", [])
        return

    # Chuyển sang «Mất» với lý do đã chọn.
    if viec[:1] == "m" and viec[1:].isdigit() and int(viec[1:]) < len(LY_DO_MAT):
        ly_do = LY_DO_MAT[int(viec[1:])]
        kq = await api.change_stage(tg_id, lead_id, "lost", lost_reason=ly_do)
        if not kq or kq.get("error"):
            await _bao_loi(callback, kq)
            return
        await callback.answer("Đã chuyển lead sang Mất")
        if msg:
            await _sua_tin(msg, f"<b>Đã chuyển sang Mất</b> · {html.escape(ly_do)}", [])
        return

    await callback.answer("Nút này không còn dùng nữa", show_alert=True)
