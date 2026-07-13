"""Tests for HR resignation/transfer endpoints."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, Team
from app.models.lead import Lead, Activity
from app.models.project import Project, Task

from tests.conftest import auth_header, _uid


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def team(db_session: AsyncSession) -> Team:
    team = Team(
        id=_uid(),
        name="Sales A",
        code="SA",
        department="SALES",
    )
    db_session.add(team)
    await db_session.flush()
    return team


@pytest_asyncio.fixture
async def salesperson(db_session: AsyncSession, team: Team) -> User:
    user = User(
        id=_uid(),
        full_name="Nguyen Van A",
        email="nguyena@test.com",
        password_hash="hashed",
        role="data_entry",
        department="SALES",
        team_id=team.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def teammate(db_session: AsyncSession, team: Team) -> User:
    user = User(
        id=_uid(),
        full_name="Tran Van B",
        email="tranb@test.com",
        password_hash="hashed",
        role="data_entry",
        department="SALES",
        team_id=team.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def pm_user(db_session: AsyncSession) -> User:
    user = User(
        id=_uid(),
        full_name="PM User",
        email="pm@test.com",
        password_hash="hashed",
        role="pm",
        department="PM",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def project(db_session: AsyncSession, pm_user: User) -> Project:
    proj = Project(
        id=_uid(),
        code="HR-TEST",
        name="HR Test Project",
        client_name="Client X",
        stage="design",
        status="active",
        pm_id=pm_user.id,
    )
    db_session.add(proj)
    await db_session.flush()
    return proj


@pytest_asyncio.fixture
async def leads(
    db_session: AsyncSession, salesperson: User, teammate: User
) -> list[Lead]:
    """Create 3 leads assigned to salesperson."""
    leads = []
    for i in range(3):
        lead = Lead(
            id=_uid(),
            name=f"Lead {i+1}",
            phone=f"090000000{i}",
            stage="new",
            assigned_to=salesperson.id,
        )
        db_session.add(lead)
        leads.append(lead)
    await db_session.flush()
    return leads


@pytest_asyncio.fixture
async def tasks(
    db_session: AsyncSession, salesperson: User, project: Project
) -> list[Task]:
    """Create 2 tasks assigned to salesperson."""
    tasks = []
    for i in range(2):
        task = Task(
            id=_uid(),
            project_id=project.id,
            title=f"Task {i+1}",
            status="in_progress",
            stage="design",
            assigned_to=salesperson.id,
            order=i + 1,
        )
        db_session.add(task)
        tasks.append(task)
    await db_session.flush()
    return tasks


# ---------------------------------------------------------------------------
# Tests: POST /hr/resign-preview
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resign_preview(client, admin_user, salesperson, leads, tasks):
    resp = await client.post(
        "/api/v1/hr/resign-preview",
        json={"user_id": salesperson.id},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_name"] == "Nguyen Van A"
    assert data["lead_count"] == 3
    assert data["task_count"] == 2
    assert len(data["leads"]) == 3
    assert len(data["tasks"]) == 2
    # Verify lead structure
    lead = data["leads"][0]
    assert "id" in lead and "name" in lead and "phone" in lead and "stage" in lead
    # Verify task structure
    task = data["tasks"][0]
    assert "id" in task and "title" in task and "project_name" in task and "status" in task
    assert task["project_name"] == "HR Test Project"


@pytest.mark.asyncio
async def test_resign_preview_user_not_found(client, admin_user):
    resp = await client.post(
        "/api/v1/hr/resign-preview",
        json={"user_id": "nonexistent"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_resign_preview_no_permission(client, salesperson):
    resp = await client.post(
        "/api/v1/hr/resign-preview",
        json={"user_id": salesperson.id},
        headers=auth_header(salesperson),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Tests: POST /hr/resign
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resign_auto_assign_leads_to_teammate(
    client, admin_user, salesperson, teammate, leads, tasks, project, db_session
):
    """When no transfer_leads_to, leads go to least-loaded teammate."""
    resp = await client.post(
        "/api/v1/hr/resign",
        json={"user_id": salesperson.id},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["transferred_leads"] == 3
    # Tasks: no transfer_tasks_to, fallback to PM
    assert data["transferred_tasks"] == 2

    # Verify leads now assigned to teammate
    for lead in leads:
        await db_session.refresh(lead)
        assert lead.assigned_to == teammate.id

    # Verify activity was created
    act_result = await db_session.execute(
        select(Activity).where(Activity.lead_id == leads[0].id)
    )
    act = act_result.scalar_one()
    assert "nghỉ việc" in act.content
    assert salesperson.full_name in act.content

    # Verify user is deactivated
    await db_session.refresh(salesperson)
    assert salesperson.is_active is False
    assert salesperson.resign_date is not None
    assert salesperson.resigned_by == admin_user.id


@pytest.mark.asyncio
async def test_resign_explicit_transfer(
    client, admin_user, salesperson, teammate, leads, tasks, db_session
):
    """When transfer_leads_to and transfer_tasks_to are specified."""
    resp = await client.post(
        "/api/v1/hr/resign",
        json={
            "user_id": salesperson.id,
            "transfer_leads_to": teammate.id,
            "transfer_tasks_to": teammate.id,
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["transferred_leads"] == 3
    assert data["transferred_tasks"] == 2

    for lead in leads:
        await db_session.refresh(lead)
        assert lead.assigned_to == teammate.id
    for task in tasks:
        await db_session.refresh(task)
        assert task.assigned_to == teammate.id


@pytest.mark.asyncio
async def test_resign_fallback_tasks_to_pm(
    client, admin_user, salesperson, pm_user, leads, tasks, project, db_session
):
    """When no transfer_tasks_to, tasks go to project PM."""
    resp = await client.post(
        "/api/v1/hr/resign",
        json={"user_id": salesperson.id},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    for task in tasks:
        await db_session.refresh(task)
        assert task.assigned_to == pm_user.id


@pytest.mark.asyncio
async def test_resign_user_not_found(client, admin_user):
    resp = await client.post(
        "/api/v1/hr/resign",
        json={"user_id": "nonexistent"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_resign_already_inactive(client, admin_user, salesperson, db_session):
    salesperson.is_active = False
    await db_session.commit()

    resp = await client.post(
        "/api/v1/hr/resign",
        json={"user_id": salesperson.id},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_resign_no_permission(client, salesperson):
    resp = await client.post(
        "/api/v1/hr/resign",
        json={"user_id": salesperson.id},
        headers=auth_header(salesperson),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Tests: POST /hr/undo-resign
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_undo_resign_within_window(
    client, admin_user, salesperson, db_session
):
    """Undo should succeed within 7 days."""
    salesperson.is_active = False
    salesperson.resign_date = datetime.now(timezone.utc) - timedelta(days=3)
    salesperson.resigned_by = admin_user.id
    await db_session.commit()

    resp = await client.post(
        "/api/v1/hr/undo-resign",
        json={"user_id": salesperson.id},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "restored"

    await db_session.refresh(salesperson)
    assert salesperson.is_active is True
    assert salesperson.resign_date is None
    assert salesperson.resigned_by is None


@pytest.mark.asyncio
async def test_undo_resign_expired_window(
    client, admin_user, salesperson, db_session
):
    """Undo should fail after 7 days."""
    salesperson.is_active = False
    salesperson.resign_date = datetime.now(timezone.utc) - timedelta(days=8)
    salesperson.resigned_by = admin_user.id
    await db_session.commit()

    resp = await client.post(
        "/api/v1/hr/undo-resign",
        json={"user_id": salesperson.id},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 400
    assert "7 ngày" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_undo_resign_not_resigned(client, admin_user, salesperson):
    resp = await client.post(
        "/api/v1/hr/undo-resign",
        json={"user_id": salesperson.id},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 400
    assert "chưa nghỉ việc" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_undo_resign_user_not_found(client, admin_user):
    resp = await client.post(
        "/api/v1/hr/undo-resign",
        json={"user_id": "nonexistent"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_undo_resign_no_permission(client, salesperson, db_session):
    """Active non-admin user should be blocked with 403."""
    # Note: we must test with an ACTIVE user of wrong role (not deactivated),
    # because get_current_user returns 401 for inactive users before RBAC runs.
    resp = await client.post(
        "/api/v1/hr/undo-resign",
        json={"user_id": salesperson.id},
        headers=auth_header(salesperson),
    )
    assert resp.status_code == 403


# Need this import for the activity check
from sqlalchemy import select
