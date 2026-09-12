"""Tests for P&L (Profit & Loss) API — summary, project list, project detail, RBAC."""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from app.cache import cache
from app.models.contract import Contract
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


# ── start_date + status trong P&L (vá 05/09/2026: FE dựng bộ chọn kỳ từ đây) ──

@pytest.mark.asyncio
class TestPLProjectStartDate:
    async def test_list_tra_start_date_va_status(self, client: AsyncClient, admin_user, project_with_financials, db_session):
        from datetime import datetime

        project_with_financials.start_date = datetime(2026, 3, 15)
        await db_session.commit()

        resp = await client.get("/api/v1/pl/projects", headers=auth_header(admin_user))
        assert resp.status_code == 200
        item = next(i for i in resp.json() if i["project_id"] == project_with_financials.id)
        # date-only yyyy-mm-dd — FE slice(0,7) dựng availableMonths, khớp định dạng MOCK
        assert item["start_date"] == "2026-03-15"
        assert item["status"] == project_with_financials.status

    async def test_list_start_date_null_khong_no(self, client: AsyncClient, admin_user, project_with_financials):
        # Fixture không set start_date → None: dự án cũ chưa nhập ngày không được làm nổ API
        resp = await client.get("/api/v1/pl/projects", headers=auth_header(admin_user))
        assert resp.status_code == 200
        item = next(i for i in resp.json() if i["project_id"] == project_with_financials.id)
        assert item["start_date"] is None
        assert item["status"] == project_with_financials.status

    async def test_detail_tra_start_date(self, client: AsyncClient, admin_user, project_with_financials, db_session):
        from datetime import datetime

        project_with_financials.start_date = datetime(2026, 3, 15)
        await db_session.commit()

        resp = await client.get(
            f"/api/v1/pl/projects/{project_with_financials.id}", headers=auth_header(admin_user)
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["start_date"] == "2026-03-15"
        assert body["status"] == project_with_financials.status


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


# ── Cache /pl (vá 09/09/2026) ─────────────────────────────────────────────
# Trước đó @cached nằm TRÊN @router.get → router đăng ký hàm gốc, cache là
# mã chết trên đường HTTP. Nhóm test này chốt 3 hợp đồng: (1) cache thật sự
# sống, (2) 2 endpoint cùng prefix không đụng key nhau, (3) sửa dự án qua API
# thật sự làm mới dữ liệu (clear_prefix("pl") trong projects.py có tác dụng).

@pytest.mark.asyncio
class TestPLCache:
    async def test_lan_2_tra_tu_cache_khong_query_db(
        self, client: AsyncClient, admin_user, project_with_financials, db_session
    ):
        r1 = await client.get("/api/v1/pl/summary", headers=auth_header(admin_user))
        assert r1.status_code == 200
        assert any(k.startswith("pl") for k in cache._store), (
            "sau request đầu cache._store phải có key prefix 'pl' — "
            "nếu rỗng tức @cached lại thành mã chết (kiểm tra thứ tự decorator)"
        )

        # Thêm hợp đồng ký mới THẲNG vào DB (không qua API nên không invalidate).
        # Nếu lần 2 thấy số mới nghĩa là endpoint vẫn query DB thay vì trả cache.
        db_session.add(Contract(
            id=str(uuid.uuid4()),
            code="HD-CACHE-01",
            project_id=project_with_financials.id,
            title="HD test cache",
            status="signed",
            total_value=1_000_000_000,
        ))
        await db_session.commit()

        r2 = await client.get("/api/v1/pl/summary", headers=auth_header(admin_user))
        assert r2.json()["total_revenue"] == r1.json()["total_revenue"], (
            "lần 2 phải trả nguyên response cache (chưa thấy hợp đồng mới)"
        )

        # clear_prefix("pl") → request kế tiếp phải query lại và thấy số mới
        cache.clear_prefix("pl")
        r3 = await client.get("/api/v1/pl/summary", headers=auth_header(admin_user))
        assert r3.json()["total_revenue"] == r1.json()["total_revenue"] + 1_000_000_000

    async def test_summary_va_projects_khong_dung_key_nhau(
        self, client: AsyncClient, admin_user, project_with_financials
    ):
        r_sum = await client.get("/api/v1/pl/summary", headers=auth_header(admin_user))
        r_proj = await client.get("/api/v1/pl/projects", headers=auth_header(admin_user))
        assert r_sum.status_code == 200
        assert r_proj.status_code == 200

        # Key chỉ có prefix (bug cũ) thì cả 2 endpoint cùng ra key "pl" —
        # /pl/projects sẽ trả nhầm dict summary đã cache của /pl/summary.
        pl_keys = [k for k in cache._store if k.startswith("pl")]
        assert len(pl_keys) == 2, f"2 endpoint phải ra 2 key riêng, nhận: {pl_keys}"
        assert isinstance(r_proj.json(), list)
        assert "total_revenue" in r_sum.json()

    async def test_sua_status_du_an_lam_moi_pl(
        self, client: AsyncClient, admin_user, project_with_financials
    ):
        r1 = await client.get("/api/v1/pl/projects", headers=auth_header(admin_user))
        item1 = next(i for i in r1.json() if i["project_id"] == project_with_financials.id)
        assert item1["status"] == "active"

        # PUT đổi status qua API → projects.py phải clear_prefix("pl")
        r_put = await client.put(
            f"/api/v1/projects/{project_with_financials.id}",
            json={"status": "completed"},
            headers=auth_header(admin_user),
        )
        assert r_put.status_code == 200, r_put.text

        r2 = await client.get("/api/v1/pl/projects", headers=auth_header(admin_user))
        item2 = next(i for i in r2.json() if i["project_id"] == project_with_financials.id)
        assert item2["status"] == "completed", (
            "vẫn thấy status cũ = response dính cache 300s, invalidation không chạy"
        )
