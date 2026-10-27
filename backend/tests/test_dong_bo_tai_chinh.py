"""Đồng bộ tiền HĐ ↔ dự án ↔ Tài chính ↔ P&L (27/10/2026)."""

import pytest
from sqlalchemy import select

from app.models.contract import Contract
from app.models.payroll import Transaction
from app.models.project import Project
from app.models.vat_tu import DongPhieuVatTu
from tests.conftest import auth_header, _uid


async def _hd(db, admin) -> Contract:
    p = Project(id=_uid(), code=f"JMH-{_uid()[:4]}", name="Nhà", client_name="K", status="active",
                total_value=1, spent=0, pm_id=admin.id)
    c = Contract(id=_uid(), code=f"HD-{_uid()[:6]}", project_id=p.id, title="HĐ thi công", status="draft",
                 total_value=1_000_000_000, contract_kind="thi_cong",
                 payment_terms={"installments": [
                     {"name": "Đợt 1", "percentage": 50, "milestone": "signing", "status": "pending"},
                     {"name": "Đợt 2", "percentage": 50, "milestone": "handover", "status": "pending"}]})
    db.add_all([p, c])
    await db.commit()
    return c


async def _gd(db, ma):
    return (await db.execute(select(Transaction).where(Transaction.code == ma)
                             .execution_options(populate_existing=True))).scalars().first()


@pytest.mark.asyncio
async def test_thu_sinh_giao_dich_va_bo_thu_huy(client, db_session, admin_user):
    c = await _hd(db_session, admin_user)
    r = await client.put(f"/api/v1/contracts/{c.id}/payments/0", json={"status": "paid", "paid_date": "2026-10-05"},
                         headers=auth_header(admin_user))
    assert r.status_code == 200, r.text
    gd = await _gd(db_session, f"THU-{c.code}-D1")
    assert gd and gd.type == "income" and float(gd.amount) == 500_000_000 and gd.status == "completed"
    r = await client.put(f"/api/v1/contracts/{c.id}/payments/0", json={"status": "pending"},
                         headers=auth_header(admin_user))
    assert r.status_code == 200
    assert (await _gd(db_session, f"THU-{c.code}-D1")).status == "cancelled"


@pytest.mark.asyncio
async def test_thu_mot_phan_can_so_tien(client, db_session, admin_user):
    c = await _hd(db_session, admin_user)
    r = await client.put(f"/api/v1/contracts/{c.id}/payments/1", json={"status": "partial"},
                         headers=auth_header(admin_user))
    assert r.status_code == 400
    r = await client.put(f"/api/v1/contracts/{c.id}/payments/1", json={"status": "partial", "amount": 100_000_000},
                         headers=auth_header(admin_user))
    assert r.status_code == 200 and r.json()["payment_terms"]["installments"][1]["status"] == "partial"
    assert float((await _gd(db_session, f"THU-{c.code}-D2")).amount) == 100_000_000


@pytest.mark.asyncio
async def test_sua_lich_thu(client, db_session, admin_user):
    c = await _hd(db_session, admin_user)
    await client.put(f"/api/v1/contracts/{c.id}/payments/0", json={"status": "paid"}, headers=auth_header(admin_user))
    url = f"/api/v1/contracts/{c.id}/lich-thu"
    r = await client.put(url, json={"dot": [{"name": "Cọc", "percentage": 50}, {"name": "B", "percentage": 40}]},
                         headers=auth_header(admin_user))
    assert r.status_code == 400  # tổng 90%
    r = await client.put(url, json={"dot": [{"name": "Cọc", "percentage": 100}]}, headers=auth_header(admin_user))
    assert r.status_code == 200  # bỏ đợt 2 chưa thu được
    r = await client.put(url, json={"dot": [
        {"name": "Cọc", "percentage": 50}, {"name": "Thô", "percentage": 30, "due_date": "2026-12-01"},
        {"name": "Bàn giao", "percentage": 20}]}, headers=auth_header(admin_user))
    ds = r.json()["payment_terms"]["installments"]
    assert r.status_code == 200 and len(ds) == 3 and ds[0]["status"] == "paid"
    assert ds[1]["due_date"].startswith("2026-12-01")


@pytest.mark.asyncio
async def test_gia_tri_hd_ve_du_an_va_spent(client, db_session, admin_user):
    c = await _hd(db_session, admin_user)
    r = await client.put(f"/api/v1/contracts/{c.id}", json={"total_value": 1_200_000_000},
                         headers=auth_header(admin_user))
    assert r.status_code == 200, r.text
    p = (await db_session.execute(select(Project).where(Project.id == c.project_id)
                                  .execution_options(populate_existing=True))).scalar_one()
    assert float(p.total_value) == 1_200_000_000
    db_session.add(DongPhieuVatTu(id=_uid(), project_id=p.id, ma_tu_do="X", so_luong=10, gia_von=100_000,
                                  trang_thai="da_dat"))
    await db_session.commit()
    r = await client.post("/api/v1/accounting/transactions", json={
        "type": "expense", "category": "labor", "amount": 2_000_000, "description": "Nhân công",
        "project_id": p.id}, headers=auth_header(admin_user))
    assert r.status_code in (200, 201), r.text
    p = (await db_session.execute(select(Project).where(Project.id == c.project_id)
                                  .execution_options(populate_existing=True))).scalar_one()
    assert float(p.spent) == 3_000_000
