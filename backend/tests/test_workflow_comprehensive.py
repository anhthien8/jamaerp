"""Comprehensive workflow tests — critical business logic paths."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.auth import hash_password
from app.models.lead import Lead
from app.models.project import Project, Task
from app.models.customer import Customer
from app.models.contract import Contract
from app.models.inventory import Material, MaterialUsage
from tests.conftest import auth_header, _uid


# ── Helper ──────────────────────────────────────────────────────────────

async def _create_lead(db, user, stage="new"):
    lead = Lead(
        id=_uid(), name="Test Lead", phone="0901234567",
        source="facebook", property_type="townhouse",
        area_sqm=100, estimated_budget=5_000_000_000,
        stage=stage, priority="high",
        assigned_to=user.id, team_id="demo-team-01",
    )
    db.add(lead)
    await db.commit()
    return lead


# ── Lead → Project auto-conversion ──────────────────────────────────────

@pytest.mark.asyncio
class TestLeadConversion:
    async def test_signed_design_creates_project_and_tasks(self, client, admin_user, db_session):
        lead = await _create_lead(db_session, admin_user)
        resp = await client.put(
            f"/api/v1/leads/{lead.id}/stage",
            headers=auth_header(admin_user),
            json={"new_stage": "signed_design"},
        )
        assert resp.status_code == 200

        # Verify customer created
        cust = (await db_session.execute(
            __import__('sqlalchemy').select(__import__('app.models.customer', fromlist=['Customer']).Customer)
        )).scalars().first()
        assert cust is not None

        # Verify project created
        proj = (await db_session.execute(
            __import__('sqlalchemy').select(Project).where(Project.lead_id == lead.id)
        )).scalars().first()
        assert proj is not None

        # Verify 19 tasks created
        tasks = (await db_session.execute(
            __import__('sqlalchemy').select(Task).where(Task.project_id == proj.id)
        )).scalars().all()
        assert len(tasks) == 19

        # Verify contract draft created
        contracts = (await db_session.execute(
            __import__('sqlalchemy').select(Contract).where(Contract.project_id == proj.id)
        )).scalars().all()
        assert len(contracts) >= 1
        assert contracts[0].status == "draft"


# ── Task progress recalculation ──────────────────────────────────────────

@pytest.mark.asyncio
class TestTaskProgress:
    async def test_progress_updates_on_status_change(self, client, admin_user, project, db_session):
        # project has 3 tasks: 1 done, 1 in_progress, 1 not_started → 33%
        assert project.progress == 30

        # Find the not_started task
        tasks = (await db_session.execute(
            __import__('sqlalchemy').select(Task).where(Task.project_id == project.id, Task.status == "not_started")
        )).scalars().all()
        assert len(tasks) == 1

        # Change to done → should be 67%
        resp = await client.put(
            f"/api/v1/projects/tasks/{tasks[0].id}/status",
            headers=auth_header(admin_user),
            json={"status": "done"},
        )
        assert resp.status_code == 200

        # Verify project progress updated
        proj = (await db_session.execute(
            __import__('sqlalchemy').select(Project).where(Project.id == project.id)
        )).scalar_one()
        assert proj.progress >= 60  # 2/3 done


# ── Inventory stock deduction ───────────────────────────────────────────

@pytest.mark.asyncio
class TestInventoryStock:
    async def test_material_usage_deducts_stock(self, client, admin_user, project, db_session):
        mat = Material(
            id=_uid(), code="MAT-TEST", name="Test Material",
            category="wood", unit="m2", unit_price=100_000,
            quantity_in_stock=100, min_stock=10,
        )
        db_session.add(mat)
        await db_session.commit()

        resp = await client.post(
            "/api/v1/inventory/use",
            headers=auth_header(admin_user),
            json={"material_id": mat.id, "project_id": project.id, "quantity": 10, "date": "2026-07-24T00:00:00"},
        )
        assert resp.status_code in (200, 201)

        # Verify stock deducted
        updated_mat = (await db_session.execute(
            __import__('sqlalchemy').select(Material).where(Material.id == mat.id)
        )).scalar_one()
        assert updated_mat.quantity_in_stock == 90


# ── Stage change to paused ──────────────────────────────────────────────

@pytest.mark.asyncio
class TestPauseProject:
    async def test_pause_with_reason(self, client, admin_user, project, db_session):
        resp = await client.put(
            f"/api/v1/projects/{project.id}/stage",
            headers=auth_header(admin_user),
            json={"stage": "paused", "pause_reason": "Chờ xin phép xây dựng"},
        )
        assert resp.status_code == 200

        # Verify pause_reason saved
        proj = (await db_session.execute(
            __import__('sqlalchemy').select(Project).where(Project.id == project.id)
        )).scalar_one()
        assert proj.stage == "paused"
        assert proj.pause_reason == "Chờ xin phép xây dựng"


# ── Bulk lead operations ────────────────────────────────────────────────

@pytest.mark.asyncio
class TestBulkOperations:
    async def test_bulk_stage_change(self, client, admin_user, db_session):
        leads = []
        for i in range(3):
            lead = await _create_lead(db_session, admin_user, stage="new")
            leads.append(lead)

        resp = await client.post(
            "/api/v1/leads/bulk/stage",
            headers=auth_header(admin_user),
            json={"lead_ids": [l.id for l in leads], "new_stage": "interested"},
        )
        assert resp.status_code == 200
        assert resp.json()["updated"] == 3

        # Verify all leads changed
        for lead in leads:
            refreshed = (await db_session.execute(
                __import__('sqlalchemy').select(Lead).where(Lead.id == lead.id)
            )).scalar_one()
            assert refreshed.stage == "interested"


# ── CSV export ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestCSVExport:
    async def test_leads_export(self, client, admin_user, db_session):
        await _create_lead(db_session, admin_user)
        resp = await client.get(
            "/api/v1/leads/export",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        content_type = resp.headers.get("content-type", "")
        assert "csv" in content_type or "text" in content_type
        content = resp.text
        assert "Ten" in content or "Tên" in content
        assert "Test Lead" in content
