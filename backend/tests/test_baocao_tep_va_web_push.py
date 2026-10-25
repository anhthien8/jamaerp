"""/baocao gửi bản vẽ/PDF → chép vào topic dự án + báo người phụ trách; Web Push
(đăng ký máy, đẩy thông báo, dọn máy chết) — 25/10/2026."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.models.notification import Notification, SystemSetting
from app.models.media import ProjectDocument
from app.models.project import Project, Task, TaskActivity, TaskAssignee
from app.models.push_subscription import PushSubscription
from app.services import media_gateway, web_push
from tests.conftest import _uid, auth_header

KHO = "-1001234567890"


class FakeCopy:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    async def __call__(self, method, data, files=None):
        self.calls.append((method, data))
        if method == "createForumTopic":
            return {"message_thread_id": 77, "name": data["name"]}
        if method == "copyMessage":
            return {"message_id": 555}
        raise AssertionError(method)


@pytest.fixture
def tg(monkeypatch):
    fake = FakeCopy()
    monkeypatch.setattr(media_gateway, "_tg", fake)
    media_gateway._chat_khong_co_topic.clear()
    return fake


@pytest_asyncio.fixture
async def kho(db_session: AsyncSession):
    db_session.add(SystemSetting(key="storage_telegram_chat_id", value=KHO))
    await db_session.commit()


def _tep(project, **kw):
    return {
        "project_id": project.id, "from_chat_id": -1009999, "message_id": 42,
        "thread_id": 1, "file_id": "BQAC-big", "file_name": "file thiet ke test.skp",
        "mime": "application/octet-stream", "file_size": 221_400_000,
        "caption": "bản vẽ 2D tầng 1", **kw,
    }


@pytest.mark.asyncio
class TestTepVaoTopic:
    async def test_chep_vao_topic_va_ghi_tai_lieu(self, client: AsyncClient, admin_user, project, kho, tg, db_session):
        r = await client.post("/api/v1/media/document-from-telegram", headers=auth_header(admin_user), json=_tep(project))
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["link"] == "https://t.me/c/1234567890/555"
        copy = [d for m, d in tg.calls if m == "copyMessage"]
        assert len(copy) == 1
        assert copy[0]["message_thread_id"] == "77" and copy[0]["from_chat_id"] == "-1009999"
        assert "bản vẽ 2D tầng 1" in copy[0]["caption"]
        doc = await db_session.get(ProjectDocument, body["id"])
        assert doc.project_id == project.id and doc.size_bytes == 221_400_000
        assert doc.telegram_chat_id == KHO and doc.telegram_message_id == 555

    async def test_da_o_dung_topic_khong_chep_lai(self, client: AsyncClient, admin_user, project, kho, tg, db_session):
        project.telegram_topic_id = 77
        await db_session.commit()
        r = await client.post(
            "/api/v1/media/document-from-telegram", headers=auth_header(admin_user),
            json=_tep(project, from_chat_id=int(KHO), thread_id=77),
        )
        assert r.status_code == 201, r.text
        assert r.json()["link"] == "https://t.me/c/1234567890/42"
        assert not tg.calls

    async def test_chua_cau_hinh_kho_503(self, client: AsyncClient, admin_user, project, tg):
        r = await client.post("/api/v1/media/document-from-telegram", headers=auth_header(admin_user), json=_tep(project))
        assert r.status_code == 503


@pytest.mark.asyncio
async def test_bao_cao_bao_nguoi_phu_trach_tru_nguoi_gui(
    client: AsyncClient, admin_user, designer_user, sales_user, db_session,
):
    proj = Project(
        id=_uid(), code="JMH-PUSH1", name="Push", client_name="K", stage="design",
        status="active", total_value=1, pm_id=admin_user.id, sales_id=sales_user.id,
    )
    task = Task(id=_uid(), project_id=proj.id, title="Thiết kế", status="in_progress", stage="design", order=1)
    db_session.add_all([proj, task])
    await db_session.flush()
    db_session.add(TaskAssignee(task_id=task.id, user_id=designer_user.id))
    await db_session.commit()

    r = await client.post(
        "/api/v1/telegram/site-report", headers=auth_header(admin_user),
        json={
            "project_code": proj.code, "content": "bản vẽ 2D tầng 1", "reporter_tg_id": 900001,
            "attachments": [{"name": "a.skp", "size_text": "221.4 MB",
                             "link": "https://t.me/c/1234567890/555", "in_storage": True}],
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["notified"] == 2
    ds = (await db_session.execute(select(Notification).where(Notification.type == "site_report"))).scalars().all()
    assert {n.user_id for n in ds} == {designer_user.id, sales_user.id}
    assert all(n.link == f"/projects?id={proj.id}" for n in ds)
    act = await db_session.get(TaskActivity, r.json()["activity_id"])
    assert "topic dự án, nhóm Kho" in act.content


# ── Web Push ──────────────────────────────────────────────────────────────

@pytest.fixture
def vapid(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "VAPID_PUBLIC_KEY", "pub-test")
    monkeypatch.setattr(s, "VAPID_PRIVATE_KEY", "priv-test")


def _sub(i=1):
    return {"endpoint": f"https://fcm.googleapis.com/fcm/send/abc{i}", "keys": {"p256dh": "p" * 20, "auth": "a" * 8}}


@pytest.mark.asyncio
class TestPush:
    async def test_chua_cau_hinh_503(self, client: AsyncClient, admin_user, monkeypatch):
        monkeypatch.setattr(get_settings(), "VAPID_PRIVATE_KEY", "")
        r = await client.post("/api/v1/push/subscribe", headers=auth_header(admin_user), json=_sub())
        assert r.status_code == 503
        r = await client.get("/api/v1/push/public-key", headers=auth_header(admin_user))
        assert r.json()["enabled"] is False

    async def test_dang_ky_chuyen_may_va_huy(self, client: AsyncClient, admin_user, sales_user, vapid, db_session):
        h = auth_header(admin_user)
        assert (await client.post("/api/v1/push/subscribe", headers=h, json=_sub())).status_code == 201
        assert (await client.post("/api/v1/push/subscribe", headers=h, json=_sub())).status_code == 201
        assert (await client.get("/api/v1/push/status", headers=h)).json() == {"enabled": True, "devices": 1}
        # Cùng máy, người khác đăng nhập → máy chuyển sang người mới
        await client.post("/api/v1/push/subscribe", headers=auth_header(sales_user), json=_sub())
        assert (await client.get("/api/v1/push/status", headers=h)).json()["devices"] == 0
        await client.post("/api/v1/push/unsubscribe", headers=auth_header(sales_user), json={"endpoint": _sub()["endpoint"]})
        so = (await db_session.execute(select(func.count()).select_from(PushSubscription))).scalar_one()
        assert so == 0

    async def test_endpoint_khong_https_400(self, client: AsyncClient, admin_user, vapid):
        bad = {**_sub(), "endpoint": "http://evil.example/push"}
        assert (await client.post("/api/v1/push/subscribe", headers=auth_header(admin_user), json=bad)).status_code == 400

    async def test_gom_thong_bao_khi_flush(self, db_session, admin_user):
        db_session.info.pop(web_push.KHOA_HANG_DOI, None)
        db_session.add(Notification(user_id=admin_user.id, type="system", title="T", body="B", link="/x"))
        await db_session.flush()
        hang = db_session.info[web_push.KHOA_HANG_DOI]
        assert hang[-1]["title"] == "T" and hang[-1]["url"] == "/x"
        await db_session.rollback()
        assert web_push.KHOA_HANG_DOI not in db_session.info


@pytest.mark.asyncio
async def test_day_nhieu_xoa_may_chet(db_engine, db_session, admin_user, vapid, monkeypatch):
    for i in (1, 2):
        db_session.add(PushSubscription(
            user_id=admin_user.id, endpoint_hash=web_push.bam_endpoint(_sub(i)["endpoint"]),
            endpoint=_sub(i)["endpoint"], p256dh="p" * 20, auth="a" * 8,
        ))
    await db_session.commit()
    monkeypatch.setattr(web_push, "_gui_mot", lambda sub, payload: 410 if sub["endpoint"].endswith("2") else 201)
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    gui = await web_push.day_nhieu(
        [{"user_id": admin_user.id, "title": "Báo cáo mới", "body": "x", "url": "/", "tag": "1"}],
        session_factory=factory,
    )
    assert gui == 1
    con = (await db_session.execute(select(PushSubscription.endpoint))).scalars().all()
    assert con == [_sub(1)["endpoint"]]
