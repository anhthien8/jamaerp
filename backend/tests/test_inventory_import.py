"""Import vật tư/báo giá NCC hàng loạt — POST /inventory/import (Bước 1 gói NCC, 22/07)."""

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header


@pytest.mark.asyncio
class TestInventoryImport:
    async def test_import_creates_and_updates(self, client: AsyncClient, accountant_user):
        # Lần 1: tạo mới 2 vật tư (1 dòng nhãn Việt, 1 dòng thiếu mã → tự sinh VT-xxx)
        resp = await client.post(
            "/api/v1/inventory/import",
            headers=auth_header(accountant_user),
            json={"rows": [
                {"code": "VT-900", "name": "Gỗ sồi QA", "category": "Gỗ", "unit": "tấm", "unit_price": 500000, "supplier": "NCC A", "quantity_in_stock": 10, "min_stock": 2},
                {"name": "Sơn QA", "category": "Sơn", "unit_price": 200000, "supplier": "NCC B"},
            ]},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["created"] == 2 and body["updated"] == 0 and body["errors"] == []

        # Lần 2: báo giá mới từ NCC khác — khớp theo mã, chỉ ghi đè giá + NCC
        resp2 = await client.post(
            "/api/v1/inventory/import",
            headers=auth_header(accountant_user),
            json={"rows": [{"code": "VT-900", "name": "Gỗ sồi QA", "unit_price": 450000, "supplier": "NCC C"}]},
        )
        assert resp2.status_code == 200
        assert resp2.json()["updated"] == 1 and resp2.json()["created"] == 0

        listing = await client.get("/api/v1/inventory?page_size=50", headers=auth_header(accountant_user))
        items = {m["code"]: m for m in listing.json()["items"]}
        assert items["VT-900"]["unit_price"] == 450000
        assert items["VT-900"]["supplier"] == "NCC C"
        assert items["VT-900"]["quantity_in_stock"] == 10  # không bị ghi đè vì file không có cột tồn
        assert items["VT-900"]["category"] == "wood"

    async def test_import_reports_row_errors(self, client: AsyncClient, accountant_user):
        resp = await client.post(
            "/api/v1/inventory/import",
            headers=auth_header(accountant_user),
            json={"rows": [
                {"name": "", "unit_price": 100},
                {"name": "Vật tư lỗi danh mục", "category": "danh mục lạ"},
                {"name": "Vật tư OK", "category": "Kính"},
            ]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["created"] == 1
        assert len(body["errors"]) == 2

    async def test_import_denied_for_sales(self, client: AsyncClient, sales_user):
        resp = await client.post(
            "/api/v1/inventory/import",
            headers=auth_header(sales_user),
            json={"rows": [{"name": "X"}]},
        )
        assert resp.status_code == 403
