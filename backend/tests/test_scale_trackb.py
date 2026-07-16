"""Spec 05 Track B — test khóa hành vi các refactor N+1.

Nguyên tắc (spec 05 §11.2): kết quả AGGREGATE phải giống hệt bản loop per-user cũ.
`month_summary` (per-user, giữ nguyên) là chuẩn đối chiếu cho `team_month_summary`.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.auth import hash_password
from app.models.attendance import AttendanceRecord
from app.models.user import User, Team
from app.services.attendance_service import month_summary, team_month_summary

from tests.conftest import auth_header

PERIOD = "2026-06"


def _uid() -> str:
    return str(uuid.uuid4())


async def _make_user(db: AsyncSession, role: str = "data_entry", dept: str = "SALES",
                     team_id: str | None = None) -> User:
    uid = _uid()
    user = User(
        id=uid, full_name=f"TB {role} {uid[:6]}", email=f"tb-{uid[:8]}@test.com",
        password_hash=hash_password("test1234"), role=role, department=dept,
        team_id=team_id, is_active=True,
        telegram_user_id=20_000_000 + hash(uid) % 9_000_000,
    )
    db.add(user)
    await db.flush()
    return user


def _att(user_id: str, day: int, hours: float, ot: float = 0, ot_status: str = "none",
         review: bool = False) -> AttendanceRecord:
    d = date(2026, 6, day)
    return AttendanceRecord(
        id=_uid(), user_id=user_id, work_date=d,
        check_in=datetime(2026, 6, day, 1, 0, tzinfo=timezone.utc),
        check_out=datetime(2026, 6, day, 1 + int(hours), 0, tzinfo=timezone.utc),
        source="web", work_hours=hours, ot_hours=ot, ot_status=ot_status,
        needs_review=review,
    )


class TestTeamMonthSummaryEquivalence:
    """team_month_summary (1 aggregate) == month_summary (per-user) trên mọi cấu hình dữ liệu."""

    @pytest.mark.asyncio
    async def test_aggregate_matches_per_user_loop(self, db_session):
        # 3 user với hồ sơ công KHÁC NHAU có chủ đích:
        u_full = await _make_user(db_session)     # đủ công + OT approved
        u_partial = await _make_user(db_session)  # công lẻ (4h, 6h) + OT pending + needs_review
        u_empty = await _make_user(db_session)    # không có bản ghi nào trong kỳ

        for day in range(2, 12):  # 10 ngày đủ 8h
            db_session.add(_att(u_full.id, day, 8.0))
        db_session.add(_att(u_full.id, 12, 8.0, ot=2.0, ot_status="approved"))
        db_session.add(_att(u_full.id, 13, 8.0, ot=1.5, ot_status="approved"))

        db_session.add(_att(u_partial.id, 2, 4.0))
        db_session.add(_att(u_partial.id, 3, 6.0))
        db_session.add(_att(u_partial.id, 4, 8.0, ot=3.0, ot_status="pending"))  # pending KHÔNG tính
        db_session.add(_att(u_partial.id, 5, 8.0, review=True))
        db_session.add(_att(u_partial.id, 6, 0.0))  # record 0h (nghỉ không lương) — records đếm, work_days không

        # Nhiễu: bản ghi NGOÀI kỳ — không được lẫn vào
        db_session.add(AttendanceRecord(
            id=_uid(), user_id=u_partial.id, work_date=date(2026, 7, 1),
            source="web", work_hours=8.0,
        ))
        await db_session.commit()

        user_ids = [u_full.id, u_partial.id, u_empty.id]
        aggregate = await team_month_summary(db_session, user_ids, PERIOD)

        for uid in (u_full.id, u_partial.id):
            expected = await month_summary(db_session, uid, PERIOD)
            actual = aggregate[uid]
            assert actual == expected, (
                f"Aggregate lệch per-user cho {uid}:\n  aggregate={actual}\n  per-user ={expected}"
            )

        # User không có bản ghi → không có key (endpoint tự điền _empty_summary)
        assert u_empty.id not in aggregate

    @pytest.mark.asyncio
    async def test_empty_input(self, db_session):
        assert await team_month_summary(db_session, [], PERIOD) == {}


class TestTeamEndpointUsesAggregate:
    @pytest.mark.asyncio
    async def test_team_endpoint_shape_and_zero_fill(self, client, db_session):
        """Endpoint /attendance/team: user không có công vẫn xuất hiện với summary 0."""
        leader = await _make_user(db_session, role="leader")
        team = Team(id=_uid(), name="Team TB", code=f"TB-{_uid()[:4]}", department="SALES", leader_id=leader.id)
        db_session.add(team)
        await db_session.flush()
        leader.team_id = team.id
        member = await _make_user(db_session, team_id=team.id)
        db_session.add(_att(member.id, 3, 8.0, ot=2.0, ot_status="approved"))
        await db_session.commit()

        resp = await client.get(f"/api/v1/attendance/team?period={PERIOD}", headers=auth_header(leader))
        assert resp.status_code == 200
        rows = {r["user_id"]: r for r in resp.json()["items"]}

        assert rows[member.id]["work_days_fraction"] == 1.0
        assert rows[member.id]["ot_approved_hours"] == 2.0
        # Leader chưa chấm công kỳ đó → vẫn có dòng, toàn 0
        assert rows[leader.id]["records"] == 0
        assert rows[leader.id]["total_hours"] == 0.0


class TestPendingOTScope:
    @pytest.mark.asyncio
    async def test_leader_sees_only_own_team_ot(self, client, db_session):
        leader_a = await _make_user(db_session, role="leader")
        team_a = Team(id=_uid(), name="Team A", code=f"TA-{_uid()[:4]}", department="SALES", leader_id=leader_a.id)
        db_session.add(team_a)
        await db_session.flush()
        leader_a.team_id = team_a.id
        member_a = await _make_user(db_session, team_id=team_a.id)
        member_b = await _make_user(db_session)  # team khác (không team)

        db_session.add(_att(member_a.id, 3, 8.0, ot=2.0, ot_status="pending"))
        db_session.add(_att(member_b.id, 3, 8.0, ot=3.0, ot_status="pending"))
        await db_session.commit()

        resp = await client.get("/api/v1/attendance/ot/pending", headers=auth_header(leader_a))
        assert resp.status_code == 200
        user_ids = {item["user_id"] for item in resp.json()["items"]}
        assert member_a.id in user_ids
        assert member_b.id not in user_ids  # khác team — leader A không thấy

        # full_name phải được join sẵn (không N+1)
        assert all(item.get("full_name") for item in resp.json()["items"])


class TestDelegationFilterInSQL:
    @pytest.mark.asyncio
    async def test_expired_delegation_excluded(self, client, db_session):
        """Ủy quyền HẾT HẠN không còn thấy đơn (lọc trong SQL, không lọc Python)."""
        from app.models.approval import ApprovalRequest

        requester = await _make_user(db_session)
        approver = await _make_user(db_session, role="leader")
        delegate_valid = await _make_user(db_session, role="leader")
        delegate_expired = await _make_user(db_session, role="leader")

        now = datetime.now(timezone.utc)
        approver.delegate_to = delegate_valid.id
        approver.delegate_until = now + timedelta(days=1)

        approver2 = await _make_user(db_session, role="leader")
        approver2.delegate_to = delegate_expired.id
        approver2.delegate_until = now - timedelta(days=1)  # đã hết hạn

        db_session.add(ApprovalRequest(
            id=_uid(), type="leave", ref_id=_uid(), title="Đơn test ủy quyền",
            requester_id=requester.id, current_approver_id=approver.id,
            step=1, total_steps=1, status="pending",
        ))
        db_session.add(ApprovalRequest(
            id=_uid(), type="leave", ref_id=_uid(), title="Đơn test ủy quyền hết hạn",
            requester_id=requester.id, current_approver_id=approver2.id,
            step=1, total_steps=1, status="pending",
        ))
        await db_session.commit()

        r_valid = await client.get("/api/v1/approvals/pending-for-me", headers=auth_header(delegate_valid))
        assert r_valid.status_code == 200
        assert r_valid.json()["count"] == 1
        assert r_valid.json()["items"][0]["delegated"] is True
        assert r_valid.json()["items"][0]["requester_name"]  # join sẵn

        r_expired = await client.get("/api/v1/approvals/pending-for-me", headers=auth_header(delegate_expired))
        assert r_expired.status_code == 200
        assert r_expired.json()["count"] == 0
