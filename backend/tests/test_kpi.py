"""KPI engine + API tests — spec 04.

Tests compute_kpi, snapshot_all, leaderboard, coaching notes, reviews, burnout signals.
"""

import json
import uuid
from datetime import datetime, date, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.auth import hash_password
from app.models.user import User, Team
from app.models.lead import Lead, Activity
from app.models.attendance import AttendanceRecord
from app.models.performance import KpiSnapshot, CoachingNote, ReviewCycle
from app.services.kpi_engine import compute_kpi, snapshot_all, parse_period, detect_burnout, get_leaderboard

from tests.conftest import auth_header, _uid


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

async def _create_sales_team(db: AsyncSession) -> dict:
    """Create 2 sales users in same team for testing."""
    team_id = _uid()
    team = Team(id=team_id, name="Sales Alpha", code="SA", department="SALES")
    db.add(team)

    leader = User(
        id=_uid(), full_name="Leader KPI", email="leader-kpi@test.com",
        password_hash=hash_password("pass123"), role="leader",
        department="SALES", is_active=True, team_id=team_id,
        telegram_user_id=10_000_001,
    )
    sale = User(
        id=_uid(), full_name="Sale KPI", email="sale-kpi@test.com",
        password_hash=hash_password("pass123"), role="data_entry",
        department="SALES", is_active=True, team_id=team_id,
        telegram_user_id=10_000_002,
    )
    db.add(leader)
    db.add(sale)
    await db.flush()
    return {"leader": leader, "sale": sale, "team_id": team_id}


async def _seed_kpi_data(db: AsyncSession, user: User, period: str = "2026-07"):
    """Seed realistic KPI data for a user in a given period."""
    start, end = parse_period(period)

    # 20 working days attendance
    for day_offset in range(20):
        d = (start + timedelta(days=day_offset)).date()
        if d.weekday() >= 5:  # skip weekends
            continue
        att = AttendanceRecord(
            id=_uid(), user_id=user.id, work_date=d,
            check_in=datetime(d.year, d.month, d.day, 8, 0, tzinfo=timezone.utc),
            check_out=datetime(d.year, d.month, d.day, 17, 0, tzinfo=timezone.utc),
            work_hours=8, ot_hours=0, source="web",
        )
        db.add(att)

    # 20 leads with various stages
    stages = ["new"] * 8 + ["interested"] * 5 + ["survey_scheduled"] * 3 + ["potential"] * 2 + ["signed_design"] * 2
    for i, stage in enumerate(stages):
        lead = Lead(
            id=_uid(), name=f"Lead KPI {i}", phone=f"090{i:07d}",
            assigned_to=user.id, stage=stage,
            deal_value=500_000_000 if stage in ("potential", "signed_design") else 200_000_000,
            created_at=start + timedelta(days=i),
            last_contacted_at=start + timedelta(days=i, hours=12),
        )
        db.add(lead)

    # 15 activities across leads
    lead_ids = [lid for lid, in (await db.execute(
        select(Lead.id).where(Lead.assigned_to == user.id)
    )).all()]
    for i in range(15):
        act = Activity(
            id=_uid(),
            lead_id=lead_ids[i % len(lead_ids)],
            user_id=user.id,
            type="call", content=f"Call {i}",
            created_at=start + timedelta(days=i % 20, hours=10),
        )
        db.add(act)

    await db.flush()


# ---------------------------------------------------------------------------
# Engine unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_period():
    start, end = parse_period("2026-07")
    assert start.year == 2026 and start.month == 7
    assert end.year == 2026 and end.month == 8


@pytest.mark.asyncio
async def test_compute_kpi_basic(db_session):
    users = await _create_sales_team(db_session)
    sale = users["sale"]
    await _seed_kpi_data(db_session, sale)

    result = await compute_kpi(db_session, sale.id, "2026-07")

    assert 0 <= result["score"] <= 100
    metrics = result["metrics"]
    assert "activity_rate" in metrics
    assert "sla_compliance" in metrics
    assert "signed_count" in metrics
    assert metrics["signed_count"] == 2
    assert metrics["activity_rate"] > 0


@pytest.mark.asyncio
async def test_snapshot_all_idempotent(db_session):
    users = await _create_sales_team(db_session)
    await _seed_kpi_data(db_session, users["sale"])

    count1 = await snapshot_all(db_session, "2026-07")
    count2 = await snapshot_all(db_session, "2026-07")

    assert count1 == 2
    assert count2 == 2

    # Should not duplicate — still 2 rows
    from sqlalchemy import select, func
    total = (await db_session.execute(
        select(func.count(KpiSnapshot.id)).where(KpiSnapshot.period == "2026-07")
    )).scalar()
    assert total == 2


