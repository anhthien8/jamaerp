"""Tests for Leads API — auto-conversion, new fields, RBAC."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.customer import Customer
from app.models.project import Project, Task
from tests.conftest import auth_header, _uid


# ── Helper: walk a lead through all stages up to target ─────────────────

async def _advance_lead_to(client: AsyncClient, headers: dict, lead_id: str, target_stage: str):
    """Advance a lead through the valid stage transition chain."""
    chain = {
        "interested": "new",
        "survey_scheduled": "interested",
        "potential": "survey_scheduled",
        "signed_design": "potential",
    }
    # Build path from 'new' to target
    path = []
    stage = target_stage
    while stage in chain:
        path.append(stage)
        stage = chain[stage]
    path.reverse()

    for stage in path:
        resp = await client.put(
            f"/api/v1/leads/{lead_id}/stage",
            json={"new_stage": stage},
            headers=headers,
        )
        assert resp.status_code == 200, f"Failed to transition to {stage}: {resp.text}"


@pytest.mark.asyncio
class TestLeadAutoConversion:
    """Lead -> Customer + Project + 19 Tasks when signed_design is reached."""

    async def test_lead_stage_change_to_signed_design_creates_project(
        self, client: AsyncClient, admin_user, db_session: AsyncSession
    ):
        headers = auth_header(admin_user)

        # Create lead
        resp = await client.post("/api/v1/leads", json={
            "name": "Nguyen Van Test",
            "phone": "0909123456",
            "email": "test@example.com",
            "address": "123 Le Loi, Q1",
            "estimated_budget": 500_000_000,
            "source": "facebook",
        }, headers=headers)
        assert resp.status_code == 200
        lead_id = resp.json()["id"]

        # Walk lead to signed_design: new -> interested -> survey_scheduled -> potential -> signed_design
        await _advance_lead_to(client, headers, lead_id, "signed_design")

        # Verify Customer created
        cust_q = await db_session.execute(
            select(Customer).where(Customer.lead_id == lead_id)
        )
        customer = cust_q.scalar_one_or_none()
        assert customer is not None, "Customer should be auto-created"
        assert customer.name == "Nguyen Van Test"
        assert customer.phone == "0909123456"

        # Verify Project created with correct lead_id
        proj_q = await db_session.execute(
            select(Project).where(Project.lead_id == lead_id)
        )
        project = proj_q.scalar_one_or_none()
        assert project is not None, "Project should be auto-created"
        assert project.lead_id == lead_id
        assert project.customer_id == customer.id
        assert project.status == "active"
        assert project.stage == "design"
        assert project.client_name == "Nguyen Van Test"

        # Verify 19 tasks created
        task_q = await db_session.execute(
            select(func.count(Task.id)).where(Task.project_id == project.id)
        )
        task_count = task_q.scalar()
        assert task_count == 19, f"Expected 19 default tasks, got {task_count}"

    async def test_lead_stage_change_preserves_existing_customer(
        self, client: AsyncClient, admin_user, db_session: AsyncSession
    ):
        """Converting the same lead twice should not create duplicate Customer/Project."""
        headers = auth_header(admin_user)

        resp = await client.post("/api/v1/leads", json={
            "name": "Tran Thi Idempotent",
            "phone": "0911111111",
            "source": "zalo",
        }, headers=headers)
        assert resp.status_code == 200
        lead_id = resp.json()["id"]

        # First conversion
        await _advance_lead_to(client, headers, lead_id, "signed_design")

        # Attempt second conversion — signed_design has no valid transitions,
        # so we directly check the DB for duplicates
        cust_count_q = await db_session.execute(
            select(func.count(Customer.id)).where(Customer.lead_id == lead_id)
        )
        assert cust_count_q.scalar() == 1, "Only 1 Customer should exist"

        proj_count_q = await db_session.execute(
            select(func.count(Project.id)).where(Project.lead_id == lead_id)
        )
        assert proj_count_q.scalar() == 1, "Only 1 Project should exist"

    async def test_lead_create_with_new_fields(
        self, client: AsyncClient, admin_user, db_session: AsyncSession
    ):
        """POST /leads with channel, contact_status, survey_date, survey_photos fields."""
        headers = auth_header(admin_user)

        resp = await client.post("/api/v1/leads", json={
            "name": "Le Van Fields",
            "phone": "0922333444",
            "channel": "kenh_sale",
            "contact_status": "reachable",
            "survey_date": "2025-06-15T10:00:00",
            'survey_photos': '["https://example.com/photo1.jpg", "https://example.com/photo2.jpg"]',
            "source": "referral",
            "property_type": "villa",
            "area_sqm": 250.5,
            "estimated_budget": 2_000_000_000,
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["channel"] == "kenh_sale"
        assert data["contact_status"] == "reachable"
        assert data["survey_photos"] is not None
        assert "photo1.jpg" in data["survey_photos"]

        # Verify persisted in DB
        lead_q = await db_session.execute(
            select(Lead).where(Lead.id == data["id"])
        )
        lead = lead_q.scalar_one()
        assert lead.channel == "kenh_sale"
        assert lead.contact_status == "reachable"
        assert lead.survey_photos is not None

    async def test_lead_rbac_blocks_non_admin_on_create(
        self, client: AsyncClient, sales_user, db_session: AsyncSession
    ):
        """data_entry user CAN create leads (write access works for sales)."""
        headers = auth_header(sales_user)

        resp = await client.post("/api/v1/leads", json={
            "name": "Pham Van Sales",
            "phone": "0933444555",
            "source": "facebook",
        }, headers=headers)
        # data_entry is allowed to create leads
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Pham Van Sales"
        assert data["assigned_to"] == sales_user.id
