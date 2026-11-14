"""R00 (14/11/2026): tin Telegram kèm nút bấm + nút «Mở ERP» trỏ thẳng việc cần làm."""
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.database as database
from app.middleware.auth import hash_password
from app.models.lead import Lead
from app.models.notification import Notification, SystemSetting
from app.models.user import User
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


# ── R00 mục 6: tin về lead kèm hàng nút «Đã gọi · Đã gặp/Zoom · Hẹn lại · Mở ERP» ──

def _bat_tin(monkeypatch) -> list[tuple]:
    gui: list[tuple] = []

    async def fake_send(chat, text, parse_mode="HTML", reply_markup=None):
        gui.append((chat, text, reply_markup))
        return True

    monkeypatch.setattr(automation, "send_telegram", fake_send)
    monkeypatch.setattr(telegram_notify.get_settings(), "FRONTEND_URL", "http://localhost:3000", raising=False)
    return gui


def _lead_qua_han(owner_id: str, so_ngay: int, ten: str = "Anh Nam – Vinhomes") -> Lead:
    now = datetime.now(timezone.utc)
    return Lead(
        id=str(uuid.uuid4()), name=ten, phone="0909000111", stage="interested", assigned_to=owner_id,
        created_at=now - timedelta(days=so_ngay + 10), last_contacted_at=now - timedelta(days=so_ngay),
    )


def _hang_lead(lead_id: str) -> list[list[dict]]:
    return [
        [{"text": "Đã gọi", "callback_data": f"ld:goi:{lead_id}"},
         {"text": "Đã gặp/Zoom", "callback_data": f"ld:gz:{lead_id}"}],
        [{"text": "Hẹn lại", "callback_data": f"ld:hl:{lead_id}"}],
        [{"text": "Mở ERP", "url": f"https://crm.jamahome.vn/leads?id={lead_id}"}],
    ]


@pytest.mark.asyncio
async def test_nhac_cham_soc_kem_nut_lead_va_sdt_trong_chu(db_session, sales_user, monkeypatch):
    gui = _bat_tin(monkeypatch)
    sales_user.telegram_user_id = 555002
    lead = _lead_qua_han(sales_user.id, so_ngay=5)
    db_session.add(lead)
    await db_session.commit()

    assert (await automation.run_followup_reminders(db_session))["reminded"] == 1
    chat, text, mk = gui[0]
    assert chat == 555002
    assert "0909000111" in text  # SĐT nằm trong chữ — Telegram tự biến thành số bấm gọi
    assert mk["inline_keyboard"] == _hang_lead(lead.id)
    # callback_data của Telegram tối đa 64 byte — lead id là uuid 36 ký tự
    assert all(len(b["callback_data"].encode()) <= 64
               for h in mk["inline_keyboard"] for b in h if "callback_data" in b)


@pytest.mark.asyncio
async def test_thu_hoi_chi_nguoi_moi_nhan_nut_lead(db_session, sales_user, monkeypatch):
    gui = _bat_tin(monkeypatch)
    nguoi_moi = User(
        id=str(uuid.uuid4()), full_name="Sale Nhận", email="sale.nhan@test.com",
        password_hash=hash_password("x12345678"), role="data_entry", department="SALES",
        is_active=True, telegram_user_id=555004,
    )
    sales_user.telegram_user_id = 555003
    db_session.add(nguoi_moi)
    lead = _lead_qua_han(sales_user.id, so_ngay=10)
    db_session.add(lead)
    await db_session.commit()

    assert (await automation.run_lead_recall(db_session))["recalled"] == 1
    theo_nguoi = {chat: (text, mk) for chat, text, mk in gui}
    text_cu, mk_cu = theo_nguoi[555003]
    text_moi, mk_moi = theo_nguoi[555004]
    # Người cũ không còn giữ lead: chỉ còn «Mở ERP», không nút ghi chạm khách
    assert mk_cu["inline_keyboard"] == [[{"text": "Mở ERP", "url": f"https://crm.jamahome.vn/leads?id={lead.id}"}]]
    assert mk_moi["inline_keyboard"] == _hang_lead(lead.id)
    assert "0909000111" in text_moi
    assert text_cu.startswith("<b>Lead bị thu hồi") and text_moi.startswith("<b>Lead mới được giao")


@pytest.mark.asyncio
async def test_ten_khach_co_ky_tu_html_van_gui_duoc(db_session, sales_user, monkeypatch):
    gui = _bat_tin(monkeypatch)
    sales_user.telegram_user_id = 555005
    await db_session.commit()
    assert await automation._notify(db_session, sales_user, "lead_assigned", "Lead mới: A&B <VIP>",
                                    "Anh Tâm & chị Hoa", link="/leads?id=L9", ref_id="L9") is True
    _, text, _ = gui[0]
    assert text == "<b>Lead mới: A&amp;B &lt;VIP&gt;</b>\nAnh Tâm &amp; chị Hoa"
    # Trong app vẫn lưu chữ gốc, không bị thoát
    n = (await db_session.execute(select(Notification).where(Notification.ref_id == "L9"))).scalar_one()
    assert n.title == "Lead mới: A&B <VIP>"
