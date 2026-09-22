"""Quyền riêng của từng người phải DÙNG ĐƯỢC thật (22/09/2026).

User báo: «Sửa lỗi khi cập nhật chức năng tài khoản thì không sử dụng được.
Chức năng, phân quyền được setup mặc định theo vị trí, tuy nhiên nếu bổ sung
thêm chức năng thuộc bộ phận khác (Trường hợp cần nhân sự A được phân công hỗ
trợ xử lý của nhân sự B) thì vẫn sẽ được cập nhật chức năng.»

Hai lớp lỗi tìm được khi đọc code:
  1. Frontend: Sidebar/BottomNav/Quy trình/Tổng quan tính quyền bằng
     `getPermissions(role)` — BỎ QUA `users.custom_permissions`. Backend lưu và
     tôn trọng quyền riêng, nhưng MENU không bao giờ hiện ⇒ «không sử dụng được».
     Đã chuyển 4 chỗ đó sang `effectivePermissions` của useAuth.
  2. Đổi vị trí của một người thì phần lệch quyền cũ vẫn giữ nguyên ⇒ họ bị
     đóng băng theo vị trí cũ. Đã rebase phần lệch theo vị trí mới.

File này khóa phần BACKEND: cấp chéo bộ phận thì API phải cho dùng thật, còn
lead thì vẫn chặn cứng theo bộ phận (nguyên tắc 22/09) — override không mở được.
"""

import pytest
from sqlalchemy import select

from app.middleware.permissions import quyen_hieu_luc, xoa_cache_quyen
from app.models.user import User
from tests.conftest import auth_header


@pytest.fixture(autouse=True)
def _sach_cache_quyen():
    xoa_cache_quyen()
    yield
    xoa_cache_quyen()


async def _tao_vai_tro(client, admin, role_key, role_name, department, **quyen):
    resp = await client.post(
        "/api/v1/users/roles",
        json={"role_key": role_key, "role_name": role_name, "department": department,
              "permissions": {"canViewProjects": True, **quyen}},
        headers=auth_header(admin),
    )
    assert resp.status_code == 200, resp.text


async def _tao_user(client, db, admin, email, role, department):
    resp = await client.post(
        "/api/v1/users",
        json={"full_name": f"NV {email.split('@')[0]}", "email": email,
              "password": "secret123", "role": role, "department": department},
        headers=auth_header(admin),
    )
    assert resp.status_code == 200, resp.text
    return (await db.execute(select(User).where(User.id == resp.json()["id"]))).scalar_one()


async def _cap_quyen_rieng(client, admin, uid, **quyen):
    resp = await client.put(f"/api/v1/users/{uid}/permissions",
                            json={"permissions": quyen}, headers=auth_header(admin))
    assert resp.status_code == 200, resp.text


# ── Cấp chéo bộ phận: phải dùng được THẬT ───────────────────────────────────

@pytest.mark.asyncio
async def test_cap_them_chuc_nang_cheo_bo_phan_thi_dung_duoc(client, db_session, admin_user):
    """Nhân sự Thiết kế được phân công hỗ trợ việc Thu mua → cấp «Xem Kho»."""
    await _tao_vai_tro(client, admin_user, "thiet_ke", "Thiết kế", "DESIGN",
                       canViewInventory=False)
    nv = await _tao_user(client, db_session, admin_user, "tk@test.com", "thiet_ke", "DESIGN")

    truoc = await client.get("/api/v1/inventory", headers=auth_header(nv))
    assert truoc.status_code == 403, "chưa cấp thì phải bị chặn"

    await _cap_quyen_rieng(client, admin_user, nv.id, canViewInventory=True)
    xoa_cache_quyen()
    sau = await client.get("/api/v1/inventory", headers=auth_header(nv))
    assert sau.status_code == 200, f"cấp rồi phải dùng được, nhận {sau.status_code}: {sau.text}"


