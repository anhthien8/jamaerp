"""Gói Vận hành 27/10/2026: lead trùng SĐT, lead web báo người chia, khoá TK còn việc, nghỉ việc bàn giao PIC, KPI tự chụp."""

import pytest
from sqlalchemy import select

from app.models.lead import Lead
from app.models.notification import Notification
from app.models.project import Project
from app.services.so_dien_thoai import chuan_hoa_sdt
from app.services.zalo_analysis import _llm_enrich  # noqa: F401  (import được là đủ)
from tests.conftest import auth_header, _uid


def test_chuan_hoa_sdt():
    assert chuan_hoa_sdt("+84 912-345.678") == "0912345678"
    assert chuan_hoa_sdt("0912 345 678") == "0912345678"
    assert chuan_hoa_sdt(None) == ""


@pytest.mark.asyncio
async def test_lead_trung_sdt_409(client, admin_user):
    r = await client.post("/api/v1/leads", json={"name": "Chị Mai", "phone": "0912345678"}, headers=auth_header(admin_user))
    assert r.status_code in (200, 201), r.text
    r2 = await client.post("/api/v1/leads", json={"name": "Mai", "phone": "+84 912 345 678"}, headers=auth_header(admin_user))
    assert r2.status_code == 409
    assert r2.json()["detail"]["lead_id"] == r.json()["id"]


@pytest.mark.asyncio
async def test_lead_web_bao_nguoi_chia(client, db_session, admin_user):
    r = await client.post("/api/v1/instant-quote/public", json={
        "name": "Anh Web", "phone": "+84 987 000 111", "mode": "renovation", "area_sqm": 60})
    assert r.status_code == 200, r.text
    ld = (await db_session.execute(select(Lead).where(Lead.phone == "0987000111"))).scalars().first()
    assert ld is not None
    tb = (await db_session.execute(select(Notification).where(Notification.type == "lead_unassigned"))).scalars().all()
    assert tb


@pytest.mark.asyncio
async def test_khoa_tai_khoan_con_viec_409(client, db_session, admin_user, sales_user):
    db_session.add(Lead(id=_uid(), name="K", phone="0900000001", stage="new", assigned_to=sales_user.id))
    await db_session.commit()
    r = await client.put(f"/api/v1/users/{sales_user.id}", json={"is_active": False}, headers=auth_header(admin_user))
    assert r.status_code == 409, r.text


@pytest.mark.asyncio
async def test_nghi_viec_ban_giao_pic(client, db_session, admin_user, sales_user):
    p = Project(id=_uid(), code=f"JMH-{_uid()[:4]}", name="Nhà", client_name="K", status="active",
                total_value=1, spent=0, pm_id=admin_user.id, sales_id=sales_user.id)
    db_session.add(p)
    await db_session.commit()
    r = await client.post("/api/v1/hr/resign", json={"user_id": sales_user.id, "transfer_tasks_to": admin_user.id},
                          headers=auth_header(admin_user))
    assert r.status_code == 200, r.text
    p = (await db_session.execute(select(Project).where(Project.id == p.id)
                                  .execution_options(populate_existing=True))).scalar_one()
    assert p.sales_id == admin_user.id


@pytest.mark.asyncio
async def test_kpi_team_tu_chup(client, admin_user, sales_user):
    r = await client.get("/api/v1/kpi/team", headers=auth_header(admin_user))
    assert r.status_code == 200, r.text
