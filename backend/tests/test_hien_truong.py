"""Gói Hiện trường (27/10/2026): sự cố có hạn + giao PM, Việc của tôi, chọn đầu việc khi báo cáo, /duan ẩn tiền."""

import pytest
from sqlalchemy import select

from app.models.project import Task, TaskActivity
from tests.conftest import auth_header
from tests.test_telegram_workflow import _seed_telegram_project


@pytest.mark.asyncio
async def test_su_co_co_han_va_giao_pm(client, db_session, admin_user, sales_user):
    p = await _seed_telegram_project(db_session, admin_user)
    p.pm_id = sales_user.id
    await db_session.commit()
    r = await client.post("/api/v1/telegram/incident", headers=auth_header(admin_user), json={
        "project_code": p.code, "description": "Thấm trần", "severity": "critical", "reporter_tg_id": 900001})
    assert r.status_code == 201, r.text
    t = (await db_session.execute(select(Task).where(Task.id == r.json()["task_id"])
                                  .execution_options(populate_existing=True))).scalar_one()
    assert t.due_date is not None and "Sự cố" in t.title
    # PM thấy việc này trong «Việc của tôi»
    ds = (await client.get("/api/v1/projects/tasks/mine", headers=auth_header(sales_user))).json()
    assert any(x["id"] == t.id and x["han"] for x in ds)


@pytest.mark.asyncio
async def test_bao_cao_gan_dung_dau_viec_chon(client, db_session, admin_user):
    p = await _seed_telegram_project(db_session, admin_user)
    viec = (await db_session.execute(select(Task).where(Task.project_id == p.id, Task.status == "done"))).scalar_one()
    r = await client.post("/api/v1/telegram/site-report", headers=auth_header(admin_user), json={
        "project_code": p.code, "content": "Xong 2D", "reporter_tg_id": 900001, "task_id": viec.id})
    assert r.status_code in (200, 201), r.text
    a = (await db_session.execute(select(TaskActivity).where(TaskActivity.task_id == viec.id))).scalars().all()
    assert a


@pytest.mark.asyncio
async def test_duan_an_tien_voi_nguoi_ngoai(client, db_session, admin_user, designer_user):
    p = await _seed_telegram_project(db_session, admin_user)
    r = (await client.get(f"/api/v1/telegram/project/{p.code}", headers=auth_header(designer_user))).json()
    assert r["project"]["total_value"] is None and "open_tasks" in r
    r = (await client.get(f"/api/v1/telegram/project/{p.code}", headers=auth_header(admin_user))).json()
    assert r["project"]["total_value"] == 10_000_000_000


@pytest.mark.asyncio
async def test_portal_khach_dong_y_vat_tu(client, db_session, project):
    import uuid as _u
    from app.models.customer import Customer
    from app.models.vat_tu import DongPhieuVatTu
    cust = Customer(id=str(_u.uuid4()), name="K", phone="0900000099", type="individual",
                    portal_token=str(_u.uuid4()), portal_enabled=True)
    db_session.add(cust)
    await db_session.flush()
    project.customer_id = cust.id
    d = DongPhieuVatTu(id=str(_u.uuid4()), project_id=project.id, ma_tu_do="G60", so_luong=10,
                       gia_von=100, gia_ban=150, trang_thai="da_chot_gia")
    db_session.add(d)
    await db_session.commit()
    r = await client.get(f"/api/v1/portal/{cust.portal_token}/projects/{project.id}/vat-tu")
    assert r.status_code == 200
    row = r.json()[0]
    assert "gia_von" not in row and row["thanh_tien"] == 1500 and row["cho_khach_duyet"]
    r = await client.post(f"/api/v1/portal/{cust.portal_token}/vat-tu/{d.id}/dong-y", json={})
    assert r.status_code == 200 and r.json()["khach_dong_y_luc"] and not r.json()["cho_khach_duyet"]
    r = await client.post(f"/api/v1/portal/sai-token/vat-tu/{d.id}/dong-y", json={})
    assert r.status_code == 404
