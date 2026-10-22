"""Vào ca văn phòng phải ở trong bán kính GPS (chốt 22/10/2026).

Chặn cứng khi thiếu GPS hoặc ngoài bán kính, trừ: bộ phận hiện trường, check-in
công trình có thật, đang dùng mạng văn phòng, admin chưa lưu tọa độ, tắt cờ.
"""

import pytest
import pytest_asyncio

from app.models.user import User
from app.middleware.auth import hash_password
from tests.conftest import auth_header, _uid

VP_LAT, VP_LNG = 10.776000, 106.700000
GAN = (VP_LAT + 0.00009, VP_LNG)    # ~10 m
XA = (VP_LAT + 0.000225, VP_LNG)    # ~25 m


async def _cau_hinh(client, admin_user, **them):
    body = {"networks": ["10.77.0.0/16"], "lat": VP_LAT, "lng": VP_LNG, "radius_m": 20, **them}
    r = await client.put("/api/v1/attendance/office-config", json=body,
                         headers=auth_header(admin_user))
    assert r.status_code == 200, r.text
    return r


@pytest_asyncio.fixture
async def ops_user(db_session) -> User:
    u = User(id=_uid(), full_name="Giám Sát Hiện Trường", email="ops-gps@test.com",
             password_hash=hash_password("x12345678"), role="data_entry",
             department="OPS", is_active=True, telegram_user_id=900777)
    db_session.add(u)
    await db_session.commit()
    return u


@pytest.mark.asyncio
class TestVaoCaGps:
    async def test_cau_hinh_nhan_ban_kinh_10m_va_truong_moi(self, client, admin_user):
        await _cau_hinh(client, admin_user, radius_m=10, require_gps=True,
                        field_departments=["ops", "PM"])
        r = await client.get("/api/v1/attendance/office-config", headers=auth_header(admin_user))
        d = r.json()["office"]
        assert d["radius_m"] == 10
        assert d["require_gps"] is True
        assert d["field_departments"] == ["OPS", "PM"]

    async def test_thieu_gps_bi_chan(self, client, admin_user, sales_user):
        await _cau_hinh(client, admin_user)
        r = await client.post("/api/v1/attendance/checkin", json={},
                              headers=auth_header(sales_user))
        assert r.status_code == 400
        assert "Cần bật vị trí" in r.json()["detail"]

    async def test_cach_25m_bi_chan_kem_khoang_cach(self, client, admin_user, sales_user):
        await _cau_hinh(client, admin_user)
        r = await client.post("/api/v1/attendance/checkin",
                              json={"latitude": XA[0], "longitude": XA[1]},
                              headers=auth_header(sales_user))
        assert r.status_code == 400
        detail = r.json()["detail"]
        assert "cách văn phòng 25 m" in detail and "cho phép 20 m" in detail

    async def test_trong_10m_vao_ca_duoc(self, client, admin_user, sales_user):
        await _cau_hinh(client, admin_user)
        r = await client.post("/api/v1/attendance/checkin",
                              json={"latitude": GAN[0], "longitude": GAN[1]},
                              headers=auth_header(sales_user))
        assert r.status_code == 200, r.text
        assert r.json()["record"]["gps_ok"] is True

    async def test_hien_truong_cach_25m_van_vao_ca(self, client, admin_user, ops_user):
        await _cau_hinh(client, admin_user)
        r = await client.post("/api/v1/attendance/checkin",
                              json={"latitude": XA[0], "longitude": XA[1]},
                              headers=auth_header(ops_user))
        assert r.status_code == 200, r.text

    async def test_mang_van_phong_khong_can_gps(self, client, admin_user, sales_user):
        await _cau_hinh(client, admin_user)
        r = await client.post("/api/v1/attendance/checkin", json={},
                              headers={**auth_header(sales_user), "X-Forwarded-For": "10.77.3.9"})
        assert r.status_code == 200, r.text
        assert r.json()["record"]["ip_ok"] is True

    async def test_chua_luu_toa_do_khong_chan(self, client, admin_user, sales_user):
        r = await client.put("/api/v1/attendance/office-config",
                             json={"networks": ["10.77.0.0/16"]},
                             headers=auth_header(admin_user))
        assert r.status_code == 200
        r = await client.post("/api/v1/attendance/checkin", json={},
                              headers=auth_header(sales_user))
        assert r.status_code == 200, r.text

    async def test_tat_bat_buoc_gps_khong_chan(self, client, admin_user, sales_user):
        await _cau_hinh(client, admin_user, require_gps=False)
        r = await client.post("/api/v1/attendance/checkin", json={},
                              headers=auth_header(sales_user))
        assert r.status_code == 200, r.text

    async def test_checkin_cong_trinh_that_duoc_mien(self, client, admin_user, project):
        await _cau_hinh(client, admin_user)
        r = await client.post("/api/v1/attendance/checkin",
                              json={"project_id": project.id},
                              headers=auth_header(admin_user))
        assert r.status_code == 200, r.text

    async def test_ma_du_an_bia_khong_ne_duoc_gps(self, client, admin_user, sales_user):
        await _cau_hinh(client, admin_user)
        r = await client.post("/api/v1/attendance/checkin",
                              json={"project_id": "khong-ton-tai"},
                              headers=auth_header(sales_user))
        assert r.status_code == 400

    async def test_lan_vao_ca_thu_hai_khong_bi_chan(self, client, admin_user, sales_user):
        await _cau_hinh(client, admin_user)
        ok = await client.post("/api/v1/attendance/checkin",
                               json={"latitude": GAN[0], "longitude": GAN[1]},
                               headers=auth_header(sales_user))
        assert ok.status_code == 200
        lai = await client.post("/api/v1/attendance/checkin", json={},
                                headers=auth_header(sales_user))
        assert lai.status_code == 200
        assert lai.json()["created"] is False

    async def test_telegram_van_phong_thieu_gps_bi_chan_co_gps_thi_duoc(
        self, client, admin_user, sales_user
    ):
        await _cau_hinh(client, admin_user)
        h = auth_header(sales_user)
        r = await client.post("/api/v1/telegram/attendance/checkin",
                              json={"user_tg_id": sales_user.telegram_user_id}, headers=h)
        assert r.status_code == 400
        assert "Cần bật vị trí" in r.json()["detail"]
        r = await client.post("/api/v1/telegram/attendance/checkin",
                              json={"user_tg_id": sales_user.telegram_user_id,
                                    "latitude": GAN[0], "longitude": GAN[1]}, headers=h)
        assert r.status_code == 201, r.text
