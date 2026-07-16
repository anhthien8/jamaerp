"""Zalo Listener tests (spec 09) — cấu hình admin, ingest secret-authed, phân tích tín hiệu, RBAC."""

import os
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.zalo import ZaloGroup, ZaloSignal
from tests.conftest import auth_header

ZALO_SECRET = "test-zalo-secret-abc"


@pytest.fixture(autouse=True)
def _set_zalo_secret(monkeypatch):
    """Đặt ZALO_INGEST_SECRET cho settings (cache qua get_settings)."""
    from app.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "ZALO_INGEST_SECRET", ZALO_SECRET)


ZH = {"X-Zalo-Secret": ZALO_SECRET}


class TestZaloAdminConfig:
    @pytest.mark.asyncio
    async def test_login_flow_sets_awaiting(self, client, admin_user):
        r = await client.get("/api/v1/zalo/session", headers=auth_header(admin_user))
        assert r.status_code == 200
        assert r.json()["status"] == "logged_out"

        r2 = await client.post("/api/v1/zalo/session/login", headers=auth_header(admin_user))
        assert r2.status_code == 200
        assert r2.json()["status"] == "awaiting_qr"

    @pytest.mark.asyncio
    async def test_only_admin_configures(self, client, sales_user):
        r = await client.get("/api/v1/zalo/session", headers=auth_header(sales_user))
        assert r.status_code == 403


class TestZaloIngestSecret:
    @pytest.mark.asyncio
    async def test_wrong_secret_401(self, client):
        r = await client.get("/api/v1/zalo/ingest/pending-login", headers={"X-Zalo-Secret": "wrong"})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_pending_login_reflects_admin_request(self, client, admin_user):
        await client.post("/api/v1/zalo/session/login", headers=auth_header(admin_user))
        r = await client.get("/api/v1/zalo/ingest/pending-login", headers=ZH)
        assert r.status_code == 200
        assert r.json()["login_requested"] is True

    @pytest.mark.asyncio
    async def test_session_report_qr_then_loggedin(self, client, admin_user):
        await client.post("/api/v1/zalo/session/login", headers=auth_header(admin_user))
        # ingest đẩy QR
        r = await client.post("/api/v1/zalo/ingest/session", headers=ZH,
                              json={"status": "qr_ready", "qr_image": "data:image/png;base64,AAAA"})
        assert r.status_code == 200
        # admin thấy QR
        r2 = await client.get("/api/v1/zalo/session", headers=auth_header(admin_user))
        assert r2.json()["status"] == "qr_ready"
        assert r2.json()["qr_image"] == "data:image/png;base64,AAAA"
        # ingest báo đăng nhập xong → login_requested tắt, QR ẩn
        await client.post("/api/v1/zalo/ingest/session", headers=ZH,
                          json={"status": "logged_in", "account_name": "Zalo Bot"})
        r3 = await client.get("/api/v1/zalo/session", headers=auth_header(admin_user))
        assert r3.json()["status"] == "logged_in"
        assert r3.json()["account_name"] == "Zalo Bot"
        assert r3.json()["qr_image"] is None


