"""Thẻ cảnh báo Tổng quan lấy SỐ THẬT (13/08/2026).

Trước đó FE hiển thị `?? 4` cho «Lead quá hạn» và 0 cứng cho «Việc quá hạn»
(audit demo/frontend-only 13/08). Backend nay trả:
- /dashboard/executive: overdue_tasks (toàn công ty)
- /dashboard/personal:  overdue_leads + overdue_tasks (phạm vi chính chủ)
Test này chốt hợp đồng field, khỏi tái diễn số bịa.
"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import cache
from app.models.lead import Lead
from app.models.project import Project, Task
from app.models.user import User
from tests.conftest import _uid, auth_header


def _now_naive() -> datetime:
    # Cột DateTime của model là naive — ghi naive cho khớp cả SQLite lẫn Postgres
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.mark.asyncio
class TestExecutiveOverdueTasks:
    async def test_dem_viec_qua_han_toan_cong_ty(
        self, client: AsyncClient, db_session: AsyncSession, admin_user: User, project: Project
    ):
        now = _now_naive()
        db_session.add_all([
            Task(id=_uid(), project_id=project.id, title="Quá hạn chưa xong",
                 status="in_progress", due_date=now - timedelta(days=2)),
            Task(id=_uid(), project_id=project.id, title="Quá hạn nhưng đã xong",
                 status="done", due_date=now - timedelta(days=2)),
            Task(id=_uid(), project_id=project.id, title="Còn hạn",
                 status="in_progress", due_date=now + timedelta(days=2)),
            Task(id=_uid(), project_id=project.id, title="Không đặt hạn",
                 status="in_progress", due_date=None),
        ])
        await db_session.commit()
        cache.clear_prefix("dashboard")  # cache in-memory sống xuyên test trong 1 process

        resp = await client.get("/api/v1/dashboard/executive", headers=auth_header(admin_user))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["overdue_tasks"] == 1, (
            "Chỉ task quá due_date VÀ chưa done mới được đếm — "
            f"nhận {body['overdue_tasks']}"
        )


@pytest.mark.asyncio
class TestPersonalOverdue:
    async def test_lead_va_viec_qua_han_pham_vi_chinh_chu(
        self, client: AsyncClient, db_session: AsyncSession,
        sales_user: User, admin_user: User, project: Project,
    ):
        now = _now_naive()
        # Lead: 5 ngày không liên hệ → quá hạn; vừa liên hệ → không; của người khác → không tính
        db_session.add_all([
            Lead(id=_uid(), name="Lead quá hạn", phone="0900000001", stage="potential",
                 assigned_to=sales_user.id, last_contacted_at=now - timedelta(days=5)),
            Lead(id=_uid(), name="Lead vừa liên hệ", phone="0900000002", stage="potential",
                 assigned_to=sales_user.id, last_contacted_at=now),
            Lead(id=_uid(), name="Lead người khác", phone="0900000003", stage="potential",
                 assigned_to=admin_user.id, last_contacted_at=now - timedelta(days=5)),
        ])
        # Task: giao đích danh sales + quá hạn chưa xong → tính; của người khác → không
        db_session.add_all([
            Task(id=_uid(), project_id=project.id, title="Việc của sales quá hạn",
                 status="in_progress", assigned_to=sales_user.id,
                 due_date=now - timedelta(days=1)),
            Task(id=_uid(), project_id=project.id, title="Việc người khác quá hạn",
                 status="in_progress", assigned_to=admin_user.id,
                 due_date=now - timedelta(days=1)),
        ])
        await db_session.commit()

        resp = await client.get("/api/v1/dashboard/personal", headers=auth_header(sales_user))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["overdue_leads"] == 1, f"phạm vi chính chủ — nhận {body['overdue_leads']}"
        assert body["overdue_tasks"] == 1, f"phạm vi chính chủ — nhận {body['overdue_tasks']}"

    async def test_khong_du_lieu_thi_tra_0_khong_phai_thieu_field(
        self, client: AsyncClient, sales_user: User
    ):
        resp = await client.get("/api/v1/dashboard/personal", headers=auth_header(sales_user))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # Field phải LUÔN có mặt — FE `?? 0` chỉ là lưới an toàn, không phải nguồn số
        assert body["overdue_leads"] == 0
        assert body["overdue_tasks"] == 0
