"""Đổi họ tên trên Hồ sơ 360° — chỉ Ban Giám đốc + Kế toán/Nhân sự (24/10/2026)."""

import pytest

from app.middleware.permissions import xoa_cache_quyen
from tests.conftest import auth_header


@pytest.fixture(autouse=True)
def _sach_cache_quyen():
    xoa_cache_quyen()
    yield
    xoa_cache_quyen()


@pytest.mark.asyncio
async def test_ke_toan_doi_ten_nguoi_khac(client, accountant_user, sales_user):
    resp = await client.put(
        f"/api/v1/users/{sales_user.id}/full-name",
        json={"full_name": "  Nguyễn   Văn  Mới "},
        headers=auth_header(accountant_user),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["full_name"] == "Nguyễn Văn Mới"


@pytest.mark.asyncio
async def test_admin_doi_ten(client, admin_user, sales_user):
    resp = await client.put(
        f"/api/v1/users/{sales_user.id}/full-name",
        json={"full_name": "Trần Thị B"}, headers=auth_header(admin_user),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_nhan_vien_khong_tu_doi_ten(client, sales_user):
    resp = await client.put(
        f"/api/v1/users/{sales_user.id}/full-name",
        json={"full_name": "Tên tự đặt"}, headers=auth_header(sales_user),
    )
    assert resp.status_code == 403
    # đường PUT chung cũng không lách được
    resp = await client.put(
        f"/api/v1/users/{sales_user.id}",
        json={"full_name": "Tên tự đặt"}, headers=auth_header(sales_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_ten_qua_ngan(client, admin_user, sales_user):
    resp = await client.put(
        f"/api/v1/users/{sales_user.id}/full-name",
        json={"full_name": " a "}, headers=auth_header(admin_user),
    )
    assert resp.status_code == 400
