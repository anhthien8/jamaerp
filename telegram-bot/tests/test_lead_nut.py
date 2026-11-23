"""R00 mục 7-8: trả lời tin bot = ghi chú; gõ tự do → hỏi lại «Ghi vào lead …?» rồi mới ghi."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram import types
from aiogram.dispatcher.event.bases import SkipHandler

from bot.handlers import lead_nut
from conftest import bam, chay, nhan_nut

LEAD = "1b2c3d4e-0000-4000-8000-00000000abcd"
KHAC = "9f8e7d6c-0000-4000-8000-00000000ef01"
ERP = f"https://crm.jamahome.vn/leads?id={LEAD}"
VN = timezone(timedelta(hours=7))


def _mk(*hang):
    return types.InlineKeyboardMarkup(inline_keyboard=[list(h) for h in hang])


def _tin(text="", reply_to=None, markup=None, mid=50, html_text=None):
    return SimpleNamespace(
        text=text, html_text=html_text if html_text is not None else text, message_id=mid,
        chat=SimpleNamespace(type="private", id=111), from_user=SimpleNamespace(id=111),
        reply_to_message=reply_to, reply_markup=markup,
        reply=AsyncMock(), answer=AsyncMock(), edit_text=AsyncMock(), edit_reply_markup=AsyncMock(),
    )


def _tin_lead_cua_bot():
    """Tin nhắc chăm khách của bot: hàng nút ld:… + «Mở ERP»."""
    return _tin("Nhắc chăm sóc KH", markup=_mk(
        *lead_nut.hang_nut_chinh(LEAD), [types.InlineKeyboardButton(text="Mở ERP", url=ERP)],
    ), mid=10)


def _lead_tra_ve(**kw):
    return {"ok": True, "moi_ghi": True, "nhan": "Ghi chú", "noi_dung": "x",
            "lead": {"id": LEAD, "name": "Anh Nam – Vinhomes", "mo_erp": ERP}, **kw}


@pytest.fixture
def api(monkeypatch):
    gia = SimpleNamespace(lead_touch=AsyncMock(), lead_doan=AsyncMock(), change_stage=AsyncMock())
    monkeypatch.setattr(lead_nut, "api", gia)
    return gia


# ── Lead của một tin bot ─────────────────────────────────────────────────────


def test_lead_cua_tin_doc_nut_ld_hoac_link_mo_erp():
    assert lead_nut.lead_cua_tin(_tin_lead_cua_bot()) == LEAD
    chi_link = _tin(markup=_mk([types.InlineKeyboardButton(text="Mở ERP", url=ERP)]))
    assert lead_nut.lead_cua_tin(chi_link) == LEAD
    # Câu hỏi «Ghi vào lead nào?» chưa xác nhận → không coi là tin về lead đó
    cau_hoi = _tin(markup=_mk([types.InlineKeyboardButton(text="Đúng", callback_data=f"lt:g:-:-:{LEAD}")]))
    assert lead_nut.lead_cua_tin(cau_hoi) is None
    assert lead_nut.lead_cua_tin(_tin()) is None
    assert lead_nut.lead_cua_tin(None) is None


# ── Trả lời tin = ghi chú ────────────────────────────────────────────────────


def test_tra_loi_tin_lead_ghi_chu_dung_lead(api):
    api.lead_touch.return_value = _lead_tra_ve()
    m = _tin("Khách muốn thêm phòng làm việc", reply_to=_tin_lead_cua_bot(), mid=77)
    chay(lead_nut.tra_loi_tin_lead(m))
    api.lead_touch.assert_awaited_once_with(111, LEAD, {
        "viec": "ghi_chu", "noi_dung": "Khách muốn thêm phòng làm việc",
        "telegram_message_id": 77, "telegram_chat_id": 111,
    })
    text = m.reply.await_args.args[0]
    assert "Đã ghi chú" in text and "Anh Nam – Vinhomes" in text and lead_nut.HOI_HEN in text
    nut = m.reply.await_args.kwargs["reply_markup"]
    assert ("Mai", f"ld:h1:{LEAD}") in nhan_nut(nut)
    assert nut.inline_keyboard[-1][0].url == ERP


def test_tra_loi_tin_khong_phai_lead_thi_bo_qua(api):
    m = _tin("ok", reply_to=_tin("Chào buổi sáng"))
    with pytest.raises(SkipHandler):
        chay(lead_nut.tra_loi_tin_lead(m))
    api.lead_touch.assert_not_awaited()


def test_tra_loi_lead_khong_phu_trach_bao_loi(api):
    api.lead_touch.return_value = {"error": "Lead này không do bạn phụ trách"}
    m = _tin("ghi thêm", reply_to=_tin_lead_cua_bot())
    chay(lead_nut.tra_loi_tin_lead(m))
    assert m.reply.await_args.args[0] == "Lead này không do bạn phụ trách"


# ── Gõ tự do ─────────────────────────────────────────────────────────────────


def _doan(**kw):
    return {"la_bao_cham": True, "chac_chan": True, "viec": "gap", "hen_tiep_luc": "2026-11-24T09:00:00",
            "plan_type": None, "tom_tat": "Đã gặp trực tiếp · hẹn lại 09:00 thứ Ba 24/11",
            "ung_vien": [{"id": LEAD, "name": "Anh Nam – Vinhomes", "stage_label": "Đang tư vấn", "duoi_sdt": "111"}],
            "goi_y": [{"id": KHAC, "name": "Chị Mai – Ecopark", "stage_label": "Đang tư vấn", "duoi_sdt": "678"}],
            **kw}


def test_cau_tu_do_chac_chan_hoi_dung_khong(api):
    api.lead_doan.return_value = _doan()
    m = _tin("gặp anh Nam Vinhomes xong, khách xin 3 ngày")
    chay(lead_nut.cau_tu_do(m))
    text = m.reply.await_args.args[0]
    assert text.startswith("Đã gặp trực tiếp · hẹn lại 09:00 thứ Ba 24/11\nGhi vào lead <b>Anh Nam – Vinhomes</b>")
    nut = nhan_nut(m.reply.await_args.kwargs["reply_markup"])
    assert nut == [("Đúng", f"lt:m:2611240900:-:{LEAD}"), ("Chọn lead khác", f"lk:m:2611240900:-:{LEAD}"),
                   ("Huỷ", "lx")]
    assert all(len(d.encode()) <= 64 for _, d in nut)
    api.lead_touch.assert_not_awaited()  # chưa ghi gì


def test_cau_tu_do_chua_chac_cho_chon_lead(api):
    api.lead_doan.return_value = _doan(chac_chan=False, viec="goi", hen_tiep_luc=None, tom_tat="Đã gọi")
    m = _tin("gọi rồi")
    chay(lead_nut.cau_tu_do(m))
    assert m.reply.await_args.args[0] == "Đã gọi\nGhi vào lead nào?"
    nut = nhan_nut(m.reply.await_args.kwargs["reply_markup"])
    assert nut == [("Anh Nam – Vinhomes · …111", f"lt:g:-:-:{LEAD}"),
                   ("Chị Mai – Ecopark · …678", f"lt:g:-:-:{KHAC}"), ("Huỷ", "lx")]


def test_khong_phai_bao_cham_de_luong_lead_moi(api):
    api.lead_doan.return_value = {"la_bao_cham": False, "ung_vien": [], "goi_y": []}
    with pytest.raises(SkipHandler):
        chay(lead_nut.cau_tu_do(_tin("Anh Tuấn 0911222333 cần thiết kế căn hộ 80m2")))
    api.lead_doan.return_value = None  # ERP không trả lời → vẫn để luồng cũ lo
    with pytest.raises(SkipHandler):
        chay(lead_nut.cau_tu_do(_tin("xin chào")))


# ── Bấm Đúng / Chọn lead khác / Huỷ ──────────────────────────────────────────


def _cau_hoi(cau="gặp anh Nam Vinhomes xong, khách xin 3 ngày"):
    goc = _tin(cau, mid=200)
    return _tin(html_text="Đã gặp trực tiếp · hẹn lại 09:00 thứ Ba 24/11\nGhi vào lead <b>Anh Nam</b>?",
                reply_to=goc, mid=201)


def test_bam_dung_ghi_kem_hen_va_cau_goc(api):
    api.lead_touch.return_value = _lead_tra_ve(nhan="Đã gặp trực tiếp · hẹn lại 09:00 thứ Ba 24/11")
    hen = (datetime.now(VN) + timedelta(days=3)).replace(hour=9, minute=0, second=0, microsecond=0, tzinfo=None)
    msg = _cau_hoi()
    cb = bam(f"lt:m:{hen:%y%m%d%H%M}:f:{LEAD}", message=msg)
    chay(lead_nut.bam_xac_nhan_lead(cb))
    api.lead_touch.assert_awaited_once_with(111, LEAD, {
        "viec": "gap", "telegram_message_id": 200, "telegram_chat_id": 111,
        "noi_dung": "gặp anh Nam Vinhomes xong, khách xin 3 ngày",
        "hen_tiep_luc": hen.isoformat(), "plan_type": "offline",
    })
    text = msg.edit_text.await_args.args[0]
    assert text == "<b>Đã ghi</b> vào lead Anh Nam – Vinhomes: Đã gặp trực tiếp · hẹn lại 09:00 thứ Ba 24/11"
    nut = msg.edit_text.await_args.kwargs["reply_markup"].inline_keyboard
    assert len(nut) == 1 and nut[0][0].url == ERP  # đã có hẹn → chỉ còn «Mở ERP»


def test_bam_dung_hen_da_qua_thi_bo_hen_va_hoi_hen(api):
    api.lead_touch.return_value = _lead_tra_ve(nhan="Đã gặp trực tiếp")
    msg = _cau_hoi()
    chay(lead_nut.bam_xac_nhan_lead(bam(f"lt:m:2001010900:-:{LEAD}", message=msg)))
    assert "hen_tiep_luc" not in api.lead_touch.await_args.args[2]
    text = msg.edit_text.await_args.args[0]
    assert "Giờ hẹn trong câu đã qua" in text and text.endswith(lead_nut.HOI_HEN)


def test_chi_hen_ma_gio_da_qua_thi_khong_ghi(api):
    cb = bam(f"lt:h:2001010900:o:{LEAD}", message=_cau_hoi())
    chay(lead_nut.bam_xac_nhan_lead(cb))
    api.lead_touch.assert_not_awaited()
    assert cb.answer.await_args.kwargs.get("show_alert") is True


def test_chon_lead_khac_bo_lead_dang_hoi(api):
    api.lead_doan.return_value = _doan()
    msg = _cau_hoi()
    chay(lead_nut.bam_xac_nhan_lead(bam(f"lk:m:2611240900:-:{LEAD}", message=msg)))
    api.lead_doan.assert_awaited_once_with(111, "gặp anh Nam Vinhomes xong, khách xin 3 ngày", dung_ai=False)
    text = msg.edit_text.await_args.args[0]
    assert text == "Đã gặp trực tiếp · hẹn lại 09:00 thứ Ba 24/11\nGhi vào lead nào?"
    nut = nhan_nut(msg.edit_text.await_args.kwargs["reply_markup"])
    assert nut == [("Chị Mai – Ecopark · …678", f"lt:m:2611240900:-:{KHAC}"), ("Huỷ", "lx")]


def test_huy_khong_ghi(api):
    msg = _cau_hoi()
    chay(lead_nut.bam_xac_nhan_lead(bam("lx", message=msg)))
    assert msg.edit_text.await_args.args[0] == "Đã huỷ, không ghi gì."
    api.lead_touch.assert_not_awaited()
