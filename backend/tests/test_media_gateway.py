"""Kho ảnh công trình (Đợt 2, 23/10/2026): chuẩn hoá ảnh, chống trùng, link ký,
topic Telegram theo dự án, ingest ảnh thả vào topic, báo cáo bot gắn ảnh,
portal khách chỉ thấy tiến độ + ảnh được chia sẻ, Drive chưa cấu hình."""

import io
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.media import MediaFile
from app.models.notification import SystemSetting
from app.models.project import Project, Task, TaskActivity
from app.services import drive_mirror, media_gateway
from app.services.media_gateway import normalize_image, url_media
from tests.conftest import _uid, auth_header

KHO = "-1001234567890"


def _png(w=3000, h=1000, mau=(10, 120, 200, 128)) -> bytes:
    out = io.BytesIO()
    Image.new("RGBA", (w, h), mau).save(out, format="PNG")
    return out.getvalue()


class FakeTelegram:
    """Thay `_tg` — ghi lại lời gọi, trả kết quả giống Bot API."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self._msg = 100

    async def __call__(self, method, data, files=None):
        self.calls.append((method, data))
        if method == "createForumTopic":
            return {"message_thread_id": 77, "name": data["name"]}
        if method == "sendPhoto":
            self._msg += 1
            return {"message_id": self._msg, "photo": [
                {"file_id": "small", "file_unique_id": "s", "width": 90, "height": 30},
                {"file_id": f"big-{self._msg}", "file_unique_id": f"u{self._msg}",
                 "width": 1280, "height": 427, "file_size": 5000},
            ]}
        if method == "sendMediaGroup":
            import json as _json
            out = []
            for _ in _json.loads(data["media"]):
                self._msg += 1
                out.append({"message_id": self._msg, "photo": [
                    {"file_id": f"big-{self._msg}", "file_unique_id": f"u{self._msg}",
                     "width": 1280, "height": 960},
                ]})
            self.files = files
            return out
        if method == "getFile":
            return {"file_path": "photos/x.jpg"}
        raise AssertionError(method)

    def dem(self, method):
        return sum(1 for m, _ in self.calls if m == method)


@pytest.fixture
def tg(monkeypatch):
    fake = FakeTelegram()
    monkeypatch.setattr(media_gateway, "_tg", fake)
    media_gateway._chat_khong_co_topic.clear()
    return fake


@pytest_asyncio.fixture
async def kho(db_session: AsyncSession):
    db_session.add(SystemSetting(key="storage_telegram_chat_id", value=KHO))
    await db_session.commit()


async def _gan_pic_thiet_ke(db_session, project, designer_user):
    # Dự án chưa có PIC đúng phòng thì ai cũng vào được (lối thoát «chưa phân
    # công») — gắn một PIC thật để kiểm phạm vi.
    project.pm_id = designer_user.id  # designer_user thuộc OPS → cột pm_id
    await db_session.commit()


async def _upload(client, user, project, data=None, **form):
    return await client.post(
        "/api/v1/media/upload",
        headers=auth_header(user),
        data={"project_id": project.id, **form},
        files={"file": ("a.png", data or _png(), "image/png")},
    )


# ── Chuẩn hoá ─────────────────────────────────────────────────────────────

def test_normalize_png_trong_suot_thanh_jpg_thu_nho():
    jpg, w, h = normalize_image(_png())
    assert jpg[:3] == b"\xff\xd8\xff"
    assert (w, h) == (1920, 640)


def test_normalize_tu_choi_file_khong_phai_anh():
    with pytest.raises(media_gateway.MediaError) as e:
        normalize_image(b"not an image")
    assert "HEIC" in str(e.value)


# ── Upload từ web ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestUpload:
    async def test_chua_cau_hinh_kho_tra_503(self, client: AsyncClient, admin_user, project, tg):
        resp = await _upload(client, admin_user, project)
        assert resp.status_code == 503
        assert "Kho ảnh" in resp.json()["detail"]

    async def test_upload_tao_topic_mot_lan_va_chong_trung(
        self, client: AsyncClient, admin_user, project, kho, tg, db_session
    ):
        r1 = await _upload(client, admin_user, project, caption="Đổ bê tông sàn")
        assert r1.status_code == 201, r1.text
        b1 = r1.json()
        assert b1["deduped"] is False
        assert b1["url"] == url_media(b1["id"])
        assert len(b1["url"]) < 100
        assert b1["shared_with_customer"] is True  # tien_do mặc định khách thấy
        assert (b1["width"], b1["height"]) == (1920, 640)

        r2 = await _upload(client, admin_user, project, data=_png(800, 600, (1, 2, 3, 255)), kind="su_co")
        assert r2.status_code == 201
        assert r2.json()["shared_with_customer"] is False  # sự cố không cho khách

        r3 = await _upload(client, admin_user, project)  # trùng ảnh đầu
        assert r3.json()["deduped"] is True
        assert r3.json()["id"] == b1["id"]

        assert tg.dem("createForumTopic") == 1
        assert tg.dem("sendPhoto") == 2
        gui = [d for m, d in tg.calls if m == "sendPhoto"][0]
        assert gui["message_thread_id"] == "77"
        assert gui["caption"].startswith("#JMH_TEST")
        await db_session.refresh(project)
        assert project.telegram_topic_id == 77

    async def test_nhom_khong_bat_topics_van_gui(
        self, client: AsyncClient, admin_user, project, kho, tg, monkeypatch
    ):
        async def khong_forum(method, data, files=None):
            if method == "createForumTopic":
                raise media_gateway.MediaError("Telegram từ chối: Bad Request: the chat is not a forum", 502)
            return await tg(method, data, files)

        monkeypatch.setattr(media_gateway, "_tg", khong_forum)
        resp = await _upload(client, admin_user, project)
        assert resp.status_code == 201
        gui = [d for m, d in tg.calls if m == "sendPhoto"][0]
        assert "message_thread_id" not in gui

    async def test_kind_sai_tra_400(self, client: AsyncClient, admin_user, project, kho, tg):
        resp = await _upload(client, admin_user, project, kind="linh_tinh")
        assert resp.status_code == 400

    async def test_nguoi_ngoai_du_an_khong_upload_duoc(
        self, client: AsyncClient, sales_user, designer_user, project, kho, tg, db_session
    ):
        await _gan_pic_thiet_ke(db_session, project, designer_user)
        resp = await _upload(client, sales_user, project)
        assert resp.status_code == 403
        assert tg.dem("sendPhoto") == 0


# ── Xem, liệt kê, chia sẻ ─────────────────────────────────────────────────

@pytest.mark.asyncio
class TestXemVaChiaSe:
    async def test_link_ky_sai_404_dung_200(
        self, client: AsyncClient, admin_user, project, kho, tg, monkeypatch
    ):
        media_id = (await _upload(client, admin_user, project)).json()["id"]

        async def fake_tai(db, media):
            return b"\xff\xd8\xffJPG"

        monkeypatch.setattr("app.api.media.tai_anh", fake_tai)
        assert (await client.get(f"/api/v1/media/{media_id}/0000000000000000.jpg")).status_code == 404
        ok = await client.get(f"/api/v1{url_media(media_id)}")
        assert ok.status_code == 200
        assert ok.headers["content-type"] == "image/jpeg"
        assert ok.content == b"\xff\xd8\xffJPG"

    async def test_list_va_patch(
        self, client: AsyncClient, admin_user, sales_user, designer_user, project, kho, tg, db_session
    ):
        await _gan_pic_thiet_ke(db_session, project, designer_user)
        media_id = (await _upload(client, admin_user, project)).json()["id"]
        lst = await client.get(f"/api/v1/media?project_id={project.id}", headers=auth_header(admin_user))
        assert lst.status_code == 200
        assert lst.json()["total"] == 1
        assert lst.json()["items"][0]["user_name"] == admin_user.full_name

        assert (await client.get(
            f"/api/v1/media?project_id={project.id}", headers=auth_header(sales_user)
        )).status_code == 403
        assert (await client.patch(
            f"/api/v1/media/{media_id}", json={"shared_with_customer": False},
            headers=auth_header(sales_user),
        )).status_code == 403

        p = await client.patch(
            f"/api/v1/media/{media_id}", json={"shared_with_customer": False, "caption": "Ảnh nội bộ"},
            headers=auth_header(admin_user),
        )
        assert p.status_code == 200
        assert p.json()["shared_with_customer"] is False
        assert p.json()["caption"] == "Ảnh nội bộ"

    async def test_status_chi_admin(self, client: AsyncClient, admin_user, sales_user, kho):
        assert (await client.get("/api/v1/media/status", headers=auth_header(sales_user))).status_code == 403
        body = (await client.get("/api/v1/media/status", headers=auth_header(admin_user))).json()
        assert body["storage_chat_configured"] is True
        assert body["drive_configured"] is False


# ── Ảnh từ bot / thả vào topic ────────────────────────────────────────────

@pytest.mark.asyncio
class TestTelegram:
    async def test_from_telegram_dang_lai_bang_file_id(
        self, client: AsyncClient, admin_user, project, kho, tg
    ):
        body = {"file_id": "AgACabc", "file_unique_id": "UQ1", "project_code": "jmh-test", "kind": "su_co"}
        r1 = await client.post("/api/v1/media/from-telegram", json=body, headers=auth_header(admin_user))
        assert r1.status_code == 201, r1.text
        assert r1.json()["shared_with_customer"] is False
        gui = [d for m, d in tg.calls if m == "sendPhoto"][0]
        assert gui["photo"] == "AgACabc"
        r2 = await client.post("/api/v1/media/from-telegram", json=body, headers=auth_header(admin_user))
        assert r2.json()["deduped"] is True
        assert tg.dem("sendPhoto") == 1

    async def test_ingest_theo_topic(
        self, client: AsyncClient, admin_user, project, kho, tg, db_session
    ):
        project.telegram_topic_id = 55
        await db_session.commit()
        base = {"file_id": "F1", "file_unique_id": "U1", "chat_id": int(KHO), "message_id": 9, "thread_id": 55}
        ok = await client.post("/api/v1/media/ingest-telegram", json=base, headers=auth_header(admin_user))
        assert ok.status_code == 201, ok.text
        assert ok.json()["project_code"] == "JMH-TEST"
        assert tg.dem("sendPhoto") == 0  # ảnh đã ở đúng chỗ, không đăng lại

        la = await client.post(
            "/api/v1/media/ingest-telegram", json={**base, "file_unique_id": "U2", "thread_id": 999},
            headers=auth_header(admin_user),
        )
        assert la.status_code == 404
        nhom_khac = await client.post(
            "/api/v1/media/ingest-telegram", json={**base, "file_unique_id": "U3", "chat_id": -100999},
            headers=auth_header(admin_user),
        )
        assert nhom_khac.status_code == 404

    async def test_bao_cao_cong_trinh_gan_anh_dung_du_an(
        self, client: AsyncClient, admin_user, project, kho, tg, db_session
    ):
        khac = Project(id=_uid(), code="JMH-OTHER", name="Khác", client_name="X", stage="design", status="active")
        db_session.add(khac)
        await db_session.commit()
        m1 = (await client.post("/api/v1/media/from-telegram", headers=auth_header(admin_user), json={
            "file_id": "A", "file_unique_id": "UA", "project_code": "JMH-TEST"})).json()["id"]
        m_khac = (await client.post("/api/v1/media/from-telegram", headers=auth_header(admin_user), json={
            "file_id": "B", "file_unique_id": "UB", "project_code": "JMH-OTHER"})).json()["id"]

        resp = await client.post("/api/v1/telegram/site-report", headers=auth_header(admin_user), json={
            "project_code": "JMH-TEST", "content": "Xong phần thô",
            "media_ids": [m_khac, m1], "photos": ["file-id-cu"], "reporter_tg_id": 900001,
        })
        assert resp.status_code == 201, resp.text
        act = await db_session.get(TaskActivity, resp.json()["activity_id"])
        assert act.media_url == url_media(m1)
        assert act.kind == "tien_do"
        assert "file-id-cu" not in act.content


# ── Nhật ký đầu việc từ web ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_nhieu_anh_gui_mot_album(
    client: AsyncClient, admin_user, project, kho, tg, db_session
):
    """3 ảnh mới + 1 ảnh trùng trong lượt → MỘT sendMediaGroup 3 ảnh, caption ở ảnh đầu."""
    a, b, c = (_png(400, 300, (i, 2, 3, 255)) for i in (10, 20, 30))
    resp = await client.post(
        "/api/v1/media/upload-batch", headers=auth_header(admin_user),
        data={"project_id": project.id, "caption": "Ốp lát phòng khách"},
        files=[("files", (f"{i}.png", d, "image/png")) for i, d in enumerate([a, b, c, a])],
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert len(body["items"]) == 4
    assert body["deduped_count"] == 1
    assert body["items"][3]["id"] == body["items"][0]["id"]
    assert tg.dem("sendMediaGroup") == 1
    assert tg.dem("sendPhoto") == 0
    import json as _json
    gui = [d for m, d in tg.calls if m == "sendMediaGroup"][0]
    media = _json.loads(gui["media"])
    assert len(media) == 3 and len(tg.files) == 3
    assert "Ốp lát phòng khách (3 ảnh)" in media[0]["caption"]
    assert "caption" not in media[1]
    assert gui["message_thread_id"] == "77"
    n = (await db_session.execute(select(func.count()).select_from(MediaFile))).scalar()
    assert n == 3

    # Gửi lại cả lô → không đăng gì thêm
    lai = await client.post(
        "/api/v1/media/upload-batch", headers=auth_header(admin_user),
        data={"project_id": project.id},
        files=[("files", ("a.png", a, "image/png")), ("files", ("b.png", b, "image/png"))],
    )
    assert lai.json()["deduped_count"] == 2
    assert tg.dem("sendMediaGroup") == 1


@pytest.mark.asyncio
async def test_upload_batch_mot_anh_dung_sendphoto(client: AsyncClient, admin_user, project, kho, tg):
    resp = await client.post(
        "/api/v1/media/upload-batch", headers=auth_header(admin_user),
        data={"project_id": project.id},
        files=[("files", ("a.png", _png(500, 500), "image/png"))],
    )
    assert resp.status_code == 201
    assert tg.dem("sendPhoto") == 1 and tg.dem("sendMediaGroup") == 0


@pytest.mark.asyncio
async def test_activity_base64_bi_chan_422_va_kind_tu_dong(client: AsyncClient, admin_user, project, db_session):
    task_id = (await db_session.execute(select(Task.id).where(Task.project_id == project.id))).scalars().first()
    to = await client.post(
        f"/api/v1/projects/tasks/{task_id}/activities", headers=auth_header(admin_user),
        json={"content": "ảnh", "media_url": "data:image/jpeg;base64," + "A" * 600},
    )
    assert to.status_code == 422
    ok = await client.post(
        f"/api/v1/projects/tasks/{task_id}/activities", headers=auth_header(admin_user),
        json={"content": "ảnh", "media_url": url_media("abc")},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["kind"] == "tien_do"
    ghi_chu = await client.post(
        f"/api/v1/projects/tasks/{task_id}/activities", headers=auth_header(admin_user),
        json={"content": "gọi khách hẹn lịch"},
    )
    assert ghi_chu.json()["kind"] == "khac"


# ── Portal khách ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_portal_chi_thay_tien_do_va_anh_duoc_chia_se(
    client: AsyncClient, admin_user, project, db_session
):
    cust = Customer(id=_uid(), name="Khách", phone="0900000009", type="individual",
                    portal_token=str(uuid.uuid4()), portal_enabled=True)
    db_session.add(cust)
    await db_session.flush()
    project.customer_id = cust.id
    task_id = (await db_session.execute(select(Task.id).where(Task.project_id == project.id))).scalars().first()
    for kind, noi_dung in (("tien_do", "Lát sàn xong"), ("su_co", "Nứt tường"),
                           ("vat_tu", "Yeu cau vat tu: xi"), ("cham_cong", "CHECK-IN")):
        db_session.add(TaskActivity(task_id=task_id, user_id=admin_user.id, content=noi_dung,
                                    kind=kind, media_url=url_media("x")))
    db_session.add_all([
        MediaFile(sha256="a", project_id=project.id, uploaded_by=admin_user.id, kind="tien_do",
                  shared_with_customer=True, telegram_file_id="f1", caption="Phòng khách"),
        MediaFile(sha256="b", project_id=project.id, kind="su_co", shared_with_customer=False,
                  telegram_file_id="f2"),
    ])
    await db_session.commit()

    goc = f"/api/v1/portal/{cust.portal_token}/projects/{project.id}"
    acts = (await client.get(f"{goc}/activities")).json()["activities"]
    assert [a["content"] for a in acts] == ["Lát sàn xong"]
    assert "media_url" not in acts[0]

    media = (await client.get(f"{goc}/media")).json()
    assert media["total"] == 1
    item = media["days"][0]["items"][0]
    assert item["caption"] == "Phòng khách"
    assert item["user_name"] == admin_user.full_name
    assert item["url"].startswith("/media/")

    khach_la = Customer(id=_uid(), name="Lạ", phone="0900000010", type="individual",
                        portal_token=str(uuid.uuid4()), portal_enabled=True)
    db_session.add(khach_la)
    await db_session.commit()
    assert (await client.get(
        f"/api/v1/portal/{khach_la.portal_token}/projects/{project.id}/media"
    )).status_code == 403


# ── Drive ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_drive_chua_cau_hinh_bo_qua_giu_pending(db_session, project):
    db_session.add(MediaFile(sha256="c", project_id=project.id, telegram_file_id="f"))
    await db_session.commit()
    res = await drive_mirror.sao_anh_cho(db_session)
    assert res["status"] == "skipped"
    st = await drive_mirror.trang_thai(db_session)
    assert st["pending"] == 1 and st["drive_configured"] is False
