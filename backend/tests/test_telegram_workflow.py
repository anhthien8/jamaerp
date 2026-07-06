"""Tests for Telegram Workflow API — all endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.auth import hash_password
from app.models.project import Project, Task, TaskActivity
from app.models.inventory import Material
from app.api.telegram_workflow import MaterialRequest
from tests.conftest import auth_header, _uid


# ── Helper: seed a project + tasks for telegram tests ─────────────────────

async def _seed_telegram_project(db_session: AsyncSession, user) -> Project:
    """Create a project with tasks for telegram workflow tests."""
    proj = Project(
        id=_uid(),
        code="JMH-TG01",
        name="Telegram Test Project",
        client_name="TG Client",
        client_phone="0911111111",
        stage="design",
        status="active",
        total_value=10_000_000_000,
        spent=1_000_000_000,
        designer_id=user.id,
    )
    db_session.add(proj)

    task1 = Task(
        id=_uid(), project_id=proj.id, title="Thiet ke 2D",
        status="done", stage="design", order=1,
    )
    task2 = Task(
        id=_uid(), project_id=proj.id, title="Thiet ke 3D",
        status="in_progress", stage="design", order=2,
    )
    db_session.add_all([task1, task2])

    # Seed a material for price lookup
    material = Material(
        id=_uid(), code="MAT-TG", name="Da op lat",
        category="stone", unit="m2", unit_price=500_000,
        quantity_in_stock=200,
    )
    db_session.add(material)

    await db_session.commit()
    return proj


# ── GET /telegram/project/{code} ─────────────────────────────────────────

@pytest.mark.asyncio
class TestProjectLookup:
    async def test_lookup_existing_project(self, client: AsyncClient, admin_user, db_session):
        proj = await _seed_telegram_project(db_session, admin_user)
        resp = await client.get(
            f"/api/v1/telegram/project/{proj.code}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["project"]["code"] == proj.code
        assert body["tasks_summary"]["total"] == 2
        assert body["tasks_summary"]["done"] == 1
        assert body["tasks_summary"]["in_progress"] == 1

    async def test_lookup_not_found(self, client: AsyncClient, admin_user):
        resp = await client.get(
            "/api/v1/telegram/project/NOPE-99",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404


# ── POST /telegram/site-report ───────────────────────────────────────────

@pytest.mark.asyncio
class TestSiteReport:
    async def test_create_site_report(self, client: AsyncClient, admin_user, db_session):
        proj = await _seed_telegram_project(db_session, admin_user)
        resp = await client.post(
            "/api/v1/telegram/site-report",
            headers=auth_header(admin_user),
            json={
                "project_code": proj.code,
                "content": "Hoàn thành phần thô tầng 1",
                "photos": ["https://example.com/photo1.jpg"],
                "reporter_tg_id": 900001,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["project_code"] == proj.code
        assert body["reporter"] == admin_user.full_name
        assert "activity_id" in body

    async def test_site_report_missing_tasks(self, client: AsyncClient, admin_user, db_session):
        """Project with no tasks should fail."""
        proj = Project(
            id=_uid(), code="JMH-EMPTY", name="Empty",
            client_name="X", stage="design", status="active",
        )
        db_session.add(proj)
        await db_session.commit()

        resp = await client.post(
            "/api/v1/telegram/site-report",
            headers=auth_header(admin_user),
            json={
                "project_code": "JMH-EMPTY",
                "content": "Report",
                "photos": [],
                "reporter_tg_id": 900001,
            },
        )
        assert resp.status_code == 400


# ── POST /telegram/material-request ──────────────────────────────────────

@pytest.mark.asyncio
class TestMaterialRequest:
    async def test_create_material_request_within_budget(self, client: AsyncClient, admin_user, db_session):
        proj = await _seed_telegram_project(db_session, admin_user)
        resp = await client.post(
            "/api/v1/telegram/material-request",
            headers=auth_header(admin_user),
            json={
                "project_code": proj.code,
                "material_name": "Da op lat",
                "quantity": 10,
                "unit": "m2",
                "requester_tg_id": 900001,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "pending"
        assert body["over_budget"] is False
        assert body["estimated_cost"] == 5_000_000  # 10 * 500,000

    async def test_material_request_over_budget(self, client: AsyncClient, admin_user, db_session):
        """Request that would exceed project budget."""
        proj = Project(
            id=_uid(), code="JMH-BUD", name="Budget Test",
            client_name="X", stage="design", status="active",
            total_value=1_000_000_000,
            spent=900_000_000,
        )
        db_session.add(proj)
        # Need a task for project to be valid
        task = Task(id=_uid(), project_id=proj.id, title="T1", status="in_progress", stage="design", order=1)
        db_session.add(task)

        # Material for price lookup — unit_price high enough that 15 units exceed budget
        mat = Material(
            id=_uid(), code="MAT-BUD", name="Go soi",
            category="wood", unit="m2", unit_price=10_000_000,  # 10M/m2
            quantity_in_stock=50,
        )
        db_session.add(mat)
        await db_session.commit()
        await db_session.refresh(proj)

        resp = await client.post(
            "/api/v1/telegram/material-request",
            headers=auth_header(admin_user),
            json={
                "project_code": "JMH-BUD",
                "material_name": "Go soi",
                "quantity": 15,
                "unit": "m2",
                "requester_tg_id": 900001,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        # estimated_cost = 15 * 10,000,000 = 150,000,000
        # budget_remaining = 1,000,000,000 - 900,000,000 = 100,000,000
        # spent(900M) + estimated(150M) = 1,050M > total(1,000M) → over_budget
        assert body["estimated_cost"] == 150_000_000
        assert body["over_budget"] is True


# ── POST /telegram/incident ──────────────────────────────────────────────

@pytest.mark.asyncio
class TestIncidentReport:
    async def test_report_high_severity_incident(self, client: AsyncClient, admin_user, db_session):
        proj = await _seed_telegram_project(db_session, admin_user)
        resp = await client.post(
            "/api/v1/telegram/incident",
            headers=auth_header(admin_user),
            json={
                "project_code": proj.code,
                "description": "Ro nuoc tu bep",
                "severity": "high",
                "reporter_tg_id": 900001,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["severity"] == "high"
        assert body["assigned_to"] is not None  # high -> assigned to designer

    async def test_report_low_severity_incident(self, client: AsyncClient, admin_user, db_session):
        proj = await _seed_telegram_project(db_session, admin_user)
        resp = await client.post(
            "/api/v1/telegram/incident",
            headers=auth_header(admin_user),
            json={
                "project_code": proj.code,
                "description": "Vet ban nho",
                "severity": "low",
                "reporter_tg_id": 900001,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["assigned_to"] is None  # low -> no auto-assign


# ── POST /telegram/checkin ───────────────────────────────────────────────

@pytest.mark.asyncio
class TestCheckin:
    async def test_checkin_success(self, client: AsyncClient, admin_user, db_session):
        proj = await _seed_telegram_project(db_session, admin_user)
        resp = await client.post(
            "/api/v1/telegram/checkin",
            headers=auth_header(admin_user),
            json={
                "project_code": proj.code,
                "latitude": 10.762622,
                "longitude": 106.660172,
                "user_tg_id": 900001,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["latitude"] == 10.762622
        assert body["longitude"] == 106.660172
        assert body["user"] == admin_user.full_name

    async def test_checkin_unknown_project(self, client: AsyncClient, admin_user):
        resp = await client.post(
            "/api/v1/telegram/checkin",
            headers=auth_header(admin_user),
            json={
                "project_code": "NOPE-99",
                "latitude": 0,
                "longitude": 0,
                "user_tg_id": 900001,
            },
        )
        assert resp.status_code == 404


# ── POST /telegram/checkout ──────────────────────────────────────────────

@pytest.mark.asyncio
class TestCheckout:
    async def test_checkout_success(self, client: AsyncClient, admin_user, db_session):
        proj = await _seed_telegram_project(db_session, admin_user)
        resp = await client.post(
            "/api/v1/telegram/checkout",
            headers=auth_header(admin_user),
            json={
                "project_code": proj.code,
                "user_tg_id": 900001,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["project_code"] == proj.code
        assert "checkout_time" in body

    async def test_checkout_no_tasks(self, client: AsyncClient, admin_user, db_session):
        proj = Project(
            id=_uid(), code="JMH-NO-TASKS", name="No Tasks",
            client_name="X", stage="design", status="active",
        )
        db_session.add(proj)
        await db_session.commit()

        resp = await client.post(
            "/api/v1/telegram/checkout",
            headers=auth_header(admin_user),
            json={
                "project_code": "JMH-NO-TASKS",
                "user_tg_id": 900001,
            },
        )
        assert resp.status_code == 400


# ── POST /telegram/approve/{id} & /reject/{id} ──────────────────────────

@pytest.mark.asyncio
class TestMaterialApproval:
    async def _create_pending_request(self, db_session, project, user) -> MaterialRequest:
        mr = MaterialRequest(
            id=str(uuid.uuid4()),
            project_id=project.id,
            material_name="Da op lat",
            quantity=5,
            unit="m2",
            estimated_cost=2_500_000,
            status="pending",
            requester_id=user.id,
        )
        db_session.add(mr)
        await db_session.commit()
        return mr

    async def test_approve_material_request(self, client: AsyncClient, admin_user, purchasing_user, db_session):
        proj = await _seed_telegram_project(db_session, admin_user)
        mr = await self._create_pending_request(db_session, proj, admin_user)

        resp = await client.post(
            f"/api/v1/telegram/approve/{mr.id}",
            headers=auth_header(admin_user),
            json={"approver_tg_id": 900005},  # purchasing user
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "approved"

    async def test_approve_by_unauthorized_role(self, client: AsyncClient, admin_user, designer_user, db_session):
        proj = await _seed_telegram_project(db_session, admin_user)
        mr = await self._create_pending_request(db_session, proj, admin_user)

        resp = await client.post(
            f"/api/v1/telegram/approve/{mr.id}",
            headers=auth_header(admin_user),
            json={"approver_tg_id": 900004},  # designer - no approve permission
        )
        assert resp.status_code == 403

    async def test_reject_material_request(self, client: AsyncClient, admin_user, db_session):
        proj = await _seed_telegram_project(db_session, admin_user)
        mr = await self._create_pending_request(db_session, proj, admin_user)

        resp = await client.post(
            f"/api/v1/telegram/reject/{mr.id}",
            headers=auth_header(admin_user),
            json={
                "approver_tg_id": 900001,
                "reason": "Vuot ngan sach",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "rejected"
        assert body["reject_reason"] == "Vuot ngan sach"

    async def test_approve_nonexistent_request(self, client: AsyncClient, admin_user):
        resp = await client.post(
            "/api/v1/telegram/approve/nonexistent-id",
            headers=auth_header(admin_user),
            json={"approver_tg_id": 900001},
        )
        assert resp.status_code == 404

    async def test_approve_already_resolved(self, client: AsyncClient, admin_user, db_session):
        proj = await _seed_telegram_project(db_session, admin_user)
        mr = MaterialRequest(
            id=str(uuid.uuid4()),
            project_id=proj.id,
            material_name="Already Done",
            quantity=1, unit="cai",
            estimated_cost=0,
            status="approved",  # already resolved
            requester_id=admin_user.id,
        )
        db_session.add(mr)
        await db_session.commit()

        resp = await client.post(
            f"/api/v1/telegram/approve/{mr.id}",
            headers=auth_header(admin_user),
            json={"approver_tg_id": 900001},
        )
        assert resp.status_code == 400
