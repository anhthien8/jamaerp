"""Nhãn đội của lead đi theo người phụ trách (27/08/2026).

Lỗi user báo: «Leader chỉ xem được Lead gắn cho mình, không xem được Lead của
các nhân viên thuộc team mình phụ trách».

Gốc rễ: phạm vi lead của trưởng nhóm đọc `leads.team_id`, mà cột đó chỉ được
đặt đúng MỘT lần — lúc giao lead (`assign_lead`: lead.team_id =
target_user.team_id). Đổi đội của người sau đó thì nhãn trôi và không ai gắn lại:
  - Sale nhận data lúc chưa có đội → lead mang team_id NULL. Xếp vào đội sau thì
    trưởng nhóm không bao giờ thấy số data đó.
  - Sale chuyển đội → lead cũ vẫn đeo nhãn đội cũ.

Nay mọi đường đổi đội (xếp thành viên / sửa hồ sơ / tạo & đổi trưởng nhóm) đều
gắn lại nhãn cho lead của người đó.
"""

import pytest
from sqlalchemy import select

from app.middleware.permissions import xoa_cache_quyen
from app.models.lead import Lead
from app.models.user import User
from tests.conftest import auth_header


@pytest.fixture(autouse=True)
def _sach_cache_quyen():
    xoa_cache_quyen()
    yield
    xoa_cache_quyen()


async def _tao_user(client, db_session, admin, *, email, role, department="SALES"):
    resp = await client.post(
        "/api/v1/users",
        json={
            "full_name": f"NV {email.split('@')[0]}", "email": email,
            "password": "secret123", "role": role, "department": department,
        },
        headers=auth_header(admin),
    )
    assert resp.status_code == 200, resp.text
    uid = resp.json()["id"]
    return (await db_session.execute(select(User).where(User.id == uid))).scalar_one()


