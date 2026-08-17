"""GET /users/task-assignable — dropdown «Đảm nhận» trang Dự án (14/08/2026).

Trang Dự án từng dùng GET /users làm nguồn dropdown «Đảm nhận» nên dính hai
phạm vi sai ngữ cảnh:
  - Trưởng nhóm KD (leader/sale_leader) bị cắt về «nhóm mình + chính mình» —
    không ai thuộc DESIGN/OPS/PURCHASING → dropdown task Thiết kế/Thi công/
    Thu mua RỖNG, tên người phụ trách chéo phòng hiển thị trống.
  - Vai trò tùy chỉnh không có canViewHR (quan_ly_du_an/thiet_ke/
    giam_sat_thi_cong) dính thẳng 403.
Endpoint mới gate theo «Xem Dự án»/«Tạo Công việc», trả đủ nhân sự đang làm
việc nhưng CHỈ danh tính tối thiểu — không SĐT/email/bậc lương. Scope GET /users
giữ nguyên cho ngữ cảnh Nhân sự.
"""

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.middleware.permissions import xoa_cache_quyen
from app.models.user import User
from tests.conftest import auth_header


@pytest.fixture(autouse=True)
def _sach_cache_quyen():
    """Cache quyền là biến module (TTL 60s) — xóa trước/sau mỗi test kẻo leak."""
    xoa_cache_quyen()
    yield
    xoa_cache_quyen()


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


@pytest_asyncio.fixture
async def bo_may(client, db_session, admin_user):
    """Trưởng nhóm KD (đội riêng) + nhân sự Thiết kế/Thi công ngoài đội +
    quản lý dự án (vai trò tùy chỉnh, không canViewHR) + 1 người đã nghỉ."""
    await _tao_vai_tro(
        client, admin_user,
        role_key="quan_ly_du_an", role_name="Quản lý dự án", department="OPS",
        permissions={"canViewProjects": True, "canCreateTasks": True, "canEditTasks": True},
    )
    # Vai trò không dính gì tới dự án — để test 403 (nền data_entry có
    # canViewProjects=True nên phải tắt tường minh)
    await _tao_vai_tro(
        client, admin_user,
        role_key="ke_toan_kho", role_name="Kế toán kho", department="ACCT",
        permissions={"canViewProjects": False, "canCreateTasks": False},
    )

    leader = await _tao_user(client, db_session, admin_user, email="leader@test.com", role="leader", department="SALES")
    resp = await client.post(
        "/api/v1/users/teams",
        json={"name": "Đội Kinh doanh 1", "code": "KD1", "leader_id": leader.id},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text

    designer = await _tao_user(client, db_session, admin_user, email="designer@test.com", role="data_entry", department="DESIGN")
    ops = await _tao_user(client, db_session, admin_user, email="ops@test.com", role="supervisor", department="OPS")
    qlda = await _tao_user(client, db_session, admin_user, email="qlda@test.com", role="quan_ly_du_an", department="OPS")
    ktk = await _tao_user(client, db_session, admin_user, email="ktk@test.com", role="ke_toan_kho", department="ACCT")

    nghi_viec = await _tao_user(client, db_session, admin_user, email="nghi@test.com", role="data_entry", department="DESIGN")
    nghi_viec.is_active = False
    await db_session.commit()

    return {
        "leader": leader, "designer": designer, "ops": ops,
        "qlda": qlda, "ktk": ktk, "nghi_viec": nghi_viec,
    }


# ---------------------------------------------------------------------------
# 1. Trưởng nhóm hệ thống: GET /users bị cắt về nhóm, /task-assignable thấy đủ
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_leader_thay_du_nhan_su_cac_phong(client, bo_may):
    h = auth_header(bo_may["leader"])

    # GET /users (ngữ cảnh Nhân sự): giữ nguyên phạm vi nhóm — KHÔNG thấy Thiết kế
    resp = await client.get("/api/v1/users", headers=h)
    assert resp.status_code == 200
    hr_ids = {u["id"] for u in resp.json()["items"]}
    assert bo_may["designer"].id not in hr_ids
    assert bo_may["leader"].id in hr_ids

    # /task-assignable: đủ nhân sự chéo phòng cho dropdown «Đảm nhận»
    resp = await client.get("/api/v1/users/task-assignable", headers=h)
    assert resp.status_code == 200, resp.text
    ids = {u["id"] for u in resp.json()}
    assert bo_may["designer"].id in ids  # DESIGN — trước đây rỗng với leader
    assert bo_may["ops"].id in ids       # OPS
    assert bo_may["leader"].id in ids


# ---------------------------------------------------------------------------
# 2. Vai trò tùy chỉnh không canViewHR: /users 403 nhưng /task-assignable OK
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quan_ly_du_an_khong_canViewHR_van_co_dropdown(client, bo_may):
    h = auth_header(bo_may["qlda"])

    resp = await client.get("/api/v1/users", headers=h)
    assert resp.status_code == 403  # ngữ cảnh Nhân sự vẫn đóng

    resp = await client.get("/api/v1/users/task-assignable", headers=h)
    assert resp.status_code == 200, resp.text
    ids = {u["id"] for u in resp.json()}
    assert bo_may["designer"].id in ids and bo_may["ops"].id in ids


# ---------------------------------------------------------------------------
# 3. Admin: thấy đủ; người nghỉ việc không xuất hiện; không lộ SĐT/email/lương
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_thay_du_va_khong_lo_thong_tin_nhay_cam(client, bo_may, admin_user):
    resp = await client.get("/api/v1/users/task-assignable", headers=auth_header(admin_user))
    assert resp.status_code == 200
    items = resp.json()
    ids = {u["id"] for u in items}
    assert {bo_may["leader"].id, bo_may["designer"].id, bo_may["ops"].id} <= ids
    assert bo_may["nghi_viec"].id not in ids  # đã nghỉ — không giao việc được

    for item in items:
        assert "phone" not in item
        assert "email" not in item
        assert "salary_grade_id" not in item
        assert "custom_permissions" not in item


# ---------------------------------------------------------------------------
# 4. Không có quyền Dự án lẫn Tạo Công việc: 403
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_khong_quyen_du_an_bi_403(client, bo_may):
    resp = await client.get("/api/v1/users/task-assignable", headers=auth_header(bo_may["ktk"]))
    assert resp.status_code == 403
