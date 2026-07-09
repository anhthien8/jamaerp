"""Tests for CSKH automation — follow-up reminders, lead recall, payment reminders, BOD report."""

import uuid
from datetime import datetime, timedelta, timezone, date

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, func

from app.models.lead import Lead, Activity
from app.models.contract import Contract
from app.models.user import User
from app.models.notification import Notification, SystemSetting
from app.services.automation import (
    run_followup_reminders,
    run_lead_recall,
    run_payment_reminders,
    get_automation_settings,
    set_automation_setting,
)
from app.services.bod_report import build_bod_report, send_bod_report
from tests.conftest import auth_header


def _uid() -> str:
    return str(uuid.uuid4())


def _days_ago(n: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=n)


@pytest_asyncio.fixture
async def sales_user_2(db_session) -> User:
    """A second SALES user (recall reassignment target)."""
    from app.middleware.auth import hash_password

    user = User(
        id=_uid(),
        full_name="Sales Two",
        email="sales2@test.com",
        password_hash=hash_password("sales123"),
        role="data_entry",
        department="SALES",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


def _make_lead(assigned_to: str, days_since_contact: int, stage: str = "interested") -> Lead:
    return Lead(
        id=_uid(),
        name=f"KH Test {days_since_contact}d",
        phone="0909000111",
        stage=stage,
        assigned_to=assigned_to,
        created_at=_days_ago(days_since_contact + 10),
        last_contacted_at=_days_ago(days_since_contact),
    )


# ── Follow-up reminders ──────────────────────────────────────────────────

@pytest.mark.asyncio
class TestFollowupReminders:
    async def test_overdue_lead_creates_notification(self, db_session, sales_user):
        db_session.add(_make_lead(sales_user.id, days_since_contact=5))
        await db_session.commit()

        result = await run_followup_reminders(db_session)
        await db_session.commit()

        assert result["reminded"] == 1
        notifs = (await db_session.execute(
            select(Notification).where(Notification.user_id == sales_user.id)
        )).scalars().all()
        assert len(notifs) == 1
        assert notifs[0].type == "followup_reminder"

    async def test_fresh_lead_not_reminded(self, db_session, sales_user):
        db_session.add(_make_lead(sales_user.id, days_since_contact=1))
        await db_session.commit()

        result = await run_followup_reminders(db_session)
        assert result["reminded"] == 0

    async def test_inactive_stage_skipped(self, db_session, sales_user):
        db_session.add(_make_lead(sales_user.id, days_since_contact=10, stage="lost"))
        await db_session.commit()

        result = await run_followup_reminders(db_session)
        assert result["reminded"] == 0

    async def test_dedupe_unread_notification(self, db_session, sales_user):
        db_session.add(_make_lead(sales_user.id, days_since_contact=5))
        await db_session.commit()

        await run_followup_reminders(db_session)
        await db_session.commit()
        result2 = await run_followup_reminders(db_session)
        await db_session.commit()

        assert result2["reminded"] == 0  # deduped
        count = (await db_session.execute(
            select(func.count(Notification.id)).where(Notification.user_id == sales_user.id)
        )).scalar()
        assert count == 1

    async def test_unassigned_lead_skipped(self, db_session, sales_user):
        lead = _make_lead(sales_user.id, days_since_contact=5)
        lead.assigned_to = None
        db_session.add(lead)
        await db_session.commit()

        result = await run_followup_reminders(db_session)
        assert result["reminded"] == 0


# ── Lead recall ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestLeadRecall:
    async def test_overdue_lead_reassigned(self, db_session, sales_user, sales_user_2):
        lead = _make_lead(sales_user.id, days_since_contact=10)
        db_session.add(lead)
        await db_session.commit()

        result = await run_lead_recall(db_session)
        await db_session.commit()

        assert result["recalled"] == 1
        await db_session.refresh(lead)
        assert lead.assigned_to == sales_user_2.id

        # Activity log created
        acts = (await db_session.execute(
            select(Activity).where(Activity.lead_id == lead.id, Activity.type == "assignment")
        )).scalars().all()
        assert len(acts) == 1

        # Both users notified
        old_notif = (await db_session.execute(
            select(Notification).where(
                Notification.user_id == sales_user.id,
                Notification.type == "lead_recalled",
            )
        )).scalars().all()
        new_notif = (await db_session.execute(
            select(Notification).where(
                Notification.user_id == sales_user_2.id,
                Notification.type == "lead_assigned",
            )
        )).scalars().all()
        assert len(old_notif) == 1
        assert len(new_notif) == 1

    async def test_recall_resets_contact_clock(self, db_session, sales_user, sales_user_2):
        lead = _make_lead(sales_user.id, days_since_contact=10)
        db_session.add(lead)
        await db_session.commit()

        await run_lead_recall(db_session)
        await db_session.commit()
        await db_session.refresh(lead)

        # Fresh clock → no immediate follow-up reminder for new owner
        assert (datetime.now(timezone.utc) - lead.last_contacted_at.replace(tzinfo=timezone.utc)).days == 0

    async def test_no_candidate_no_recall(self, db_session, sales_user):
        # Only one SALES user — no one to reassign to
        db_session.add(_make_lead(sales_user.id, days_since_contact=10))
        await db_session.commit()

        result = await run_lead_recall(db_session)
        assert result["recalled"] == 0

    async def test_recall_disabled_via_setting(self, db_session, sales_user, sales_user_2):
        await set_automation_setting(db_session, "lead_recall_enabled", "false")
        db_session.add(_make_lead(sales_user.id, days_since_contact=10))
        await db_session.commit()

        result = await run_lead_recall(db_session)
        assert result["status"] == "skipped"

    async def test_fresh_lead_not_recalled(self, db_session, sales_user, sales_user_2):
        db_session.add(_make_lead(sales_user.id, days_since_contact=2))
        await db_session.commit()

        result = await run_lead_recall(db_session)
        assert result["recalled"] == 0


# ── Payment reminders ────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestPaymentReminders:
    async def test_pending_installments_notify_accountant(
        self, db_session, accountant_user, project
    ):
        contract = Contract(
            id=_uid(),
            code="HD-TEST-01",
            project_id=project.id,
            title="HĐ thi công test",
            status="signed",
            total_value=1_000_000_000,
            signed_date=date.today() - timedelta(days=10),
        )
        db_session.add(contract)
        await db_session.commit()

        result = await run_payment_reminders(db_session)
        await db_session.commit()

        assert result["reminded"] >= 1
        notifs = (await db_session.execute(
            select(Notification).where(
                Notification.user_id == accountant_user.id,
                Notification.type == "payment_reminder",
            )
        )).scalars().all()
        assert len(notifs) == 1
        assert "HD-TEST-01" in notifs[0].title

    async def test_fully_paid_contract_skipped(self, db_session, accountant_user, project):
        contract = Contract(
            id=_uid(),
            code="HD-TEST-02",
            project_id=project.id,
            title="HĐ đã thanh toán",
            status="signed",
            total_value=500_000_000,
            signed_date=date.today() - timedelta(days=30),
            payment_terms={
                "installments": [
                    {"name": "Đợt 1", "percentage": 50, "milestone": "signing", "status": "paid"},
                    {"name": "Đợt 2", "percentage": 50, "milestone": "handover", "status": "paid"},
                ]
            },
        )
        db_session.add(contract)
        await db_session.commit()

        result = await run_payment_reminders(db_session)
        assert result["reminded"] == 0

    async def test_recently_signed_contract_skipped(self, db_session, accountant_user, project):
        contract = Contract(
            id=_uid(),
            code="HD-TEST-03",
            project_id=project.id,
            title="HĐ mới ký",
            status="signed",
            total_value=500_000_000,
            signed_date=date.today() - timedelta(days=1),
        )
        db_session.add(contract)
        await db_session.commit()

        result = await run_payment_reminders(db_session)
        assert result["reminded"] == 0


# ── Automation settings ──────────────────────────────────────────────────

@pytest.mark.asyncio
class TestAutomationSettings:
    async def test_defaults_returned(self, db_session):
        settings = await get_automation_settings(db_session)
        assert settings["followup_reminder_days"] == "3"
        assert settings["lead_recall_days"] == "7"

    async def test_setting_persisted(self, db_session):
        await set_automation_setting(db_session, "followup_reminder_days", "5")
        await db_session.commit()
        settings = await get_automation_settings(db_session)
        assert settings["followup_reminder_days"] == "5"

    async def test_settings_api_admin_ok(self, client: AsyncClient, admin_user):
        resp = await client.get("/api/v1/automation/settings", headers=auth_header(admin_user))
        assert resp.status_code == 200
        assert "followup_reminder_days" in resp.json()

    async def test_settings_api_blocks_sales(self, client: AsyncClient, sales_user):
        resp = await client.get("/api/v1/automation/settings", headers=auth_header(sales_user))
        assert resp.status_code == 403

    async def test_settings_update_api(self, client: AsyncClient, admin_user):
        resp = await client.put(
            "/api/v1/automation/settings",
            json={"followup_reminder_days": 4, "lead_recall_enabled": False},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["followup_reminder_days"] == "4"
        assert body["lead_recall_enabled"] == "false"

    async def test_settings_update_validates_range(self, client: AsyncClient, admin_user):
        resp = await client.put(
            "/api/v1/automation/settings",
            json={"followup_reminder_days": 999},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 400

    async def test_manual_trigger_api(self, client: AsyncClient, admin_user):
        resp = await client.post("/api/v1/automation/run/all", headers=auth_header(admin_user))
        assert resp.status_code == 200
        body = resp.json()
        assert "followups" in body and "recalls" in body and "payments" in body


# ── BOD report ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestBodReport:
    async def test_build_daily_report(self, db_session, admin_user, sales_user):
        # Lead must be created within last day so daily report counts it
        lead = _make_lead(sales_user.id, days_since_contact=0)
        lead.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
        db_session.add(lead)
        await db_session.commit()

        report = await build_bod_report(db_session, "daily")
        assert report["period"] == "daily"
        assert "BÁO CÁO" in report["text"]
        assert report["metrics"]["new_leads"] >= 1

    async def test_send_report_notifies_bod_users(self, db_session, admin_user, sales_user):
        result = await send_bod_report(db_session, "daily")
        assert result["recipients"] >= 1  # admin_user

        notifs = (await db_session.execute(
            select(Notification).where(
                Notification.user_id == admin_user.id,
                Notification.type == "bod_report",
            )
        )).scalars().all()
        assert len(notifs) == 1

        # Sales user is NOT BOD → no report notification
        sales_notifs = (await db_session.execute(
            select(Notification).where(
                Notification.user_id == sales_user.id,
                Notification.type == "bod_report",
            )
        )).scalars().all()
        assert len(sales_notifs) == 0

    async def test_report_api_preview(self, client: AsyncClient, admin_user):
        resp = await client.get(
            "/api/v1/automation/bod-report/daily/preview", headers=auth_header(admin_user)
        )
        assert resp.status_code == 200
        assert "text" in resp.json()

    async def test_report_api_invalid_period(self, client: AsyncClient, admin_user):
        resp = await client.get(
            "/api/v1/automation/bod-report/yearly/preview", headers=auth_header(admin_user)
        )
        assert resp.status_code == 400


# ── Notifications API ────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestNotificationsAPI:
    async def test_list_own_notifications(self, client: AsyncClient, db_session, sales_user):
        db_session.add(Notification(
            user_id=sales_user.id, type="system", title="Test", body="Body"
        ))
        await db_session.commit()

        resp = await client.get("/api/v1/notifications", headers=auth_header(sales_user))
        assert resp.status_code == 200
        body = resp.json()
        assert body["unread_count"] == 1
        assert len(body["items"]) == 1

    async def test_cannot_see_others_notifications(
        self, client: AsyncClient, db_session, sales_user, admin_user
    ):
        db_session.add(Notification(
            user_id=admin_user.id, type="system", title="Admin only", body=""
        ))
        await db_session.commit()

        resp = await client.get("/api/v1/notifications", headers=auth_header(sales_user))
        assert resp.status_code == 200
        assert resp.json()["unread_count"] == 0

    async def test_mark_read(self, client: AsyncClient, db_session, sales_user):
        notif = Notification(user_id=sales_user.id, type="system", title="T", body="")
        db_session.add(notif)
        await db_session.commit()

        resp = await client.put(
            f"/api/v1/notifications/{notif.id}/read", headers=auth_header(sales_user)
        )
        assert resp.status_code == 200

        resp2 = await client.get("/api/v1/notifications", headers=auth_header(sales_user))
        assert resp2.json()["unread_count"] == 0

    async def test_mark_read_forbidden_for_other_user(
        self, client: AsyncClient, db_session, sales_user, admin_user
    ):
        notif = Notification(user_id=admin_user.id, type="system", title="T", body="")
        db_session.add(notif)
        await db_session.commit()

        resp = await client.put(
            f"/api/v1/notifications/{notif.id}/read", headers=auth_header(sales_user)
        )
        assert resp.status_code == 404

    async def test_mark_all_read(self, client: AsyncClient, db_session, sales_user):
        for i in range(3):
            db_session.add(Notification(user_id=sales_user.id, type="system", title=f"N{i}", body=""))
        await db_session.commit()

        resp = await client.put("/api/v1/notifications/read-all", headers=auth_header(sales_user))
        assert resp.status_code == 200

        resp2 = await client.get("/api/v1/notifications", headers=auth_header(sales_user))
        assert resp2.json()["unread_count"] == 0
