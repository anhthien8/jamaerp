"""HR Phase 1 tests — chấm công, nghỉ phép, approval engine, payroll + PIT, offboarding."""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.auth import hash_password
from app.models.attendance import AttendanceRecord
from app.models.approval import ApprovalRequest
from app.models.audit import AuditLog
from app.models.leave import LeaveBalance, LeaveRequest
from app.models.payroll import Commission, Payroll, SalaryAdvance
from app.models.salary_grade import SalaryGrade
from app.models.user import User, Team
from app.services.attendance_service import period_of, vn_today
from app.services.payroll_engine import compute_pit

from tests.conftest import auth_header, _uid


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def team_with_leader(db_session: AsyncSession):
    """Team SALES có leader + 1 nhân viên sales."""
    leader = User(
        id=_uid(), full_name="Leader Test", email="leader@test.com",
        password_hash=hash_password("leader123"), role="leader",
        department="SALES", is_active=True, telegram_user_id=900010,
    )
    db_session.add(leader)
    await db_session.flush()

    team = Team(id=_uid(), name="Team Test", code="T-TEST", department="SALES", leader_id=leader.id)
    db_session.add(team)
    await db_session.flush()

    leader.team_id = team.id
    member = User(
        id=_uid(), full_name="Member Test", email="member@test.com",
        password_hash=hash_password("member123"), role="data_entry",
        department="SALES", team_id=team.id, is_active=True, telegram_user_id=900011,
    )
    db_session.add(member)
    await db_session.commit()
    return {"team": team, "leader": leader, "member": member}


@pytest_asyncio.fixture
async def grade_12m(db_session: AsyncSession) -> SalaryGrade:
    grade = SalaryGrade(
        id=_uid(), grade_name="Bậc test 20tr", base_salary=20_000_000,
        bhxh_rate=10.5, bhxh_company_rate=21.5, bhyt_rate=1.5, bhtn_rate=1.0,
        effective_date=date(2026, 1, 1),
    )
    db_session.add(grade)
    await db_session.commit()
    return grade


def _full_month_attendance(db_session: AsyncSession, user: User, period: str, days: int = 22):
    """Chèn `days` ngày công đủ 8h trong kỳ."""
    year, month = int(period[:4]), int(period[5:7])
    added = 0
    d = date(year, month, 1)
    while added < days and d.month == month:
        if d.weekday() != 6:
            db_session.add(AttendanceRecord(
                id=_uid(), user_id=user.id, work_date=d,
                check_in=datetime(d.year, d.month, d.day, 1, 0, tzinfo=timezone.utc),
                check_out=datetime(d.year, d.month, d.day, 9, 0, tzinfo=timezone.utc),
                source="web", work_hours=8.0,
            ))
            added += 1
        d += timedelta(days=1)
    return added


# ---------------------------------------------------------------------------
# 1. PIT — thuế lũy tiến từng phần
# ---------------------------------------------------------------------------

class TestPIT:
    def test_zero_and_negative(self):
        assert compute_pit(0) == 0
        assert compute_pit(-5_000_000) == 0

    def test_bracket_1(self):
        # 2tr thu nhập tính thuế → 5%
        assert compute_pit(2_000_000) == 100_000

    def test_bracket_boundary_5m(self):
        assert compute_pit(5_000_000) == 250_000

    def test_bracket_2(self):
        # 8tr: 5tr×5% + 3tr×10% = 250k + 300k
        assert compute_pit(8_000_000) == 550_000

    def test_bracket_4(self):
        # 20tr: 250k + 500k + 8tr×15%(1.2tr) + 2tr×20%(400k) = 2.35tr
        assert compute_pit(20_000_000) == 2_350_000

    def test_top_bracket(self):
        # 100tr: 250k+500k+1.2tr+2.8tr+5tr+8.4tr + 20tr×35%(7tr) = 25.15tr
        assert compute_pit(100_000_000) == 25_150_000


# ---------------------------------------------------------------------------
# 2. Chấm công
# ---------------------------------------------------------------------------

