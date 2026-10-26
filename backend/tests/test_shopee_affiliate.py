"""Shopee Affiliate (26/10/2026): ký, chuẩn hoá, cài đặt admin, ghép mẫu, cần thương lượng, gợi ý NCC."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.auth import hash_password
from app.models.project import Project
from app.models.supplier import Supplier
from app.models.user import User
from app.models.vat_tu import BaoGiaDongVatTu, DongPhieuVatTu, MauVatTu
from app.services import shopee_affiliate as sa
from tests.conftest import _uid, auth_header


@pytest_asyncio.fixture
async def thu_mua(db_session: AsyncSession) -> User:
    u = User(id=_uid(), full_name="Thu Mua SP", email="thumua.sp@test.com", password_hash=hash_password("x"),
             role="data_entry", department="PURCHASING", is_active=True)
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def mau(db_session: AsyncSession) -> MauVatTu:
    m = MauVatTu(ma="TM 9001", hang="Viglacera", nhom="60x60")
    db_session.add(m)
    await db_session.commit()
    return m


def test_ky_va_chuan_hoa():
    assert sa.ky("1", "s", 10, "{}") == __import__("hashlib").sha256(b"110{}s").hexdigest()
    d = sa.chuan_hoa_sp({"itemId": 123, "productName": "Gạch", "priceMin": "150000", "priceMax": "180000",
                         "commissionRate": "0.05", "sales": 12, "offerLink": "https://s.shopee.vn/x"})
    assert d["item_id"] == "123" and d["gia"] == 150000 and d["hoa_hong_pct"] == 5.0
    assert d["link_aff"] == "https://s.shopee.vn/x"


@pytest.mark.asyncio
async def test_cai_dat_chi_admin_va_che_secret(client: AsyncClient, admin_user, sales_user):
    r = await client.put("/api/v1/shopee-settings", json={"app_id": "111", "secret": "abcdefghijklmnop"},
                         headers=auth_header(sales_user))
    assert r.status_code == 403
    r = await client.put("/api/v1/shopee-settings", json={"app_id": "111", "secret": "abcdefghijklmnop"},
                         headers=auth_header(admin_user))
    assert r.status_code == 200 and r.json()["san_sang"] is True
    assert "abcdefghijklmnop" not in r.text
    # bỏ trống secret khi lưu lại không xoá khoá cũ
    r = await client.put("/api/v1/shopee-settings", json={"app_id": "222", "secret": ""}, headers=auth_header(admin_user))
    assert r.json()["secret_set"] is True and r.json()["app_id"] == "222"


@pytest.mark.asyncio
async def test_chua_co_khoa_bao_503(client: AsyncClient, thu_mua, mau):
    r = await client.get(f"/api/v1/vat-tu/mau/{mau.id}/shopee", headers=auth_header(thu_mua))
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_tim_va_ghep_mau(client: AsyncClient, thu_mua, sales_user, mau, monkeypatch):
    async def gia(db, kw, limit=8):
        assert "TM 9001" in kw
        return [{"item_id": "9", "ten": "Gạch TM", "gia": 120000, "link_aff": "https://s.shopee.vn/a"}]
    monkeypatch.setattr(sa, "tim_san_pham", gia)
    r = await client.get(f"/api/v1/vat-tu/mau/{mau.id}/shopee", headers=auth_header(sales_user))
    assert r.status_code == 403
    r = await client.get(f"/api/v1/vat-tu/mau/{mau.id}/shopee", headers=auth_header(thu_mua))
    assert r.status_code == 200 and r.json()["items"][0]["gia"] == 120000
    r = await client.put(f"/api/v1/vat-tu/mau/{mau.id}/shopee",
                         json={"item_id": "9", "ten": "Gạch TM", "gia": 120000, "link_aff": "https://s.shopee.vn/a"},
                         headers=auth_header(thu_mua))
    assert r.status_code == 200 and r.json()["gia_shopee"] == 120000 and r.json()["gia_shopee_luc"]
    r = await client.delete(f"/api/v1/vat-tu/mau/{mau.id}/shopee", headers=auth_header(thu_mua))
    assert r.json()["gia_shopee"] is None


@pytest.mark.asyncio
async def test_can_thuong_luong_va_goi_y_ncc(client: AsyncClient, db_session, admin_user, thu_mua, sales_user, mau):
    mau.gia_shopee = 100000
    p = Project(id=_uid(), code="JMH-SP1", name="Nhà", client_name="Khách", status="active", total_value=1)
    a = Supplier(id=_uid(), name="NCC A", chiet_khau_pct=20)   # 110k → 88k sau CK
    b = Supplier(id=_uid(), name="NCC B", chiet_khau_pct=0)    # 95k
    db_session.add_all([p, a, b])
    await db_session.flush()
    d = DongPhieuVatTu(id=_uid(), project_id=p.id, mau_id=mau.id, so_luong=10)
    cu = DongPhieuVatTu(id=_uid(), project_id=p.id, mau_id=mau.id, so_luong=100, gia_von=90000, ncc_id=b.id,
                        trang_thai="da_dat")
    db_session.add_all([d, cu])
    await db_session.flush()
    db_session.add_all([
        BaoGiaDongVatTu(dong_id=d.id, supplier_id=a.id, ncc_ten="NCC A", gia=110000),
        BaoGiaDongVatTu(dong_id=d.id, supplier_id=b.id, ncc_ten="NCC B", gia=95000),
    ])
    await db_session.commit()

    r = await client.get("/api/v1/vat-tu/can-thuong-luong", headers=auth_header(sales_user))
    assert r.status_code == 403
    r = await client.get("/api/v1/vat-tu/can-thuong-luong", headers=auth_header(thu_mua))
    items = r.json()["items"]
    assert [x["ncc_ten"] for x in items] == ["NCC A"] and items[0]["chenh_pct"] == 10.0

    r = await client.get(f"/api/v1/vat-tu/mau/{mau.id}/goi-y-ncc", headers=auth_header(admin_user))
    j = r.json()
    assert j["goi_y"]["ncc_ten"] == "NCC A" and j["goi_y"]["gia_sau_ck"] == 88000
    assert j["items"][1]["da_mua"] == 9_000_000 and j["items"][0]["cao_hon_shopee"] is False


@pytest.mark.asyncio
async def test_cap_nhat_hang_tuan_khong_khoa_thi_bo_qua(db_session, mau):
    mau.shopee_item_id = "9"
    await db_session.commit()
    assert await sa.cap_nhat_gia_hang_tuan(db_session) == 0
