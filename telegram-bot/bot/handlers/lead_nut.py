"""Làm việc với lead ngay trên tin bot (R00 mục 4, 7, 8 — 14-21/11/2026).

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

Trả lời (reply) bằng chữ vào tin bot về một lead = ghi chú vào đúng lead đó (mục 7).

Gõ tự do «gặp anh Nam Vinhomes xong, khách xin 3 ngày» (mục 8): server đoán việc + hẹn +
lead trong số lead CỦA CHÍNH người gõ (POST /telegram/lead/doan), bot hỏi lại — không ghi mù:
  lt:<v>:<hẹn>:<p>:<lead_id>   Đúng / chọn lead này → ghi
  lk:<v>:<hẹn>:<p>:<lead_id>   Chọn lead khác
  lx                           Huỷ
  v: g gọi · m gặp · z Zoom · v khách lên VP · n ghi chú · h chỉ hẹn
  hẹn: YYMMDDHHMM giờ VN hoặc «-» · p: o online · f offline · s khảo sát · «-»
"""

import html
import logging
import re
from datetime import datetime, timedelta, timezone

from aiogram import F, Router, types
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.filters import StateFilter

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


def _loi(kq: dict | None) -> str:
    if kq is None:
        return "Không kết nối được ERP, thử lại sau ít phút"
    loi = kq.get("error")
    return loi if isinstance(loi, str) else "Không ghi được, mở ERP để làm tiếp"


async def _bao_loi(callback: types.CallbackQuery, kq: dict | None) -> None:
    await callback.answer(_loi(kq)[:190], show_alert=True)


def _tin_cua_nut(callback: types.CallbackQuery) -> types.Message | None:
    """Tin chứa nút; None khi Telegram không còn cho sửa (tin quá cũ)."""
    m = callback.message
    return None if m is None or isinstance(m, types.InaccessibleMessage) else m


def _ban_phim_lead(hang: Hang, lead: dict) -> types.InlineKeyboardMarkup | None:
    """Các hàng nút + «Mở ERP» trỏ thẳng lead (server trả `mo_erp`)."""
    url = lead.get("mo_erp")
    tat_ca = [*hang, *([[types.InlineKeyboardButton(text="Mở ERP", url=url)]] if url else [])]
    return types.InlineKeyboardMarkup(inline_keyboard=tat_ca) if tat_ca else None


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
    msg = _tin_cua_nut(callback)
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


# ── Trả lời tin bot = ghi chú (mục 7) ────────────────────────────────────────

_LINK_LEAD = re.compile(r"/leads\?id=([0-9a-fA-F-]{36})")


def lead_cua_tin(message) -> str | None:
    """Lead mà một tin của bot nói tới: nút `ld:` (id ở cuối) hoặc link «Mở ERP» `leads?id=`.

    Không đọc nút `lt:`/`lk:` của câu hỏi «Ghi vào lead nào?» — lead đó chưa được xác nhận.
    """
    mk = getattr(message, "reply_markup", None)
    for hang in mk.inline_keyboard if mk else []:
        for b in hang:
            if (b.callback_data or "").startswith("ld:"):
                return b.callback_data.rsplit(":", 1)[-1]
            m = _LINK_LEAD.search(b.url or "")
            if m:
                return m.group(1)
    return None


@router.message(
    StateFilter(None), F.chat.type == "private", F.text & ~F.text.startswith("/"), F.reply_to_message,
)
async def tra_loi_tin_lead(message: types.Message):
    lead_id = lead_cua_tin(message.reply_to_message)
    if not lead_id:
        raise SkipHandler()
    kq = await api.lead_touch(
        message.from_user.id, lead_id, {"viec": "ghi_chu", "noi_dung": message.text, **_the_tg(message)},
    )
    if not kq or kq.get("error"):
        await message.reply(_loi(kq))
        return
    if not kq.get("moi_ghi"):
        await message.reply("Ghi chú này đã ghi rồi.")
        return
    lead = kq.get("lead") or {}
    await message.reply(
        f"<b>Đã ghi chú</b> vào lead {html.escape(lead.get('name') or '')}\n{HOI_HEN}",
        reply_markup=_ban_phim_lead(hang_hen(lead_id, sau_khi_ghi=True), lead),
    )


# ── Gõ tự do → hỏi lại → ghi (mục 8) ─────────────────────────────────────────

MA_VIEC = {"goi": "g", "gap": "m", "zoom": "z", "vp": "v", "ghi_chu": "n", "hen": "h"}
VIEC_CUA_MA = {ma: viec for viec, ma in MA_VIEC.items()}
MA_LOAI_HEN = {"online": "o", "offline": "f", "survey": "s"}
LOAI_HEN_CUA_MA = {ma: loai for loai, ma in MA_LOAI_HEN.items()}
HOI_CHON = "Ghi vào lead nào?"
SO_LEAD_CHON = 6


def ma_viec(kq: dict) -> str:
    """`<v>:<hẹn>:<p>` — việc server đoán, gói vào callback_data."""
    hen = "-"
    if kq.get("hen_tiep_luc"):
        hen = datetime.fromisoformat(kq["hen_tiep_luc"]).strftime("%y%m%d%H%M")
    return f"{MA_VIEC[kq['viec']]}:{hen}:{MA_LOAI_HEN.get(kq.get('plan_type') or '', '-')}"


def _nut_cb(text: str, data: str) -> types.InlineKeyboardButton:
    return types.InlineKeyboardButton(text=text, callback_data=data)


