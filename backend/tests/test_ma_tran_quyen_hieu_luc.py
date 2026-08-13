"""Ma trận quyền HIỆU LỰC trên endpoint thật (GĐ1→GĐ3 — 13/08/2026).

Khác test_rbac_matrix.py (gác theo role cứng có từ trước), file này soát lớp gác
MỚI theo ma trận Phân quyền:
- GĐ1: endpoint tài chính/kho gác bằng yeu_cau(quyền) — kỳ vọng 200/403 SUY TỪ
  _ROLE_PERMISSION_DEFAULTS, nên đổi ma trận mặc định là test tự đổi theo.
- GĐ2: /accounting/commissions cắt phạm vi server-side — không có «Xem hoa hồng
  người khác» thì chỉ thấy của mình.
- GĐ3: vai trò phòng ban seed sẵn đi qua đúng cửa (thu_mua vào kho, thiet_ke không).
- Chốt cửa: MỌI route /api/v1 mới đều phải qua get_current_user, trừ danh sách
  công khai đã duyệt (webhook có secret riêng, portal theo token, auth, health).
"""

import uuid

import pytest
from fastapi.routing import APIRoute

from app.middleware.auth import get_current_user, hash_password
from app.middleware.permissions import _ROLE_PERMISSION_DEFAULTS
from app.models.payroll import Commission
from app.models.user import User
from app.seed import seed_vai_tro_phong_ban
from tests.conftest import auth_header


