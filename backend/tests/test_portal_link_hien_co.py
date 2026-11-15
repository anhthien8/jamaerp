"""Link portal «hiện có»: gọi nhiều lần vẫn một link, không xoay token, không tự bật lại."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.project import Project
from app.models.user import User
from tests.conftest import auth_header, _uid


def _khach(**kw) -> Customer:
    return Customer(id=_uid(), name="KH Portal", phone="0911222333", type="individual", **kw)


def _du_an(**kw) -> Project:
    return Project(id=_uid(), code=f"JMH-{_uid()[:6]}", name="Nhà anh Ba", client_name="Anh Ba",
                   stage="design", status="active", **kw)


@pytest.mark.asyncio
class TestPortalLinkHienCo:
    async def test_goi_hai_lan_cung_mot_token(
        self, client: AsyncClient, db_session: AsyncSession, admin_user: User
    ):
        kh = _khach()
        db_session.add(kh)
        await db_session.commit()
        url = f"/api/v1/customers/{kh.id}/portal-link"
        r1 = await client.post(url, headers=auth_header(admin_user))
        r2 = await client.post(url, headers=auth_header(admin_user))
        assert r1.status_code == 200, r1.text
        assert r1.json()["portal_token"]
        assert r1.json()["portal_enabled"] is True
        assert r2.json()["portal_token"] == r1.json()["portal_token"]

    async def test_token_co_san_giu_nguyen_va_khong_tu_bat_lai(
        self, client: AsyncClient, db_session: AsyncSession, admin_user: User
    ):
        kh = _khach(portal_token="token-da-gui-khach", portal_enabled=False)
        db_session.add(kh)
        await db_session.commit()
        r = await client.post(f"/api/v1/customers/{kh.id}/portal-link", headers=auth_header(admin_user))
        assert r.status_code == 200, r.text
        assert r.json()["portal_token"] == "token-da-gui-khach"
        assert r.json()["portal_enabled"] is False
        await db_session.refresh(kh)
        assert kh.portal_enabled is False

    async def test_sale_khong_phu_trach_bi_403(
        self, client: AsyncClient, db_session: AsyncSession, sales_user: User
    ):
        kh = _khach()
        db_session.add(kh)
        await db_session.commit()
        r = await client.post(f"/api/v1/customers/{kh.id}/portal-link", headers=auth_header(sales_user))
        assert r.status_code == 403
        await db_session.refresh(kh)
        assert kh.portal_token is None

    async def test_sale_phu_trach_lay_duoc_ca_khi_du_an_noi_qua_lead(
        self, client: AsyncClient, db_session: AsyncSession, sales_user: User
    ):
        kh_truc_tiep = _khach()
        kh_qua_lead = _khach(lead_id=_uid())
        db_session.add_all([
            kh_truc_tiep, kh_qua_lead,
            _du_an(customer_id=kh_truc_tiep.id, sales_id=sales_user.id),
            _du_an(lead_id=kh_qua_lead.lead_id, pm_id=sales_user.id),
        ])
        await db_session.commit()
        for kh in (kh_truc_tiep, kh_qua_lead):
            r = await client.post(f"/api/v1/customers/{kh.id}/portal-link", headers=auth_header(sales_user))
            assert r.status_code == 200, r.text
            assert r.json()["portal_token"]

    async def test_theo_du_an_tra_dung_khach_va_cung_token(
        self, client: AsyncClient, db_session: AsyncSession, admin_user: User, sales_user: User
    ):
        kh = _khach(portal_token="token-cu", portal_enabled=True)
        da = _du_an(customer_id=kh.id, sales_id=admin_user.id)
        da_le = _du_an()
        db_session.add_all([kh, da, da_le])
        await db_session.commit()
        r = await client.post(f"/api/v1/customers/portal-link-du-an/{da.id}", headers=auth_header(admin_user))
        assert r.status_code == 200, r.text
        assert r.json() == {"customer_id": kh.id, "portal_token": "token-cu", "portal_enabled": True}
        # người không phụ trách dự án không lấy được link
        r = await client.post(f"/api/v1/customers/portal-link-du-an/{da.id}", headers=auth_header(sales_user))
        assert r.status_code == 403
        # dự án tạo tay, không gắn khách
        r = await client.post(f"/api/v1/customers/portal-link-du-an/{da_le.id}", headers=auth_header(admin_user))
        assert r.status_code == 404
