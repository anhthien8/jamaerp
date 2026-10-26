"""NCC tự tạo từ Vật tư + mã số thuế (26/10/2026)."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.auth import hash_password
from app.models.project import Project
from app.models.supplier import Supplier
from app.models.user import User
from app.models.vat_tu import BaoGiaDongVatTu, DongPhieuVatTu
from app.services import ncc as ncc_svc
from tests.conftest import _uid, auth_header


@pytest_asyncio.fixture
async def thu_mua(db_session: AsyncSession) -> User:
    u = User(id=_uid(), full_name="Thu Mua NCC", email="thumua.ncc@test.com", password_hash=hash_password("x"),
             role="data_entry", department="PURCHASING", is_active=True)
    db_session.add(u)
    await db_session.commit()
    return u


async def _so_ncc(db) -> int:
    return (await db.execute(select(func.count()).select_from(Supplier))).scalar()


def test_chuan_mst():
    assert ncc_svc.chuan_mst(" 0100109106 ") == "0100109106"
    assert ncc_svc.chuan_mst("0100109106-001") == "0100109106-001"
    assert ncc_svc.chuan_mst("12345") is None


@pytest.mark.asyncio
async def test_mau_go_ten_ncc_tu_tao_va_khong_trung(client: AsyncClient, db_session, thu_mua):
    db_session.add(Supplier(id=_uid(), name="Hiệp Phát"))
    await db_session.commit()
    truoc = await _so_ncc(db_session)
    r = await client.post("/api/v1/vat-tu/mau", json={"ma": "HP1", "ncc_gan_nhat_ten": "  hiệp   phát "},
                          headers=auth_header(thu_mua))
    assert r.status_code == 201 and r.json()["ncc_gan_nhat_ten"] == "Hiệp Phát"
    assert await _so_ncc(db_session) == truoc
    r = await client.post("/api/v1/vat-tu/mau", json={"ma": "DS1", "ncc_gan_nhat_ten": "Daisan"},
                          headers=auth_header(thu_mua))
    assert r.status_code == 201
    assert await _so_ncc(db_session) == truoc + 1
    ten = [x["name"] for x in (await client.get("/api/v1/vat-tu/ncc", headers=auth_header(thu_mua))).json()]
    assert "Daisan" in ten and "Hiệp Phát" in ten


@pytest.mark.asyncio
async def test_bao_gia_bot_tao_ncc_kem_mst(client: AsyncClient, db_session, thu_mua):
    p = Project(id=_uid(), code="JMH-NCC1", name="Nhà", client_name="K", status="active", total_value=1)
    db_session.add(p)
    await db_session.flush()
    d = DongPhieuVatTu(id=_uid(), project_id=p.id, ma_tu_do="X1", so_luong=1)
    db_session.add(d)
    await db_session.commit()
    r = await client.post("/api/v1/vat-tu/bot/ghi-bao-gia", json={
        "items": [{"dong_id": d.id, "ncc_ten": "Gạch Minh Long", "gia": 100000}],
        "ncc_mst": "0312345678", "ncc_dia_chi": "Q7, TP HCM"}, headers=auth_header(thu_mua))
    assert r.status_code == 201
    s = (await db_session.execute(select(Supplier).where(Supplier.name == "Gạch Minh Long"))).scalar_one()
    assert s.ma_so_thue == "0312345678" and s.address == "Q7, TP HCM"
    b = (await db_session.execute(select(BaoGiaDongVatTu).where(BaoGiaDongVatTu.dong_id == d.id))).scalar_one()
    assert b.supplier_id == s.id
    # «NCC chưa rõ» không tạo NCC rác
    truoc = await _so_ncc(db_session)
    await client.post("/api/v1/vat-tu/bot/ghi-bao-gia", json={
        "items": [{"dong_id": d.id, "ncc_ten": "NCC chưa rõ", "gia": 1}]}, headers=auth_header(thu_mua))
    assert await _so_ncc(db_session) == truoc


@pytest.mark.asyncio
async def test_tra_mst(client: AsyncClient, admin_user, monkeypatch):
    async def gia(mst):
        return {"ma_so_thue": mst, "ten_cong_ty": "CÔNG TY A", "dia_chi": "HN"}
    monkeypatch.setattr(ncc_svc, "tra_mst", gia)
    r = await client.get("/api/v1/suppliers/tra-mst/abc", headers=auth_header(admin_user))
    assert r.status_code == 400
    r = await client.get("/api/v1/suppliers/tra-mst/0100109106", headers=auth_header(admin_user))
    assert r.status_code == 200 and r.json()["ten_cong_ty"] == "CÔNG TY A"