def ban_phim_chon(ma: str, leads: list[dict]) -> types.InlineKeyboardMarkup:
    hang, da = [], set()
    for ld in leads:
        if ld["id"] in da or len(hang) >= SO_LEAD_CHON:
            continue
        da.add(ld["id"])
        ten = ld["name"] if len(ld["name"]) <= 40 else ld["name"][:39] + "…"
        hang.append([_nut_cb(f"{ten} · …{ld.get('duoi_sdt') or ''}", f"lt:{ma}:{ld['id']}")])
    hang.append([_nut_cb("Huỷ", "lx")])
    return types.InlineKeyboardMarkup(inline_keyboard=hang)


@router.message(StateFilter(None), F.chat.type == "private", F.text & ~F.text.startswith("/"))
async def cau_tu_do(message: types.Message):
    kq = await api.lead_doan(message.from_user.id, message.text)
    if not kq or kq.get("error") or not kq.get("la_bao_cham") or kq.get("viec") not in MA_VIEC:
        raise SkipHandler()  # không phải báo chăm khách → luồng nhập lead mới lo
    ma = ma_viec(kq)
    tom_tat = html.escape(kq.get("tom_tat") or "")
    ung = kq.get("ung_vien") or []
    if kq.get("chac_chan") and ung:
        u = ung[0]
        await message.reply(
            f"{tom_tat}\nGhi vào lead <b>{html.escape(u['name'])}</b> "
            f"({html.escape(u.get('stage_label') or '')}, SĐT đuôi {u.get('duoi_sdt') or ''})?",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [_nut_cb("Đúng", f"lt:{ma}:{u['id']}"), _nut_cb("Chọn lead khác", f"lk:{ma}:{u['id']}")],
                [_nut_cb("Huỷ", "lx")],
            ]),
        )
        return
    leads = [*ung, *(kq.get("goi_y") or [])]
    if not leads:
        raise SkipHandler()
    await message.reply(f"{tom_tat}\n{HOI_CHON}", reply_markup=ban_phim_chon(ma, leads))


def _gio_hen_tu_ma(hen: str) -> datetime | None:
    if hen == "-":
        return None
    try:
        return datetime.strptime(hen, "%y%m%d%H%M")
    except ValueError:
        return None


@router.callback_query(F.data.startswith(("lt:", "lk:")) | (F.data == "lx"))
async def bam_xac_nhan_lead(callback: types.CallbackQuery):
    msg = _tin_cua_nut(callback)
    if callback.data == "lx":
        if msg:
            try:
                await msg.edit_text("Đã huỷ, không ghi gì.", reply_markup=None)
            except Exception as e:
                logger.info("Không sửa được tin huỷ: %s", e)
        await callback.answer("Đã huỷ")
        return
    try:
        kieu, v, hen, p, lead_id = callback.data.split(":", 4)
        viec = VIEC_CUA_MA[v]
    except (ValueError, KeyError):
        await callback.answer("Nút không hợp lệ", show_alert=True)
        return
    goc = getattr(msg, "reply_to_message", None) if msg else None
    cau = (getattr(goc, "text", None) or "").strip()
    tg_id = callback.from_user.id

    if kieu == "lk":
        kq = await api.lead_doan(tg_id, cau, dung_ai=False)
        if not kq or kq.get("error"):
            await _bao_loi(callback, kq)
            return
        khac = [ld for ld in [*(kq.get("ung_vien") or []), *(kq.get("goi_y") or [])] if ld["id"] != lead_id]
        if not khac or msg is None:
            await callback.answer("Không còn lead nào khác đang chăm. Mở ERP để chọn.", show_alert=True)
            return
        dong_dau = (msg.html_text or "").split("\n", 1)[0]
        try:
            await msg.edit_text(f"{dong_dau}\n{HOI_CHON}", reply_markup=ban_phim_chon(f"{v}:{hen}:{p}", khac))
        except Exception as e:
            logger.info("Không đổi được danh sách lead: %s", e)
        await callback.answer()
        return

    # lt: ghi vào lead đã chọn
    hen_luc = _gio_hen_tu_ma(hen)
    qua_gio = hen_luc is not None and hen_luc <= datetime.now(VN).replace(tzinfo=None)
    if qua_gio:
        hen_luc = None
    if viec == "hen" and hen_luc is None:
        await callback.answer("Giờ hẹn đã qua — gõ lại giờ hẹn mới giúp nhé.", show_alert=True)
        return
    if viec == "ghi_chu" and not cau:
        await callback.answer("Không thấy câu gốc để ghi — gõ lại giúp nhé.", show_alert=True)
        return
    payload = {"viec": viec, **_the_tg(goc)}
    if cau:
        payload["noi_dung"] = cau
    if hen_luc is not None:
        payload["hen_tiep_luc"] = hen_luc.isoformat()
        if p in LOAI_HEN_CUA_MA:
            payload["plan_type"] = LOAI_HEN_CUA_MA[p]
    kq = await api.lead_touch(tg_id, lead_id, payload)
    if not kq or kq.get("error"):
        await _bao_loi(callback, kq)
        return
    await callback.answer("Đã ghi vào ERP" if kq.get("moi_ghi") else "Đã ghi rồi")
    if msg is None:
        return
    lead = kq.get("lead") or {}
    text = f"<b>Đã ghi</b> vào lead {html.escape(lead.get('name') or '')}: {html.escape(kq.get('nhan') or '')}"
    if qua_gio:
        text += "\nGiờ hẹn trong câu đã qua nên chưa đặt hẹn."
    hoi_hen = hen_luc is None
    if hoi_hen:
        text += f"\n{HOI_HEN}"
    try:
        await msg.edit_text(
            text, reply_markup=_ban_phim_lead(hang_hen(lead_id, sau_khi_ghi=True) if hoi_hen else [], lead),
        )
    except Exception as e:
        logger.info("Không sửa được tin xác nhận lead: %s", e)
