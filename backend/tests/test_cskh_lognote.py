"""Lognote CSKH — đánh giá chất lượng chăm sóc của team KD (27/08/2026).

Admin CSKH gọi lại khách để chấm chất lượng chăm sóc của nhân viên kinh doanh
rồi ghi ghi chú vào thẻ lead. Chốt với chủ dự án:
  1. Lưu dạng LOGNOTE nhiều mục (activity type `cskh`) — mỗi mục tự có ngày giờ
     + tên người nhập, không mục nào đè mục nào.
  2. Chỉ Admin CSKH (điều phối KD) + admin được GHI. Trưởng nhóm và sale KHÔNG —
     đây là đánh giá VỀ họ, tự viết được thì mất ý nghĩa kiểm soát.
  3. Ai xem được lead đều ĐỌC được (minh bạch để sale tự sửa).
  4. Ghi lognote KHÔNG được đụng `last_contacted_at`: đó là cuộc gọi kiểm tra,
     không phải team KD chăm khách — tính vào sẽ xoá oan cờ "Quá hạn".
"""

import pytest
from sqlalchemy import select

from app.middleware.permissions import xoa_cache_quyen
from app.models.lead import Lead
from app.models.user import User
from tests.conftest import auth_header


@pytest.fixture(autouse=True)
def _sach_cache_quyen():
    """Cache quyền là biến module (TTL 60s) — xóa trước/sau mỗi test kẻo leak."""
    xoa_cache_quyen()
    yield
    xoa_cache_quyen()


