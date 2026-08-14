"""Luồng data theo nhóm KD (14/08/2026).

Admin CSKH nhập data lên hệ thống → chia cho Trưởng nhóm KD (sale_leader) →
trưởng nhóm chia tiếp cho sale trong nhóm → sale chăm sóc & cập nhật. Yêu cầu:
  - Trưởng nhóm CHỈ thấy lead + nhân sự thuộc nhóm mình.
  - Admin CSKH (điều phối) được chia data THAY trưởng nhóm — toàn phạm vi,
    và KHÔNG cần quyền Nhân sự để thấy dropdown «Giao data» (/users/assignable).
  - Trưởng nhóm chưa được xếp đội: chỉ thấy lead của mình, chưa chia được
    (tránh Lead.team_id == NULL khớp lead trôi nổi).
"""

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.middleware.permissions import xoa_cache_quyen
from app.models.lead import Lead
from app.models.notification import Notification
from app.models.user import User, Team
from tests.conftest import auth_header


@pytest.fixture(autouse=True)
def _sach_cache_quyen():
    """Cache quyền là biến module (TTL 60s) — xóa trước/sau mỗi test kẻo leak."""
    xoa_cache_quyen()
    yield
    xoa_cache_quyen()


# ---------------------------------------------------------------------------
# Helpers dựng bộ máy: 2 vai trò tùy chỉnh + 2 đội + nhân sự + lead
# ---------------------------------------------------------------------------

async def _tao_vai_tro(client, admin, *, role_key, role_name, department, permissions):
    resp = await client.post(
        "/api/v1/users/roles",
        json={
            "role_key": role_key, "role_name": role_name,
            "department": department, "permissions": permissions,
        },
        headers=auth_header(admin),
    )
    assert resp.status_code == 200, resp.text


