"""R00 — rà soát 23/11: tin không bị nuốt khi đang dở luồng nhập lead mới; bản tin/thẻ khách
không đăng vào nhóm; «Chọn lead khác» khi chỉ AI hiểu câu.

Chạy qua Dispatcher thật (thứ tự router như bot/main.py: lead_nut trước lead_intake) để bắt
đúng cách aiogram lọc theo trạng thái FSM.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher.event.bases import UNHANDLED
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import SendMessage

from bot.handlers import briefing, lead_intake, lead_nut
from bot.handlers.lead_intake import LeadIntakeState
from conftest import bam, chay, nhan_nut

LEAD = "1b2c3d4e-0000-4000-8000-00000000abcd"
KHAC = "9f8e7d6c-0000-4000-8000-00000000ef01"
UID = 111

# Gắn router một lần cho cả tệp (router chỉ gắn được vào một Dispatcher).
DP = Dispatcher(storage=MemoryStorage())
DP.include_router(lead_nut.router)
DP.include_router(lead_intake.router)
BOT = Bot(token="42:TEST")


@pytest.fixture
def gui(monkeypatch):
    """Mọi lời gọi Bot API (reply/answer/edit) → ghi lại, không ra mạng."""
    ds: list = []

    async def fake_call(self, method, request_timeout=None):
        ds.append(method)
        return True

    monkeypatch.setattr(Bot, "__call__", fake_call)
    return ds


@pytest.fixture
def api(monkeypatch):
    gia = SimpleNamespace(lead_touch=AsyncMock(), lead_doan=AsyncMock(), lead_the=AsyncMock(),
                          change_stage=AsyncMock(), parse_lead=AsyncMock(), ban_tin=AsyncMock())
    monkeypatch.setattr(lead_nut, "api", gia)
    monkeypatch.setattr(lead_intake, "api", gia)
    monkeypatch.setattr(briefing, "api", gia)
    return gia


def _tin_bot_ve_lead() -> dict:
    return {
        "message_id": 10, "date": 0, "chat": {"id": UID, "type": "private"},
        "from": {"id": 42, "is_bot": True, "first_name": "JAMA"},
        "text": "Lead mới được giao: Anh Nam",
        "reply_markup": {"inline_keyboard": [
            [{"text": "Đã gọi", "callback_data": f"ld:goi:{LEAD}"}],
            [{"text": "Mở ERP", "url": f"https://crm.jamahome.vn/leads?id={LEAD}"}],
        ]},
    }


def _update(text: str, reply: bool = False, mid: int = 20) -> types.Update:
    msg = {"message_id": mid, "date": 0, "chat": {"id": UID, "type": "private"},
           "from": {"id": UID, "is_bot": False, "first_name": "Sale"}, "text": text}
    if reply:
        msg["reply_to_message"] = _tin_bot_ve_lead()
    return types.Update.model_validate({"update_id": mid, "message": msg}, context={"bot": BOT})


def _ctx():
    return DP.fsm.get_context(BOT, chat_id=UID, user_id=UID)


async def _dat_trang_thai(st) -> None:
    await _ctx().set_state(st)


def _chu_da_gui(gui) -> list[str]:
    return [m.text for m in gui if isinstance(m, SendMessage)]


@pytest.mark.parametrize("trang_thai", [None, LeadIntakeState.confirming, LeadIntakeState.waiting_text])
def test_tra_loi_tin_lead_luon_ghi_du_dang_do_luong_nhap_lead(api, gui, trang_thai):
    api.lead_touch.return_value = {"ok": True, "moi_ghi": True, "lead": {"id": LEAD, "name": "Anh Nam"}}

    async def kich_ban():
        await _dat_trang_thai(trang_thai)
        kq = await DP.feed_update(BOT, _update("Khách chốt phương án 2, tuần sau ký", reply=True))
        assert kq is not UNHANDLED
        assert await _ctx().get_state() is None  # thẻ lead mới bỏ ngỏ đã thôi
    chay(kich_ban())
    payload = api.lead_touch.await_args.args[2]
    assert api.lead_touch.await_args.args[1] == LEAD
    assert payload["viec"] == "ghi_chu" and payload["noi_dung"] == "Khách chốt phương án 2, tuần sau ký"
    api.parse_lead.assert_not_awaited()


def test_the_lead_moi_bo_ngo_van_hoi_ghi_vao_lead(api, gui):
    api.lead_doan.return_value = {
        "la_bao_cham": True, "chac_chan": True, "viec": "goi", "hen_tiep_luc": None, "plan_type": None,
        "tom_tat": "Đã gọi", "ung_vien": [{"id": LEAD, "name": "Anh Nam", "stage_label": "Đang tư vấn",
                                           "duoi_sdt": "111"}], "goi_y": []}

    async def kich_ban():
        await _dat_trang_thai(LeadIntakeState.confirming)
        assert await DP.feed_update(BOT, _update("gọi anh Nam rồi")) is not UNHANDLED
        assert await _ctx().get_state() is None
    chay(kich_ban())
    assert any("Ghi vào lead <b>Anh Nam</b>" in t for t in _chu_da_gui(gui))


def test_the_lead_moi_bo_ngo_khong_nuot_tin_khac(api, gui):
    """Trước đây: trạng thái `confirming` không handler nào nhận chữ → tin mất im lặng."""
    api.lead_doan.return_value = {"la_bao_cham": False, "ung_vien": [], "goi_y": []}

    async def kich_ban():
        await _dat_trang_thai(LeadIntakeState.confirming)
        assert await DP.feed_update(BOT, _update("xin chào")) is not UNHANDLED
        assert await _ctx().get_state() is None
    chay(kich_ban())
    assert any(t.startswith("Bot chưa hiểu tin này.") for t in _chu_da_gui(gui))


def test_ngay_sau_lenh_lead_van_doc_lead_moi(api, gui):
    """/lead rồi dán thông tin khách: vẫn là luồng nhập lead mới, không bị đoán là báo chăm khách."""
    api.parse_lead.return_value = None

    async def kich_ban():
        await _dat_trang_thai(LeadIntakeState.waiting_text)
        await DP.feed_update(BOT, _update("Chị Hoa 0911222333 căn hộ 80m2 Ecopark"))
        # Phân tích hỏng → thôi trạng thái chờ, tin sau không bị đọc như lead mới
        assert await _ctx().get_state() is None
    chay(kich_ban())
    api.parse_lead.assert_awaited_once()
    api.lead_doan.assert_not_awaited()


# ── Bản tin / thẻ khách không đăng vào nhóm ──────────────────────────────────


def _tin_nhom(text: str = "/briefing") -> SimpleNamespace:
    return SimpleNamespace(text=text, chat=SimpleNamespace(type="supergroup", id=-100123),
                           from_user=SimpleNamespace(id=UID), answer=AsyncMock())


def test_briefing_trong_nhom_khong_tai_du_lieu(api):
    m = _tin_nhom()
    chay(briefing.cmd_briefing(m))
    assert m.answer.await_args.args[0] == briefing.CHI_CHAT_RIENG
    api.ban_tin.assert_not_awaited()


def test_the_khach_tu_ban_tin_trong_nhom_khong_dang(api):
    msg = SimpleNamespace(chat=SimpleNamespace(type="supergroup", id=-100123), answer=AsyncMock(),
                          reply_markup=None, message_id=5)
    cb = bam(f"ld:bt:{LEAD}", message=msg)
    chay(lead_nut.bam_nut_lead(cb))
    api.lead_the.assert_not_awaited()
    msg.answer.assert_not_awaited()
    assert cb.answer.await_args.kwargs.get("show_alert") is True


# ── «Chọn lead khác» khi chỉ AI hiểu câu ─────────────────────────────────────


def test_chon_lead_khac_khi_bo_luat_khong_ra_gi_thi_lay_khach_dang_cham(api):
    goi_y = [{"id": LEAD, "name": "Chị Mai – Ecopark", "duoi_sdt": "678"},
             {"id": KHAC, "name": "Anh Nam – Vinhomes", "duoi_sdt": "111"}]
    api.lead_doan.side_effect = [{"la_bao_cham": False, "ung_vien": [], "goi_y": []},
                                 {"la_bao_cham": False, "ung_vien": [], "goi_y": goi_y}]
    goc = SimpleNamespace(text="khách Ecopark chốt layout rồi", message_id=200,
                          chat=SimpleNamespace(type="private", id=UID))
    msg = SimpleNamespace(html_text="Ghi chú\nGhi vào lead <b>Chị Mai</b>?", reply_to_message=goc,
                          chat=SimpleNamespace(type="private", id=UID), edit_text=AsyncMock(), message_id=201)
    chay(lead_nut.bam_xac_nhan_lead(bam(f"lk:n:-:-:{LEAD}", message=msg)))
    assert [c.args[1] for c in api.lead_doan.await_args_list] == ["khách Ecopark chốt layout rồi", ""]
    nut = nhan_nut(msg.edit_text.await_args.kwargs["reply_markup"])
    assert nut == [("Anh Nam – Vinhomes · …111", f"lt:n:-:-:{KHAC}"), ("Huỷ", "lx")]
