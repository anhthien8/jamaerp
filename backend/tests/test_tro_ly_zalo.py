"""Trợ lý Zalo (23/10/2026) — phạm vi xem, phiên lưu, đồng bộ nhóm, khách chờ, tóm tắt ngày."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.zalo import ZaloDigest, ZaloGroup, ZaloMessage, ZaloSignal, ZaloStaff
from app.services import zalo_assistant as tro_ly
from app.middleware.auth import hash_password
from tests.conftest import auth_header

ZALO_SECRET = "test-zalo-secret-abc"
ZH = {"X-Zalo-Secret": ZALO_SECRET}


@pytest.fixture(autouse=True)
def _set_zalo_secret(monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "ZALO_INGEST_SECRET", ZALO_SECRET)


@pytest.fixture(autouse=True)
def tele(monkeypatch):
    """Chặn Telegram thật, ghi lại (chat_id, text). Tắt AI để tóm tắt chạy bản đếm."""
    sent: list[tuple[int, str]] = []

    async def fake_send(chat_id, text, *a, **kw):
        sent.append((chat_id, text))
        return True

    async def no_llm(*a, **kw):
        return False

    monkeypatch.setattr("app.services.telegram_notify.send_telegram", fake_send)
    monkeypatch.setattr("app.services.llm_config.llm_available", no_llm)
    return sent


@pytest_asyncio.fixture
async def tp_sales(db_session: AsyncSession) -> User:
    """Trưởng phòng Kinh doanh (vai `leader`, phòng SALES)."""
    u = User(id=str(uuid.uuid4()), full_name="TP Kinh doanh", email="tpkd@test.com",
             password_hash=hash_password("x12345678"), role="leader", department="SALES",
             is_active=True, telegram_user_id=900101)
    db_session.add(u)
    await db_session.commit()
    return u


async def _nhom(db, zid, kind="customer", department=None, **kw) -> ZaloGroup:
    g = ZaloGroup(id=str(uuid.uuid4()), zalo_group_id=zid, name=kw.pop("name", f"Nhóm {zid}"),
                  kind=kind, monitoring=True, department=department, **kw)
    db.add(g)
    await db.commit()
    return g


async def _tin_hieu(db, group, summary, type_="quote_request"):
    s = ZaloSignal(id=str(uuid.uuid4()), group_id=group.id, type=type_, summary=summary, status="new")
    db.add(s)
    await db.commit()
    return s


def _naive_utc(**delta) -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(**delta)


class TestPhamVi:
    @pytest.mark.asyncio
    async def test_truong_phong_chi_thay_phong_minh(self, client, db_session, admin_user, tp_sales):
        g_kd = await _nhom(db_session, "kd", department="SALES")
        g_tk = await _nhom(db_session, "tk", department="DESIGN")
        await _tin_hieu(db_session, g_kd, "việc phòng KD")
        await _tin_hieu(db_session, g_tk, "việc phòng TK")

        r = await client.get("/api/v1/zalo/signals", headers=auth_header(tp_sales))
        tom = {s["summary"] for s in r.json()["items"]}
        assert "việc phòng KD" in tom and "việc phòng TK" not in tom

        ra = await client.get("/api/v1/zalo/signals", headers=auth_header(admin_user))
        assert {"việc phòng KD", "việc phòng TK"} <= {s["summary"] for s in ra.json()["items"]}

        ov = (await client.get("/api/v1/zalo/overview", headers=auth_header(tp_sales))).json()
        assert ov["scope"] == "phong" and ov["department"] == "SALES"
        assert ov["groups_monitored"] == 1
        assert ov["new_by_type"] == {"quote_request": 1}

    @pytest.mark.asyncio
    async def test_nhan_vien_khong_vao_trang(self, client, sales_user):
        for path in ("/api/v1/zalo/overview", "/api/v1/zalo/digests"):
            r = await client.get(path, headers=auth_header(sales_user))
            assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_truong_phong_xu_ly_tin_hieu_phong_minh(self, client, db_session, tp_sales):
        s_kd = await _tin_hieu(db_session, await _nhom(db_session, "kd2", department="SALES"), "a")
        s_tk = await _tin_hieu(db_session, await _nhom(db_session, "tk2", department="DESIGN"), "b")
        h = auth_header(tp_sales)
        r1 = await client.post(f"/api/v1/zalo/signals/{s_kd.id}/action", headers=h, json={"action": "actioned"})
        assert r1.status_code == 200
        r2 = await client.post(f"/api/v1/zalo/signals/{s_tk.id}/action", headers=h, json={"action": "actioned"})
        assert r2.status_code == 403

    @pytest.mark.asyncio
    async def test_gan_phong_cho_nhom(self, client, db_session, admin_user):
        g = await _nhom(db_session, "gp")
        h = auth_header(admin_user)
        r = await client.patch(f"/api/v1/zalo/groups/{g.id}", headers=h, json={"department": "OPS"})
        assert r.status_code == 200 and r.json()["department"] == "OPS"
        r = await client.patch(f"/api/v1/zalo/groups/{g.id}", headers=h, json={"department": "XYZ"})
        assert r.status_code == 422
        r = await client.patch(f"/api/v1/zalo/groups/{g.id}", headers=h, json={"department": ""})
        assert r.json()["department"] is None


class TestPhienVaNhom:
    def test_ma_hoa_phien_khu_hoi(self):
        tok = tro_ly.ma_hoa_phien({"cookie": [{"k": "v"}], "imei": "abc"})
        assert "abc" not in tok
        assert tro_ly.giai_ma_phien(tok) == {"cookie": [{"k": "v"}], "imei": "abc"}
        assert tro_ly.giai_ma_phien("rác") is None
        assert tro_ly.giai_ma_phien(None) is None

    @pytest.mark.asyncio
    async def test_credentials_luu_doc_xoa(self, client, admin_user):
        body = {"cookie": [{"name": "zpw", "value": "1"}], "imei": "imei-1", "user_agent": "UA"}
        assert (await client.post("/api/v1/zalo/ingest/credentials", headers=ZH, json=body)).status_code == 200
        # đang logged_out → không trả phiên (admin đã đăng xuất)
        assert (await client.get("/api/v1/zalo/ingest/credentials", headers=ZH)).json()["credentials"] is None
        await client.post("/api/v1/zalo/ingest/session", headers=ZH, json={"status": "logged_in", "account_name": "Bot"})
        c = (await client.get("/api/v1/zalo/ingest/credentials", headers=ZH)).json()["credentials"]
        assert c["imei"] == "imei-1" and c["userAgent"] == "UA"
        # admin đăng xuất → xóa luôn phiên
        await client.post("/api/v1/zalo/session/logout", headers=auth_header(admin_user))
        await client.post("/api/v1/zalo/ingest/session", headers=ZH, json={"status": "logged_in"})
        assert (await client.get("/api/v1/zalo/ingest/credentials", headers=ZH)).json()["credentials"] is None

    @pytest.mark.asyncio
    async def test_credentials_can_secret(self, client):
        r = await client.get("/api/v1/zalo/ingest/credentials", headers={"X-Zalo-Secret": "sai"})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_dong_bo_nhom_moi_tat_san(self, client, db_session):
        g = await _nhom(db_session, "co-san", name="Nhom co-san")
        r = await client.post("/api/v1/zalo/ingest/groups", headers=ZH, json={"groups": [
            {"zalo_group_id": "co-san", "name": "Tên thật", "member_count": 12},
            {"zalo_group_id": "moi", "name": "Nhóm mới", "member_count": 5},
        ]})
        assert r.json()["created"] == 1
        await db_session.refresh(g)
        assert g.name == "Tên thật" and g.member_count == 12 and g.monitoring is True
        moi = (await db_session.execute(select(ZaloGroup).where(ZaloGroup.zalo_group_id == "moi"))).scalar_one()
        assert moi.monitoring is False

    @pytest.mark.asyncio
    async def test_loi_dang_nhap_tat_yeu_cau_qr(self, client, admin_user):
        await client.post("/api/v1/zalo/session/login", headers=auth_header(admin_user))
        await client.post("/api/v1/zalo/ingest/session", headers=ZH, json={"status": "error", "error_msg": "QR hết hạn"})
        r = await client.get("/api/v1/zalo/ingest/pending-login", headers=ZH)
        assert r.json()["login_requested"] is False


class TestNhanVienVaKhachCho:
    @pytest.mark.asyncio
    async def test_nhan_vien_hoi_gia_trong_nhom_khach_khong_tinh(self, client, db_session):
        await _nhom(db_session, "noi-bo", kind="internal")
        await _nhom(db_session, "khach", kind="customer")
        await client.post("/api/v1/zalo/ingest/message", headers=ZH, json={
            "zalo_group_id": "noi-bo", "group_name": "NB", "sender_zalo_id": "nv1", "sender_name": "Sale A", "text": "ok",
        })
        assert await db_session.get(ZaloStaff, "nv1") is not None
        # nhân viên nhắc giá trong nhóm khách → không phải «khách hỏi giá»
        await client.post("/api/v1/zalo/ingest/message", headers=ZH, json={
            "zalo_group_id": "khach", "group_name": "K", "sender_zalo_id": "nv1", "sender_name": "Sale A",
            "text": "Em gửi anh báo giá bao nhiêu nhé",
        })
        # khách hỏi giá → có tín hiệu
        await client.post("/api/v1/zalo/ingest/message", headers=ZH, json={
            "zalo_group_id": "khach", "group_name": "K", "sender_zalo_id": "kh1", "sender_name": "Anh B",
            "text": "Cho anh hỏi báo giá bao nhiêu?",
        })
        sigs = (await db_session.execute(select(ZaloSignal).where(ZaloSignal.type == "quote_request"))).scalars().all()
        assert len(sigs) == 1
        msgs = (await db_session.execute(select(ZaloMessage).order_by(ZaloMessage.created_at))).scalars().all()
        assert [m.is_staff for m in msgs] == [True, True, False]

    @pytest.mark.asyncio
    async def test_khach_cho_qua_gio_bao_mot_lan(self, db_session, admin_user, tp_sales, tele):
        g = await _nhom(db_session, "kc", department="SALES")
        g_ok = await _nhom(db_session, "kc-ok", department="SALES")
        db_session.add_all([
            ZaloMessage(id=str(uuid.uuid4()), group_id=g.id, sender_name="Chị C", text="Bao giờ thi công?",
                        is_staff=False, created_at=_naive_utc(hours=3)),
            # nhóm này nhân viên đã trả lời sau cùng → không báo
            ZaloMessage(id=str(uuid.uuid4()), group_id=g_ok.id, sender_name="KH", text="?",
                        is_staff=False, created_at=_naive_utc(hours=4)),
            ZaloMessage(id=str(uuid.uuid4()), group_id=g_ok.id, sender_name="Sale", text="Dạ em gọi lại",
                        is_staff=True, created_at=_naive_utc(hours=3)),
        ])
        await db_session.commit()

        tao = await tro_ly.kiem_tra_khach_cho(db_session, gio=2)
        assert len(tao) == 1 and tao[0].group_id == g.id and tao[0].type == "unanswered"
        nguoi_nhan = {cid for cid, _ in tele}
        assert {admin_user.telegram_user_id, tp_sales.telegram_user_id} <= nguoi_nhan

        assert await tro_ly.kiem_tra_khach_cho(db_session, gio=2) == []  # không báo lặp

    @pytest.mark.asyncio
    async def test_chua_qua_gio_khong_bao(self, db_session):
        g = await _nhom(db_session, "kc2")
        db_session.add(ZaloMessage(id=str(uuid.uuid4()), group_id=g.id, sender_name="KH", text="alo",
                                   is_staff=False, created_at=_naive_utc(minutes=30)))
        await db_session.commit()
        assert await tro_ly.kiem_tra_khach_cho(db_session, gio=2) == []


class TestTomTatNgay:
    @pytest.mark.asyncio
    async def test_tom_tat_khong_ai_gui_dung_nguoi(self, client, db_session, admin_user, tp_sales, tele):
        g_kd = await _nhom(db_session, "dg-kd", department="SALES", name="Nhóm KD")
        g_tk = await _nhom(db_session, "dg-tk", department="DESIGN", name="Nhóm TK")
        for g in (g_kd, g_tk):
            db_session.add(ZaloMessage(id=str(uuid.uuid4()), group_id=g.id, sender_name="X", text="nội dung",
                                       is_staff=False, created_at=_naive_utc(minutes=5)))
        await db_session.commit()

        r = await client.post("/api/v1/zalo/digests/run", headers=auth_header(admin_user), params={"send": "true"})
        assert r.status_code == 200 and r.json()["groups"] == 2

        gui_admin = "\n".join(t for cid, t in tele if cid == admin_user.telegram_user_id)
        gui_tp = "\n".join(t for cid, t in tele if cid == tp_sales.telegram_user_id)
        assert "Nhóm KD" in gui_admin and "Nhóm TK" in gui_admin
        assert "Nhóm KD" in gui_tp and "Nhóm TK" not in gui_tp

        ds = (await db_session.execute(select(ZaloDigest))).scalars().all()
        assert len(ds) == 2 and all(not d.by_llm and "1 tin nhắn" in d.summary for d in ds)

        # trưởng phòng xem trang chỉ thấy nhóm phòng mình
        rd = await client.get("/api/v1/zalo/digests", headers=auth_header(tp_sales))
        assert [it["group_name"] for it in rd.json()["items"]] == ["Nhóm KD"]

    @pytest.mark.asyncio
    async def test_chi_admin_chay_tom_tat(self, client, tp_sales):
        r = await client.post("/api/v1/zalo/digests/run", headers=auth_header(tp_sales))
        assert r.status_code == 403


class TestCaiDat:
    @pytest.mark.asyncio
    async def test_cai_dat_tro_ly(self, client, admin_user):
        h = auth_header(admin_user)
        r = await client.put("/api/v1/automation/settings", headers=h, json={
            "zalo_digest_enabled": False, "zalo_digest_hour": 18, "zalo_unanswered_hours": 3,
        })
        assert r.status_code == 200
        s = r.json()
        assert s["zalo_digest_enabled"] == "false" and s["zalo_digest_hour"] == "18" and s["zalo_unanswered_hours"] == "3"
        bad = await client.put("/api/v1/automation/settings", headers=h, json={"zalo_unanswered_hours": 0})
        assert bad.status_code == 400
        bad = await client.put("/api/v1/automation/settings", headers=h, json={"zalo_digest_hour": 24})
        assert bad.status_code == 400
