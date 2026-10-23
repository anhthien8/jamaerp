"""Tài liệu dự án tải thẳng từ CRM (23/10/2026) — thay «gửi Telegram rồi dán link».

- Upload → sendDocument vào topic dự án, ghi final_file_url + lịch sử phiên bản.
- Link tải ký HMAC; sai chữ ký 404; file >20MB chuyển sang link tin nhắn Telegram.
- Chưa cấu hình nhóm Kho → 503 kèm hướng dẫn, không ghi gì.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media import ProjectDocument
from app.models.project import Task
from app.services import media_gateway
from tests.conftest import auth_header
from tests.test_media_gateway import KHO, FakeTelegram, kho  # noqa: F401 — fixture kho


class FakeTelegramFile(FakeTelegram):
    async def __call__(self, method, data, files=None):
        if method == "sendDocument":
            self.calls.append((method, data))
            self._msg += 1
            ten = files["document"][0]
            return {"message_id": self._msg, "document": {"file_id": f"doc-{self._msg}", "file_name": ten}}
        return await super().__call__(method, data, files)


@pytest.fixture
def tg(monkeypatch):
    fake = FakeTelegramFile()
    monkeypatch.setattr(media_gateway, "_tg", fake)
    media_gateway._chat_khong_co_topic.clear()
    return fake


async def _task(db_session, project) -> Task:
    return (await db_session.execute(select(Task).where(Task.project_id == project.id))).scalars().first()


@pytest.mark.asyncio
async def test_tai_file_ghi_phien_ban(client: AsyncClient, db_session: AsyncSession, admin_user, project, kho, tg, monkeypatch):  # noqa: F811
    task = await _task(db_session, project)
    h = auth_header(admin_user)
    r = await client.post("/api/v1/media/task-file", data={"task_id": task.id},
                          files={"file": ("Bản vẽ tầng 1.pdf", b"%PDF-1.4 abc", "application/pdf")}, headers=h)
    assert r.status_code == 201, r.text
    body = r.json()
    url = body["final_file_url"]
    assert url.startswith("/media/docs/") and url.endswith("B%E1%BA%A3n%20v%E1%BA%BD%20t%E1%BA%A7ng%201.pdf")
    assert body["final_file_versions"][-1]["label"] == "Bản vẽ tầng 1.pdf"
    gui = [d for m, d in tg.calls if m == "sendDocument"][0]
    assert gui["chat_id"] == KHO and gui["message_thread_id"] == "77"
    assert gui["caption"].startswith("#JMH_TEST 📁")

    async def fake_tai(doc):
        return b"%PDF-1.4 abc"
    monkeypatch.setattr("app.api.media.tai_tai_lieu", fake_tai)
    r = await client.get("/api/v1" + url)  # không cần JWT — link ký
    assert r.status_code == 200
    assert r.content == b"%PDF-1.4 abc"
    assert r.headers["content-disposition"].startswith("inline")

    sai = url.replace(url.split("/")[4], "0" * 16)
    r = await client.get("/api/v1" + sai)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_file_lon_chuyen_link_telegram(client: AsyncClient, db_session: AsyncSession, admin_user, project, kho, tg):  # noqa: F811
    doc = ProjectDocument(project_id=project.id, filename="nha.skp", size_bytes=30 * 1024 * 1024,
                          telegram_chat_id=KHO, telegram_message_id=555, telegram_file_id="x")
    db_session.add(doc)
    await db_session.commit()
    r = await client.get("/api/v1" + media_gateway.url_tai_lieu(doc), follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "https://t.me/c/1234567890/555"


@pytest.mark.asyncio
async def test_chua_cau_hinh_kho(client: AsyncClient, db_session: AsyncSession, admin_user, project, tg):
    task = await _task(db_session, project)
    r = await client.post("/api/v1/media/task-file", data={"task_id": task.id},
                          files={"file": ("a.dwg", b"AC1027", "application/octet-stream")},
                          headers=auth_header(admin_user))
    assert r.status_code == 503
    assert "dán link" in r.json()["detail"]
    assert (await db_session.execute(select(ProjectDocument))).scalars().first() is None


@pytest.mark.asyncio
async def test_nguoi_ngoai_khong_tai_duoc(client: AsyncClient, db_session: AsyncSession, project, sales_user, designer_user, kho, tg):  # noqa: F811
    project.pm_id = designer_user.id
    project.designer_id = designer_user.id
    project.sales_id = designer_user.id
    await db_session.commit()
    task = await _task(db_session, project)
    r = await client.post("/api/v1/media/task-file", data={"task_id": task.id},
                          files={"file": ("a.pdf", b"x", "application/pdf")}, headers=auth_header(sales_user))
    assert r.status_code == 403
