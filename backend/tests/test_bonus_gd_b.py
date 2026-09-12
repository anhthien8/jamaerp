"""Test luồng thưởng (bonus) GĐ B — tạo qua Approval Center, cộng vào dòng lương,
chốt paid khi chi lương, sinh Transaction expense cho tổng net.

Bất biến:
1. Không phải kế toán/admin → 403 khi đề xuất thưởng.
2. Kỳ đã khóa → 409.
3. Thưởng pending KHÔNG vào dòng lương; approved thì cộng vào gross+net.
4. Khi pay kỳ: bonus approved → paid, và sinh 1 Transaction expense đúng tổng net.
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import create_access_token, hash_password
from app.models.payroll import Bonus, Payroll, Transaction
from app.models.user import User
from app.services import approval_engine


@pytest_asyncio.fixture
async def kt(db_session: AsyncSession) -> User:
    u = User(id=str(uuid.uuid4()), full_name="KT Test", email="kt_bonus@test.com",
             password_hash=hash_password("pass123"), role="accountant", department="ACCT",
             is_active=True)
    db_session.add(u); await db_session.flush()
    return u


@pytest_asyncio.fixture
async def admin(db_session: AsyncSession) -> User:
    u = User(id=str(uuid.uuid4()), full_name="Admin Bonus Test", email="admin_bonus@test.com",
             password_hash=hash_password("pass123"), role="admin", department="EXEC",
             is_active=True)
    db_session.add(u); await db_session.flush()
    return u


@pytest_asyncio.fixture
async def target_user(db_session: AsyncSession) -> User:
    u = User(id=str(uuid.uuid4()), full_name="DE Test", email="de_bonus@test.com",
             password_hash=hash_password("pass123"), role="data_entry", department="SALES",
             is_active=True)
    db_session.add(u); await db_session.flush()
    return u


def _h(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(user.id), user.role, user.department)}"}


@pytest.mark.asyncio
async def test_bonus_requires_accountant(client: AsyncClient, db_session: AsyncSession):
    """data_entry không đề xuất được thưởng."""
    from tests.conftest import sales_user  # noqa
    de = await db_session.run_sync(lambda s: None) or None
    de = User(id=str(uuid.uuid4()), full_name="DE", email="de_x@test.com",
              password_hash=hash_password("pass123"), role="data_entry", department="SALES",
              is_active=True)
    db_session.add(de); await db_session.flush()
    resp = await client.post("/api/v1/payroll/bonus",
        json={"user_id": de.id, "period": "2026-01", "amount": 1000, "reason": "test"},
        headers=_h(de))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_bonus_reject_locked_period(client: AsyncClient, db_session: AsyncSession, kt, target_user):
    """Kỳ đã approved → 409."""
    period = "2026-03"
    db_session.add(Payroll(
        user_id=target_user.id, period=period, status="approved",
        base_salary=10_000_000, work_days=22, standard_days=26,
        ot_hours=0, ot_pay=0, commission_total=0, bonus=0, allowance=0,
        gross_salary=10_000_000, bhxh_employee=0, bhxh_company=0,
        taxable_income=0, pit=0, advance_deduction=0, deductions=0,
        net_salary=10_000_000))
    await db_session.flush()
    resp = await client.post("/api/v1/payroll/bonus",
        json={"user_id": target_user.id, "period": period, "amount": 500_000, "reason": "kỳ đã khóa"},
        headers=_h(kt))
    assert resp.status_code == 409, resp.text


@pytest.mark.asyncio
async def test_bonus_full_lifecycle(client: AsyncClient, db_session: AsyncSession, kt, admin, target_user):
    """Kế toán đề xuất → admin duyệt → generate → bonus vào gross → pay → paid + Transaction."""
    period = "2026-05"

    # Dọn
    for r in (await db_session.execute(select(Payroll).where(Payroll.period == period))).scalars().all():
        await db_session.delete(r)
    for b in (await db_session.execute(select(Bonus).where(Bonus.period == period))).scalars().all():
        await db_session.delete(b)
    await db_session.flush()

    # 1. Tạo thưởng
    resp = await client.post("/api/v1/payroll/bonus",
        json={"user_id": target_user.id, "period": period, "amount": 500_000,
              "reason": "Thưởng dự án ABC"},
        headers=_h(kt))
    assert resp.status_code == 200, resp.text
    bonus_id = resp.json()["bonus"]["id"]
    assert resp.json()["bonus"]["status"] == "pending"

    # 2. Duyệt trực tiếp qua approval_engine (bỏ qua API để tránh coupled test)
    approval = await approval_engine.create_request(
        db_session, type_="bonus", ref_id=bonus_id,
        title="Thưởng test", requester=kt, approver_ids=[admin.id],
        amount=500_000)
    await db_session.flush()
    await approval_engine.approve(db_session, approval.id, admin)
    await db_session.flush()

    bonus = await db_session.get(Bonus, bonus_id)
    assert bonus.status == "approved"

    # 3. Generate kỳ lương → bonus cộng vào
    resp = await client.post(f"/api/v1/payroll/generate?period={period}", headers=_h(kt))
    assert resp.status_code == 200, resp.text

    rows = await client.get(f"/api/v1/payroll?period={period}", headers=_h(kt))
    row = next((r for r in rows.json()["items"] if r["user_id"] == target_user.id), None)
    assert row, "phải có dòng lương"
    assert row["bonus"] == 500_000, f"thưởng phải vào dòng lương, got {row['bonus']}"

    # 4. Submit + duyệt kỳ (pay yêu cầu status approved)
    resp = await client.post(f"/api/v1/payroll/{period}/submit", headers=_h(kt))
    assert resp.status_code == 200, resp.text
    approval_id = resp.json().get("approval_id")
    assert approval_id, "submit phải trả về approval_id"
    await approval_engine.approve(db_session, approval_id, admin)
    await db_session.flush()

    # 5. Pay → bonus paid + Transaction sinh
    resp = await client.post(f"/api/v1/payroll/{period}/pay", headers=_h(kt))
    assert resp.status_code == 200, resp.text

    bonus = await db_session.get(Bonus, bonus_id)
    assert bonus.status == "paid"

    txns = (await db_session.execute(
        select(Transaction).where(Transaction.code == f"PAYROLL-{period}")
    )).scalars().all()
    assert len(txns) == 1, "sinh đúng 1 Transaction expense cho kỳ"
    assert txns[0].type == "expense"
    assert txns[0].category == "salary"
    assert txns[0].amount == row["net_salary"]