async def _tao_doi(client, admin, *, name, code, leader_id=None):
    resp = await client.post(
        "/api/v1/users/teams",
        json={"name": name, "code": code, "leader_id": leader_id},
        headers=auth_header(admin),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _xep_thanh_vien(client, admin, team_id, user_ids):
    resp = await client.put(
        f"/api/v1/users/teams/{team_id}/members",
        json={"user_ids": user_ids},
        headers=auth_header(admin),
    )
    assert resp.status_code == 200, resp.text


async def _tao_lead_giao_cho(client, admin, user_id, name="Chị Mai"):
    resp = await client.post(
        "/api/v1/leads",
        json={"name": name, "phone": "0901234567", "assigned_to": user_id},
        headers=auth_header(admin),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _lead_team_id(db_session, lead_id):
    lead = (await db_session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one()
    await db_session.refresh(lead)
    return lead.team_id


# ---------------------------------------------------------------------------
# 1. Kịch bản đúng của lỗi: sale nhận data TRƯỚC khi được xếp đội
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_xep_vao_doi_sau_thi_lead_cu_van_ve_dung_doi(client, db_session, admin_user):
    """Sale nhận lead lúc chưa có đội → xếp vào đội → trưởng nhóm PHẢI thấy lead đó."""
    leader = await _tao_user(client, db_session, admin_user, email="leader@test.com", role="leader")
    sale = await _tao_user(client, db_session, admin_user, email="sale@test.com", role="data_entry")

    # Lead giao cho sale khi sale còn "chưa xếp đội" → nhãn đội NULL
    lead_id = await _tao_lead_giao_cho(client, admin_user, sale.id)
    assert await _lead_team_id(db_session, lead_id) is None

    team_id = await _tao_doi(client, admin_user, name="Đội KD 1", code="KD1", leader_id=leader.id)
    await _xep_thanh_vien(client, admin_user, team_id, [sale.id])

    # Nhãn đội của lead cũ đã được gắn lại
    assert await _lead_team_id(db_session, lead_id) == team_id

    # Và trưởng nhóm thật sự THẤY lead đó trong danh sách
    resp = await client.get("/api/v1/leads", headers=auth_header(leader))
    assert resp.status_code == 200, resp.text
    ids = {l["id"] for l in resp.json()["items"]}
    assert lead_id in ids, "trưởng nhóm phải thấy data của quân mình"


# ---------------------------------------------------------------------------
# 2. Chuyển sang đội khác: đội cũ mất data, đội mới nhận
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chuyen_doi_thi_lead_theo_nguoi(client, db_session, admin_user):
    leader1 = await _tao_user(client, db_session, admin_user, email="leader1@test.com", role="leader")
    leader2 = await _tao_user(client, db_session, admin_user, email="leader2@test.com", role="leader")
    sale = await _tao_user(client, db_session, admin_user, email="sale@test.com", role="data_entry")

    doi1 = await _tao_doi(client, admin_user, name="Đội KD 1", code="KD1", leader_id=leader1.id)
    doi2 = await _tao_doi(client, admin_user, name="Đội KD 2", code="KD2", leader_id=leader2.id)
    await _xep_thanh_vien(client, admin_user, doi1, [sale.id])

    lead_id = await _tao_lead_giao_cho(client, admin_user, sale.id)
    assert await _lead_team_id(db_session, lead_id) == doi1

    # Chuyển sale sang đội 2
    await _xep_thanh_vien(client, admin_user, doi2, [sale.id])
    assert await _lead_team_id(db_session, lead_id) == doi2

    # Trưởng nhóm đội cũ KHÔNG còn thấy data của người đã rời đi
    resp = await client.get("/api/v1/leads", headers=auth_header(leader1))
    assert lead_id not in {l["id"] for l in resp.json()["items"]}
    resp = await client.get("/api/v1/leads", headers=auth_header(leader2))
    assert lead_id in {l["id"] for l in resp.json()["items"]}


# ---------------------------------------------------------------------------
# 3. Gỡ khỏi đội: lead về kho chung (không đeo nhãn đội cũ)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_go_khoi_doi_thi_lead_mat_nhan(client, db_session, admin_user):
    leader = await _tao_user(client, db_session, admin_user, email="leader@test.com", role="leader")
    sale = await _tao_user(client, db_session, admin_user, email="sale@test.com", role="data_entry")
    team_id = await _tao_doi(client, admin_user, name="Đội KD 1", code="KD1", leader_id=leader.id)
    await _xep_thanh_vien(client, admin_user, team_id, [sale.id])
    lead_id = await _tao_lead_giao_cho(client, admin_user, sale.id)
    assert await _lead_team_id(db_session, lead_id) == team_id

    # Xếp lại đội KHÔNG có sale → sale bị gỡ khỏi đội
    await _xep_thanh_vien(client, admin_user, team_id, [])
    assert await _lead_team_id(db_session, lead_id) is None
    resp = await client.get("/api/v1/leads", headers=auth_header(leader))
    assert lead_id not in {l["id"] for l in resp.json()["items"]}


# ---------------------------------------------------------------------------
# 4. Đổi đội qua đường sửa hồ sơ nhân sự cũng phải kéo lead đi theo
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sua_ho_so_doi_team_thi_lead_theo(client, db_session, admin_user):
    leader = await _tao_user(client, db_session, admin_user, email="leader@test.com", role="leader")
    sale = await _tao_user(client, db_session, admin_user, email="sale@test.com", role="data_entry")
    team_id = await _tao_doi(client, admin_user, name="Đội KD 1", code="KD1", leader_id=leader.id)
    lead_id = await _tao_lead_giao_cho(client, admin_user, sale.id)
    assert await _lead_team_id(db_session, lead_id) is None

    resp = await client.put(
        f"/api/v1/users/{sale.id}",
        json={"team_id": team_id},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    assert await _lead_team_id(db_session, lead_id) == team_id


# ---------------------------------------------------------------------------
# 5. Lead CHƯA giao ai vẫn ở kho chung — không bị vơ vào đội nào
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lead_chua_giao_ai_khong_bi_gan_doi(client, db_session, admin_user):
    leader = await _tao_user(client, db_session, admin_user, email="leader@test.com", role="leader")
    sale = await _tao_user(client, db_session, admin_user, email="sale@test.com", role="data_entry")
    team_id = await _tao_doi(client, admin_user, name="Đội KD 1", code="KD1", leader_id=leader.id)

    resp = await client.post(
        "/api/v1/leads",
        json={"name": "Khách trôi nổi", "phone": "0909999999"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    lead_id = resp.json()["id"]

    await _xep_thanh_vien(client, admin_user, team_id, [sale.id])
    assert await _lead_team_id(db_session, lead_id) is None, "lead kho chung không thuộc đội nào"


# ---------------------------------------------------------------------------
# 6. Trưởng nhóm thấy ĐỦ lead của nhiều nhân viên trong nhóm
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_truong_nhom_thay_lead_cua_ca_nhom(client, db_session, admin_user):
    leader = await _tao_user(client, db_session, admin_user, email="leader@test.com", role="leader")
    sale1 = await _tao_user(client, db_session, admin_user, email="sale1@test.com", role="data_entry")
    sale2 = await _tao_user(client, db_session, admin_user, email="sale2@test.com", role="data_entry")
    ngoai_doi = await _tao_user(client, db_session, admin_user, email="ngoai@test.com", role="data_entry")

    team_id = await _tao_doi(client, admin_user, name="Đội KD 1", code="KD1", leader_id=leader.id)
    await _xep_thanh_vien(client, admin_user, team_id, [sale1.id, sale2.id])

    lead1 = await _tao_lead_giao_cho(client, admin_user, sale1.id, name="KH của sale 1")
    lead2 = await _tao_lead_giao_cho(client, admin_user, sale2.id, name="KH của sale 2")
    lead_leader = await _tao_lead_giao_cho(client, admin_user, leader.id, name="KH của trưởng nhóm")
    lead_ngoai = await _tao_lead_giao_cho(client, admin_user, ngoai_doi.id, name="KH đội khác")

    resp = await client.get("/api/v1/leads", headers=auth_header(leader))
    assert resp.status_code == 200, resp.text
    ids = {l["id"] for l in resp.json()["items"]}
    assert {lead1, lead2, lead_leader} <= ids, "phải thấy lead của cả nhóm, không chỉ của mình"
    assert lead_ngoai not in ids, "không được thấy lead ngoài nhóm"
