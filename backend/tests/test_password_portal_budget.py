"""Tests: đổi/quên mật khẩu, portal nghiệm thu, budget P&L, phải thu, nhắc bảo hành."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import _reset_codes
from app.middleware.auth import hash_password
from app.models.contract import Contract
from app.models.customer import Customer
from app.models.notification import Notification
from app.models.project import Project
from app.models.user import User
from tests.conftest import auth_header, _uid


# ── Đổi mật khẩu ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestChangePassword:
    async def test_change_ok_then_login_new(self, client: AsyncClient, admin_user: User):
        resp = await client.post(
            "/api/v1/auth/change-password",
            json={"old_password": "admin123", "new_password": "newpass456"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "newpass456"},
        )
        assert login.status_code == 200

    async def test_wrong_old_password(self, client: AsyncClient, admin_user: User):
        resp = await client.post(
            "/api/v1/auth/change-password",
            json={"old_password": "sai-bet", "new_password": "newpass456"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 400

    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/change-password",
            json={"old_password": "x", "new_password": "newpass456"},
        )
        assert resp.status_code in (401, 403)


# ── Quên mật khẩu qua Telegram ────────────────────────────────────────────

@pytest.mark.asyncio
class TestForgotPassword:
    async def test_full_reset_flow(self, client: AsyncClient, db_session: AsyncSession, admin_user: User):
        admin_user.telegram_user_id = 900001
        await db_session.commit()

        resp = await client.post("/api/v1/auth/forgot-password", json={"email": "admin@test.com"})
        assert resp.status_code == 200
        entry = _reset_codes.get("admin@test.com")
        assert entry is not None, "mã reset phải được lưu"
        code = entry[0]

        resp = await client.post(
            "/api/v1/auth/reset-password",
            json={"email": "admin@test.com", "code": code, "new_password": "resetpass9"},
        )
        assert resp.status_code == 200
        login = await client.post(
            "/api/v1/auth/login", json={"email": "admin@test.com", "password": "resetpass9"}
        )
        assert login.status_code == 200

    async def test_wrong_code_rejected(self, client: AsyncClient, db_session: AsyncSession, admin_user: User):
        admin_user.telegram_user_id = 900001
        await db_session.commit()
        await client.post("/api/v1/auth/forgot-password", json={"email": "admin@test.com"})
        resp = await client.post(
            "/api/v1/auth/reset-password",
            json={"email": "admin@test.com", "code": "000000x", "new_password": "resetpass9"},
        )
        assert resp.status_code == 400

    async def test_no_telegram_generic_response(self, client: AsyncClient, admin_user: User):
        admin_user.telegram_user_id = None
        resp = await client.post("/api/v1/auth/forgot-password", json={"email": "admin@test.com"})
        # Không lộ user tồn tại hay không — luôn 200 generic, không lưu mã
        assert resp.status_code == 200
        assert "admin@test.com" not in _reset_codes


# ── Portal: xác nhận nghiệm thu giai đoạn ─────────────────────────────────

@pytest_asyncio.fixture
async def portal_customer(db_session: AsyncSession, project: Project) -> Customer:
    cust = Customer(
        id=_uid(), name="Khách Portal", phone="0900000001", type="individual",
        portal_token=str(uuid.uuid4()), portal_enabled=True,
    )
    db_session.add(cust)
    await db_session.flush()
    project.customer_id = cust.id
    await db_session.commit()
    return cust


@pytest.mark.asyncio
class TestPortalAcceptStage:
    async def test_accept_then_idempotent(
        self, client: AsyncClient, db_session: AsyncSession, portal_customer: Customer, project: Project
    ):
        url = f"/api/v1/portal/{portal_customer.portal_token}/projects/{project.id}/accept-stage"
        resp = await client.post(url, json={"stage": "design", "note": "OK đẹp"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "accepted"
        assert body["acceptance"]["by"] == "Khách Portal"

        # DB đã lưu
        await db_session.refresh(project)
        assert "design" in (project.stage_acceptances or {})

        # Gọi lần 2 → không ghi đè
        resp2 = await client.post(url, json={"stage": "design", "note": "lần 2"})
        assert resp2.json()["status"] == "already_accepted"

    async def test_invalid_stage(self, client: AsyncClient, portal_customer: Customer, project: Project):
        url = f"/api/v1/portal/{portal_customer.portal_token}/projects/{project.id}/accept-stage"
        resp = await client.post(url, json={"stage": "bay-mau", "note": ""})
        assert resp.status_code == 400

    async def test_wrong_token(self, client: AsyncClient, project: Project):
        resp = await client.post(
            f"/api/v1/portal/{uuid.uuid4()}/projects/{project.id}/accept-stage",
            json={"stage": "design", "note": ""},
        )
        assert resp.status_code == 404

    async def test_detail_returns_acceptances(
        self, client: AsyncClient, portal_customer: Customer, project: Project
    ):
        url = f"/api/v1/portal/{portal_customer.portal_token}/projects/{project.id}"
        await client.post(url + "/accept-stage", json={"stage": "design", "note": ""})
        resp = await client.get(url)
        assert resp.status_code == 200
        assert "design" in resp.json()["project"]["stage_acceptances"]


# ── Budget vs Actual + Phải thu ───────────────────────────────────────────

@pytest.mark.asyncio
class TestBudgetAndReceivables:
    async def test_update_budget_and_pl_detail(
        self, client: AsyncClient, admin_user: User, project: Project
    ):
        resp = await client.put(
            f"/api/v1/projects/{project.id}",
            json={"budget_total": 4_000_000_000},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["budget_total"] == 4_000_000_000

        pl = await client.get(f"/api/v1/pl/projects/{project.id}", headers=auth_header(admin_user))
        assert pl.status_code == 200
        assert pl.json()["budget_total"] == 4_000_000_000

    async def test_receivables_from_pending_installments(
        self, client: AsyncClient, db_session: AsyncSession, admin_user: User, project: Project
    ):
        contract = Contract(
            id=_uid(), code="HD-RECV-001", project_id=project.id, title="HĐ thu tiền",
            status="signed", total_value=1_000_000_000,
            payment_terms={"installments": [
                {"name": "Đợt 1", "percentage": 30, "status": "paid"},
                {"name": "Đợt 2", "percentage": 30, "status": "pending"},
                {"name": "Đợt 3", "percentage": 40, "status": "pending"},
            ]},
        )
        db_session.add(contract)
        await db_session.commit()

        resp = await client.get("/api/v1/pl/receivables", headers=auth_header(admin_user))
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_receivable"] == 700_000_000
        codes = [c["contract_code"] for c in body["contracts"]]
        assert "HD-RECV-001" in codes

    async def test_receivables_requires_clevel(
        self, client: AsyncClient, sales_user: User
    ):
        resp = await client.get("/api/v1/pl/receivables", headers=auth_header(sales_user))
        assert resp.status_code == 403


# ── Generate portal link — hồi quy NameError uuid + shape {portal_token} ──

@pytest.mark.asyncio
class TestGeneratePortalLink:
    async def test_generate_returns_portal_token(
        self, client: AsyncClient, db_session: AsyncSession, admin_user: User
    ):
        cust = Customer(id=_uid(), name="KH Gen Link", phone="0911", type="individual")
        db_session.add(cust)
        await db_session.commit()
        resp = await client.post(
            f"/api/v1/customers/{cust.id}/generate-portal-link", headers=auth_header(admin_user)
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("portal_token"), "phải trả portal_token"
        # token dùng được với portal công khai
        portal = await client.get(f"/api/v1/portal/{body['portal_token']}")
        assert portal.status_code == 200

    async def test_generate_requires_admin_or_leader(
        self, client: AsyncClient, db_session: AsyncSession, sales_user: User
    ):
        cust = Customer(id=_uid(), name="KH Quyền", phone="0912", type="individual")
        db_session.add(cust)
        await db_session.commit()
        resp = await client.post(
            f"/api/v1/customers/{cust.id}/generate-portal-link", headers=auth_header(sales_user)
        )
        assert resp.status_code == 403


# ── Dashboard personal — hồi quy UnboundLocalError timedelta (500 mọi role) ──

@pytest.mark.asyncio
class TestPersonalDashboard:
    async def test_personal_dashboard_200_for_supervisor(
        self, client: AsyncClient, designer_user: User
    ):
        resp = await client.get("/api/v1/dashboard/personal", headers=auth_header(designer_user))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "priorities" in body or "total_leads" in body

    async def test_personal_dashboard_200_for_sales(
        self, client: AsyncClient, sales_user: User
    ):
        resp = await client.get("/api/v1/dashboard/personal", headers=auth_header(sales_user))
        assert resp.status_code == 200, resp.text


# ── Nhắc bảo hành ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestWarrantyReminders:
    async def test_notifies_before_expiry(
        self, client: AsyncClient, db_session: AsyncSession, admin_user: User, project: Project
    ):
        from app.services.automation import run_warranty_reminders

        # warranty_end = handover + 12×30 ngày; handover 350 ngày trước → còn 10 ngày
        project.handover_date = datetime.now(timezone.utc) - timedelta(days=350)
        project.warranty_months = 12
        project.status = "completed"
        await db_session.commit()

        result = await run_warranty_reminders(db_session)
        assert result["notified"] >= 1

        notif = await db_session.execute(
            select(Notification).where(Notification.type == "warranty_reminder")
        )
        assert notif.scalars().first() is not None

    async def test_no_notify_far_from_expiry(
        self, client: AsyncClient, db_session: AsyncSession, project: Project
    ):
        from app.services.automation import run_warranty_reminders

        project.handover_date = datetime.now(timezone.utc) - timedelta(days=30)
        project.warranty_months = 12
        await db_session.commit()

        result = await run_warranty_reminders(db_session)
        assert result["notified"] == 0
