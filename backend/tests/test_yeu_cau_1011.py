"""Yêu cầu 10/11/2026: xoá nhân sự đã nghỉ + ngày khảo sát lead theo tháng."""

import pytest

from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_xoa_nhan_su_da_nghi_khoi_danh_sach(client, admin_user, sales_user):
    h = auth_header(admin_user)
    sid = sales_user.id
    # Đang làm thì không xoá được
    resp = await client.delete(f"/api/v1/hr/resigned/{sid}", headers=h)
    assert resp.status_code == 400, resp.text
    resp = await client.post("/api/v1/hr/resign", json={"user_id": sid}, headers=h)
    assert resp.status_code == 200, resp.text
    # Đã nghỉ: vẫn còn trong danh sách cho tới khi bấm Xoá
    ds = (await client.get("/api/v1/users?page_size=500", headers=h)).json()["items"]
    assert sid in {u["id"] for u in ds}
    resp = await client.delete(f"/api/v1/hr/resigned/{sid}", headers=h)
    assert resp.status_code == 200, resp.text
    ds = (await client.get("/api/v1/users?page_size=500", headers=h)).json()["items"]
    assert sid not in {u["id"] for u in ds}


@pytest.mark.asyncio
async def test_ngay_khao_sat_loc_thang_va_thong_ke(client, admin_user):
    h = auth_header(admin_user)
    uid = admin_user.id
    ids = []
    for i, ngay in enumerate(["2026-11-03", "2026-11-28T23:30:00+07:00", "2026-10-15", None]):
        resp = await client.post("/api/v1/leads", json={
            "name": f"Khách {i}", "phone": f"09000000{i}", "survey_date": ngay,
            "assigned_to": uid,
        }, headers=h)
        assert resp.status_code in (200, 201), resp.text
        ids.append(resp.json()["id"])
    # Sửa ngày khảo sát qua cập nhật lead
    resp = await client.put(f"/api/v1/leads/{ids[3]}", json={"survey_date": "2026-11-10"}, headers=h)
    assert resp.status_code == 200, resp.text
    resp = await client.put(f"/api/v1/leads/{ids[0]}/stage", json={"stage": "signed_design"}, headers=h)

    ds = (await client.get("/api/v1/leads?thang_khao_sat=2026-11", headers=h)).json()["items"]
    assert {l["id"] for l in ds} == {ids[0], ids[1], ids[3]}
    tk = (await client.get("/api/v1/leads/khao-sat/thong-ke?thang=2026-11", headers=h)).json()
    assert tk["tong"] == 3
    assert tk["theo_nguoi"][0]["khao_sat"] == 3
    resp = await client.get("/api/v1/leads?thang_khao_sat=2026-13x", headers=h)
    assert resp.status_code == 422