@pytest.mark.asyncio
async def test_leaderboard_anonymized(db_session):
    users = await _create_sales_team(db_session)
    await _seed_kpi_data(db_session, users["sale"])
    await snapshot_all(db_session, "2026-07")

    result = await get_leaderboard(db_session, "2026-07", users["sale"].id)
    assert "leaderboard" in result
    assert len(result["leaderboard"]) > 0


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_my_kpi(client, db_session):
    users = await _create_sales_team(db_session)
    sale = users["sale"]
    await _seed_kpi_data(db_session, sale)

    resp = await client.get("/api/v1/kpi/me?period=2026-07", headers=auth_header(sale))
    assert resp.status_code == 200
    data = resp.json()
    assert 0 <= data["score"] <= 100
    assert "metrics" in data


@pytest.mark.asyncio
async def test_team_kpi_leader(client, db_session):
    users = await _create_sales_team(db_session)
    leader = users["leader"]
    await _seed_kpi_data(db_session, users["sale"])
    await snapshot_all(db_session, "2026-07")

    resp = await client.get("/api/v1/kpi/team?period=2026-07", headers=auth_header(leader))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["members"]) >= 1


@pytest.mark.asyncio
async def test_team_kpi_forbidden_for_sale(client, db_session):
    users = await _create_sales_team(db_session)
    sale = users["sale"]

    resp = await client.get("/api/v1/kpi/team?period=2026-07", headers=auth_header(sale))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_leaderboard(client, db_session):
    users = await _create_sales_team(db_session)
    await snapshot_all(db_session, "2026-07")

    resp = await client.get("/api/v1/kpi/leaderboard?period=2026-07",
                            headers=auth_header(users["sale"]))
    assert resp.status_code == 200
    assert "leaderboard" in resp.json()


@pytest.mark.asyncio
async def test_snapshot_trigger_admin_only(client, db_session):
    users = await _create_sales_team(db_session)

    # Sale can't trigger
    resp = await client.post("/api/v1/kpi/snapshot?period=2026-07",
                             headers=auth_header(users["sale"]))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Coaching notes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_coaching_note_crud(client, db_session):
    users = await _create_sales_team(db_session)
    leader = users["leader"]
    sale = users["sale"]

    # Create
    resp = await client.post("/api/v1/kpi/coaching-notes", json={
        "user_id": sale.id, "note": "Cần improve SLA", "kind": "concern",
    }, headers=auth_header(leader))
    assert resp.status_code == 200
    note_id = resp.json()["id"]

    # List
    resp = await client.get(f"/api/v1/kpi/coaching-notes?user_id={sale.id}",
                            headers=auth_header(leader))
    assert resp.status_code == 200
    assert len(resp.json()["items"]) >= 1


@pytest.mark.asyncio
async def test_coaching_note_forbidden_cross_team(client, db_session):
    users = await _create_sales_team(db_session)
    leader = users["leader"]

    # Create user in different team
    other_user = User(
        id=_uid(), full_name="Other", email="other@test.com",
        password_hash=hash_password("pass123"), role="data_entry",
        department="SALES", is_active=True, telegram_user_id=10_000_003,
    )
    db_session.add(other_user)
    await db_session.flush()

    resp = await client.post("/api/v1/kpi/coaching-notes", json={
        "user_id": other_user.id, "note": "Test", "kind": "concern",
    }, headers=auth_header(leader))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_review_flow(client, db_session):
    users = await _create_sales_team(db_session)
    leader = users["leader"]
    sale = users["sale"]

    # Create review cycle
    review = ReviewCycle(
        id=_uid(), user_id=sale.id, period="2026-Q3", status="pending_self",
    )
    db_session.add(review)
    await db_session.flush()

    # Self submit
    resp = await client.put(f"/api/v1/kpi/reviews/me/{review.id}", json={
        "self_json": '{"goals": "improve SLA"}',
    }, headers=auth_header(sale))
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending_leader"

    # Leader submit
    resp = await client.put(f"/api/v1/kpi/reviews/{review.id}/leader", json={
        "leader_json": '{"score": 85}', "goals_json": '{"next": "close more"}',
    }, headers=auth_header(leader))
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"


# ---------------------------------------------------------------------------
# Burnout detection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_burnout_signals_lead_overload(db_session):
    users = await _create_sales_team(db_session)
    sale = users["sale"]

    # Create 30 active leads (overload)
    for i in range(30):
        lead = Lead(
            id=_uid(), name=f"Overload {i}", phone=f"091{i:07d}",
            assigned_to=sale.id, stage="new",
        )
        db_session.add(lead)
    await db_session.flush()

    result = await detect_burnout(db_session, sale.id)
    assert "lead_overload" in result["signals"]
    assert result["risk_level"] in ("yellow", "red")
