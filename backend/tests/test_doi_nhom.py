"""Quản lý đội nhóm — UI chia đội (14/08/2026).

Bổ sung 3 mảnh backend cho trang «Quản lý tài khoản» khối Đội nhóm:
  - GET /users/teams trả kèm leader_name + member_count (chỉ đếm người đang
    làm việc) để UI vẽ thẳng, khỏi join tay.
  - PUT /users/teams/{id}/members nhận danh sách ĐẦY ĐỦ user_ids: ai thiếu bị
    gỡ, người đội khác được kéo về, trưởng nhóm của đội luôn được giữ lại.
  - DELETE /users/teams/{id} giải tán đội: thành viên về «chưa xếp đội», lead
    chỉ mất nhãn đội (người phụ trách giữ nguyên).
"""

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.middleware.permissions import xoa_cache_quyen
from app.models.audit import AuditLog
from app.models.lead import Lead
from app.models.user import User, Team
from tests.conftest import auth_header


@pytest.fixture(autouse=True)
def _sach_cache_quyen():
    """Cache quyền là biến module (TTL 60s) — xóa trước/sau mỗi test kẻo leak."""
    xoa_cache_quyen()
    yield
    xoa_cache_quyen()


# ---------------------------------------------------------------------------
# Helpers dựng bộ máy: vai trò trưởng nhóm KD + 2 đội + nhân sự
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


async def _nghi_viec(client, admin, user_id):
    resp = await client.put(
        f"/api/v1/users/{user_id}", json={"is_active": False}, headers=auth_header(admin),
    )
    assert resp.status_code == 200, resp.text


@pytest_asyncio.fixture
async def bo_may(client, db_session, admin_user):
    """Đội A (leader_a + sale_a1/a2), đội B (leader_b + sale_b1), sale_tudo chưa xếp đội."""
    await _tao_vai_tro(
        client, admin_user,
        role_key="sale_leader", role_name="Trưởng nhóm Kinh doanh", department="SALES",
        permissions={"canViewLeads": True, "leadsScope": "team", "canViewHR": True},
    )
    leader_a = await _tao_user(client, db_session, admin_user, email="leader.a@test.com", role="sale_leader", department="SALES")
    leader_b = await _tao_user(client, db_session, admin_user, email="leader.b@test.com", role="sale_leader", department="SALES")
    team_a = await _tao_doi(client, admin_user, name="Đội Alpha", code="DTA", leader_id=leader_a.id)
    team_b = await _tao_doi(client, admin_user, name="Đội Beta", code="DTB", leader_id=leader_b.id)

    sale_a1 = await _tao_user(client, db_session, admin_user, email="sale.a1@test.com", role="data_entry", department="SALES", team_id=team_a["id"])
    sale_a2 = await _tao_user(client, db_session, admin_user, email="sale.a2@test.com", role="data_entry", department="SALES", team_id=team_a["id"])
    sale_b1 = await _tao_user(client, db_session, admin_user, email="sale.b1@test.com", role="data_entry", department="SALES", team_id=team_b["id"])
    sale_tudo = await _tao_user(client, db_session, admin_user, email="sale.tudo@test.com", role="data_entry", department="SALES")

    return {
        "team_a": team_a, "team_b": team_b,
        "leader_a": leader_a, "leader_b": leader_b,
        "sale_a1": sale_a1, "sale_a2": sale_a2, "sale_b1": sale_b1,
        "sale_tudo": sale_tudo,
    }


def _doi(resp, team_id):
    return next(t for t in resp.json() if t["id"] == team_id)


