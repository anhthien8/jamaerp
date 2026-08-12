"""Vai trò tùy chỉnh — tạo, hiện trong ma trận phân quyền, sửa quyền, resolve runtime.

Bối cảnh (bug 07/08/2026): nhân sự tạo vai trò 'Admin CSKH' rồi hôm sau "tìm không ra"
vì GET /users/permissions/roles chỉ trả 6 vai trò hệ thống; đồng thời user mang vai trò
custom bị fallback quyền data_entry (sai phân quyền).
"""

import pytest

from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_custom_role_visible_and_editable_in_matrix(client, admin_user):
    h = auth_header(admin_user)

    # 1) Tạo vai trò tùy chỉnh
    resp = await client.post(
        "/api/v1/users/roles",
        json={
            "role_key": "admin_cskh",
            "role_name": "Admin CSKH",
            "department": "SALES",
            "permissions": {
                "canViewDashboard": True,
                "canViewLeads": True,
                "canViewAccounting": False,
            },
        },
        headers=h,
    )
    assert resp.status_code == 200, resp.text

    # 2) PHẢI xuất hiện trong ma trận phân quyền (bug cũ: biến mất)
    resp = await client.get("/api/v1/users/permissions/roles", headers=h)
    assert resp.status_code == 200
    roles = resp.json()["roles"]
    assert "admin_cskh" in roles
    assert roles["admin_cskh"]["custom"] is True
    assert roles["admin_cskh"]["role_name"] == "Admin CSKH"
    assert roles["admin_cskh"]["permissions"]["canViewAccounting"] is False

    # 3) Sửa quyền vai trò tùy chỉnh qua CÙNG endpoint ma trận (merge, không mất key cũ)
    resp = await client.put(
        "/api/v1/users/permissions/roles/admin_cskh",
        json={"permissions": {"canViewAccounting": True}},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    resp = await client.get("/api/v1/users/roles/custom", headers=h)
    stored = next(r for r in resp.json()["roles"] if r["role_key"] == "admin_cskh")
    assert stored["permissions"]["canViewAccounting"] is True
    assert stored["permissions"]["canViewLeads"] is True

    # 4) Vai trò không tồn tại vẫn bị 400
    resp = await client.put(
        "/api/v1/users/permissions/roles/khong_ton_tai",
        json={"permissions": {"canViewDashboard": True}},
        headers=h,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_custom_role_user_permissions_not_data_entry(client, admin_user):
    """User mang vai trò custom phải nhận đúng quyền role đó — không fallback data_entry."""
    h = auth_header(admin_user)
    resp = await client.post(
        "/api/v1/users/roles",
        json={
            "role_key": "cskh_view",
            "role_name": "CSKH View",
            "department": "SALES",
            "permissions": {
                "canViewDashboard": True,
                "canViewAccounting": False,
                "canViewLeads": True,
            },
        },
        headers=h,
    )
    assert resp.status_code == 200, resp.text

    resp = await client.post(
        "/api/v1/users",
        json={
            "full_name": "Nhân viên CSKH",
            "email": "cskh@test.com",
            "password": "secret123",
            "role": "cskh_view",
            "department": "SALES",
        },
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    uid = resp.json()["id"]

    resp = await client.get(f"/api/v1/users/{uid}/permissions", headers=h)
    assert resp.status_code == 200
    combined = resp.json()["combined_permissions"]
    # data_entry có canViewAccounting=True — fallback sai sẽ lộ quyền kế toán
    assert combined["canViewAccounting"] is False
    assert combined["canViewLeads"] is True