class TestAttendance:
    @pytest.mark.asyncio
    async def test_checkin_creates_one_record_per_day(self, client, db_session, sales_user):
        r1 = await client.post("/api/v1/attendance/checkin", json={}, headers=auth_header(sales_user))
        assert r1.status_code == 200
        assert r1.json()["created"] is True

        r2 = await client.post("/api/v1/attendance/checkin", json={}, headers=auth_header(sales_user))
        assert r2.status_code == 200
        assert r2.json()["created"] is False  # không tạo bản ghi thứ 2

        result = await db_session.execute(
            select(AttendanceRecord).where(AttendanceRecord.user_id == sales_user.id)
        )
        assert len(result.scalars().all()) == 1

    @pytest.mark.asyncio
    async def test_checkout_without_checkin_fails(self, client, sales_user):
        r = await client.post("/api/v1/attendance/checkout", headers=auth_header(sales_user))
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_checkout_computes_ot(self, client, db_session, sales_user):
        await client.post("/api/v1/attendance/checkin", json={}, headers=auth_header(sales_user))
        # Lùi check_in 10 tiếng để checkout sinh 2h OT
        result = await db_session.execute(
            select(AttendanceRecord).where(AttendanceRecord.user_id == sales_user.id)
        )
        record = result.scalar_one()
        record.check_in = datetime.now(timezone.utc) - timedelta(hours=10)
        await db_session.commit()

        r = await client.post("/api/v1/attendance/checkout", headers=auth_header(sales_user))
        assert r.status_code == 200
        data = r.json()["record"]
        assert data["work_hours"] == 8.0
        assert data["ot_hours"] == pytest.approx(2.0, abs=0.1)
        assert data["ot_status"] == "pending"

    @pytest.mark.asyncio
    async def test_ot_self_approve_forbidden(self, client, db_session, admin_user):
        record = AttendanceRecord(
            id=_uid(), user_id=admin_user.id, work_date=vn_today(),
            work_hours=8, ot_hours=2, ot_status="pending", source="web",
        )
        db_session.add(record)
        await db_session.commit()

        r = await client.post(f"/api/v1/attendance/{record.id}/ot-approve", headers=auth_header(admin_user))
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_auto_close_open_shifts(self, db_session, sales_user):
        from app.services.attendance_service import auto_close_open_shifts
        db_session.add(AttendanceRecord(
            id=_uid(), user_id=sales_user.id, work_date=vn_today(),
            check_in=datetime.now(timezone.utc) - timedelta(hours=12),
            source="web",
        ))
        await db_session.commit()

        closed = await auto_close_open_shifts(db_session)
        assert closed == 1
        result = await db_session.execute(
            select(AttendanceRecord).where(AttendanceRecord.user_id == sales_user.id)
        )
        record = result.scalar_one()
        assert record.check_out is not None
        assert record.work_hours == 8.0
        assert record.ot_hours == 0  # ca tự đóng không sinh OT
        assert record.needs_review is True


# ---------------------------------------------------------------------------
# 3. Nghỉ phép + approval engine
# ---------------------------------------------------------------------------

