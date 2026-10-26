"""Cơ cấu hoa hồng: đặt mức mới kèm ngày hiệu lực, chỉ áp dụng sau khi BGĐ duyệt."""

from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commission_structure import CommissionStructure
from app.models.user import User
from app.services.hoa_hong import muc_hoa_hong
from tests.conftest import auth_header

URL = "/api/v1/commission-structures"


async def _tao(client, user: User, rate: float, ngay: date) -> dict:
    r = await client.post(URL, headers=auth_header(user), json={
        "department": "sales", "commission_type": "design_commission",
        "rate": rate, "effective_date": ngay.isoformat(),
    })
    assert r.status_code == 200, r.text
    return r.json()


async def _duyet(client, db_session: AsyncSession, admin: User, cs_id: str):
    cs = await db_session.get(CommissionStructure, cs_id)
    await db_session.refresh(cs)
    r = await client.post(f"/api/v1/approvals/{cs.approval_id}/approve", headers=auth_header(admin))
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_chua_co_muc_duyet_thi_giu_3_va_2(db_session: AsyncSession):
    assert await muc_hoa_hong(db_session, "design_commission", date.today()) == 0.03
    assert await muc_hoa_hong(db_session, "construction_commission", date.today()) == 0.02


@pytest.mark.asyncio
async def test_doc_ca_ten_loai_cua_seed(db_session: AsyncSession):
    db_session.add(CommissionStructure(department="sales", commission_type="construction_contract",
                                       rate=0.025, effective_date=date.today(), status="da_duyet"))
    await db_session.commit()
    assert await muc_hoa_hong(db_session, "construction_commission", date.today()) == 0.025


@pytest.mark.asyncio
async def test_muc_moi_chi_ap_dung_sau_khi_bgd_duyet(
    client, db_session: AsyncSession, accountant_user: User, admin_user: User,
):
    cs = await _tao(client, accountant_user, 0.05, date.today())
    assert cs["status"] == "cho_duyet"
    # Chưa duyệt → vẫn mức cũ
    assert await muc_hoa_hong(db_session, "design_commission", date.today()) == 0.03

    await _duyet(client, db_session, admin_user, cs["id"])
    db_session.expire_all()
    assert await muc_hoa_hong(db_session, "design_commission", date.today()) == 0.05


@pytest.mark.asyncio
async def test_ngay_hieu_luc_tuong_lai_chua_ap_dung(
    client, db_session: AsyncSession, accountant_user: User, admin_user: User,
):
    cs = await _tao(client, accountant_user, 0.04, date.today() + timedelta(days=10))
    await _duyet(client, db_session, admin_user, cs["id"])
    db_session.expire_all()
    assert await muc_hoa_hong(db_session, "design_commission", date.today()) == 0.03
    assert await muc_hoa_hong(db_session, "design_commission", date.today() + timedelta(days=10)) == 0.04


@pytest.mark.asyncio
async def test_bgd_tu_choi_thi_khong_ap_dung(
    client, db_session: AsyncSession, accountant_user: User, admin_user: User,
):
    cs = await _tao(client, accountant_user, 0.09, date.today())
    row = await db_session.get(CommissionStructure, cs["id"])
    await db_session.refresh(row)
    r = await client.post(f"/api/v1/approvals/{row.approval_id}/reject",
                          headers=auth_header(admin_user), json={"reason": "cao quá"})
    assert r.status_code == 200, r.text
    db_session.expire_all()
    assert (await db_session.get(CommissionStructure, cs["id"])).status == "tu_choi"
    assert await muc_hoa_hong(db_session, "design_commission", date.today()) == 0.03


@pytest.mark.asyncio
async def test_muc_dang_cho_hoac_da_duyet_khong_sua_duoc(
    client, db_session: AsyncSession, accountant_user: User, admin_user: User,
):
    cs = await _tao(client, accountant_user, 0.05, date.today())
    r = await client.put(f"{URL}/{cs['id']}", headers=auth_header(accountant_user), json={"rate": 0.5})
    assert r.status_code == 400

    await _duyet(client, db_session, admin_user, cs["id"])
    r = await client.delete(f"{URL}/{cs['id']}", headers=auth_header(accountant_user))
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_sale_khong_dat_duoc_muc(client, sales_user: User):
    r = await client.post(URL, headers=auth_header(sales_user), json={
        "department": "sales", "commission_type": "design_commission", "rate": 0.5,
    })
    assert r.status_code == 403