async def _tao_user(client, db_session, admin, *, email, role, department, team_id=None):
    resp = await client.post(
        "/api/v1/users",
        json={
            "full_name": f"NV {email.split('@')[0]}", "email": email,
            "password": "secret123", "role": role,
            "department": department, "team_id": team_id,
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
    return resp.json()


async def _tao_lead(client, actor, *, name, assigned_to=None, phone="0901234567"):
    body = {"name": name, "phone": phone}
    if assigned_to:
        body["assigned_to"] = assigned_to
    return await client.post("/api/v1/leads", json=body, headers=auth_header(actor))


@pytest_asyncio.fixture
async def bo_may(client, db_session, admin_user):
    """Đội A (leader_a + sale_a1/a2), đội B (leader_b + sale_b1), CSKH điều phối,
    3 lead: a1/a2 thuộc đội A, b1 thuộc đội B."""
    # Vai trò trưởng nhóm KD — như seed: có canViewHR để vào trang nhân sự nhóm
    await _tao_vai_tro(
        client, admin_user,
        role_key="sale_leader", role_name="Trưởng nhóm Kinh doanh", department="SALES",
        permissions={"canViewLeads": True, "leadsScope": "team", "canViewHR": True},
    )
    # Điều phối CSKH — CHỦ Ý không cấp canViewHR: chia data không cần quyền Nhân sự
    await _tao_vai_tro(
        client, admin_user,
        role_key="admin_cskh", role_name="Admin CSKH", department="SALES",
        permissions={"canViewDashboard": True, "canViewLeads": True},
    )

    leader_a = await _tao_user(client, db_session, admin_user, email="leader.a@test.com", role="sale_leader", department="SALES")
    leader_b = await _tao_user(client, db_session, admin_user, email="leader.b@test.com", role="sale_leader", department="SALES")
    team_a = await _tao_doi(client, admin_user, name="Đội Alpha", code="DTA", leader_id=leader_a.id)
    team_b = await _tao_doi(client, admin_user, name="Đội Beta", code="DTB", leader_id=leader_b.id)
    # POST /teams với leader_id phải tự kéo trưởng nhóm về đội (đồng bộ team_id)
    assert leader_a.team_id == team_a["id"]
    assert leader_b.team_id == team_b["id"]

    sale_a1 = await _tao_user(client, db_session, admin_user, email="sale.a1@test.com", role="data_entry", department="SALES", team_id=team_a["id"])
    sale_a2 = await _tao_user(client, db_session, admin_user, email="sale.a2@test.com", role="data_entry", department="SALES", team_id=team_a["id"])
    sale_b1 = await _tao_user(client, db_session, admin_user, email="sale.b1@test.com", role="data_entry", department="SALES", team_id=team_b["id"])
    cskh = await _tao_user(client, db_session, admin_user, email="cskh@test.com", role="admin_cskh", department="SALES")

    lead_a1 = (await _tao_lead(client, admin_user, name="KH Alpha Một", assigned_to=sale_a1.id)).json()
    lead_a2 = (await _tao_lead(client, admin_user, name="KH Alpha Hai", assigned_to=sale_a2.id)).json()
    lead_b1 = (await _tao_lead(client, admin_user, name="KH Beta Một", assigned_to=sale_b1.id)).json()
    assert lead_a1["team_id"] == team_a["id"] and lead_b1["team_id"] == team_b["id"]

    return {
        "team_a": team_a, "team_b": team_b,
        "leader_a": leader_a, "leader_b": leader_b,
        "sale_a1": sale_a1, "sale_a2": sale_a2, "sale_b1": sale_b1,
        "cskh": cskh,
        "lead_a1": lead_a1, "lead_a2": lead_a2, "lead_b1": lead_b1,
    }


async def _lead_orm(db_session, lead_id) -> Lead:
    return (await db_session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one()


# ---------------------------------------------------------------------------
# 1. Phạm vi nhìn: trưởng nhóm chỉ thấy lead nhóm mình
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_truong_nhom_chi_thay_lead_nhom_minh(client, bo_may):
    h = auth_header(bo_may["leader_a"])

    resp = await client.get("/api/v1/leads", headers=h)
    ids = [l["id"] for l in resp.json()["items"]]
    assert bo_may["lead_a1"]["id"] in ids and bo_may["lead_a2"]["id"] in ids
    assert bo_may["lead_b1"]["id"] not in ids
    # SĐT lead trong nhóm: đầy đủ, không bị che
    lead = next(l for l in resp.json()["items"] if l["id"] == bo_may["lead_a1"]["id"])
    assert lead["phone"] == "0901234567"

    # Kanban lọc y hệt danh sách
    resp = await client.get("/api/v1/leads/pipeline/kanban", headers=h)
    kanban_ids = [l["id"] for col in resp.json() for l in col["leads"]]
    assert bo_may["lead_a1"]["id"] in kanban_ids
    assert bo_may["lead_b1"]["id"] not in kanban_ids

    # Xem thẳng lead nhóm khác → 403
    resp = await client.get(f"/api/v1/leads/{bo_may['lead_b1']['id']}", headers=h)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 2. Trưởng nhóm chia data: chỉ trong nhóm mình
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_truong_nhom_chia_data_trong_nhom(client, db_session, bo_may):
    h = auth_header(bo_may["leader_a"])
    lead_a1 = bo_may["lead_a1"]["id"]

    # Giao lead nhóm mình cho người CÙNG nhóm → OK, team_id giữ nguyên đội A
    resp = await client.post(
        f"/api/v1/leads/{lead_a1}/assign",
        json={"user_id": bo_may["sale_a2"].id}, headers=h,
    )
    assert resp.status_code == 200, resp.text
    orm = await _lead_orm(db_session, lead_a1)
    assert orm.assigned_to == bo_may["sale_a2"].id
    assert orm.team_id == bo_may["team_a"]["id"]

    # Giao cho người NHÓM KHÁC → 403
    resp = await client.post(
        f"/api/v1/leads/{lead_a1}/assign",
        json={"user_id": bo_may["sale_b1"].id}, headers=h,
    )
    assert resp.status_code == 403

    # Đụng vào lead nhóm khác → 403 (dù giao cho người nhóm mình)
    resp = await client.post(
        f"/api/v1/leads/{bo_may['lead_b1']['id']}/assign",
        json={"user_id": bo_may["sale_a1"].id}, headers=h,
    )
    assert resp.status_code == 403

    # Tạo lead + gắn sale nhóm mình → OK; gắn sale nhóm khác → 403
    resp = await _tao_lead(client, bo_may["leader_a"], name="KH mới A", assigned_to=bo_may["sale_a1"].id)
    assert resp.status_code == 200, resp.text
    assert resp.json()["team_id"] == bo_may["team_a"]["id"]
    resp = await _tao_lead(client, bo_may["leader_a"], name="KH mới B", assigned_to=bo_may["sale_b1"].id)
    assert resp.status_code == 403

    # Sale thường không được chia data (giữ nguyên luật cũ)
    resp = await client.post(
        f"/api/v1/leads/{lead_a1}/assign",
        json={"user_id": bo_may["sale_a1"].id},
        headers=auth_header(bo_may["sale_a1"]),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 3. Trưởng nhóm CHƯA xếp đội: chỉ thấy của mình, chưa chia được
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_truong_nhom_chua_xep_doi(client, db_session, admin_user, bo_may):
    leader_c = await _tao_user(
        client, db_session, admin_user,
        email="leader.c@test.com", role="sale_leader", department="SALES",
    )
    lead_c = (await _tao_lead(client, admin_user, name="KH của C", assigned_to=leader_c.id)).json()
    h = auth_header(leader_c)

    # Chỉ thấy lead gắn cho chính mình — KHÔNG thấy lead trôi nổi/đội khác
    # (Lead.team_id == None mà so == NULL là dò ra mọi lead chưa có đội)
    resp = await client.get("/api/v1/leads", headers=h)
    ids = [l["id"] for l in resp.json()["items"]]
    assert ids == [lead_c["id"]]
    # SĐT lead của CHÍNH mình phải đầy đủ — còn phải gọi khách
    assert resp.json()["items"][0]["phone"] == "0901234567"

    # Thấy trong danh sách thì phải MỞ và LÀM được: review đối kháng 14/08 bắt
    # được vụ trưởng nhóm teamless thấy lead của mình nhưng mở/đổi giai đoạn
    # bị 403 (can_view/can_modify thiếu fallback assigned_to)
    resp = await client.get(f"/api/v1/leads/{lead_c['id']}", headers=h)
    assert resp.status_code == 200, resp.text
    resp = await client.put(
        f"/api/v1/leads/{lead_c['id']}/stage",
        json={"new_stage": "interested"}, headers=h,
    )
    assert resp.status_code == 200, resp.text

    # Chưa có đội thì chưa chia được — kể cả lead của chính mình
    resp = await client.post(
        f"/api/v1/leads/{lead_c['id']}/assign",
        json={"user_id": leader_c.id}, headers=h,
    )
    assert resp.status_code == 403

    # Dropdown giao data: chỉ có chính mình
    resp = await client.get("/api/v1/users/assignable", headers=h)
    assert resp.status_code == 200
    assert [u["id"] for u in resp.json()] == [leader_c.id]


# ---------------------------------------------------------------------------
# 4. Admin CSKH: chia data thay trưởng nhóm, không cần quyền Nhân sự
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cskh_chia_thay_truong_nhom_khong_can_quyen_nhan_su(client, db_session, bo_may):
    h = auth_header(bo_may["cskh"])

    # Thấy toàn bộ lead, SĐT đầy đủ (họ là người nhập số)
    resp = await client.get("/api/v1/leads", headers=h)
    ids = [l["id"] for l in resp.json()["items"]]
    assert {bo_may["lead_a1"]["id"], bo_may["lead_b1"]["id"]} <= set(ids)
    assert all(l["phone"] == "0901234567" for l in resp.json()["items"])

    # Chia chéo đội thay trưởng nhóm: lead đội A → sale đội B, team_id đi theo
    resp = await client.post(
        f"/api/v1/leads/{bo_may['lead_a1']['id']}/assign",
        json={"user_id": bo_may["sale_b1"].id}, headers=h,
    )
    assert resp.status_code == 200, resp.text
    orm = await _lead_orm(db_session, bo_may["lead_a1"]["id"])
    assert orm.team_id == bo_may["team_b"]["id"]

    # Dropdown giao data mở dù KHÔNG có canViewHR — thấy nhân sự KD + trưởng nhóm,
    # và payload không lộ SĐT/lương
    resp = await client.get("/api/v1/users/assignable", headers=h)
    assert resp.status_code == 200
    items = resp.json()
    assignable_ids = {u["id"] for u in items}
    assert {bo_may["sale_a1"].id, bo_may["sale_b1"].id, bo_may["leader_a"].id} <= assignable_ids
    assert all("phone" not in u and "salary_grade_id" not in u for u in items)

    # Nhưng trang Nhân sự thì vẫn đóng (không có canViewHR/canManageUsers)
    resp = await client.get("/api/v1/users", headers=h)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_dropdown_giao_data_theo_pham_vi(client, bo_may):
    # Trưởng nhóm A: chỉ người đội A + chính mình
    resp = await client.get("/api/v1/users/assignable", headers=auth_header(bo_may["leader_a"]))
    assert resp.status_code == 200
    ids = {u["id"] for u in resp.json()}
    assert bo_may["sale_a1"].id in ids and bo_may["leader_a"].id in ids
    assert bo_may["sale_b1"].id not in ids

    # Sale thường: không có quyền chia data → 403
    resp = await client.get("/api/v1/users/assignable", headers=auth_header(bo_may["sale_a1"]))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 5. Giao hàng loạt: đúng phạm vi, lead ngoài nhóm bị bỏ qua, team_id đi theo
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_assign_theo_pham_vi(client, db_session, bo_may):
    tat_ca = [bo_may["lead_a1"]["id"], bo_may["lead_a2"]["id"], bo_may["lead_b1"]["id"]]

    # Trưởng nhóm A giao cả 3 cho sale_a1: 2 lead đội A ăn, lead đội B bị bỏ qua
    resp = await client.post(
        "/api/v1/leads/bulk/assign",
        json={"lead_ids": tat_ca, "user_id": bo_may["sale_a1"].id},
        headers=auth_header(bo_may["leader_a"]),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"updated": 2, "skipped": 1}

    orm_b1 = await _lead_orm(db_session, bo_may["lead_b1"]["id"])
    assert orm_b1.assigned_to == bo_may["sale_b1"].id  # không bị đụng
    orm_a2 = await _lead_orm(db_session, bo_may["lead_a2"]["id"])
    assert orm_a2.assigned_to == bo_may["sale_a1"].id
    assert orm_a2.team_id == bo_may["team_a"]["id"]

    # 1 thông báo gộp cho người nhận, không spam từng lead
    notifs = (
        await db_session.execute(
            select(Notification).where(
                Notification.user_id == bo_may["sale_a1"].id,
                Notification.type == "lead_assigned",
                Notification.body.like("%giao 2 lead%"),
            )
        )
    ).scalars().all()
    assert len(notifs) == 1

    # Trưởng nhóm giao hàng loạt cho người NHÓM KHÁC → 403 ngay từ cửa
    resp = await client.post(
        "/api/v1/leads/bulk/assign",
        json={"lead_ids": tat_ca, "user_id": bo_may["sale_b1"].id},
        headers=auth_header(bo_may["leader_a"]),
    )
    assert resp.status_code == 403

    # CSKH kéo lead đội A sang đội B: team_id đi theo người nhận
    resp = await client.post(
        "/api/v1/leads/bulk/assign",
        json={"lead_ids": [bo_may["lead_a1"]["id"]], "user_id": bo_may["sale_b1"].id},
        headers=auth_header(bo_may["cskh"]),
    )
    assert resp.status_code == 200 and resp.json()["updated"] == 1
    orm_a1 = await _lead_orm(db_session, bo_may["lead_a1"]["id"])
    assert orm_a1.team_id == bo_may["team_b"]["id"]

    # Sale thường → 403
    resp = await client.post(
        "/api/v1/leads/bulk/assign",
        json={"lead_ids": tat_ca, "user_id": bo_may["sale_a1"].id},
        headers=auth_header(bo_may["sale_a1"]),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_bulk_stage_theo_pham_vi(client, bo_may):
    ids = [bo_may["lead_a1"]["id"], bo_may["lead_b1"]["id"]]

    # Trưởng nhóm A: chỉ đổi được lead đội A, lead đội B skip
    resp = await client.post(
        "/api/v1/leads/bulk/stage",
        json={"lead_ids": ids, "new_stage": "interested"},
        headers=auth_header(bo_may["leader_a"]),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"updated": 1, "skipped": 1}

    # CSKH điều phối: đổi được cả hai
    resp = await client.post(
        "/api/v1/leads/bulk/stage",
        json={"lead_ids": ids, "new_stage": "potential"},
        headers=auth_header(bo_may["cskh"]),
    )
    assert resp.status_code == 200 and resp.json()["updated"] == 2

    # Sale thường → 403
    resp = await client.post(
        "/api/v1/leads/bulk/stage",
        json={"lead_ids": ids, "new_stage": "interested"},
        headers=auth_header(bo_may["sale_a1"]),
    )
    assert resp.status_code == 403

    # «Ký HĐ Thiết kế» bị chặn ở hàng loạt: endpoint lẻ tự sinh Khách hàng +
    # Dự án + Hợp đồng, đổi hàng loạt sẽ né toàn bộ side-effect và không bù được
    resp = await client.post(
        "/api/v1/leads/bulk/stage",
        json={"lead_ids": ids, "new_stage": "signed_design"},
        headers=auth_header(bo_may["cskh"]),
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 6. Xuất CSV: cùng phạm vi với danh sách; vai trò ngoài KD bị chặn
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_csv_theo_pham_vi(client, accountant_user, bo_may, admin_user):
    # Admin: đủ cả 3 lead
    resp = await client.get("/api/v1/leads/export", headers=auth_header(admin_user))
    assert resp.status_code == 200
    body = resp.text
    assert "KH Alpha Một" in body and "KH Beta Một" in body

    # Trưởng nhóm A: chỉ lead đội mình
    resp = await client.get("/api/v1/leads/export", headers=auth_header(bo_may["leader_a"]))
    body = resp.text
    assert "KH Alpha Một" in body and "KH Beta Một" not in body

    # Sale: chỉ lead của mình
    resp = await client.get("/api/v1/leads/export", headers=auth_header(bo_may["sale_a1"]))
    body = resp.text
    assert "KH Alpha Một" in body
    assert "KH Alpha Hai" not in body and "KH Beta Một" not in body

    # Kế toán: trước đây tải được TOÀN BỘ SĐT khách — giờ 403
    resp = await client.get("/api/v1/leads/export", headers=auth_header(accountant_user))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 7. Nhân sự: danh sách theo ma trận + phạm vi nhóm; hồ sơ cá nhân có gác
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_danh_sach_nhan_su_theo_nhom(client, admin_user, accountant_user, bo_may):
    # Admin: thấy tất cả
    resp = await client.get("/api/v1/users", headers=auth_header(admin_user))
    emails = [u["email"] for u in resp.json()["items"]]
    assert "sale.b1@test.com" in emails

    # Kế toán (canViewHR theo ma trận, không phải trưởng nhóm): thấy tất cả
    resp = await client.get("/api/v1/users", headers=auth_header(accountant_user))
    assert resp.status_code == 200
    assert any(u["email"] == "sale.b1@test.com" for u in resp.json()["items"])

    # Trưởng nhóm A: chỉ đội mình + chính mình
    resp = await client.get("/api/v1/users", headers=auth_header(bo_may["leader_a"]))
    assert resp.status_code == 200
    emails = {u["email"] for u in resp.json()["items"]}
    assert {"leader.a@test.com", "sale.a1@test.com", "sale.a2@test.com"} <= emails
    assert "sale.b1@test.com" not in emails and "admin@test.com" not in emails

    # Sale thường: không có canViewHR → 403 (trước đây hardcode 3 role, nay theo ma trận)
    resp = await client.get("/api/v1/users", headers=auth_header(bo_may["sale_a1"]))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_ho_so_nhan_vien_co_gac(client, admin_user, bo_may):
    sale = bo_may["sale_a1"]

    # Tự xem hồ sơ mình → OK
    resp = await client.get(f"/api/v1/users/{sale.id}", headers=auth_header(sale))
    assert resp.status_code == 200

    # Sale xem hồ sơ người khác → 403 (trước đây lộ SĐT/bậc lương cho mọi người)
    resp = await client.get(f"/api/v1/users/{admin_user.id}", headers=auth_header(sale))
    assert resp.status_code == 403

    # Trưởng nhóm A xem người trong nhóm → OK; người nhóm khác → 403
    h = auth_header(bo_may["leader_a"])
    resp = await client.get(f"/api/v1/users/{sale.id}", headers=h)
    assert resp.status_code == 200
    resp = await client.get(f"/api/v1/users/{bo_may['sale_b1'].id}", headers=h)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_tu_chuyen_nhom_bi_chan(client, db_session, admin_user, bo_may):
    sale = bo_may["sale_a1"]

    # Tự đổi team_id sang đội khác = tự mở rộng phạm vi → 403
    resp = await client.put(
        f"/api/v1/users/{sale.id}",
        json={"team_id": bo_may["team_b"]["id"]},
        headers=auth_header(sale),
    )
    assert resp.status_code == 403

    # Form tự sửa hồ sơ echo team_id CŨ (không đổi) + sửa SĐT → vẫn OK
    resp = await client.put(
        f"/api/v1/users/{sale.id}",
        json={"team_id": bo_may["team_a"]["id"], "phone": "0912345678"},
        headers=auth_header(sale),
    )
    assert resp.status_code == 200, resp.text

    # Admin chuyển nhóm thì được
    resp = await client.put(
        f"/api/v1/users/{sale.id}",
        json={"team_id": bo_may["team_b"]["id"]},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    orm = (await db_session.execute(select(User).where(User.id == sale.id))).scalar_one()
    assert orm.team_id == bo_may["team_b"]["id"]


@pytest.mark.asyncio
async def test_tu_doi_bo_phan_bi_chan(client, db_session, admin_user, bo_may):
    """Vai trò tùy chỉnh + bộ phận SALES nghiễm nhiên là điều phối KD (thấy hết
    lead, đủ SĐT, export) — tự đổi department là tự leo thang, chặn như team_id
    (review đối kháng 14/08: guard team_id có mà bỏ sót department cùng bản chất)."""
    await _tao_vai_tro(
        client, admin_user,
        role_key="thiet_ke_noi_that", role_name="Thiết kế nội thất", department="DESIGN",
        permissions={"canViewDashboard": True},
    )
    nv = await _tao_user(
        client, db_session, admin_user,
        email="tk@test.com", role="thiet_ke_noi_that", department="DESIGN",
    )
    h = auth_header(nv)

    # Tự đổi bộ phận sang SALES → 403 (nếu lọt: request kế đã là điều phối toàn cục)
    resp = await client.put(f"/api/v1/users/{nv.id}", json={"department": "SALES"}, headers=h)
    assert resp.status_code == 403
    # ...và phạm vi lead KHÔNG nở ra — vẫn chỉ thấy lead gắn cho mình (rỗng)
    resp = await client.get("/api/v1/leads", headers=h)
    assert resp.json()["items"] == []

    # Form tự sửa hồ sơ echo department CŨ + đổi SĐT → vẫn OK
    resp = await client.put(
        f"/api/v1/users/{nv.id}",
        json={"department": "DESIGN", "phone": "0987654321"}, headers=h,
    )
    assert resp.status_code == 200, resp.text

    # Admin chuyển bộ phận thì được
    resp = await client.put(
        f"/api/v1/users/{nv.id}", json={"department": "OPS"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    orm = (await db_session.execute(select(User).where(User.id == nv.id))).scalar_one()
    assert orm.department == "OPS"


# ---------------------------------------------------------------------------
# 8. Quản lý đội: tạo/sửa cần «Quản lý Users», đổi trưởng nhóm tự kéo team_id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quan_ly_doi(client, db_session, admin_user, bo_may):
    # Trùng mã đội → 400
    resp = await client.post(
        "/api/v1/users/teams",
        json={"name": "Đội trùng", "code": "dta"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 400

    # Sale thường không có canManageUsers → 403
    resp = await client.post(
        "/api/v1/users/teams",
        json={"name": "Đội lậu", "code": "DTX"},
        headers=auth_header(bo_may["sale_a1"]),
    )
    assert resp.status_code == 403

    # Đổi trưởng nhóm đội A → người mới được kéo team_id về đội A ngay
    team_a_id = bo_may["team_a"]["id"]
    resp = await client.put(
        f"/api/v1/users/teams/{team_a_id}",
        json={"leader_id": bo_may["sale_a2"].id},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["leader_id"] == bo_may["sale_a2"].id
    orm = (await db_session.execute(select(User).where(User.id == bo_may["sale_a2"].id))).scalar_one()
    assert orm.team_id == team_a_id

    # Gỡ trưởng nhóm (leader_id = null)
    resp = await client.put(
        f"/api/v1/users/teams/{team_a_id}",
        json={"leader_id": None},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    assert resp.json()["leader_id"] is None

    team_orm = (await db_session.execute(select(Team).where(Team.id == team_a_id))).scalar_one()
    assert team_orm.leader_id is None
