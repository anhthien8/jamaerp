"""Khách hàng: doanh thu + số HĐ, đọc ảnh CCCD, nhắc sinh nhật (25/10/2026)."""
import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.contract import Contract
from app.models.customer import Customer
from app.models.notification import Notification
from app.models.project import Project
from app.services import khach_hang
from tests.conftest import auth_header

pytestmark = pytest.mark.asyncio


async def _khach(db, **kw) -> Customer:
    c = Customer(id=str(uuid.uuid4()), name=kw.pop("name", "Chị Ngân"), phone="0934655611", **kw)
    db.add(c)
    await db.commit()
    return c


async def _du_an(db, cid, sales_id=None, status="active", total=None, tk=None, tc=None, code=None) -> Project:
    p = Project(id=str(uuid.uuid4()), code=code or f"P-{uuid.uuid4().hex[:6]}", name="Nhà phố", client_name="Khách", client_phone="0900000000",
                customer_id=cid, status=status, total_value=total, design_value=tk,
                construction_value=tc, sales_id=sales_id)
    db.add(p)
    await db.commit()
    return p


class TestDoanhThu:
    async def test_tong_gia_tri_du_an_va_so_hd(self, client: AsyncClient, db_session, admin_user):
        c = await _khach(db_session)
        p1 = await _du_an(db_session, c.id, total=300_000_000)
        await _du_an(db_session, c.id, tk=50_000_000, tc=150_000_000)
        await _du_an(db_session, c.id, total=999_000_000, status="cancelled")
        for i, st in enumerate(["draft", "signed", "cancelled"]):
            db_session.add(Contract(id=str(uuid.uuid4()), code=f"HD-T-{i}", project_id=p1.id,
                                    title="HĐ", status=st))
        await db_session.commit()

        r = await client.get("/api/v1/customers", headers=auth_header(admin_user))
        d = next(x for x in r.json()["items"] if x["id"] == c.id)
        assert d["doanh_thu"] == 500_000_000
        assert d["so_hop_dong"] == 2 and d["so_du_an"] == 2

        r = await client.get(f"/api/v1/customers/{c.id}", headers=auth_header(admin_user))
        assert r.json()["doanh_thu"] == 500_000_000

    async def test_luu_ngay_sinh_va_cccd(self, client: AsyncClient, admin_user):
        r = await client.post("/api/v1/customers", json={
            "name": "Phương", "phone": "0392217971", "birthday": "1990-11-02", "national_id": "079190001234",
        }, headers=auth_header(admin_user))
        assert r.status_code == 200, r.text
        assert r.json()["birthday"] == "1990-11-02" and r.json()["national_id"] == "079190001234"


class TestCccd:
    def test_chuan_hoa_ket_qua(self):
        d = khach_hang.chuan_hoa_cccd(
            '{"ho_ten":"NGUYỄN THỊ NGÂN","so_cccd":"079 190 001 234","ngay_sinh":"02/11/1990",'
            '"gioi_tinh":"Nữ","dia_chi":"Q4, TP HCM","la_cccd":true}'
        )
        assert d == {"name": "Nguyễn Thị Ngân", "national_id": "079190001234", "birthday": "1990-11-02",
                     "gender": "Nữ", "address": "Q4, TP HCM"}

    def test_khong_phai_cccd(self):
        with pytest.raises(khach_hang.CccdError):
            khach_hang.chuan_hoa_cccd({"la_cccd": False})
        with pytest.raises(khach_hang.CccdError):
            khach_hang.chuan_hoa_cccd({"ho_ten": None, "so_cccd": "12", "ngay_sinh": "abc"})

    async def test_endpoint(self, client: AsyncClient, admin_user, sales_user, monkeypatch):
        async def gia(anh, mime):
            return {"name": "A", "national_id": None, "birthday": None, "gender": None, "address": None}
        monkeypatch.setattr(khach_hang, "doc_cccd", gia)
        r = await client.post("/api/v1/customers/doc-cccd", json={"data_base64": "data:image/jpeg;base64,/9j/AA=="},
                              headers=auth_header(admin_user))
        assert r.status_code == 200 and r.json()["name"] == "A"
        r = await client.post("/api/v1/customers/doc-cccd", json={"data_base64": "@@"}, headers=auth_header(admin_user))
        assert r.status_code == 422


class TestSinhNhat:
    async def test_nhac_sale_truoc_3_ngay_va_dung_ngay_khong_trung(self, db_session, sales_user, admin_user):
        c = await _khach(db_session, birthday=date(1990, 11, 5))
        await _du_an(db_session, c.id, sales_id=sales_user.id)
        await _khach(db_session, name="Khác", birthday=date(1985, 1, 1))

        assert await khach_hang.nhac_sinh_nhat(db_session, date(2026, 11, 2)) == 1
        await db_session.commit()
        assert await khach_hang.nhac_sinh_nhat(db_session, date(2026, 11, 2)) == 0  # chạy lại không trùng
        assert await khach_hang.nhac_sinh_nhat(db_session, date(2026, 11, 5)) == 1
        await db_session.commit()
        tb = (await db_session.execute(
            select(Notification).where(Notification.type == "customer_birthday")
        )).scalars().all()
        assert {t.user_id for t in tb} == {sales_user.id}
        assert any("HÔM NAY" in t.title for t in tb)

    def test_so_ngay_toi_sinh_nhat(self):
        assert khach_hang.sinh_nhat_sap_toi(date(1990, 10, 25), date(2026, 10, 25)) == 0
        assert khach_hang.sinh_nhat_sap_toi(date(1990, 10, 24), date(2026, 10, 25)) == 364
        assert khach_hang.sinh_nhat_sap_toi(date(2000, 2, 29), date(2027, 2, 27)) == 1