class TestLeave:
    @pytest.mark.asyncio
    async def test_leave_flow_leader_approves(self, client, db_session, team_with_leader):
        member = team_with_leader["member"]
        leader = team_with_leader["leader"]

        start = (vn_today() + timedelta(days=7))
        while start.weekday() == 6:
            start += timedelta(days=1)

        r = await client.post("/api/v1/leaves", json={
            "leave_type": "annual",
            "start_date": str(start),
            "end_date": str(start),
            "reason": "việc gia đình",
        }, headers=auth_header(member))
        assert r.status_code == 200, r.text
        approval_id = r.json()["approval_id"]

        # Leader duyệt
        r2 = await client.post(f"/api/v1/approvals/{approval_id}/approve", headers=auth_header(leader))
        assert r2.status_code == 200
        assert r2.json()["request"]["status"] == "approved"

        # Balance bị trừ + attendance ngày nghỉ được ghi (leave, 8h có lương)
        balance = (await db_session.execute(
            select(LeaveBalance).where(LeaveBalance.user_id == member.id)
        )).scalar_one()
        assert balance.annual_used == 1.0

        att = (await db_session.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.user_id == member.id,
                AttendanceRecord.work_date == start,
            )
        )).scalar_one()
        assert att.source == "leave"
        assert att.work_hours == 8.0

    @pytest.mark.asyncio
    async def test_leave_over_3_days_needs_two_steps(self, client, db_session, team_with_leader, admin_user):
        member = team_with_leader["member"]
        leader = team_with_leader["leader"]

        start = vn_today() + timedelta(days=14)
        while start.weekday() != 0:  # thứ Hai
            start += timedelta(days=1)
        end = start + timedelta(days=4)  # T2-T6 = 5 ngày

        r = await client.post("/api/v1/leaves", json={
            "leave_type": "annual",
            "start_date": str(start),
            "end_date": str(end),
            "reason": "nghỉ dài ngày",
        }, headers=auth_header(member))
        assert r.status_code == 200, r.text
        approval_id = r.json()["approval_id"]

        # Cấp 1: leader — chưa chốt
        r2 = await client.post(f"/api/v1/approvals/{approval_id}/approve", headers=auth_header(leader))
        assert r2.json()["request"]["status"] == "pending"
        assert r2.json()["request"]["step"] == 2

        # Balance CHƯA bị trừ
        balance = (await db_session.execute(
            select(LeaveBalance).where(LeaveBalance.user_id == member.id)
        )).scalar_one_or_none()
        assert balance is None or balance.annual_used == 0

        # Cấp 2: admin — chốt
        r3 = await client.post(f"/api/v1/approvals/{approval_id}/approve", headers=auth_header(admin_user))
        assert r3.json()["request"]["status"] == "approved"

        balance = (await db_session.execute(
            select(LeaveBalance).where(LeaveBalance.user_id == member.id)
        )).scalar_one()
        assert balance.annual_used == 5.0

    @pytest.mark.asyncio
    async def test_leave_insufficient_balance(self, client, db_session, team_with_leader):
        member = team_with_leader["member"]
        # Đốt gần hết phép
        db_session.add(LeaveBalance(
            id=_uid(), user_id=member.id, year=vn_today().year,
            annual_total=12, annual_used=11.5,
        ))
        await db_session.commit()

        start = vn_today() + timedelta(days=7)
        while start.weekday() >= 5:
            start += timedelta(days=1)
        r = await client.post("/api/v1/leaves", json={
            "leave_type": "annual",
            "start_date": str(start),
            "end_date": str(start + timedelta(days=1)),
            "reason": "quá số dư",
        }, headers=auth_header(member))
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_requester_cannot_self_approve(self, client, team_with_leader, admin_user):
        leader = team_with_leader["leader"]
        start = vn_today() + timedelta(days=7)
        while start.weekday() == 6:
            start += timedelta(days=1)

        # Leader tự xin nghỉ → chuỗi duyệt phải là admin (không phải chính leader)
        r = await client.post("/api/v1/leaves", json={
            "leave_type": "annual",
            "start_date": str(start),
            "end_date": str(start),
            "reason": "leader xin nghỉ",
        }, headers=auth_header(leader))
        assert r.status_code == 200, r.text
        approval_id = r.json()["approval_id"]

        r2 = await client.post(f"/api/v1/approvals/{approval_id}/approve", headers=auth_header(leader))
        assert r2.status_code == 403  # không tự duyệt đơn mình

    @pytest.mark.asyncio
    async def test_double_approve_conflict(self, client, db_session, team_with_leader):
        member = team_with_leader["member"]
        leader = team_with_leader["leader"]
        start = vn_today() + timedelta(days=7)
        while start.weekday() == 6:
            start += timedelta(days=1)

        r = await client.post("/api/v1/leaves", json={
            "leave_type": "annual", "start_date": str(start), "end_date": str(start),
            "reason": "test double approve",
        }, headers=auth_header(member))
        approval_id = r.json()["approval_id"]

        r1 = await client.post(f"/api/v1/approvals/{approval_id}/approve", headers=auth_header(leader))
        assert r1.status_code == 200
        r2 = await client.post(f"/api/v1/approvals/{approval_id}/approve", headers=auth_header(leader))
        assert r2.status_code == 409  # idempotent — đơn đã xử lý

    @pytest.mark.asyncio
    async def test_approval_actions_are_audited(self, client, db_session, team_with_leader):
        member = team_with_leader["member"]
        leader = team_with_leader["leader"]
        start = vn_today() + timedelta(days=7)
        while start.weekday() == 6:
            start += timedelta(days=1)

        r = await client.post("/api/v1/leaves", json={
            "leave_type": "annual", "start_date": str(start), "end_date": str(start),
            "reason": "audit test",
        }, headers=auth_header(member))
        approval_id = r.json()["approval_id"]
        await client.post(f"/api/v1/approvals/{approval_id}/approve", headers=auth_header(leader))

        logs = (await db_session.execute(
            select(AuditLog).where(AuditLog.entity_id == approval_id)
        )).scalars().all()
        actions = {l.action for l in logs}
        assert "approval.create" in actions
        assert "approval.approve" in actions


