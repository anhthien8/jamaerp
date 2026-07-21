"""RBAC matrix — chạy MỌI version theo docs/specs/06-qa-per-role-process.md (L3 negative).

Mỗi case khớp 1 guard THẬT trong code (đã đối chiếu 15/07/2026):
- pl.py::_require_clevel: admin/executive/accountant
- accounting.py payroll/commissions: admin/accountant
- audit.py: admin only
- users.py list: admin/accountant/leader; create: admin only
- attendance.py team: admin/accountant/leader(có team); ot/pending: admin/leader/accountant
- payroll.py: admin/accountant
- inventory.py: admin/supervisor/accountant (hoặc department=PURCHASING)
- hr.py resign*: admin/leader
- leads.py list: data_entry(own)/leader(team)/admin; role khác trả DANH SÁCH RỖNG (không 403)
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.auth import hash_password
from app.models.user import User, Team

from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# Helper — tạo user inline (tránh async fixture Runner.run() conflict)
# ---------------------------------------------------------------------------

async def _create_user(session: AsyncSession, role: str, department: str,
                       telegram_id: int | None = None, team: bool = False) -> User:
    uid = str(uuid.uuid4())
    user = User(
        id=uid,
        full_name=f"{role} RBAC",
        email=f"{role}-{uid[:8]}@rbac.test",
        password_hash=hash_password("rbac123"),
        role=role,
        department=department,
        is_active=True,
        telegram_user_id=telegram_id or (10_000_000 + hash(uid) % 90_000_000),
    )
    session.add(user)
    if team:
        team_obj = Team(
            id=str(uuid.uuid4()),
            name=f"Team {role}",
            code=f"T-{role.upper()[:4]}",
            department=department,
            leader_id=user.id,
        )
        session.add(team_obj)
        await session.flush()
        user.team_id = team_obj.id
    await session.commit()
    return user


# Predefined role→dept mapping
ALL_ROLES = [
    ("admin", "EXEC"),
    ("executive", "EXEC"),
    ("leader", "SALES"),
    ("data_entry", "SALES"),
    ("supervisor", "OPS"),
    ("accountant", "ACCT"),
]


# ---------------------------------------------------------------------------
# GET matrix — (path, allowed_roles)
# ---------------------------------------------------------------------------

GET_MATRIX = [
    ("/api/v1/pl/summary", {"admin", "executive", "accountant"}),
    ("/api/v1/audit-logs", {"admin"}),
    ("/api/v1/users", {"admin", "accountant", "leader"}),
    ("/api/v1/accounting/payroll", {"admin", "accountant"}),
    ("/api/v1/payroll?period=2026-01", {"admin", "accountant"}),
    ("/api/v1/attendance/team", {"admin", "accountant", "leader"}),
    ("/api/v1/attendance/ot/pending", {"admin", "accountant", "leader"}),
    ("/api/v1/inventory", {"admin", "accountant", "supervisor"}),
]


def _get_cases():
    cases = []
    for path, allowed in GET_MATRIX:
        for role, dept in ALL_ROLES:
            expected = 200 if role in allowed else 403
            tag = role if role != "data_entry" else "sales"
            cases.append(pytest.param(path, role, dept, expected,
                                      id=f"GET {path} [{tag}]→{expected}"))
    return cases


@pytest.mark.asyncio
@pytest.mark.parametrize("path,role,dept,expected", _get_cases())
async def test_get_endpoint_rbac(client, db_session, path, role, dept, expected):
    user = await _create_user(db_session, role, dept, team=(role == "leader"))
    resp = await client.get(path, headers=auth_header(user))
    assert resp.status_code == expected, (
        f"{path} với role {role}: mong {expected}, nhận {resp.status_code} — {resp.text[:120]}"
    )


# ---------------------------------------------------------------------------
# Ngữ nghĩa đặc biệt: /leads trả RỖNG (không 403) cho role ngoài khối sales
# ---------------------------------------------------------------------------

NON_SALES_ROLES = [
    ("executive", "EXEC"),
    ("supervisor", "OPS"),
    ("accountant", "ACCT"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("role,dept", NON_SALES_ROLES)
async def test_leads_returns_empty_for_non_sales(client, db_session, role, dept):
    user = await _create_user(db_session, role, dept)
    resp = await client.get("/api/v1/leads", headers=auth_header(user))
    assert resp.status_code == 200
    assert resp.json()["items"] == [], f"{role} không được thấy lead nào"


@pytest.mark.asyncio
async def test_leads_ok_for_sales_roles(client, db_session):
    for role, dept in [("admin", "EXEC"), ("leader", "SALES"), ("data_entry", "SALES")]:
        user = await _create_user(db_session, role, dept, team=(role == "leader"))
        resp = await client.get("/api/v1/leads", headers=auth_header(user))
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Write-endpoint denies (chỉ test phía BỊ CHẶN — tránh side effect)
# ---------------------------------------------------------------------------

WRITE_DENY_CASES = [
    # (method, path, payload, blocked_roles)
    ("POST", "/api/v1/users",
     {"full_name": "X", "email": "x@x.com", "password": "12345678",
      "role": "data_entry", "department": "SALES"},
     [("executive", "EXEC"), ("leader", "SALES"), ("data_entry", "SALES"),
      ("supervisor", "OPS"), ("accountant", "ACCT")]),
    # HR = admin + accountant (kế toán kiêm nhân sự, đồng bộ FE canManageUsers — 22/07);
    # leader bị loại (bản cũ leader gọi lén được API dù UI ẩn)
    ("POST", "/api/v1/hr/resign-preview", {"user_id": "fake-id"},
     [("executive", "EXEC"), ("data_entry", "SALES"),
      ("supervisor", "OPS"), ("leader", "SALES")]),
    ("POST", "/api/v1/payroll/generate?period=2099-01", None,
     [("executive", "EXEC"), ("leader", "SALES"), ("data_entry", "SALES"),
      ("supervisor", "OPS")]),
    ("POST", "/api/v1/accounting/commissions",
     {"user_id": "00000000-0000-0000-0000-000000000001", "type": "design_commission",
      "rate": 0.03, "base_amount": 1000, "milestone": "signing",
      "milestone_pct": 0.5, "status": "pending"},
     [("executive", "EXEC"), ("leader", "SALES"), ("data_entry", "SALES"),
      ("supervisor", "OPS")]),
    ("PUT", "/api/v1/salary-grades/fake-id", {"base_salary": 1},
     [("executive", "EXEC"), ("leader", "SALES"), ("data_entry", "SALES"),
      ("supervisor", "OPS")]),
]


def _deny_cases():
    cases = []
    for method, path, payload, roles in WRITE_DENY_CASES:
        for role, dept in roles:
            tag = role if role != "data_entry" else "sales"
            cases.append(pytest.param(method, path, payload, role, dept,
                                      id=f"{method} {path.split('?')[0]} [{tag}]→403"))
    return cases


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,payload,role,dept", _deny_cases())
async def test_write_endpoint_denied(client, db_session, method, path, payload, role, dept):
    user = await _create_user(db_session, role, dept)
    if method == "POST":
        resp = await client.post(path, json=payload, headers=auth_header(user))
    else:
        resp = await client.put(path, json=payload, headers=auth_header(user))
    assert resp.status_code == 403, (
        f"{method} {path} với role {role}: PHẢI 403, nhận {resp.status_code} — {resp.text[:120]}"
    )


# ---------------------------------------------------------------------------
# Bất biến: endpoint cá nhân mở cho MỌI role
# ---------------------------------------------------------------------------

PERSONAL_PATHS = ["/api/v1/payroll/me", "/api/v1/approvals/pending-for-me",
                  "/api/v1/attendance/me", "/api/v1/leaves/balance/me"]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", PERSONAL_PATHS)
@pytest.mark.parametrize("role,dept", ALL_ROLES)
async def test_personal_endpoints_open_to_all(client, db_session, path, role, dept):
    user = await _create_user(db_session, role, dept)
    resp = await client.get(path, headers=auth_header(user))
    assert resp.status_code == 200, f"{path} phải mở cho {role}"
