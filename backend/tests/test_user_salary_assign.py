"""Gán bậc lương/người phụ thuộc qua PUT /users — mở khóa payroll (audit 22/07).

Trước đây UserUpdate không nhận salary_grade_id/dependents_count → không có đường
gán bậc lương → payroll generate toàn missing_grade, thực lĩnh 0đ.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header


@pytest.mark.asyncio
class TestUserSalaryAssign:
    async def test_accountant_assigns_salary_fields(self, client: AsyncClient, accountant_user, sales_user):
        resp = await client.put(
            f"/api/v1/users/{sales_user.id}",
            headers=auth_header(accountant_user),
            json={"dependents_count": 2},
        )
        assert resp.status_code == 200, resp.text

        detail = await client.get(
            f"/api/v1/users/{sales_user.id}", headers=auth_header(accountant_user)
        )
        assert detail.status_code == 200
        assert detail.json()["dependents_count"] == 2

    async def test_self_cannot_change_own_salary_fields(self, client: AsyncClient, sales_user):
        resp = await client.put(
            f"/api/v1/users/{sales_user.id}",
            headers=auth_header(sales_user),
            json={"dependents_count": 9},
        )
        assert resp.status_code == 403

    async def test_accountant_can_edit_other_user_profile(self, client: AsyncClient, accountant_user, sales_user):
        # Gate cũ chỉ cho admin/self — kế toán (kiêm nhân sự) bấm Sửa trên /users bị 403
        resp = await client.put(
            f"/api/v1/users/{sales_user.id}",
            headers=auth_header(accountant_user),
            json={"phone": "0999888777"},
        )
        assert resp.status_code == 200, resp.text