class TestZaloSignalAnalysis:
    @pytest.mark.asyncio
    async def test_ingest_phone_creates_lead_candidate(self, client, db_session: AsyncSession):
        r = await client.post("/api/v1/zalo/ingest/message", headers=ZH, json={
            "zalo_group_id": "g-lead", "group_name": "Nhóm KH A", "sender_name": "NV",
            "text": "Khách anh Minh 0912345678 muốn thiết kế nhà phố",
        })
        assert r.status_code == 200
        assert r.json()["stored"] is True
        assert r.json()["signals_created"] >= 1

        sigs = (await db_session.execute(select(ZaloSignal))).scalars().all()
        types = {s.type for s in sigs}
        assert "lead_candidate" in types

    @pytest.mark.asyncio
    async def test_quote_request_detected(self, client, db_session: AsyncSession):
        await client.post("/api/v1/zalo/ingest/message", headers=ZH, json={
            "zalo_group_id": "g-quote", "group_name": "Nhóm KH B", "sender_name": "KH",
            "text": "Cho em hỏi báo giá bao nhiêu vậy shop?",
        })
        sigs = (await db_session.execute(select(ZaloSignal))).scalars().all()
        assert any(s.type == "quote_request" for s in sigs)

    @pytest.mark.asyncio
    async def test_existing_phone_no_duplicate_lead(self, client, db_session: AsyncSession):
        # Tạo lead với SĐT có sẵn
        from app.models.lead import Lead
        db_session.add(Lead(
            id=str(uuid.uuid4()), name="Đã có", phone="0912345678", stage="new", source="zalo",
        ))
        await db_session.commit()

        r = await client.post("/api/v1/zalo/ingest/message", headers=ZH, json={
            "zalo_group_id": "g-dup", "group_name": "Nhóm C", "sender_name": "NV",
            "text": "anh Minh 0912345678 cần tư vấn",
        })
        assert r.status_code == 200
        sigs = (await db_session.execute(
            select(ZaloSignal).where(ZaloSignal.type == "lead_candidate")
        )).scalars().all()
        assert len(sigs) == 0  # SĐT đã là lead → không tạo lead_candidate

    @pytest.mark.asyncio
    async def test_group_auto_created_and_toggle(self, client, admin_user, db_session: AsyncSession):
        await client.post("/api/v1/zalo/ingest/message", headers=ZH, json={
            "zalo_group_id": "g-auto", "group_name": "Nhóm Tự Tạo", "sender_name": "X", "text": "test",
        })
        group = (await db_session.execute(
            select(ZaloGroup).where(ZaloGroup.zalo_group_id == "g-auto")
        )).scalar_one()
        assert group.monitoring is True

        # admin tắt theo dõi
        r = await client.patch(f"/api/v1/zalo/groups/{group.id}", headers=auth_header(admin_user),
                               json={"monitoring": False})
        assert r.status_code == 200

        # tin mới không được lưu
        r2 = await client.post("/api/v1/zalo/ingest/message", headers=ZH, json={
            "zalo_group_id": "g-auto", "group_name": "Nhóm Tự Tạo", "sender_name": "X", "text": "0912000111 báo giá",
        })
        assert r2.json()["stored"] is False


class TestZaloSignalRBAC:
    @pytest.mark.asyncio
    async def test_sale_sees_only_assigned(self, client, admin_user, sales_user, db_session: AsyncSession):
        # nhóm gán cho sales_user + 1 tín hiệu cho họ; 1 tín hiệu cho nhóm khác
        g1 = ZaloGroup(id=str(uuid.uuid4()), zalo_group_id="rb1", name="Của sale", kind="customer",
                       assigned_user_id=sales_user.id, monitoring=True)
        g2 = ZaloGroup(id=str(uuid.uuid4()), zalo_group_id="rb2", name="Nhóm khác", kind="customer", monitoring=True)
        db_session.add_all([g1, g2])
        await db_session.flush()
        db_session.add(ZaloSignal(id=str(uuid.uuid4()), group_id=g1.id, type="quote_request",
                                  summary="của sale", status="new", assigned_user_id=sales_user.id))
        db_session.add(ZaloSignal(id=str(uuid.uuid4()), group_id=g2.id, type="quote_request",
                                  summary="không phải của sale", status="new"))
        await db_session.commit()

        r = await client.get("/api/v1/zalo/signals", headers=auth_header(sales_user))
        assert r.status_code == 200
        summaries = {s["summary"] for s in r.json()["items"]}
        assert "của sale" in summaries
        assert "không phải của sale" not in summaries

        # admin thấy cả hai
        ra = await client.get("/api/v1/zalo/signals", headers=auth_header(admin_user))
        assert len({s["summary"] for s in ra.json()["items"]} & {"của sale", "không phải của sale"}) == 2