async def _tao_vai_tro_va_user(client, db_session, admin, *, role_key, role_name, department):
    h = auth_header(admin)
    resp = await client.post(
        "/api/v1/users/roles",
        json={
            "role_key": role_key, "role_name": role_name, "department": department,
            "permissions": {"canViewDashboard": True, "canViewLeads": True},
        },
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    resp = await client.post(
        "/api/v1/users",
        json={
            "full_name": f"NV {role_name}", "email": f"{role_key}@test.com",
            "password": "secret123", "role": role_key, "department": department,
        },
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    uid = resp.json()["id"]
    return (await db_session.execute(select(User).where(User.id == uid))).scalar_one()


@pytest.fixture
def ghi_chu():
    return "Gọi lại khách 27/08: khách khen bạn Mai nhiệt tình, phàn nàn 3 ngày chưa có báo giá."


async def _tao_lead(client, user, assigned_to=None):
    payload = {"name": "Chị Mai", "phone": "0901234567"}
    if assigned_to:
        payload["assigned_to"] = assigned_to
    resp = await client.post("/api/v1/leads", json=payload, headers=auth_header(user))
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _ghi_lognote(client, user, lead_id, content):
    return await client.post(
        f"/api/v1/leads/{lead_id}/activities",
        json={"type": "cskh", "content": content},
        headers=auth_header(user),
    )


# ---------------------------------------------------------------------------
# 1. Admin CSKH ghi được — mục có ngày giờ + tên người nhập
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cskh_ghi_duoc_lognote_co_ngay_va_ten(client, db_session, admin_user, ghi_chu):
    cskh = await _tao_vai_tro_va_user(
        client, db_session, admin_user,
        role_key="admin_cskh", role_name="Admin CSKH", department="SALES",
    )
    lead_id = await _tao_lead(client, admin_user)

    resp = await _ghi_lognote(client, cskh, lead_id, ghi_chu)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["type"] == "cskh"
    assert body["content"] == ghi_chu
    assert body["user_name"] == cskh.full_name  # tên người nhập
    assert body["created_at"]                    # ngày cập nhật của lognote


# ---------------------------------------------------------------------------
# 2. Lognote: mục mới KHÔNG đè mục cũ, mới nhất đứng đầu
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nhieu_muc_khong_de_nhau(client, db_session, admin_user):
    cskh = await _tao_vai_tro_va_user(
        client, db_session, admin_user,
        role_key="admin_cskh", role_name="Admin CSKH", department="SALES",
    )
    lead_id = await _tao_lead(client, admin_user)

    assert (await _ghi_lognote(client, cskh, lead_id, "Lần 1: khách hài lòng")).status_code == 200
    assert (await _ghi_lognote(client, cskh, lead_id, "Lần 2: khách kêu chậm báo giá")).status_code == 200

    resp = await client.get(f"/api/v1/leads/{lead_id}/activities", headers=auth_header(cskh))
    assert resp.status_code == 200
    lognote = [a for a in resp.json()["items"] if a["type"] == "cskh"]
    assert len(lognote) == 2, "mục mới phải THÊM chứ không đè mục cũ"
    assert lognote[0]["content"] == "Lần 2: khách kêu chậm báo giá"  # DESC: mới nhất trước


# ---------------------------------------------------------------------------
# 3. Sale và trưởng nhóm KHÔNG ghi được (403) — đây là đánh giá về chính họ
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sale_khong_tu_ghi_danh_gia_ve_minh(client, admin_user, sales_user, ghi_chu):
    lead_id = await _tao_lead(client, admin_user, assigned_to=sales_user.id)

    resp = await _ghi_lognote(client, sales_user, lead_id, ghi_chu)
    assert resp.status_code == 403, resp.text

    # Nhưng ghi chú thường thì vẫn ghi được như cũ — không chặn nhầm
    resp = await client.post(
        f"/api/v1/leads/{lead_id}/activities",
        json={"type": "note", "content": "Đã gọi khách"},
        headers=auth_header(sales_user),
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_truong_nhom_khong_ghi_duoc(client, db_session, admin_user, ghi_chu):
    leader = await _tao_vai_tro_va_user(
        client, db_session, admin_user,
        role_key="sale_leader", role_name="Trưởng nhóm Kinh doanh", department="SALES",
    )
    lead_id = await _tao_lead(client, admin_user)

    resp = await _ghi_lognote(client, leader, lead_id, ghi_chu)
    assert resp.status_code == 403, "sale_leader là SALES nhưng là trưởng nhóm — bị đánh giá, không đánh giá"


@pytest.mark.asyncio
async def test_admin_ghi_duoc(client, admin_user, ghi_chu):
    lead_id = await _tao_lead(client, admin_user)
    resp = await _ghi_lognote(client, admin_user, lead_id, ghi_chu)
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# 4. Sale ĐỌC được đánh giá về mình (minh bạch — chốt 27/08)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sale_doc_duoc_danh_gia_ve_minh(client, db_session, admin_user, sales_user, ghi_chu):
    cskh = await _tao_vai_tro_va_user(
        client, db_session, admin_user,
        role_key="admin_cskh", role_name="Admin CSKH", department="SALES",
    )
    lead_id = await _tao_lead(client, admin_user, assigned_to=sales_user.id)
    assert (await _ghi_lognote(client, cskh, lead_id, ghi_chu)).status_code == 200

    resp = await client.get(f"/api/v1/leads/{lead_id}/activities", headers=auth_header(sales_user))
    assert resp.status_code == 200, resp.text
    lognote = [a for a in resp.json()["items"] if a["type"] == "cskh"]
    assert len(lognote) == 1
    assert lognote[0]["content"] == ghi_chu
    assert lognote[0]["user_name"] == cskh.full_name


# ---------------------------------------------------------------------------
# 5. Ghi lognote KHÔNG được coi là "team KD đã chăm khách"
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lognote_khong_doi_last_contacted_at(client, db_session, admin_user, ghi_chu):
    cskh = await _tao_vai_tro_va_user(
        client, db_session, admin_user,
        role_key="admin_cskh", role_name="Admin CSKH", department="SALES",
    )
    lead_id = await _tao_lead(client, admin_user)

    lead = (await db_session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one()
    truoc = lead.last_contacted_at

    assert (await _ghi_lognote(client, cskh, lead_id, ghi_chu)).status_code == 200
    await db_session.refresh(lead)
    assert lead.last_contacted_at == truoc, "gọi kiểm tra chất lượng không phải team KD chăm khách"

    # Đối chứng: ghi chú thường VẪN cập nhật mốc liên hệ như cũ
    resp = await client.post(
        f"/api/v1/leads/{lead_id}/activities",
        json={"type": "note", "content": "Sale gọi khách"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    await db_session.refresh(lead)
    assert lead.last_contacted_at is not None and lead.last_contacted_at != truoc