# ---------------------------------------------------------------------------
# 4. Payroll + PIT + khóa kỳ
# ---------------------------------------------------------------------------

class TestPayroll:
    PERIOD = "2026-06"  # kỳ quá khứ, không đụng kỳ hiện tại

    async def _setup_member(self, db_session, member: User, grade: SalaryGrade):
        member.salary_grade_id = grade.id
        member.dependents_count = 1
        _full_month_attendance(db_session, member, self.PERIOD, days=22)
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_generate_formula_hand_checked(self, client, db_session, team_with_leader, grade_12m, accountant_user):
        """Case đối chiếu tay: lương 20tr, đủ 22 công, 1 người phụ thuộc.

        BHXH = 20tr × 13% = 2.6tr
        Taxable = 20tr − 2.6tr − 11tr − 4.4tr = 2tr → PIT = 100k
        Net = 20tr − 2.6tr − 100k = 17.3tr
        """
        member = team_with_leader["member"]
        await self._setup_member(db_session, member, grade_12m)

        r = await client.post(f"/api/v1/payroll/generate?period={self.PERIOD}", headers=auth_header(accountant_user))
        assert r.status_code == 200, r.text

        r2 = await client.get(f"/api/v1/payroll?period={self.PERIOD}", headers=auth_header(accountant_user))
        rows = {row["user_id"]: row for row in r2.json()["items"]}
        row = rows[member.id]

        assert row["work_days"] == 22.0
        assert row["gross_salary"] == 20_000_000
        assert row["bhxh_employee"] == 2_600_000
        assert row["taxable_income"] == 2_000_000
        assert row["pit"] == 100_000
        assert row["net_salary"] == 17_300_000

    @pytest.mark.asyncio
    async def test_commission_included(self, client, db_session, team_with_leader, grade_12m, accountant_user):
        member = team_with_leader["member"]
        await self._setup_member(db_session, member, grade_12m)
        db_session.add(Commission(
            id=_uid(), user_id=member.id, type="design_commission",
            rate=0.03, base_amount=100_000_000, commission_amount=3_000_000,
            milestone="signing", milestone_pct=0.5, status="approved", period=self.PERIOD,
        ))
        await db_session.commit()

        await client.post(f"/api/v1/payroll/generate?period={self.PERIOD}", headers=auth_header(accountant_user))
        r = await client.get(f"/api/v1/payroll?period={self.PERIOD}", headers=auth_header(accountant_user))
        row = {x["user_id"]: x for x in r.json()["items"]}[member.id]
        assert row["commission_total"] == 3_000_000
        assert row["gross_salary"] == 23_000_000

    @pytest.mark.asyncio
    async def test_full_flow_lock_and_pay(self, client, db_session, team_with_leader, grade_12m, accountant_user, admin_user):
        member = team_with_leader["member"]
        await self._setup_member(db_session, member, grade_12m)

        # generate → submit
        await client.post(f"/api/v1/payroll/generate?period={self.PERIOD}", headers=auth_header(accountant_user))
        r = await client.post(f"/api/v1/payroll/{self.PERIOD}/submit", headers=auth_header(accountant_user))
        assert r.status_code == 200, r.text
        approval_id = r.json()["approval_id"]

        # generate lại khi đã submit → 409
        r_regen = await client.post(f"/api/v1/payroll/generate?period={self.PERIOD}", headers=auth_header(accountant_user))
        assert r_regen.status_code == 409

        # admin duyệt → khóa kỳ
        r2 = await client.post(f"/api/v1/approvals/{approval_id}/approve", headers=auth_header(admin_user))
        assert r2.status_code == 200
        rows = (await db_session.execute(
            select(Payroll).where(Payroll.period == self.PERIOD)
        )).scalars().all()
        assert all(row.status == "approved" for row in rows)

        # Kỳ khóa: sửa chấm công của kỳ → 409
        att = (await db_session.execute(
            select(AttendanceRecord).where(AttendanceRecord.user_id == member.id).limit(1)
        )).scalars().first()
        r3 = await client.patch(f"/api/v1/attendance/{att.id}", json={
            "work_hours": 4, "note": "thử sửa kỳ khóa",
        }, headers=auth_header(accountant_user))
        assert r3.status_code == 409

        # Kỳ khóa: thêm hoa hồng lùi kỳ → 409
        r4 = await client.post("/api/v1/accounting/commissions", json={
            "user_id": member.id, "type": "design_commission", "rate": 0.03,
            "base_amount": 50_000_000, "milestone": "signing", "milestone_pct": 0.5,
            "status": "approved", "period": self.PERIOD,
        }, headers=auth_header(accountant_user))
        assert r4.status_code == 409

        # pay → paid + /payroll/me thấy phiếu của mình
        r5 = await client.post(f"/api/v1/payroll/{self.PERIOD}/pay", headers=auth_header(accountant_user))
        assert r5.status_code == 200

        r6 = await client.get("/api/v1/payroll/me", headers=auth_header(member))
        periods = [x["period"] for x in r6.json()["items"]]
        assert self.PERIOD in periods

        # Member khác không thấy phiếu người khác (chỉ của mình)
        r7 = await client.get("/api/v1/payroll/me", headers=auth_header(team_with_leader["leader"]))
        assert all(x["user_id"] in (None, team_with_leader["leader"].id) for x in r7.json()["items"])

    @pytest.mark.asyncio
    async def test_advance_deducted_in_payroll(self, client, db_session, team_with_leader, grade_12m, accountant_user, admin_user):
        member = team_with_leader["member"]
        await self._setup_member(db_session, member, grade_12m)

        # Tạo tạm ứng 2tr → kế toán duyệt
        r = await client.post("/api/v1/payroll/advance", json={
            "amount": 2_000_000, "reason": "việc gấp",
        }, headers=auth_header(member))
        assert r.status_code == 200, r.text
        approval_id = r.json()["approval_id"]
        r2 = await client.post(f"/api/v1/approvals/{approval_id}/approve", headers=auth_header(accountant_user))
        assert r2.status_code == 200

        await client.post(f"/api/v1/payroll/generate?period={self.PERIOD}", headers=auth_header(accountant_user))
        r3 = await client.get(f"/api/v1/payroll?period={self.PERIOD}", headers=auth_header(accountant_user))
        row = {x["user_id"]: x for x in r3.json()["items"]}[member.id]
        assert row["advance_deduction"] == 2_000_000
        assert row["net_salary"] == 17_300_000 - 2_000_000

    @pytest.mark.asyncio
    async def test_payroll_rbac(self, client, team_with_leader):
        member = team_with_leader["member"]
        r = await client.post(f"/api/v1/payroll/generate?period={self.PERIOD}", headers=auth_header(member))
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# 5. Offboarding bổ sung
# ---------------------------------------------------------------------------

