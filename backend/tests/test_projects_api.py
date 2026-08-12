"""Tests for Projects API — task status, progress recalculation, task CRUD."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, Task
from tests.conftest import auth_header, _uid


@pytest.mark.asyncio
class TestTaskStatusAndProgress:
    """Task status updates should recalculate project progress."""

    async def test_task_status_update_recalculates_progress(
        self, client: AsyncClient, admin_user, project: Project, db_session: AsyncSession
    ):
        """Fixture: 1 done, 1 in_progress, 1 not_started (progress=30).
        Update not_started -> done => 2/3 done = 67%."""
        headers = auth_header(admin_user)

        # Get the not_started task (order=3: "Hoan thanh")
        task_q = await db_session.execute(
            select(Task).where(
                Task.project_id == project.id,
                Task.status == "not_started",
            )
        )
        task = task_q.scalar_one()
        assert task.title == "Hoan thanh"

        # Update to done
        resp = await client.put(
            f"/api/v1/projects/tasks/{task.id}/status",
            json={"status": "done"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "done"

        # Refresh project from DB
        await db_session.refresh(project)
        # 2 done out of 3 tasks = 66%
        assert project.progress == 66, f"Expected progress ~67%, got {project.progress}%"

    async def test_task_ordering_preserved_after_status(
        self, client: AsyncClient, admin_user, project: Project, db_session: AsyncSession
    ):
        """Updating task status should not change task.order."""
        headers = auth_header(admin_user)

        # Get the in_progress task (order=2: "Thiet ke 3D")
        task_q = await db_session.execute(
            select(Task).where(
                Task.project_id == project.id,
                Task.status == "in_progress",
            )
        )
        task = task_q.scalar_one()
        original_order = task.order
        assert original_order == 2

        # Update status
        resp = await client.put(
            f"/api/v1/projects/tasks/{task.id}/status",
            json={"status": "done"},
            headers=headers,
        )
        assert resp.status_code == 200

        # Refresh task and verify order unchanged
        await db_session.refresh(task)
        assert task.order == original_order, "Task order should be preserved after status update"

    async def test_create_task(
        self, client: AsyncClient, admin_user, project: Project, db_session: AsyncSession
    ):
        """POST /projects/{id}/tasks creates a task with correct fields."""
        headers = auth_header(admin_user)

        resp = await client.post(
            f"/api/v1/projects/{project.id}/tasks",
            json={
                "title": "Lap bang tien do",
                "description": "Tien do tong chia theo hang muc",
                "stage": "construction",
                "order": 4,
                "status": "not_started",
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Lap bang tien do"
        assert data["stage"] == "construction"
        assert data["order"] == 4
        assert data["status"] == "not_started"
        assert data["project_id"] == project.id

        # Verify persisted in DB
        task_q = await db_session.execute(
            select(Task).where(Task.id == data["id"])
        )
        task = task_q.scalar_one()
        assert task.title == "Lap bang tien do"
        assert task.project_id == project.id


@pytest.mark.asyncio
class TestTaskAssign:
    """PUT /projects/{pid}/tasks/{tid}/assign — chống lỗi 'báo thành công giả'.

    Trước 12/08/2026 endpoint dùng TaskStatusUpdate (chỉ có `status`) nên Pydantic
    lặng lẽ bỏ `assigned_to`; API trả 200, giao diện hiện "Đã giao việc cho X",
    còn task thì vẫn chưa có người làm.
    """

    async def test_assign_task_persists_assignee_and_notifies(
        self, client: AsyncClient, admin_user, sales_user, project: Project, db_session: AsyncSession
    ):
        from app.models.notification import Notification

        task_q = await db_session.execute(
            select(Task).where(Task.project_id == project.id).limit(1)
        )
        task = task_q.scalars().first()

        resp = await client.put(
            f"/api/v1/projects/{project.id}/tasks/{task.id}/assign",
            json={"status": "not_started", "assigned_to": sales_user.id},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["assigned_to"] == sales_user.id

        await db_session.refresh(task)
        assert task.assigned_to == sales_user.id

        notif_q = await db_session.execute(
            select(Notification).where(Notification.user_id == sales_user.id)
        )
        assert notif_q.scalars().first() is not None

    async def test_assign_task_rejects_missing_assignee_field(
        self, client: AsyncClient, admin_user, project: Project, db_session: AsyncSession
    ):
        """Thiếu assigned_to phải 422 chứ không được im lặng trả 200."""
        task_q = await db_session.execute(
            select(Task).where(Task.project_id == project.id).limit(1)
        )
        task = task_q.scalars().first()

        resp = await client.put(
            f"/api/v1/projects/{project.id}/tasks/{task.id}/assign",
            json={"status": "not_started"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 422

    async def test_assign_task_rejects_unknown_user(
        self, client: AsyncClient, admin_user, project: Project, db_session: AsyncSession
    ):
        """ID nhân sự không tồn tại phải 404 chứ không gán bừa."""
        task_q = await db_session.execute(
            select(Task).where(Task.project_id == project.id).limit(1)
        )
        task = task_q.scalars().first()

        resp = await client.put(
            f"/api/v1/projects/{project.id}/tasks/{task.id}/assign",
            json={"assigned_to": _uid()},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404

        await db_session.refresh(task)
        assert task.assigned_to != "nguoi-khong-ton-tai"
