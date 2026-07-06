"""Tests for P&L (Profit & Loss) API — summary, project list, project detail, RBAC."""

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header


# ── GET /api/v1/pl/summary ────────────────────────────────────────────────

@pytest.mark.asyncio
class TestPLSummary:
    async def test_summary_returns_200_for_admin(self, client: AsyncClient, admin_user, project_with_financials):
        resp = await client.get("/api/v1/pl/summary", headers=auth_header(admin_user))
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_revenue"] == 4_500_000_000
        assert body["total_cost_material"] == 3_000_000
        assert body["total_cost_transaction"] == 500_000_000
        assert body["net_profit"] == 4_500_000_000 - 3_000_000 - 500_000_000
        assert body["project_count"] >= 1

    async def test_summary_returns_200_for_accountant(self, client: AsyncClient, accountant_user, project_with_financials):
        resp = await client.get("/api/v1/pl/summary", headers=auth_header(accountant_user))
        assert resp.status_code == 200

    async def test_summary_blocks_sales_user(self, client: AsyncClient, sales_user, project_with_financials):
        resp = await client.get("/api/v1/pl/summary", headers=auth_header(sales_user))
        assert resp.status_code == 403

    async def test_summary_blocks_designer_user(self, client: AsyncClient, designer_user, project_with_financials):
        resp = await client.get("/api/v1/pl/summary", headers=auth_header(designer_user))
        assert resp.status_code == 403

    async def test_summary_empty_db(self, client: AsyncClient, admin_user):
        resp = await client.get("/api/v1/pl/summary", headers=auth_header(admin_user))
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_revenue"] == 0
        assert body["total_cost"] == 0
        assert body["margin"] == 0.0

    async def test_summary_margin_calculation(self, client: AsyncClient, admin_user, project_with_financials):
        resp = await client.get("/api/v1/pl/summary", headers=auth_header(admin_user))
        body = resp.json()
        expected_margin = round((body["net_profit"] / body["total_revenue"]) * 100, 2)
        assert body["margin"] == expected_margin

    async def test_summary_no_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/pl/summary")
        assert resp.status_code in (401, 403)


# ── GET /api/v1/pl/projects ───────────────────────────────────────────────

@pytest.mark.asyncio
class TestPLProjectList:
    async def test_project_list_returns_200(self, client: AsyncClient, admin_user, project_with_financials):
        resp = await client.get("/api/v1/pl/projects", headers=auth_header(admin_user))
        assert resp.status_code == 200
        items = resp.json()
        assert isinstance(items, list)
        assert len(items) >= 1

    async def test_project_list_correct_values(self, client: AsyncClient, admin_user, project_with_financials):
        resp = await client.get("/api/v1/pl/projects", headers=auth_header(admin_user))
        items = resp.json()
        proj_item = next((i for i in items if i["project_id"] == project_with_financials.id), None)
        assert proj_item is not None
        assert proj_item["revenue"] == 4_500_000_000
        assert proj_item["cost_material"] == 3_000_000
        assert proj_item["cost_transaction"] == 500_000_000
        assert proj_item["total_cost"] == 503_000_000
        assert proj_item["profit"] == 4_500_000_000 - 503_000_000

    async def test_project_list_blocks_non_clevel(self, client: AsyncClient, sales_user, project_with_financials):
        resp = await client.get("/api/v1/pl/projects", headers=auth_header(sales_user))
        assert resp.status_code == 403


# ── GET /api/v1/pl/projects/{project_id} ──────────────────────────────────

@pytest.mark.asyncio
class TestPLProjectDetail:
    async def test_detail_returns_200(self, client: AsyncClient, admin_user, project_with_financials):
        resp = await client.get(
            f"/api/v1/pl/projects/{project_with_financials.id}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["project_id"] == project_with_financials.id
        assert body["revenue"] == 4_500_000_000

    async def test_detail_has_cost_by_category(self, client: AsyncClient, admin_user, project_with_financials):
        resp = await client.get(
            f"/api/v1/pl/projects/{project_with_financials.id}",
            headers=auth_header(admin_user),
        )
        body = resp.json()
        categories = {c["category"] for c in body["cost_by_category"]}
        assert "material" in categories
        assert "labor" in categories

    async def test_detail_not_found(self, client: AsyncClient, admin_user):
        resp = await client.get(
            "/api/v1/pl/projects/nonexistent-id",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404

    async def test_detail_blocks_non_clevel(self, client: AsyncClient, designer_user, project_with_financials):
        resp = await client.get(
            f"/api/v1/pl/projects/{project_with_financials.id}",
            headers=auth_header(designer_user),
        )
        assert resp.status_code == 403

    async def test_detail_material_as_category(self, client: AsyncClient, admin_user, project_with_financials):
        resp = await client.get(
            f"/api/v1/pl/projects/{project_with_financials.id}",
            headers=auth_header(admin_user),
        )
        body = resp.json()
        mat_cat = next((c for c in body["cost_by_category"] if c["category"] == "material"), None)
        assert mat_cat is not None
        assert mat_cat["total"] == 3_000_000
        assert mat_cat["count"] == 1


# ── Edge cases ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestPLEdgeCases:
    async def test_project_without_contracts_or_costs(self, client: AsyncClient, admin_user, project):
        resp = await client.get(
            f"/api/v1/pl/projects/{project.id}",
            headers=auth_header(admin_user),
        )
        body = resp.json()
        assert body["revenue"] == 0
        assert body["total_cost"] == 0
        assert body["profit"] == 0
        assert body["margin"] == 0.0
