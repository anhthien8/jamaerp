"""R00 (14/11/2026): tin Telegram kèm nút bấm + nút «Mở ERP» trỏ thẳng việc cần làm."""
import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.database as database
from app.models.notification import SystemSetting
from app.services import automation, telegram_notify


class _Resp:
    def __init__(self, status: int, body: dict):
        self.status_code = status
        self._body = body
        self.text = str(body)

    def json(self):
        return self._body


@pytest.fixture
def gia_lap(monkeypatch, db_engine):
    """Telegram giả: `kich_ban` = danh sách (status, body) trả lần lượt. Ghi lại payload đã gửi."""
    monkeypatch.setattr(database, "async_session", async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False))
    monkeypatch.setattr(telegram_notify, "_loi_cache", None)
    monkeypatch.setattr(telegram_notify.get_settings(), "TELEGRAM_BOT_TOKEN", "test-token", raising=False)
    monkeypatch.setattr(telegram_notify.get_settings(), "FRONTEND_URL", "http://localhost:3000", raising=False)
    da_gui: list[dict] = []
    kich_ban: list[tuple[int, dict]] = []

    class _Client:
        def __init__(self, *a, **k): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

        async def post(self, url, json):
            da_gui.append(dict(json))
            return _Resp(*(kich_ban.pop(0) if kich_ban else (200, {"ok": True})))

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    return da_gui, kich_ban


def test_mo_erp_tro_ve_erp_that_khi_may_dev(monkeypatch):
    monkeypatch.setattr(telegram_notify.get_settings(), "FRONTEND_URL", "http://localhost:3000", raising=False)
    assert telegram_notify.erp_url("/leads?id=abc") == "https://crm.jamahome.vn/leads?id=abc"
    assert telegram_notify.erp_url(None) is None
    monkeypatch.setattr(telegram_notify.get_settings(), "FRONTEND_URL", "https://erp.vidu.vn/", raising=False)
    assert telegram_notify.erp_url("leads?id=abc") == "https://erp.vidu.vn/leads?id=abc"
    mk = telegram_notify.ban_phim([[{"text": "Đã gọi", "callback_data": "ld:goi:abc"}], []], "/leads?id=abc")
    assert mk == {"inline_keyboard": [
        [{"text": "Đã gọi", "callback_data": "ld:goi:abc"}],
        [{"text": "Mở ERP", "url": "https://erp.vidu.vn/leads?id=abc"}],
    ]}
    assert telegram_notify.ban_phim(None, None) is None


@pytest.mark.asyncio
async def test_gui_kem_nut(gia_lap):
    da_gui, _ = gia_lap
    mk = telegram_notify.ban_phim(None, "/leads?id=1")
    assert await telegram_notify.send_telegram(777, "việc mới", reply_markup=mk) is True
    assert da_gui[0]["reply_markup"] == mk
    # Không nút → payload không có reply_markup (giữ nguyên tin cũ)
    assert await telegram_notify.send_telegram(777, "tin thường") is True
    assert "reply_markup" not in da_gui[1]


@pytest.mark.asyncio
async def test_nhom_len_supergroup_gui_lai_van_kem_nut(gia_lap, db_session):
    da_gui, kich_ban = gia_lap
    db_session.add(SystemSetting(key="telegram_group_chat_id", value="-4002"))
    await db_session.commit()
    kich_ban.append((400, {"ok": False, "description": "Bad Request: group chat was upgraded to a supergroup chat",
                           "parameters": {"migrate_to_chat_id": -1009002}}))
    mk = telegram_notify.ban_phim(None, "/projects?id=1")
    assert await telegram_notify.send_telegram(-4002, "báo nhóm", reply_markup=mk) is True
    assert [p["chat_id"] for p in da_gui] == [-4002, -1009002]
    assert da_gui[1]["reply_markup"] == mk


@pytest.mark.asyncio
async def test_nut_bi_tu_choi_van_gui_tin_khong_nut(gia_lap):
    da_gui, kich_ban = gia_lap
    kich_ban.append((400, {"ok": False, "description": "Bad Request: BUTTON_URL_INVALID"}))
    mk = {"inline_keyboard": [[{"text": "Mở ERP", "url": "https://x"}]]}
    assert await telegram_notify.send_telegram(777, "việc mới", reply_markup=mk) is True
    assert len(da_gui) == 2 and "reply_markup" in da_gui[0] and "reply_markup" not in da_gui[1]


@pytest.mark.asyncio
async def test_loi_nguoi_nhan_khong_gui_lai(gia_lap):
    """Người chặn bot: không thử lại không nút (vô ích), vẫn trả False như cũ."""
    da_gui, kich_ban = gia_lap
    kich_ban.append((403, {"ok": False, "description": "Forbidden: bot was blocked by the user"}))
    mk = telegram_notify.ban_phim(None, "/leads?id=1")
    assert await telegram_notify.send_telegram(777, "việc mới", reply_markup=mk) is False
    assert len(da_gui) == 1


@pytest.mark.asyncio
async def test_notify_luon_kem_mo_erp(db_session, sales_user, monkeypatch):
    gui: list[tuple] = []

    async def fake_send(chat, text, parse_mode="HTML", reply_markup=None):
        gui.append((chat, text, reply_markup))
        return True

    monkeypatch.setattr(automation, "send_telegram", fake_send)
    monkeypatch.setattr(telegram_notify.get_settings(), "FRONTEND_URL", "http://localhost:3000", raising=False)
    sales_user.telegram_user_id = 555001
    await db_session.commit()

    nut = [[{"text": "Đã gọi", "callback_data": "ld:goi:L1"}]]
    assert await automation._notify(db_session, sales_user, "lead_assigned", "Lead mới", "KH A",
                                    link="/leads?id=L1", ref_id="L1", nut=nut) is True
    chat, text, mk = gui[0]
    assert chat == 555001 and text.startswith("<b>Lead mới</b>")
    assert mk["inline_keyboard"] == [nut[0], [{"text": "Mở ERP", "url": "https://crm.jamahome.vn/leads?id=L1"}]]

    # Gửi lại ngay (vd redeploy chạy lại job) → chặn trùng trong khung giờ
    assert await automation._notify(db_session, sales_user, "lead_assigned", "Lead mới", "KH A",
                                    link="/leads?id=L1", ref_id="L1") is False
    assert len(gui) == 1