@pytest.mark.asyncio
async def test_quyen_rieng_chi_luu_phan_lech_van_thua_ke_vi_tri(client, db_session, admin_user):
    """Lưu 1 ô lệch thì 22 ô còn lại vẫn THỪA KẾ mặc định của vị trí.

    Bản cũ lưu cả bảng 23 ô làm quyền riêng ⇒ sau này sửa quyền theo vị trí thì
    người đó không được cập nhật nữa.
    """
    await _tao_vai_tro(client, admin_user, "thu_mua", "Thu mua", "PURCHASING",
                       canViewQuotations=True, canViewInventory=False)
    nv = await _tao_user(client, db_session, admin_user, "tm@test.com", "thu_mua", "PURCHASING")
    await _cap_quyen_rieng(client, admin_user, nv.id, canViewInventory=True)
    xoa_cache_quyen()

    nv = (await db_session.execute(select(User).where(User.id == nv.id))).scalar_one()
    await db_session.refresh(nv)
    import json
    assert json.loads(nv.custom_permissions) == {"canViewInventory": True}, (
        "chỉ được lưu đúng phần lệch"
    )
    perms = await quyen_hieu_luc(nv, db_session)
    assert perms["canViewInventory"] is True, "phần lệch có hiệu lực"
    assert perms["canViewQuotations"] is True, "ô không lệch vẫn thừa kế vị trí"
    assert perms["canViewProjects"] is True


@pytest.mark.asyncio
async def test_go_quyen_rieng_thi_ve_mac_dinh_vi_tri(client, db_session, admin_user):
    await _tao_vai_tro(client, admin_user, "du_toan", "Dự toán", "PURCHASING",
                       canViewInventory=False)
    nv = await _tao_user(client, db_session, admin_user, "dt@test.com", "du_toan", "PURCHASING")
    await _cap_quyen_rieng(client, admin_user, nv.id, canViewInventory=True)
    xoa_cache_quyen()
    assert (await client.get("/api/v1/inventory", headers=auth_header(nv))).status_code == 200

    # Gửi {} = xóa hết quyền riêng, về mặc định vị trí
    resp = await client.put(f"/api/v1/users/{nv.id}/permissions", json={"permissions": {}},
                            headers=auth_header(admin_user))
    assert resp.status_code == 200, resp.text
    xoa_cache_quyen()
    assert (await client.get("/api/v1/inventory", headers=auth_header(nv))).status_code == 403


# ── Nhưng LEAD thì override KHÔNG mở được (nguyên tắc 22/09) ─────────────────

@pytest.mark.asyncio
async def test_cap_quyen_rieng_khong_mo_duoc_lead_cho_bo_phan_khac(client, db_session, admin_user):
    """Chặn cứng theo bộ phận đứng TRÊN mọi override — kể cả quyền riêng của admin."""
    await _tao_vai_tro(client, admin_user, "thiet_ke", "Thiết kế", "DESIGN")
    nv = await _tao_user(client, db_session, admin_user, "tk2@test.com", "thiet_ke", "DESIGN")
    lead_id = (await client.post(
        "/api/v1/leads", json={"name": "KH A", "phone": "0900000001"},
        headers=auth_header(admin_user),
    )).json()["id"]

    await _cap_quyen_rieng(client, admin_user, nv.id, canViewLeads=True)
    xoa_cache_quyen()

    ds = await client.get("/api/v1/leads", headers=auth_header(nv))
    assert ds.status_code == 200
    assert ds.json()["items"] == [], "cấp quyền riêng cũng KHÔNG thấy lead"
    ct = await client.get(f"/api/v1/leads/{lead_id}", headers=auth_header(nv))
    assert ct.status_code == 403


@pytest.mark.asyncio
async def test_chuyen_nguoi_sang_kinh_doanh_thi_thay_lead(client, db_session, admin_user):
    """Muốn cho ai đó xem lead thì chuyển BỘ PHẬN sang Kinh doanh — đường đúng."""
    await _tao_vai_tro(client, admin_user, "thiet_ke", "Thiết kế", "DESIGN", canViewLeads=True)
    nv = await _tao_user(client, db_session, admin_user, "tk3@test.com", "thiet_ke", "DESIGN")
    lead_id = (await client.post(
        "/api/v1/leads", json={"name": "KH B", "phone": "0900000002", "assigned_to": nv.id},
        headers=auth_header(admin_user),
    )).json()["id"]
    assert (await client.get("/api/v1/leads", headers=auth_header(nv))).json()["items"] == []

    resp = await client.put(f"/api/v1/users/{nv.id}", json={"department": "SALES"},
                            headers=auth_header(admin_user))
    assert resp.status_code == 200, resp.text
    xoa_cache_quyen()
    nv = (await db_session.execute(select(User).where(User.id == nv.id))).scalar_one()
    await db_session.refresh(nv)

    ds = await client.get("/api/v1/leads", headers=auth_header(nv))
    assert lead_id in {l["id"] for l in ds.json()["items"]}, "vào bộ phận KD thì thấy lead của mình"