class TestOffboarding:
    @pytest.mark.asyncio
    async def test_resign_clears_telegram_and_reports_commissions(self, client, db_session, team_with_leader, admin_user):
        member = team_with_leader["member"]
        assert member.telegram_user_id is not None

        db_session.add(Commission(
            id=_uid(), user_id=member.id, type="design_commission",
            rate=0.03, base_amount=200_000_000, commission_amount=6_000_000,
            milestone="signing", milestone_pct=0.5, status="pending", period=None,
        ))
        await db_session.commit()

        r = await client.post("/api/v1/hr/resign", json={"user_id": member.id}, headers=auth_header(admin_user))
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["telegram_unlinked"] is True
        assert data["pending_commissions"] == 1
        assert data["pending_commission_total"] == 6_000_000
        assert data["final_payroll_created"] is True

        await db_session.refresh(member)
        assert member.telegram_user_id is None
        assert member.is_active is False

        # Dòng lương pro-rata kỳ hiện tại được tạo draft
        row = (await db_session.execute(
            select(Payroll).where(Payroll.user_id == member.id)
        )).scalars().first()
        assert row is not None
        assert row.status == "draft"
        assert "Kỳ cuối" in (row.notes or "")

        # Audit có bản ghi resign
        logs = (await db_session.execute(
            select(AuditLog).where(AuditLog.action == "user.resign", AuditLog.entity_id == member.id)
        )).scalars().all()
        assert len(logs) == 1
