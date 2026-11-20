"""Chốt theo giá gần nhất một chạm (15/11/2026): dòng vật tư kèm NCC gần nhất + cờ giá khung cũ,
chỉ cho người thấy giá vốn; chốt bằng supplier_id giữ đúng NCC của mẫu."""

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.supplier import Supplier
from app.models.vat_tu import MauVatTu
from tests.conftest import _uid, auth_header
from tests.test_vat_tu import du_an, thiet_ke, thu_mua  # noqa: F401  (fixture)

TRUONG_MOI = ("ncc_gan_nhat_id", "ncc_gan_nhat_ten", "gia_von_cap_nhat_luc", "gia_gan_nhat_cu")


@pytest.mark.asyncio
async def test_truong_ncc_gan_nhat_chi_cho_nguoi_thay_gia_von(client: AsyncClient, db_session: AsyncSession,
                                                              thu_mua, thiet_ke, sales_user, du_an):  # noqa: F811
    ncc = Supplier(id=_uid(), name="Hiệp Phát")
    m = MauVatTu(ma="TM 1", hang="Taicera", nhom="60x60", gia_von_gan_nhat=200000, ncc_gan_nhat_id=ncc.id,
                 ncc_gan_nhat_ten="Hiệp Phát", gia_von_cap_nhat_luc=datetime.utcnow() - timedelta(days=5))
    m_cu = MauVatTu(ma="TM 2", hang="Taicera", nhom="60x60", gia_von_gan_nhat=150000, ncc_gan_nhat_ten="Daisan",
                    gia_von_cap_nhat_luc=datetime.utcnow() - timedelta(days=90))
    db_session.add_all([ncc, m, m_cu])
    await db_session.commit()
    for mau in (m, m_cu):
        r = await client.post(f"/api/v1/vat-tu/du-an/{du_an.id}/dong", headers=auth_header(thiet_ke),
                              json={"phong": "Bếp", "mau_id": mau.id, "so_luong": 10})
        assert r.status_code == 201

    items = (await client.get("/api/v1/vat-tu/can-hoi-gia", headers=auth_header(thu_mua))).json()["items"]
    moi = next(i for i in items if i["ma"] == "TM 1")
    cu = next(i for i in items if i["ma"] == "TM 2")
    assert moi["ncc_gan_nhat_id"] == ncc.id and moi["ncc_gan_nhat_ten"] == "Hiệp Phát"
    assert moi["gia_gan_nhat_cu"] is False and moi["gia_von_cap_nhat_luc"]
    assert cu["gia_gan_nhat_cu"] is True

    for u in (thiet_ke, sales_user):
        body = (await client.get(f"/api/v1/vat-tu/du-an/{du_an.id}/dong", headers=auth_header(u))).json()
        for d in body["items"]:
            for cam in TRUONG_MOI:
                assert cam not in d


@pytest.mark.asyncio
async def test_chot_bang_supplier_id_giu_ncc_cua_mau(client: AsyncClient, db_session: AsyncSession,
                                                    thu_mua, thiet_ke, du_an):  # noqa: F811
    ncc = Supplier(id=_uid(), name="Hiệp Phát")
    m = MauVatTu(ma="TM 3", hang="Taicera", nhom="60x60", gia_von_gan_nhat=200000, ncc_gan_nhat_id=ncc.id,
                 ncc_gan_nhat_ten="Hiệp Phát", gia_von_cap_nhat_luc=datetime.utcnow())
    db_session.add_all([ncc, m])
    await db_session.commit()
    r = await client.post(f"/api/v1/vat-tu/du-an/{du_an.id}/dong", headers=auth_header(thiet_ke),
                          json={"phong": "Bếp", "mau_id": m.id, "so_luong": 2})
    r = await client.post(f"/api/v1/vat-tu/dong/{r.json()['id']}/chot", headers=auth_header(thu_mua),
                          json={"gia_von": 200000, "supplier_id": ncc.id, "ncc_ten": "Hiệp Phát"})
    assert r.status_code == 200, r.text
    assert r.json()["ncc_id"] == ncc.id and r.json()["trang_thai"] == "da_chot_gia"
    await db_session.refresh(m)
    assert m.ncc_gan_nhat_id == ncc.id