# ---------------------------------------------------------------------------
# 1. Danh sách đội: kèm tên trưởng nhóm + sĩ số, chỉ đếm người đang làm việc
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_danh_sach_doi_kem_truong_nhom_va_si_so(client, admin_user, bo_may):
    # Sale thường cũng xem được (UI cột «Đội» trong bảng nhân sự cần map tên)
    resp = await client.get("/api/v1/users/teams", headers=auth_header(bo_may["sale_a1"]))
    assert resp.status_code == 200, resp.text

    doi_a = _doi(resp, bo_may["team_a"]["id"])
    assert doi_a["leader_name"] == bo_may["leader_a"].full_name
    assert doi_a["member_count"] == 3  # leader_a + a1 + a2
    doi_b = _doi(resp, bo_may["team_b"]["id"])
    assert doi_b["member_count"] == 2

    # Đội chưa có trưởng nhóm → leader_name None, sĩ số 0
    team_c = await _tao_doi(client, admin_user, name="Đội Gamma", code="DTC")
    resp = await client.get("/api/v1/users/teams", headers=auth_header(admin_user))
    doi_c = _doi(resp, team_c["id"])
    assert doi_c["leader_name"] is None and doi_c["member_count"] == 0

    # Người nghỉ việc KHÔNG tính vào sĩ số (UI hiện «N thành viên» phải là số thật)
    await _nghi_viec(client, admin_user, bo_may["sale_a2"].id)
    resp = await client.get("/api/v1/users/teams", headers=auth_header(admin_user))
    assert _doi(resp, bo_may["team_a"]["id"])["member_count"] == 2


