"""Telegram (13/11/2026): nhóm lên supergroup tự đổi ID; ghi lại ai không nhận được tin bot."""
import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.database as database
from app.models.notification import SystemSetting
from app.services import telegram_notify
from tests.conftest import auth_header


class _Resp:
    def __init__(self, status: int, body: dict):
        self.status_code = status
        self._body = body
        self.text = str(body)

    def json(self):
        return self._body


@pytest.fixture
def gia_lap(monkeypatch, db_engine):
    """Telegram giả: `kich_ban[chat_id]` = (status, body). Ghi lại các chat_id đã gửi."""
    monkeypatch.setattr(database, "async_session", async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False))
    monkeypatch.setattr(telegram_notify, "_loi_cache", None)
    monkeypatch.setattr(telegram_notify.get_settings(), "TELEGRAM_BOT_TOKEN", "test-token", raising=False)
    da_gui: list[int] = []
    kich_ban: dict[int, tuple[int, dict]] = {}

    class _Client:
        def __init__(self, *a, **k): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

        async def post(self, url, json):
            da_gui.append(json["chat_id"])
            st, body = kich_ban.get(json["chat_id"], (200, {"ok": True}))
            return _Resp(st, body)

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    return da_gui, kich_ban


@pytest.mark.asyncio
async def test_nhom_len_supergroup_doi_id_va_gui_lai(gia_lap, db_session):
    da_gui, kich_ban = gia_lap
    db_session.add(SystemSetting(key="telegram_group_chat_id", value="-4001"))
    await db_session.commit()
    kich_ban[-4001] = (400, {"ok": False, "description": "Bad Request: group chat was upgraded to a supergroup chat",
                             "parameters": {"migrate_to_chat_id": -1009001}})
    assert await telegram_notify.send_telegram(-4001, "xin chào") is True
    assert da_gui == [-4001, -1009001]
    await db_session.refresh(await db_session.get(SystemSetting, "telegram_group_chat_id"))
    assert (await db_session.get(SystemSetting, "telegram_group_chat_id")).value == "-1009001"


@pytest.mark.asyncio
async def test_ghi_nguoi_chua_bam_start_roi_xoa_khi_gui_duoc(gia_lap, client: AsyncClient, admin_user, db_session):
    _, kich_ban = gia_lap
    admin_user.telegram_user_id = 777001
    await db_session.commit()
    kich_ban[777001] = (403, {"ok": False, "description": "Forbidden: bot can't initiate conversation with a user"})
    assert await telegram_notify.send_telegram(777001, "việc mới") is False

    r = await client.get("/api/v1/users/telegram-khong-nhan", headers=auth_header(admin_user))
    assert r.status_code == 200, r.text
    ds = r.json()["bi_tu_choi"]
    assert [x["id"] for x in ds] == [admin_user.id] and ds[0]["ly_do"] == "Chưa bấm Start với bot"

    # Người đó bấm Start → lần gửi sau thành công → tự ra khỏi danh sách
    kich_ban.pop(777001)
    assert await telegram_notify.send_telegram(777001, "việc mới") is True
    r = await client.get("/api/v1/users/telegram-khong-nhan", headers=auth_header(admin_user))
    assert r.json()["bi_tu_choi"] == []


def test_nhan_ly_do():
    assert telegram_notify.ly_do_loi("Forbidden: bot was blocked by the user") == "Đã chặn bot"
    assert telegram_notify.ly_do_loi("Bad Request: chat not found").startswith("Không tìm thấy chat")
    assert telegram_notify.ly_do_loi("Too Many Requests") is None