async def _tao_user(db, role: str, department: str) -> User:
    uid = str(uuid.uuid4())
    user = User(
        id=uid,
        full_name=f"{role} matrix",
        email=f"{role}-{uid[:8]}@matrix.test",
        password_hash=hash_password("matrix123"),
        role=role,
        department=department,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    return user


# ---------------------------------------------------------------------------
# GĐ1 — endpoint đọc gác theo ma trận: kỳ vọng suy từ defaults, không hard-code
# ---------------------------------------------------------------------------

ENDPOINT_THEO_QUYEN = [
    ("/api/v1/accounting/transactions", "canViewPnL"),
    ("/api/v1/accounting/summary", "canViewPnL"),
    ("/api/v1/fixed-costs", "canViewPnL"),
    ("/api/v1/variable-costs", "canViewPnL"),
    ("/api/v1/commission-structures", "canViewPnL"),
    ("/api/v1/suppliers", "canViewInventory"),
]

VAI_TRO_HE_THONG = [
    ("admin", "EXEC"),
    ("executive", "EXEC"),
    ("leader", "SALES"),
    ("data_entry", "SALES"),
    ("supervisor", "OPS"),
    ("accountant", "ACCT"),
]


def _cases_gd1():
    cases = []
    for path, quyen in ENDPOINT_THEO_QUYEN:
        for role, dept in VAI_TRO_HE_THONG:
            expected = 200 if _ROLE_PERMISSION_DEFAULTS[role][quyen] else 403
            cases.append(pytest.param(
                path, role, dept, expected,
                id=f"GET {path} [{role}]→{expected}",
            ))
    return cases


@pytest.mark.asyncio
@pytest.mark.parametrize("path,role,dept,expected", _cases_gd1())
async def test_gd1_endpoint_gac_theo_ma_tran(client, db_session, path, role, dept, expected):
    user = await _tao_user(db_session, role, dept)
    resp = await client.get(path, headers=auth_header(user))
    assert resp.status_code == expected, (
        f"{path} với {role}: mong {expected}, nhận {resp.status_code} — {resp.text[:120]}"
    )


# ---------------------------------------------------------------------------
# GĐ2 — /accounting/commissions: phạm vi cắt ở máy chủ, không phải giao diện
# ---------------------------------------------------------------------------

async def _hai_hoa_hong(db, user_minh: User, user_khac: User):
    for u in (user_minh, user_khac):
        db.add(Commission(
            id=str(uuid.uuid4()), user_id=u.id, type="design_commission",
            rate=0.03, base_amount=1_000_000_000, commission_amount=30_000_000,
            milestone="signing", milestone_pct=0.5, status="pending", period="2026-08",
        ))
    await db.commit()


@pytest.mark.asyncio
async def test_gd2_leader_chi_thay_hoa_hong_cua_minh(client, db_session):
    leader = await _tao_user(db_session, "leader", "SALES")
    khac = await _tao_user(db_session, "data_entry", "SALES")
    await _hai_hoa_hong(db_session, leader, khac)

    resp = await client.get("/api/v1/accounting/commissions", headers=auth_header(leader))
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["user_id"] == leader.id  # tuyệt đối không lộ dòng của người khác


@pytest.mark.asyncio
async def test_gd2_accountant_thay_het_hoa_hong(client, db_session):
    acct = await _tao_user(db_session, "accountant", "ACCT")
    khac = await _tao_user(db_session, "data_entry", "SALES")
    await _hai_hoa_hong(db_session, acct, khac)

    resp = await client.get("/api/v1/accounting/commissions", headers=auth_header(acct))
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 2  # canViewCommissionOthers=True → thấy hết


# ---------------------------------------------------------------------------
# GĐ3 — vai trò phòng ban seed sẵn đi qua đúng cửa trên endpoint thật
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gd3_thu_mua_vao_kho_nhung_khong_vao_tai_chinh(client, db_session):
    await seed_vai_tro_phong_ban(db_session)
    user = await _tao_user(db_session, "thu_mua", "PURCHASING")

    resp = await client.get("/api/v1/suppliers", headers=auth_header(user))
    assert resp.status_code == 200, "Thu mua PHẢI vào được danh bạ NCC (cửa chính)"

    resp = await client.get("/api/v1/accounting/transactions", headers=auth_header(user))
    assert resp.status_code == 403, "Thu mua KHÔNG được xem sổ giao dịch"


@pytest.mark.asyncio
async def test_gd3_thiet_ke_khong_vao_kho(client, db_session):
    await seed_vai_tro_phong_ban(db_session)
    user = await _tao_user(db_session, "thiet_ke", "DESIGN")

    resp = await client.get("/api/v1/suppliers", headers=auth_header(user))
    assert resp.status_code == 403, "Thiết kế không có «Xem Kho» → không thấy giá NCC"


# ---------------------------------------------------------------------------
# Chốt cửa — route /api/v1 mới nào cũng phải qua get_current_user
# ---------------------------------------------------------------------------

# Danh sách công khai ĐÃ DUYỆT 13/08/2026 — mỗi đường có lớp bảo vệ riêng:
# auth (login/quên mật khẩu), health, instant-quote public (tính năng công khai),
# zalo ingest (header X-Zalo-Secret), portal khách (token trong URL),
# feedback/telegram (shared secret của bot). Thêm route công khai MỚI thì phải
# cân nhắc + bổ sung vào đây CÓ CHỦ ĐÍCH — test này chặn kiểu "quên gác".
ROUTE_CONG_KHAI = {
    "/api/v1/auth/login",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
    "/api/v1/auth/telegram",
    "/api/v1/instant-quote/public",
    "/api/v1/zalo/ingest/pending-login",
    "/api/v1/zalo/ingest/session",
    "/api/v1/zalo/ingest/message",
    "/api/v1/portal/{token}",
    "/api/v1/portal/{token}/projects/{project_id}",
    "/api/v1/portal/{token}/projects/{project_id}/accept-stage",
    "/api/v1/portal/{token}/projects/{project_id}/activities",
    "/api/v1/feedback/telegram",
}


def _co_get_current_user(dependant) -> bool:
    for dep in dependant.dependencies:
        if dep.call is get_current_user or _co_get_current_user(dep):
            return True
    return False


def test_moi_route_api_deu_co_cua_dang_nhap():
    from app.main import app

    thieu = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith("/api/v1"):
            continue  # /health, / — ngoài API
        if route.path in ROUTE_CONG_KHAI:
            continue
        if not _co_get_current_user(route.dependant):
            thieu.append(f"{sorted(route.methods)} {route.path}")

    assert not thieu, (
        "Route thiếu cửa đăng nhập (không qua get_current_user). Nếu CỐ Ý công khai, "
        "thêm vào ROUTE_CONG_KHAI kèm lý do:\n" + "\n".join(thieu)
    )