# ---------------------------------------------------------------------------
# 2. Xếp thành viên: full-list, trưởng nhóm luôn được giữ, kéo người đội khác về
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_xep_thanh_vien_full_list_va_giu_truong_nhom(client, db_session, admin_user, bo_may):
    team_a_id = bo_may["team_a"]["id"]
    h = auth_header(admin_user)

    # Gửi [a1, tudo] (không có a2, không có leader): a2 bị gỡ, tudo được thêm,
    # trưởng nhóm tự được giữ lại dù không nằm trong danh sách
    resp = await client.put(
        f"/api/v1/users/teams/{team_a_id}/members",
        json={"user_ids": [bo_may["sale_a1"].id, bo_may["sale_tudo"].id]},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"team_id": team_a_id, "member_count": 3, "added": 1, "removed": 1}

    assert bo_may["leader_a"].team_id == team_a_id  # giữ nguyên
    assert bo_may["sale_tudo"].team_id == team_a_id
    assert bo_may["sale_a2"].team_id is None

    # Gửi danh sách RỖNG: chỉ còn trưởng nhóm — muốn gỡ leader thì đổi trưởng nhóm trước
    resp = await client.put(
        f"/api/v1/users/teams/{team_a_id}/members", json={"user_ids": []}, headers=h,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["member_count"] == 1 and resp.json()["removed"] == 2
    assert bo_may["leader_a"].team_id == team_a_id

    # Có vết audit để tra ai xếp đội lúc nào
    audit = (await db_session.execute(
        select(AuditLog).where(AuditLog.action == "team.set_members", AuditLog.entity_id == team_a_id)
    )).scalars().all()
    assert len(audit) == 2


@pytest.mark.asyncio
async def test_xep_thanh_vien_keo_nguoi_tu_doi_khac_ve(client, admin_user, bo_may):
    # Tick sale đội B vào đội A → được kéo về A luôn (UI ghi rõ hành vi này)
    resp = await client.put(
        f"/api/v1/users/teams/{bo_may['team_a']['id']}/members",
        json={"user_ids": [bo_may["sale_a1"].id, bo_may["sale_a2"].id, bo_may["sale_b1"].id]},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["added"] == 1 and resp.json()["removed"] == 0
    assert bo_may["sale_b1"].team_id == bo_may["team_a"]["id"]

    # Đội B còn mỗi trưởng nhóm
    resp = await client.get("/api/v1/users/teams", headers=auth_header(admin_user))
    assert _doi(resp, bo_may["team_b"]["id"])["member_count"] == 1


@pytest.mark.asyncio
async def test_xep_thanh_vien_chan_truong_nhom_doi_khac(client, admin_user, bo_may):
    # Kéo leader_b về đội A → 400, tránh đội B mồ côi leader đứng ngoài đội
    resp = await client.put(
        f"/api/v1/users/teams/{bo_may['team_a']['id']}/members",
        json={"user_ids": [bo_may["leader_b"].id]},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 400
    assert "trưởng nhóm đội khác" in resp.json()["detail"]
    assert bo_may["leader_b"].team_id == bo_may["team_b"]["id"]  # không bị đụng


@pytest.mark.asyncio
async def test_xep_thanh_vien_chan_nguoi_nghi_va_id_lam(client, admin_user, bo_may):
    h = auth_header(admin_user)
    team_a_id = bo_may["team_a"]["id"]

    # Người đã nghỉ việc → 400 kèm tên
    await _nghi_viec(client, admin_user, bo_may["sale_tudo"].id)
    resp = await client.put(
        f"/api/v1/users/teams/{team_a_id}/members",
        json={"user_ids": [bo_may["sale_tudo"].id]}, headers=h,
    )
    assert resp.status_code == 400
    assert "đã nghỉ việc" in resp.json()["detail"]

    # ID không tồn tại (FE cầm danh sách cũ) → 400 bảo tải lại trang
    resp = await client.put(
        f"/api/v1/users/teams/{team_a_id}/members",
        json={"user_ids": ["id-khong-co-that"]}, headers=h,
    )
    assert resp.status_code == 400
    assert "không tồn tại" in resp.json()["detail"]

    # Đội không tồn tại → 404
    resp = await client.put(
        "/api/v1/users/teams/doi-khong-co/members", json={"user_ids": []}, headers=h,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_xep_thanh_vien_phan_quyen(client, db_session, admin_user, bo_may):
    body = {"user_ids": [bo_may["sale_a1"].id]}
    url = f"/api/v1/users/teams/{bo_may['team_a']['id']}/members"

    # Sale thường không có «Quản lý Users» → 403
    resp = await client.put(url, json=body, headers=auth_header(bo_may["sale_a1"]))
    assert resp.status_code == 403
    # Trưởng nhóm KD (theo seed cũng không có canManageUsers) → 403
    resp = await client.put(url, json=body, headers=auth_header(bo_may["leader_a"]))
    assert resp.status_code == 403

    # Vai trò tùy chỉnh ĐƯỢC cấp «Quản lý Users» trong ma trận → làm được
    await _tao_vai_tro(
        client, admin_user,
        role_key="dieu_phoi_ns", role_name="Điều phối nhân sự", department="HR",
        permissions={"canViewHR": True, "canManageUsers": True},
    )
    hr = await _tao_user(client, db_session, admin_user, email="hr@test.com", role="dieu_phoi_ns", department="HR")
    resp = await client.put(url, json=body, headers=auth_header(hr))
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# 3. Giải tán đội: người về «chưa xếp đội», lead chỉ mất nhãn đội
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_giai_tan_doi(client, db_session, admin_user, bo_may):
    team_a_id = bo_may["team_a"]["id"]

    # Lead gắn sale đội A → mang nhãn đội A
    resp = await client.post(
        "/api/v1/leads",
        json={"name": "KH Alpha", "phone": "0901234567", "assigned_to": bo_may["sale_a1"].id},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    lead_id = resp.json()["id"]
    assert resp.json()["team_id"] == team_a_id

    # Sale thường không giải tán được → 403; đội ma → 404
    resp = await client.delete(f"/api/v1/users/teams/{team_a_id}", headers=auth_header(bo_may["sale_a1"]))
    assert resp.status_code == 403
    resp = await client.delete("/api/v1/users/teams/doi-khong-co", headers=auth_header(admin_user))
    assert resp.status_code == 404

    # Admin giải tán đội A
    resp = await client.delete(f"/api/v1/users/teams/{team_a_id}", headers=auth_header(admin_user))
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "message": "Đã giải tán đội Đội Alpha", "members_cleared": 3, "leads_cleared": 1,
    }

    # Thành viên (kể cả trưởng nhóm) về «chưa xếp đội»
    for key in ("leader_a", "sale_a1", "sale_a2"):
        orm = (await db_session.execute(select(User).where(User.id == bo_may[key].id))).scalar_one()
        assert orm.team_id is None

    # Lead chỉ mất nhãn đội — người phụ trách GIỮ NGUYÊN, không mất lịch sử chăm sóc
    lead = (await db_session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one()
    assert lead.team_id is None
    assert lead.assigned_to == bo_may["sale_a1"].id

    # Đội biến mất khỏi danh sách, đội B không bị vạ lây
    resp = await client.get("/api/v1/users/teams", headers=auth_header(admin_user))
    ids = [t["id"] for t in resp.json()]
    assert team_a_id not in ids and bo_may["team_b"]["id"] in ids

    # Có vết audit ghi số người + số data về kho chung
    audit = (await db_session.execute(
        select(AuditLog).where(AuditLog.action == "team.delete", AuditLog.entity_id == team_a_id)
    )).scalars().all()
    assert len(audit) == 1


# ---------------------------------------------------------------------------
# 4. Vá review đối kháng 14/08: leader mồ côi, leader nghỉ khóa đội, tự nhảy đội
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sua_ho_so_khong_chuyen_doi_truong_nhom_duong_nhiem(client, admin_user, bo_may):
    """Chuyển đội trưởng nhóm qua đường sửa hồ sơ → teams.leader_id mồ côi.

    Kể cả admin cũng phải đổi trưởng nhóm đội đó trước rồi mới chuyển được.
    """
    h = auth_header(admin_user)
    leader_a = bo_may["leader_a"]

    # Admin kéo leader_a (đang lãnh đội A) sang đội B → 400
    resp = await client.put(
        f"/api/v1/users/{leader_a.id}", json={"team_id": bo_may["team_b"]["id"]}, headers=h,
    )
    assert resp.status_code == 400
    assert "trưởng nhóm đội" in resp.json()["detail"]
    # Gỡ khỏi đội (team_id=None) cũng bị chặn như nhau
    resp = await client.put(f"/api/v1/users/{leader_a.id}", json={"team_id": None}, headers=h)
    assert resp.status_code == 400
    assert leader_a.team_id == bo_may["team_a"]["id"]  # không bị đụng

    # Form echo lại đúng đội đang lãnh (không đổi gì) → vẫn lưu bình thường
    resp = await client.put(
        f"/api/v1/users/{leader_a.id}", json={"team_id": bo_may["team_a"]["id"]}, headers=h,
    )
    assert resp.status_code == 200, resp.text

    # Đổi trưởng nhóm đội A cho người khác xong thì leader_a chuyển đội được
    resp = await client.put(
        f"/api/v1/users/teams/{bo_may['team_a']['id']}",
        json={"leader_id": bo_may["sale_a1"].id}, headers=h,
    )
    assert resp.status_code == 200, resp.text
    resp = await client.put(
        f"/api/v1/users/{leader_a.id}", json={"team_id": bo_may["team_b"]["id"]}, headers=h,
    )
    assert resp.status_code == 200, resp.text
    assert leader_a.team_id == bo_may["team_b"]["id"]


@pytest.mark.asyncio
async def test_tao_sua_doi_chan_truong_nhom_dang_lanh_doi_khac(client, admin_user, bo_may):
    """Chọn người đang lãnh đội khác làm trưởng nhóm → đội bên kia mồ côi leader."""
    h = auth_header(admin_user)

    # Tạo đội mới lấy leader_b (đang lãnh đội B) → 400
    resp = await client.post(
        "/api/v1/users/teams",
        json={"name": "Đội Gamma", "code": "DTC", "leader_id": bo_may["leader_b"].id},
        headers=h,
    )
    assert resp.status_code == 400
    assert "Đội Beta" in resp.json()["detail"]

    # Sửa đội A gán leader_b → 400 y hệt; leader_b không bị kéo đi đâu
    resp = await client.put(
        f"/api/v1/users/teams/{bo_may['team_a']['id']}",
        json={"leader_id": bo_may["leader_b"].id}, headers=h,
    )
    assert resp.status_code == 400
    assert "Đội Beta" in resp.json()["detail"]
    assert bo_may["leader_b"].team_id == bo_may["team_b"]["id"]


@pytest.mark.asyncio
async def test_truong_nhom_nghi_viec_khong_khoa_doi(client, admin_user, bo_may):
    """Leader nghỉ việc mà auto-add vào danh sách thì mọi lần lưu đều 400 — đội bị khóa cứng."""
    h = auth_header(admin_user)
    team_a_id = bo_may["team_a"]["id"]
    await _nghi_viec(client, admin_user, bo_may["leader_a"].id)

    # Xếp thành viên vẫn lưu được: leader nghỉ KHÔNG bị auto-add nhưng GIỮ nhãn đội
    # (gỡ im lặng sẽ drift với teams.leader_id — quay lại làm là mất phạm vi nhóm);
    # sale_a2 đang làm việc mà không có trong danh sách thì bị gỡ như thường
    resp = await client.put(
        f"/api/v1/users/teams/{team_a_id}/members",
        json={"user_ids": [bo_may["sale_a1"].id]}, headers=h,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["member_count"] == 1  # roster đang làm việc: chỉ sale_a1
    assert bo_may["leader_a"].team_id == team_a_id  # nhãn đội giữ nguyên
    assert bo_may["sale_a2"].team_id is None

    # Leader quay lại làm việc → đội nguyên vẹn ngay: sĩ số đếm lại đủ, không drift
    resp = await client.put(
        f"/api/v1/users/{bo_may['leader_a'].id}", json={"is_active": True}, headers=h,
    )
    assert resp.status_code == 200, resp.text
    resp = await client.get("/api/v1/users/teams", headers=h)
    doi_a = _doi(resp, team_a_id)
    assert doi_a["member_count"] == 2  # leader_a + sale_a1
    assert doi_a["leader_name"] == bo_may["leader_a"].full_name
    await _nghi_viec(client, admin_user, bo_may["leader_a"].id)  # nghỉ lại cho phần sau

    # Đổi tên đội mà leader_id echo giá trị cũ (đã nghỉ, không đổi) → vẫn lưu được
    resp = await client.put(
        f"/api/v1/users/teams/{team_a_id}",
        json={"name": "Đội Alpha Mới", "leader_id": bo_may["leader_a"].id}, headers=h,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "Đội Alpha Mới"

    # Chỉ định trưởng nhóm MỚI đã nghỉ việc thì vẫn 404 như cũ
    resp = await client.put(
        f"/api/v1/users/teams/{bo_may['team_b']['id']}",
        json={"leader_id": bo_may["leader_a"].id}, headers=h,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_tu_them_minh_vao_doi_khac_bi_chan(client, db_session, admin_user, bo_may):
    """Người được cấp «Quản lý Users» (không phải admin/kế toán) không tự nhảy đội.

    Tự thêm mình vào đội = tự mở rộng phạm vi thấy lead/SĐT của đội đó.
    """
    await _tao_vai_tro(
        client, admin_user,
        role_key="dieu_phoi_ns", role_name="Điều phối nhân sự", department="HR",
        permissions={"canViewHR": True, "canManageUsers": True},
    )
    hr = await _tao_user(client, db_session, admin_user, email="hr@test.com", role="dieu_phoi_ns", department="HR")
    url_a = f"/api/v1/users/teams/{bo_may['team_a']['id']}/members"

    # Tự tick mình vào đội A → 403
    resp = await client.put(
        url_a, json={"user_ids": [bo_may["sale_a1"].id, hr.id]}, headers=auth_header(hr),
    )
    assert resp.status_code == 403
    assert "admin/kế toán" in resp.json()["detail"]
    # Tự bổ nhiệm mình làm trưởng nhóm đội A (cũng là đường chuyển đội) → 403
    resp = await client.put(
        f"/api/v1/users/teams/{bo_may['team_a']['id']}",
        json={"leader_id": hr.id}, headers=auth_header(hr),
    )
    assert resp.status_code == 403
    # Đường vòng thứ 3: tự LẬP đội mới lấy mình làm trưởng nhóm → cũng 403
    # (phản biện vá 14/08 — create_team từng thiếu guard này)
    resp = await client.post(
        "/api/v1/users/teams",
        json={"name": "Đội Tự Lập", "code": "DTL", "leader_id": hr.id},
        headers=auth_header(hr),
    )
    assert resp.status_code == 403
    assert hr.team_id is None  # không bị đụng qua cả 3 đường

    # Admin xếp hr vào đội A trước thì hr gửi full-list có mình → hợp lệ (form echo)
    resp = await client.put(
        url_a,
        json={"user_ids": [bo_may["sale_a1"].id, bo_may["sale_a2"].id, hr.id]},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    resp = await client.put(
        url_a,
        json={"user_ids": [bo_may["sale_a1"].id, bo_may["sale_a2"].id, hr.id]},
        headers=auth_header(hr),
    )
    assert resp.status_code == 200, resp.text
