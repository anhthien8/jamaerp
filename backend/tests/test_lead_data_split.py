"""Chia data lead cho team KD (feedback 12/08/2026).

Bối cảnh: CSKH (vai trò tùy chỉnh, bộ phận SALES) nhập lead từ marketing rồi
phân chia cho nhân viên KD. Yêu cầu:
  1. Form thêm lead có "Gắn Sale" → LeadCreate.assigned_to.
  2. Không chỉ admin: CSKH (điều phối KD) cũng được phân công lead.
  3. "Tài khoản tên nào, chỉ xem tên đó" — sale chỉ thấy lead của mình;
     vai trò tùy chỉnh NGOÀI bộ phận KD cũng chỉ thấy lead của mình.
"""

import pytest
from sqlalchemy import select

from app.models.notification import Notification
from app.models.user import User
from tests.conftest import auth_header


async def _create_custom_role_user(client, db_session, admin_user, *, role_key, role_name, department):
    """Tạo vai trò tùy chỉnh + user mang vai trò đó, trả về User ORM."""
    h = auth_header(admin_user)
    resp = await client.post(
        "/api/v1/users/roles",
        json={
            "role_key": role_key,
            "role_name": role_name,
            "department": department,
            "permissions": {"canViewDashboard": True, "canViewLeads": True},
        },
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    resp = await client.post(
        "/api/v1/users",
        json={
            "full_name": f"NV {role_name}",
            "email": f"{role_key}@test.com",
            "password": "secret123",
            "role": role_key,
            "department": department,
        },
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    uid = resp.json()["id"]
    return (await db_session.execute(select(User).where(User.id == uid))).scalar_one()


async def _create_lead(client, user, name="Chị Mai", **extra):
    resp = await client.post(
        "/api/v1/leads",
        json={"name": name, "phone": "0901234567", **extra},
        headers=auth_header(user),
    )
    return resp


@pytest.mark.asyncio
async def test_create_lead_with_assigned_to(client, db_session, admin_user, sales_user):
    """Admin tạo lead + gắn sale ngay: lead thuộc về sale, sale nhận thông báo."""
    resp = await _create_lead(client, admin_user, assigned_to=sales_user.id)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["assigned_to"] == sales_user.id
    assert body["assigned_user_name"] == sales_user.full_name

    notifs = (
        await db_session.execute(
            select(Notification).where(Notification.user_id == sales_user.id)
        )
    ).scalars().all()
    assert any(n.type == "lead_assigned" and n.ref_id == body["id"] for n in notifs)

    # Lịch sử có dòng phân công
    resp = await client.get(f"/api/v1/leads/{body['id']}/activities", headers=auth_header(admin_user))
    contents = [a["content"] for a in resp.json()["items"]]
    assert any("Phân công cho" in c for c in contents)


@pytest.mark.asyncio
async def test_create_lead_without_assignee_defaults_to_creator(client, admin_user):
    resp = await _create_lead(client, admin_user)
    assert resp.status_code == 200, resp.text
    assert resp.json()["assigned_to"] == admin_user.id


@pytest.mark.asyncio
async def test_sales_cannot_assign_on_create_or_endpoint(client, admin_user, sales_user):
    """Nhân viên KD thường (data_entry) không được phân chia data."""
    # Gắn khi tạo → 403
    resp = await _create_lead(client, sales_user, assigned_to=admin_user.id)
    assert resp.status_code == 403

    # Endpoint assign → 403
    lead = (await _create_lead(client, admin_user)).json()
    resp = await client.post(
        f"/api/v1/leads/{lead['id']}/assign",
        json={"user_id": sales_user.id},
        headers=auth_header(sales_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cskh_coordinator_can_assign_and_sees_all(client, db_session, admin_user, sales_user):
    """CSKH (vai trò tùy chỉnh, bộ phận SALES) = điều phối: gắn sale được, thấy hết lead, đủ SĐT."""
    cskh = await _create_custom_role_user(
        client, db_session, admin_user,
        role_key="admin_cskh", role_name="Admin CSKH", department="SALES",
    )

    # CSKH tạo lead + gắn thẳng cho sale (bug cũ: 403 "Chỉ admin hoặc leader")
    resp = await _create_lead(client, cskh, name="KH Website", assigned_to=sales_user.id)
    assert resp.status_code == 200, resp.text
    lead_id = resp.json()["id"]
    assert resp.json()["assigned_to"] == sales_user.id

    # CSKH đổi phụ trách qua endpoint assign
    resp = await client.post(
        f"/api/v1/leads/{lead_id}/assign",
        json={"user_id": admin_user.id},
        headers=auth_header(cskh),
    )
    assert resp.status_code == 200, resp.text

    # CSKH thấy lead không thuộc về mình, SĐT không bị che (họ là người nhập số)
    resp = await client.get("/api/v1/leads", headers=auth_header(cskh))
    items = resp.json()["items"]
    assert any(l["id"] == lead_id for l in items)
    lead = next(l for l in items if l["id"] == lead_id)
    assert lead["phone"] == "0901234567"


@pytest.mark.asyncio
async def test_scope_sale_and_non_sales_custom_role_see_only_own(client, db_session, admin_user, sales_user):
    """'Tài khoản tên nào, chỉ xem tên đó': sale + vai trò tùy chỉnh ngoài KD chỉ thấy lead của mình."""
    mine = (await _create_lead(client, admin_user, name="Của Sale", assigned_to=sales_user.id)).json()
    other = (await _create_lead(client, admin_user, name="Của Admin")).json()

    # Sale (data_entry): chỉ thấy lead được gắn cho mình
    resp = await client.get("/api/v1/leads", headers=auth_header(sales_user))
    ids = [l["id"] for l in resp.json()["items"]]
    assert mine["id"] in ids and other["id"] not in ids

    # Kanban cũng phải lọc như vậy
    resp = await client.get("/api/v1/leads/pipeline/kanban", headers=auth_header(sales_user))
    kanban_ids = [l["id"] for col in resp.json() for l in col["leads"]]
    assert mine["id"] in kanban_ids and other["id"] not in kanban_ids

    # Vai trò tùy chỉnh NGOÀI bộ phận KD (vd Thiết kế): không còn thấy tất cả (lỗ hổng cũ)
    designer = await _create_custom_role_user(
        client, db_session, admin_user,
        role_key="design_lead", role_name="Trưởng Thiết kế", department="DESIGN",
    )
    resp = await client.get("/api/v1/leads", headers=auth_header(designer))
    assert resp.json()["items"] == []
