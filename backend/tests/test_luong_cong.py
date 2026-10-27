"""Ngày lễ tính công, rút đơn nghỉ, xem công nhân viên theo phạm vi (27/10/2026)."""

from datetime import date

import pytest
from sqlalchemy import select

from app.models.leave import LeaveRequest
from app.services.attendance_service import ngay_le_trong_khoang
from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_ngay_le_mac_dinh_va_them(client, db_session, admin_user, sales_user):
    ds = await ngay_le_trong_khoang(db_session, date(2026, 9, 1), date(2026, 9, 30))
    assert date(2026, 9, 2) in ds
    r = await client.put("/api/v1/attendance/ngay-le", json={"ngay": ["2026-02-17"]}, headers=auth_header(sales_user))
    assert r.status_code == 403
    r = await client.put("/api/v1/attendance/ngay-le", json={"ngay": ["2026-02-17"]}, headers=auth_header(admin_user))
    assert r.status_code == 200, r.text
    r = await client.get("/api/v1/attendance/ngay-le?nam=2026", headers=auth_header(admin_user))
    assert "2026-02-17" in r.json()["them"]


@pytest.mark.asyncio
async def test_don_nghi_tru_ngay_le_va_rut_don(client, db_session, sales_user, admin_user):
    r = await client.post("/api/v1/leaves", json={"leave_type": "annual", "start_date": "2026-09-01",
                          "end_date": "2026-09-03", "reason": "Về quê"}, headers=auth_header(sales_user))
    assert r.status_code in (200, 201), r.text
    lv = r.json().get("leave", r.json())
    assert lv["days"] == 2  # 02/09 là lễ
    r = await client.post(f"/api/v1/leaves/{lv['id']}/huy", headers=auth_header(sales_user))
    assert r.status_code == 200, r.text
    st = (await db_session.execute(select(LeaveRequest.status).where(LeaveRequest.id == lv["id"])
                                   .execution_options(populate_existing=True))).scalar()
    assert st == "cancelled"
    r = await client.post(f"/api/v1/leaves/{lv['id']}/huy", headers=auth_header(sales_user))
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_xem_cong_nguoi_khac_can_pham_vi(client, sales_user, designer_user, admin_user):
    r = await client.get(f"/api/v1/attendance/me?user_id={designer_user.id}", headers=auth_header(sales_user))
    assert r.status_code == 403
    r = await client.get(f"/api/v1/attendance/me?user_id={designer_user.id}", headers=auth_header(admin_user))
    assert r.status_code == 200
