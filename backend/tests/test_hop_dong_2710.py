"""Gói Hợp đồng 27/10/2026: tạm dừng giữ giai đoạn, hoàn thành → nghiệm thu HĐ, phụ lục."""

import pytest
from sqlalchemy import select

from app.models.contract import Contract
from app.models.project import Project
from tests.conftest import auth_header, _uid


async def _du_an(db, admin, stage="construction") -> Project:
    p = Project(id=_uid(), code=f"JMH-{_uid()[:4]}", name="Nhà", client_name="K", status="active",
                stage=stage, total_value=1, spent=0, pm_id=admin.id)
    db.add(p)
    await db.commit()
    return p


async def _lai(db, model, id_):
    return (await db.execute(select(model).where(model.id == id_)
                             .execution_options(populate_existing=True))).scalar_one()


@pytest.mark.asyncio
async def test_tam_dung_giu_giai_doan(client, db_session, admin_user):
    p = await _du_an(db_session, admin_user)
    url = f"/api/v1/projects/{p.id}/stage"
    r = await client.put(url, json={"stage": "paused", "pause_reason": "Chờ phép"}, headers=auth_header(admin_user))
    assert r.status_code == 200, r.text
    p2 = await _lai(db_session, Project, p.id)
    assert p2.status == "paused" and p2.stage == "construction"
    k = (await client.get("/api/v1/projects/pipeline/kanban", headers=auth_header(admin_user))).json()
    cot = next(c["projects"] for c in k if c["stage"] == "paused")
    assert any(x["id"] == p.id for x in cot)
    await client.put(url, json={"stage": "construction"}, headers=auth_header(admin_user))
    assert (await _lai(db_session, Project, p.id)).status == "active"


@pytest.mark.asyncio
async def test_hoan_thanh_nghiem_thu_hd(client, db_session, admin_user):
    p = await _du_an(db_session, admin_user)
    c = Contract(id=_uid(), code=f"HD-{_uid()[:6]}", project_id=p.id, title="Thi công", status="signed",
                 total_value=500_000_000, contract_kind="thi_cong", payment_terms={"installments": []})
    db_session.add(c)
    await db_session.commit()
    r = await client.put(f"/api/v1/projects/{p.id}/stage", json={"stage": "completed"}, headers=auth_header(admin_user))
    assert r.status_code == 200, r.text
    p2 = await _lai(db_session, Project, p.id)
    assert p2.handover_date is not None and p2.warranty_end_date is not None
    assert (await _lai(db_session, Contract, c.id)).status == "completed"


@pytest.mark.asyncio
async def test_phu_luc_cong_gia_tri(client, db_session, admin_user):
    p = await _du_an(db_session, admin_user)
    c = Contract(id=_uid(), code=f"HD-{_uid()[:6]}", project_id=p.id, title="Thi công", status="signed",
                 total_value=1_000_000_000, contract_kind="thi_cong", payment_terms={"installments": []})
    db_session.add(c)
    await db_session.commit()
    r = await client.post(f"/api/v1/contracts/{c.id}/phu-luc", json={"title": "Phát sinh đá", "total_value": 50_000_000},
                          headers=auth_header(admin_user))
    assert r.status_code == 200, r.text
    pl = r.json()
    assert pl["parent_contract_id"] == c.id and pl["code"].endswith("-PL1")
    assert float((await _lai(db_session, Project, p.id)).total_value) == 1_050_000_000
    r = await client.post(f"/api/v1/contracts/{pl['id']}/phu-luc", json={"title": "Lồng nhau", "total_value": 1},
                          headers=auth_header(admin_user))
    assert r.status_code == 400
