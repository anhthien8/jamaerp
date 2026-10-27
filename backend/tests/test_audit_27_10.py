"""Vá các lỗ quy trình từ audit 27/10/2026 (tiền HĐ, nhân sự, dự án). Dữ liệu giả."""

import pytest
from sqlalchemy import select

from app.models.contract import Contract
from app.models.payroll import Commission, Transaction
from app.models.project import Project, Task
from app.models.user import User
from tests.conftest import auth_header, _uid


def _hd(project_id: str, status: str = "signed") -> Contract:
    return Contract(
        id=_uid(), code=f"HD-{_uid()[:6]}", project_id=project_id, title="HĐ thi công giả",
        status=status, total_value=1_000_000_000, contract_kind="thi_cong",
        payment_terms={"installments": [
            {"name": "Đợt 1", "percentage": 50, "status": "pending"},
            {"name": "Đợt 2", "percentage": 50, "status": "pending"},
        ]},
    )


async def _du_an(db, **kw) -> Project:
    p = Project(id=_uid(), code=f"JMH-{_uid()[:4]}", name="Nhà giả", client_name="Khách giả",
                stage=kw.pop("stage", "construction"), status=kw.pop("status", "active"),
                total_value=1_000_000_000, spent=0, progress=0, **kw)
    db.add(p)
    await db.commit()
    return p


async def _put_thu(client, kt, c, idx, body):
    return await client.put(f"/api/v1/contracts/{c.id}/payments/{idx}", json=body, headers=auth_header(kt))


@pytest.mark.asyncio
class TestTienHopDong:
    async def test_thu_mot_phan_roi_thu_du_lay_lai_theo_phan_tram(self, client, db_session, accountant_user):
        p = await _du_an(db_session)
        c = _hd(p.id)
        db_session.add(c)
        await db_session.commit()
        r = await _put_thu(client, accountant_user, c, 0, {"status": "partial", "amount": 100_000_000})
        assert r.status_code == 200, r.text
        r = await _put_thu(client, accountant_user, c, 0, {"status": "paid"})
        assert r.status_code == 200, r.text
        inst = r.json()["payment_terms"]["installments"][0]
        assert inst["status"] == "paid" and "amount" not in inst

    async def test_hd_nhap_thu_tien_tu_ky(self, client, db_session, accountant_user):
        p = await _du_an(db_session)
        c = _hd(p.id, status="draft")
        db_session.add(c)
        await db_session.commit()
        r = await _put_thu(client, accountant_user, c, 0, {"status": "paid"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "signed"

    async def test_giao_dich_thu_tu_sinh_khong_sua_xoa_o_ke_toan(self, client, db_session, accountant_user):
        p = await _du_an(db_session)
        c = _hd(p.id)
        db_session.add(c)
        await db_session.commit()
        assert (await _put_thu(client, accountant_user, c, 0, {"status": "paid"})).status_code == 200
        gd = (await db_session.execute(select(Transaction).where(Transaction.code.like(f"THU-{c.code}-%")))).scalars().first()
        assert gd is not None
        h = auth_header(accountant_user)
        assert (await client.delete(f"/api/v1/accounting/transactions/{gd.id}", headers=h)).status_code == 400
        assert (await client.put(f"/api/v1/accounting/transactions/{gd.id}", json={"amount": 1}, headers=h)).status_code == 400

    async def test_huy_hd_go_hoa_hong_chua_duyet_va_khong_ky_lai(self, client, db_session, admin_user, accountant_user):
        p = await _du_an(db_session)
        c = _hd(p.id)
        db_session.add(c)
        db_session.add(Commission(user_id=admin_user.id, type="hh_sale", rate=0.01, base_amount=1,
                                  commission_amount=1, status="pending", contract_id=c.id))
        await db_session.commit()
        assert (await _put_thu(client, accountant_user, c, 0, {"status": "paid"})).status_code == 200
        h = auth_header(admin_user)
        r = await client.put(f"/api/v1/contracts/{c.id}", json={"status": "cancelled"}, headers=h)
        assert r.status_code == 200, r.text
        con = (await db_session.execute(select(Commission).where(
            Commission.contract_id == c.id, Commission.status.in_(("pending", "cho_moc"))
        ).execution_options(populate_existing=True))).scalars().all()
        assert con == []
        gd = (await db_session.execute(select(Transaction).where(Transaction.code.like(f"THU-{c.code}-%"))
                                       .execution_options(populate_existing=True))).scalars().all()
        assert gd and all(g.status == "cancelled" for g in gd)
        r = await client.put(f"/api/v1/contracts/{c.id}", json={"status": "signed"}, headers=h)
        assert r.status_code == 400
        assert (await _put_thu(client, accountant_user, c, 1, {"status": "paid"})).status_code == 400


@pytest.mark.asyncio
class TestNhanSu:
    async def test_ke_toan_khong_doi_mat_khau_admin(self, client, admin_user, accountant_user):
        r = await client.put(f"/api/v1/users/{admin_user.id}", json={"password": "MatKhauGia123!"},
                             headers=auth_header(accountant_user))
        assert r.status_code == 403

    async def test_ke_toan_khong_cho_admin_nghi(self, client, admin_user, accountant_user):
        r = await client.post("/api/v1/hr/resign", json={"user_id": admin_user.id}, headers=auth_header(accountant_user))
        assert r.status_code in (400, 403)

    async def test_admin_cuoi_khong_tu_nghi(self, client, admin_user):
        r = await client.post("/api/v1/hr/resign", json={"user_id": admin_user.id}, headers=auth_header(admin_user))
        assert r.status_code == 400


@pytest.mark.asyncio
class TestDuAn:
    async def test_hoan_thanh_con_viec_mo_phai_xac_nhan(self, client, db_session, admin_user):
        p = await _du_an(db_session)
        db_session.add(Task(id=_uid(), project_id=p.id, title="Ốp lát WC", stage="construction", status="in_progress"))
        await db_session.commit()
        h = auth_header(admin_user)
        r = await client.put(f"/api/v1/projects/{p.id}/stage", json={"stage": "completed"}, headers=h)
        assert r.status_code == 409 and r.json()["detail"]["code"] == "con_viec_mo"
        r = await client.put(f"/api/v1/projects/{p.id}/stage", json={"stage": "completed", "force": True}, headers=h)
        assert r.status_code == 200 and r.json()["status"] == "completed"
        r = await client.put(f"/api/v1/projects/{p.id}/stage", json={"stage": "construction"}, headers=h)
        assert r.status_code == 200 and r.json()["status"] == "active"
