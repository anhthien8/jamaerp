"""Hai ô mới trong ma trận Phân quyền: «Sửa Nhà cung cấp» + «Sửa Khách hàng» (22/09/2026).

Trước bản này hai quyền đó hardcode trong `suppliers.py` / `customers.py`, KHÔNG
có ô nào trong ma trận 23 chức năng nên admin không cấp cũng không thu được.

Đo prod 22/09 trước khi đổi:
  - Nhà cung cấp: chỉ **6 người** sửa được (4 admin + 2 supervisor). TOÀN BỘ **8
    nhân sự Thu mua** (thu_mua 4 / du_toan 3 / dutoan_thumua_leader 1) không sửa
    được, dù cập nhật nhà cung cấp đúng là việc của họ.
  - Khách hàng: 17 người (admin 4, accountant 1, leader 4, data_entry 8). Luật cũ
    xét VAI TRÒ chứ không xét bộ phận nên `leader` phòng Thiết kế lại có quyền,
    còn 4 tài khoản Admin CSKH — chính nhóm chăm khách — thì không.
    Ngoài ra luật cũ liệt kê vai trò `"sales"` vốn KHÔNG tồn tại trong hệ thống.

Mặc định mới của 6 vai trò hệ thống được đặt để GIỮ ĐÚNG hiện trạng — không mở
cũng không siết thêm ai. Muốn đổi thì tích/bỏ tích ở trang Phân quyền.
"""

import pytest
from sqlalchemy import select

from app.middleware.permissions import (
    _ROLE_PERMISSION_DEFAULTS, NHAN_QUYEN, quyen_hieu_luc, xoa_cache_quyen,
)
from app.models.user import User
from tests.conftest import auth_header


@pytest.fixture(autouse=True)
def _sach_cache_quyen():
    xoa_cache_quyen()
    yield
    xoa_cache_quyen()


HAI_O = ("canEditSuppliers", "canEditCustomers")


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


async def _tao_ncc(client, nguoi, ten="NCC Thép Miền Nam"):
    return await client.post(
        "/api/v1/suppliers", json={"name": ten, "phone": "0281234567"},
        headers=auth_header(nguoi),
    )


async def _tao_khach(client, nguoi, ten="Anh Bảo"):
    return await client.post(
        "/api/v1/customers", json={"name": ten, "phone": "0908887776"},
        headers=auth_header(nguoi),
    )


# ── Hai ô phải có mặt đầy đủ trong ma trận ─────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("o", HAI_O)
async def test_o_moi_co_trong_moi_vai_tro_he_thong(o):
    """Thiếu key ở một vai trò là người đó rơi về giá trị mặc định của người khác."""
    for vai, perms in _ROLE_PERMISSION_DEFAULTS.items():
        assert o in perms, f"vai trò {vai} thiếu ô {o}"
    assert o in NHAN_QUYEN, f"{o} chưa có nhãn tiếng Việt"


@pytest.mark.asyncio
async def test_mac_dinh_giu_dung_hien_trang_truoc_khi_doi():
    """Chốt lại đúng con số đã đo trên prod — đổi mặc định phải làm test này đỏ."""
    d = _ROLE_PERMISSION_DEFAULTS
    ncc = {v for v in d if d[v]["canEditSuppliers"]}
    kh = {v for v in d if d[v]["canEditCustomers"]}
    assert ncc == {"admin", "supervisor"}, f"Nhà cung cấp lệch hiện trạng: {ncc}"
    assert kh == {"admin", "accountant", "leader", "data_entry"}, f"Khách hàng lệch: {kh}"


# ── Nhà cung cấp ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_thu_mua_duoc_cap_thi_sua_duoc_nha_cung_cap(client, db_session, admin_user):
    """Đúng vấn đề đã báo: nhân sự Thu mua phải sửa được nhà cung cấp."""
    await _tao_vai_tro(client, admin_user, "thu_mua", "Thu mua", "PURCHASING",
                       canEditSuppliers=True)
    nv = await _tao_user(client, db_session, admin_user, "tm@test.com", "thu_mua", "PURCHASING")
    resp = await _tao_ncc(client, nv)
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_chua_cap_thi_van_bi_chan(client, db_session, admin_user):
    await _tao_vai_tro(client, admin_user, "thiet_ke", "Thiết kế", "DESIGN")
    nv = await _tao_user(client, db_session, admin_user, "tk@test.com", "thiet_ke", "DESIGN")
    resp = await _tao_ncc(client, nv)
    assert resp.status_code == 403
    assert "Sửa Nhà cung cấp" in resp.json()["detail"], "phải chỉ rõ ô nào còn thiếu"


