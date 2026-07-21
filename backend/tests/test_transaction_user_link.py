"""Giao dịch Lương/Hoa hồng liên kết nhân viên (related_user_id) — feedback user 22/07.

Schema TransactionCreate có user_id từ đầu nhưng model/endpoint từng bỏ quên;
test chốt: tạo giao dịch gắn nhân viên → danh sách trả về id + tên nhân viên.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header


@pytest.mark.asyncio
class TestTransactionUserLink:
    async def test_create_salary_tx_with_user_link(self, client: AsyncClient, accountant_user, sales_user):
        resp = await client.post(
            "/api/v1/accounting/transactions",
            headers=auth_header(accountant_user),
            json={
                "type": "expense",
                "category": "salary",
                "description": "Tạm ứng lương QA",
                "amount": 5_000_000,
                "user_id": str(sales_user.id),
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["related_user_id"] == str(sales_user.id)

        # Danh sách phải trả về cả tên nhân viên (join ở tầng API)
        listing = await client.get(
            "/api/v1/accounting/transactions", headers=auth_header(accountant_user)
        )
        assert listing.status_code == 200
        items = listing.json()["items"]
        tx = next(t for t in items if t["description"] == "Tạm ứng lương QA")
        assert tx["related_user_id"] == str(sales_user.id)
        assert tx["related_user_name"] == sales_user.full_name

    async def test_create_tx_without_user_link_stays_null(self, client: AsyncClient, accountant_user):
        resp = await client.post(
            "/api/v1/accounting/transactions",
            headers=auth_header(accountant_user),
            json={
                "type": "expense",
                "category": "salary",
                "description": "Lương tổng cả kỳ QA",
                "amount": 100_000_000,
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["related_user_id"] is None
