"""Tests for Inventory API — stock deduction, material list, RBAC."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Material, MaterialUsage
from app.models.project import Project
from tests.conftest import auth_header, _uid


@pytest.mark.asyncio
class TestInventoryStockDeduction:
    """Material usage should auto-deduct stock."""

    async def test_material_usage_deducts_stock(
        self, client: AsyncClient, admin_user, project: Project, db_session: AsyncSession
    ):
        """Create material with qty=100, use 10, verify stock=90."""
        headers = auth_header(admin_user)

        # Create material
        resp = await client.post("/api/v1/inventory", json={
            "code": "MAT-TEST-001",
            "name": "Go oc cho",
            "category": "wood",
            "unit": "m2",
            "unit_price": 150_000,
            "quantity_in_stock": 100,
            "min_stock": 10,
        }, headers=headers)
        assert resp.status_code == 200
        material_id = resp.json()["id"]
        assert resp.json()["quantity_in_stock"] == 100

        # Record usage (POST /inventory/use)
        resp = await client.post("/api/v1/inventory/use", json={
            "material_id": material_id,
            "project_id": project.id,
            "quantity": 10,
        }, headers=headers)
        assert resp.status_code == 200
        usage_data = resp.json()
        assert usage_data["quantity"] == 10

        # Verify stock deducted
        resp = await client.get(
            f"/api/v1/inventory/{material_id}",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["quantity_in_stock"] == 90

    async def test_material_list_returns_items(
        self, client: AsyncClient, admin_user, db_session: AsyncSession
    ):
        """GET /inventory returns seeded materials."""
        headers = auth_header(admin_user)

        # Seed 2 materials
        mat1 = Material(
            id=_uid(), code="MAT-A01", name="Sat hop",
            category="metal", unit="kg", unit_price=25_000, quantity_in_stock=200,
        )
        mat2 = Material(
            id=_uid(), code="MAT-A02", name="Son nuoc",
            category="paint", unit="lit", unit_price=50_000, quantity_in_stock=50,
        )
        db_session.add_all([mat1, mat2])
        await db_session.commit()

        resp = await client.get("/api/v1/inventory", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        names = [m["name"] for m in data["items"]]
        assert "Sat hop" in names
        assert "Son nuoc" in names

    async def test_inventory_rbac_blocks_unauthorized(
        self, client: AsyncClient, sales_user
    ):
        """data_entry user (role=data_entry, dept=SALES) cannot access inventory."""
        headers = auth_header(sales_user)

        resp = await client.get("/api/v1/inventory", headers=headers)
        assert resp.status_code == 403
        assert "Không có quyền" in resp.json()["detail"]