@pytest.mark.asyncio
async def test_cap_quyen_rieng_cho_dung_mot_nguoi(client, db_session, admin_user):
    """Trường hợp «nhân sự A hỗ trợ việc của nhân sự B» — cấp riêng, không đổi vai trò."""
    await _tao_vai_tro(client, admin_user, "du_toan", "Dự toán", "PURCHASING")
    nv = await _tao_user(client, db_session, admin_user, "dt@test.com", "du_toan", "PURCHASING")
    assert (await _tao_ncc(client, nv)).status_code == 403

    r = await client.put(f"/api/v1/users/{nv.id}/permissions",
                         json={"permissions": {"canEditSuppliers": True}},
                         headers=auth_header(admin_user))
    assert r.status_code == 200, r.text
    xoa_cache_quyen()
    assert (await _tao_ncc(client, nv, "NCC Gỗ An Cường")).status_code == 200


@pytest.mark.asyncio
async def test_sua_va_xoa_ncc_cung_theo_o_do(client, db_session, admin_user):
    """Guard dùng cho cả tạo/sửa/xoá — không để sót đường nào."""
    await _tao_vai_tro(client, admin_user, "thu_mua2", "Thu mua 2", "PURCHASING",
                       canEditSuppliers=True)
    nv = await _tao_user(client, db_session, admin_user, "tm2@test.com", "thu_mua2", "PURCHASING")
    tao = await _tao_ncc(client, nv, "NCC Nhôm Xingfa")
    assert tao.status_code == 200, tao.text
    ncc_id = tao.json()["id"]

    sua = await client.put(f"/api/v1/suppliers/{ncc_id}", json={"phone": "0287654321"},
                           headers=auth_header(nv))
    assert sua.status_code == 200, sua.text

    await _tao_vai_tro(client, admin_user, "thiet_ke2", "Thiết kế 2", "DESIGN")
    nguoi_la = await _tao_user(client, db_session, admin_user, "tk2@test.com", "thiet_ke2", "DESIGN")
    assert (await client.put(f"/api/v1/suppliers/{ncc_id}", json={"phone": "0280000000"},
                             headers=auth_header(nguoi_la))).status_code == 403


# ── Khách hàng ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sale_van_sua_duoc_khach_hang(client, db_session, admin_user):
    """Hiện trạng phải được giữ: sale (data_entry) vẫn sửa hồ sơ khách."""
    nv = await _tao_user(client, db_session, admin_user, "sale@test.com", "data_entry", "SALES")
    resp = await _tao_khach(client, nv)
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_bo_phan_khac_khong_sua_duoc_khach_hang(client, db_session, admin_user):
    await _tao_vai_tro(client, admin_user, "giam_sat_thi_cong", "Giám sát thi công", "OPS")
    nv = await _tao_user(client, db_session, admin_user, "gs@test.com",
                         "giam_sat_thi_cong", "OPS")
    resp = await _tao_khach(client, nv)
    assert resp.status_code == 403
    assert "Sửa Khách hàng" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_admin_cskh_cap_duoc_quyen_sua_khach_hang(client, db_session, admin_user):
    """Admin CSKH là nhóm chăm khách mà luật cũ lại không cho sửa — nay cấp được."""
    await _tao_vai_tro(client, admin_user, "admin_cskh", "Admin CSKH", "SALES",
                       canViewLeads=True, canEditCustomers=True)
    nv = await _tao_user(client, db_session, admin_user, "cskh@test.com", "admin_cskh", "SALES")
    resp = await _tao_khach(client, nv, "Chị Lan")
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_thu_quyen_thi_chan_ngay(client, db_session, admin_user):
    """Bỏ tích phải có hiệu lực thật — không chỉ đổi giao diện."""
    nv = await _tao_user(client, db_session, admin_user, "sale2@test.com", "data_entry", "SALES")
    assert (await _tao_khach(client, nv, "Anh Tùng")).status_code == 200

    r = await client.put(f"/api/v1/users/{nv.id}/permissions",
                         json={"permissions": {"canEditCustomers": False}},
                         headers=auth_header(admin_user))
    assert r.status_code == 200, r.text
    xoa_cache_quyen()
    assert (await _tao_khach(client, nv, "Anh Dũng")).status_code == 403


@pytest.mark.asyncio
async def test_hai_o_doc_lap_nhau(client, db_session, admin_user):
    """Cấp quyền Nhà cung cấp KHÔNG kéo theo quyền Khách hàng và ngược lại."""
    await _tao_vai_tro(client, admin_user, "thu_mua3", "Thu mua 3", "PURCHASING",
                       canEditSuppliers=True)
    nv = await _tao_user(client, db_session, admin_user, "tm3@test.com", "thu_mua3", "PURCHASING")
    assert (await _tao_ncc(client, nv, "NCC Kính Việt")).status_code == 200
    assert (await _tao_khach(client, nv, "Anh Khoa")).status_code == 403

    perms = await quyen_hieu_luc(nv, db_session)
    assert perms["canEditSuppliers"] is True
    assert perms["canEditCustomers"] is False
