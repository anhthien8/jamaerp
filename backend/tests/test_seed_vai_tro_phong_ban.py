"""Seed 4 vai trò phòng ban (GĐ3 — 13/08/2026): idempotent, không ghi đè chỉnh sửa.

Chạy MỖI lần boot (khác seed_database chỉ chạy khi DB trống) nên phải bảo đảm:
- Thêm đủ 4 vai trò khi chưa có gì.
- Chạy lại không nhân đôi.
- Admin đã chỉnh quyền trên trang Phân quyền → seed KHÔNG được ghi đè.
- Vai trò custom có sẵn (vd admin_cskh) phải còn nguyên.
- User mang vai trò seed phải resolve đúng quyền lúc runtime.
"""

import json

import pytest

from app.middleware.auth import hash_password
from app.models.notification import SystemSetting
from app.models.user import User
from app.seed import _VAI_TRO_PHONG_BAN, seed_vai_tro_phong_ban
from tests.conftest import auth_header

BON_VAI_TRO = {"quan_ly_du_an", "thiet_ke", "giam_sat_thi_cong", "thu_mua"}
# 14/08/2026: thêm sale_leader (Trưởng nhóm Kinh doanh) — khác 4 vai trò phòng ban:
# ĐƯỢC xem leads (phạm vi nhóm), vẫn không đụng tài chính.
VAI_TRO_SEED = BON_VAI_TRO | {"sale_leader"}


async def _doc_custom_roles(db_session) -> list[dict]:
    setting = await db_session.get(SystemSetting, "custom_roles")
    return json.loads(setting.value) if setting else []


@pytest.mark.asyncio
async def test_seed_them_du_4_vai_tro_khi_db_trong(db_session):
    await seed_vai_tro_phong_ban(db_session)
    await db_session.commit()

    roles = await _doc_custom_roles(db_session)
    assert {r["role_key"] for r in roles} == VAI_TRO_SEED
    # Mỗi vai trò phải mang ĐỦ 25 khóa quyền — thiếu khóa là resolve fallback sai
    for r in roles:
        assert len(r["permissions"]) == len(_VAI_TRO_PHONG_BAN[0]["permissions"]), r["role_key"]
    # Nguyên tắc: không vai trò seed nào thấy tài chính; riêng leads chỉ
    # sale_leader được xem (phạm vi nhóm), 4 vai trò phòng ban thì không.
    for r in roles:
        assert r["permissions"]["canViewAccounting"] is False, r["role_key"]
        assert r["permissions"]["canViewPnL"] is False, r["role_key"]
        assert r["permissions"]["canViewLeads"] is (r["role_key"] == "sale_leader"), r["role_key"]


@pytest.mark.asyncio
async def test_seed_chay_lai_khong_nhan_doi(db_session):
    await seed_vai_tro_phong_ban(db_session)
    await seed_vai_tro_phong_ban(db_session)
    await db_session.commit()

    roles = await _doc_custom_roles(db_session)
    assert len(roles) == len(VAI_TRO_SEED)  # không nhân đôi


@pytest.mark.asyncio
async def test_seed_khong_ghi_de_chinh_sua_cua_admin(db_session):
    """Admin tắt quyền trên trang Phân quyền → boot lại seed KHÔNG được bật lại."""
    await seed_vai_tro_phong_ban(db_session)

    # Giả lập admin chỉnh: thiet_ke được mở thêm quyền xem hợp đồng
    roles = await _doc_custom_roles(db_session)
    for r in roles:
        if r["role_key"] == "thiet_ke":
            r["permissions"]["canViewContracts"] = True
    setting = await db_session.get(SystemSetting, "custom_roles")
    setting.value = json.dumps(roles, ensure_ascii=False)
    await db_session.commit()

    # Boot lại (seed chạy lần nữa) — chỉnh sửa phải còn nguyên
    await seed_vai_tro_phong_ban(db_session)
    await db_session.commit()

    roles = await _doc_custom_roles(db_session)
    thiet_ke = next(r for r in roles if r["role_key"] == "thiet_ke")
    assert thiet_ke["permissions"]["canViewContracts"] is True


@pytest.mark.asyncio
async def test_seed_giu_nguyen_vai_tro_custom_co_san(db_session):
    """Vai trò admin tự tạo (vd admin_cskh) phải sống sót qua seed."""
    db_session.add(SystemSetting(
        key="custom_roles",
        value=json.dumps([{
            "role_key": "admin_cskh",
            "role_name": "Admin CSKH",
            "department": "SALES",
            "permissions": {"canViewDashboard": True, "canViewLeads": True},
        }], ensure_ascii=False),
    ))
    await db_session.commit()

    await seed_vai_tro_phong_ban(db_session)
    await db_session.commit()

    roles = await _doc_custom_roles(db_session)
    keys = {r["role_key"] for r in roles}
    assert keys == VAI_TRO_SEED | {"admin_cskh"}
    cskh = next(r for r in roles if r["role_key"] == "admin_cskh")
    assert cskh["permissions"] == {"canViewDashboard": True, "canViewLeads": True}


@pytest.mark.asyncio
async def test_user_vai_tro_seed_resolve_dung_quyen(client, db_session, admin_user):
    """User mang vai trò thu_mua phải nhận đúng quyền định nghĩa — không fallback data_entry."""
    await seed_vai_tro_phong_ban(db_session)

    user = User(
        id="u-thu-mua-01",
        full_name="Nhân viên Thu mua",
        email="thumua@test.com",
        password_hash=hash_password("secret123"),
        role="thu_mua",
        department="PURCHASING",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    resp = await client.get("/api/v1/users/permissions/me", headers=auth_header(user))
    assert resp.status_code == 200
    perms = resp.json()["permissions"]
    assert perms["canViewInventory"] is True     # cửa chính: kho + NCC + so giá
    assert perms["canViewAccounting"] is False   # data_entry mặc định True — fallback sai sẽ lộ
    assert perms["canViewLeads"] is False
    assert perms["canViewApprovals"] is True
