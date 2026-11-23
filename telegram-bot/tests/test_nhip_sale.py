"""R00 mục 9-10: nút kết quả buổi hẹn, thẻ khách từ bản tin sáng, /briefing, nhãn giai đoạn."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram import types

from bot.handlers import briefing, lead_nut, pipeline
from bot.nhan_giai_doan import NHAN_GIAI_DOAN
from conftest import bam, chay, nhan_nut

LEAD = "1b2c3d4e-0000-4000-8000-00000000abcd"
KHAC = "9f8e7d6c-0000-4000-8000-00000000ef01"
ERP = f"https://crm.jamahome.vn/leads?id={LEAD}"


def _tin(text="", markup=None, mid=10):
    return SimpleNamespace(
        text=text, html_text=text, message_id=mid, chat=SimpleNamespace(type="private", id=111),
        from_user=SimpleNamespace(id=999), reply_to_message=None, reply_markup=markup,
        reply=AsyncMock(), answer=AsyncMock(), edit_text=AsyncMock(), edit_reply_markup=AsyncMock(),
    )


def _mo_erp():
    return [types.InlineKeyboardButton(text="Mở ERP", url=ERP)]


def _cau_hoi_ket_qua():
    """Tin «Buổi hẹn với … thế nào?» server gửi (nut_ket_qua_hen + Mở ERP)."""
    return _tin("<b>Buổi hẹn với Anh Nam thế nào?</b>", types.InlineKeyboardMarkup(
        inline_keyboard=[*lead_nut.hang_ket_qua(LEAD, ERP), _mo_erp()]))


@pytest.fixture
def api(monkeypatch):
    gia = SimpleNamespace(lead_touch=AsyncMock(), lead_the=AsyncMock(), change_stage=AsyncMock(),
                          ban_tin=AsyncMock(), lead_doan=AsyncMock())
    monkeypatch.setattr(lead_nut, "api", gia)
    monkeypatch.setattr(briefing, "api", gia)
    return gia


def test_hang_ket_qua_khop_server():
    nut = nhan_nut(types.InlineKeyboardMarkup(inline_keyboard=lead_nut.hang_ket_qua(LEAD, ERP)))
    assert nut == [("Chốt được", None), ("Cần theo tiếp", f"ld:tt:{LEAD}"),
                   ("Khách hoãn", f"ld:ho:{LEAD}"), ("Mất", f"ld:mk:{LEAD}")]
    assert lead_nut.hang_ket_qua(LEAD, ERP)[0][0].url == f"{ERP}&chot=1"
    # Không có link lead → không có nút «Chốt được»
    assert [b.text for b in lead_nut.hang_ket_qua(LEAD)[0]] == ["Cần theo tiếp"]


def test_can_theo_tiep_mo_chon_hen_quay_lai_ve_ket_qua(api):
    msg = _cau_hoi_ket_qua()
    chay(lead_nut.bam_nut_lead(bam(f"ld:tt:{LEAD}", message=msg)))
    mk = msg.edit_reply_markup.await_args.kwargs["reply_markup"]
    assert nhan_nut(mk)[:4] == [("Mai", f"ld:h1:{LEAD}"), ("3 ngày", f"ld:h3:{LEAD}"),
                                ("1 tuần", f"ld:h7:{LEAD}"), ("Quay lại", f"ld:kq:{LEAD}")]
    assert mk.inline_keyboard[-1][0].url == ERP
    api.lead_touch.assert_not_awaited()
    # Quay lại → hàng kết quả, «Chốt được» dựng lại từ link «Mở ERP»
    chay(lead_nut.bam_nut_lead(bam(f"ld:kq:{LEAD}", message=msg)))
    mk = msg.edit_reply_markup.await_args.kwargs["reply_markup"]
    assert mk.inline_keyboard[0][0].text == "Chốt được" and mk.inline_keyboard[0][0].url == f"{ERP}&chot=1"


def test_khach_hoan_ghi_chu_roi_hoi_hen(api):
    api.lead_touch.return_value = {"ok": True, "moi_ghi": True, "noi_dung": "Khách hoãn buổi hẹn"}
    msg = _cau_hoi_ket_qua()
    chay(lead_nut.bam_nut_lead(bam(f"ld:ho:{LEAD}", message=msg)))
    api.lead_touch.assert_awaited_once_with(111, LEAD, {
        "viec": "ghi_chu", "noi_dung": "Khách hoãn buổi hẹn", "telegram_message_id": 10, "telegram_chat_id": 111,
    })
    text = msg.edit_text.await_args.args[0]
    assert "Khách hoãn buổi hẹn" in text and text.endswith(lead_nut.HOI_HEN)
    assert ("Không hẹn", f"ld:kh:{LEAD}") in nhan_nut(msg.edit_text.await_args.kwargs["reply_markup"])


def test_mat_chon_ly_do_quay_lai_ve_ket_qua(api):
    msg = _cau_hoi_ket_qua()
    chay(lead_nut.bam_nut_lead(bam(f"ld:mk:{LEAD}", message=msg)))
    nut = nhan_nut(msg.edit_reply_markup.await_args.kwargs["reply_markup"])
    assert nut[0] == ("Ngân sách không phù hợp", f"ld:m0:{LEAD}") and ("Quay lại", f"ld:kq:{LEAD}") in nut


def _ban_tin_msg():
    return _tin("<b>Hôm nay của bạn</b>", types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="1. Anh Nam", callback_data=f"ld:bt:{LEAD}"),
         types.InlineKeyboardButton(text="2. Chị Mai", callback_data=f"ld:bq:{KHAC}")],
        [types.InlineKeyboardButton(text="Mở ERP", url="https://crm.jamahome.vn/leads")],
    ]))


def _the(**kw):
    return {"lead": {"id": LEAD, "name": "Anh Nam – Vinhomes", "stage_label": "Đang tư vấn", "phone": "0909000111",
                     "mo_erp": ERP, "hen": [{"luc": "2026-11-24T09:00:00", "loai": "Khảo sát"}], **kw}}


def test_bam_dong_ban_tin_gui_the_khach(api):
    api.lead_the.return_value = _the()
    msg = _ban_tin_msg()
    chay(lead_nut.bam_nut_lead(bam(f"ld:bt:{LEAD}", message=msg)))
    api.lead_the.assert_awaited_once_with(111, LEAD)
    text = msg.answer.await_args.args[0]
    assert text == "<b>Anh Nam – Vinhomes</b> · Đang tư vấn\nSĐT 0909000111\nKhảo sát: 09:00 thứ Ba 24/11"
    mk = msg.answer.await_args.kwargs["reply_markup"]
    assert nhan_nut(mk)[:3] == [("Đã gọi", f"ld:goi:{LEAD}"), ("Đã gặp/Zoom", f"ld:gz:{LEAD}"), ("Hẹn lại", f"ld:hl:{LEAD}")]
    assert mk.inline_keyboard[-1][0].url == ERP
    msg.edit_text.assert_not_awaited()  # bản tin giữ nguyên


def test_bam_hen_hom_qua_gui_the_kem_nut_ket_qua(api):
    api.lead_the.return_value = _the()
    msg = _ban_tin_msg()
    chay(lead_nut.bam_nut_lead(bam(f"ld:bq:{LEAD}", message=msg)))
    text = msg.answer.await_args.args[0]
    assert text.endswith("Buổi hẹn hôm qua thế nào?")
    mk = msg.answer.await_args.kwargs["reply_markup"]
    assert mk.inline_keyboard[0][0].url == f"{ERP}&chot=1"
    assert ("Cần theo tiếp", f"ld:tt:{LEAD}") in nhan_nut(mk)


def test_the_khach_khong_phu_trach_bao_loi(api):
    api.lead_the.return_value = {"error": "Lead này không do bạn phụ trách"}
    cb = bam(f"ld:bt:{LEAD}", message=_ban_tin_msg())
    chay(lead_nut.bam_nut_lead(cb))
    assert cb.answer.await_args.args[0] == "Lead này không do bạn phụ trách"


def test_tra_loi_ban_tin_khong_ghi_nham_khach():
    """Bản tin nhiều khách: trả lời vào đó không được ghi chú vào khách đầu tiên."""
    assert lead_nut.lead_cua_tin(_ban_tin_msg()) is None
    assert lead_nut.lead_cua_tin(_cau_hoi_ket_qua()) == LEAD


def test_briefing_gui_ban_tin_kem_nut(api):
    api.ban_tin.return_value = {"text": "<b>Hôm nay của bạn</b>", "reply_markup": {"inline_keyboard": [
        [{"text": "1. Anh Nam", "callback_data": f"ld:bt:{LEAD}"}]]}}
    m = _tin("/briefing")
    m.from_user = SimpleNamespace(id=111)
    chay(briefing.cmd_briefing(m))
    assert m.answer.await_args.args[0] == "<b>Hôm nay của bạn</b>"
    assert nhan_nut(m.answer.await_args.kwargs["reply_markup"]) == [("1. Anh Nam", f"ld:bt:{LEAD}")]
    api.ban_tin.return_value = {"text": None, "reply_markup": None}
    chay(briefing.cmd_briefing(m))
    assert m.answer.await_args.args[0] == briefing.KHONG_CO_VIEC
    api.ban_tin.return_value = None
    chay(briefing.cmd_briefing(m))
    assert m.answer.await_args.args[0] == briefing.LOI_TAI


def test_nhan_giai_doan_khop_backend():
    assert NHAN_GIAI_DOAN == {
        "new": "Tiếp nhận mới", "interested": "Đang tư vấn", "surveyed": "Đã khảo sát",
        "survey_scheduled": "Đã gửi báo giá", "potential": "Đang đàm phán", "signed_design": "Deal đã thắng",
        "lost": "Mất", "dormant": "Ngủ đông",
    }
    assert pipeline.STAGE_LABELS is NHAN_GIAI_DOAN
