"""Đặt hàng – Leader Thu mua duyệt – Giám sát nhận hàng kèm ảnh (13/11/2026)."""
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.auth import hash_password
from app.models.media import MediaFile
from app.models.notification import Notification
from app.models.user import User
from app.models.vat_tu import DongPhieuVatTu
from tests.conftest import _uid, auth_header
from tests.test_vat_tu import du_an, mau, thiet_ke, thu_mua  # noqa: F401 — fixture dùng chung


@pytest_asyncio.fixture
async def leader_tm(db_session: AsyncSession) -> User:
    u = User(id=_uid(), full_name="Leader Thu Mua", email="leadertm@test.com", password_hash=hash_password("x"),
             role="dutoan_thumua_leader", department="PURCHASING", is_active=True)
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def giam_sat(db_session: AsyncSession, du_an) -> User:  # noqa: F811
    u = User(id=_uid(), full_name="Giam Sat Test", email="giamsat@test.com", password_hash=hash_password("x"),
             role="data_entry", department="OPS", is_active=True)
    db_session.add(u)
    await db_session.commit()
    du_an.pm_id = u.id
    du_an.budget_total = 10_000_000
    await db_session.commit()
    return u


async def _dong_da_chot(client, thu_mua, du_an, mau, so_luong=10, gia_von=200000):  # noqa: F811
    r = await client.post(f"/api/v1/vat-tu/du-an/{du_an.id}/dong", headers=auth_header(thu_mua),
                          json={"phong": "Bếp", "mau_id": mau.id, "so_luong": so_luong})
    dong_id = r.json()["id"]
    r = await client.post(f"/api/v1/vat-tu/dong/{dong_id}/chot", headers=auth_header(thu_mua), json={"gia_von": gia_von})
    assert r.status_code == 200, r.text
    r = await client.post(f"/api/v1/vat-tu/dong/{dong_id}/khach-dong-y", headers=auth_header(thu_mua), json={})
    assert r.status_code == 200, r.text
    return dong_id


async def _anh(db: AsyncSession, project_id: str, n: int) -> list[str]:
    ids = []
    for _ in range(n):
        m = MediaFile(id=_uid(), sha256=_uid(), project_id=project_id, kind="vat_tu")
        db.add(m)
        ids.append(m.id)
    await db.commit()
    return ids


@pytest.mark.asyncio
class TestDatNhanHang:
    async def test_trong_bao_gia_tu_qua_roi_giam_sat_nhan_du(self, client: AsyncClient, thu_mua, giam_sat, du_an, mau, db_session):  # noqa: F811
        dong_id = await _dong_da_chot(client, thu_mua, du_an, mau)
        # Không còn đổi tay trạng thái «Đã đặt»
        r = await client.patch(f"/api/v1/vat-tu/dong/{dong_id}", headers=auth_header(thu_mua), json={"trang_thai": "da_dat"})
        assert r.status_code == 400
        r = await client.post(f"/api/v1/vat-tu/dong/{dong_id}/dat-hang", headers=auth_header(thu_mua), json={})
        assert r.status_code == 200, r.text
        assert r.json()["trang_thai"] == "da_dat" and r.json()["sl_dat"] == 10
        # Giám sát được báo hàng sắp về
        n = (await db_session.execute(select(Notification).where(Notification.user_id == giam_sat.id))).scalars().all()
        assert any("đã đặt" in x.title for x in n)

        # Thu mua không được xác nhận nhận hàng
        anh = await _anh(db_session, du_an.id, 2)
        r = await client.post(f"/api/v1/vat-tu/dong/{dong_id}/nhan-hang", headers=auth_header(thu_mua),
                              json={"ket_qua": "du", "anh_ids": anh})
        assert r.status_code == 403
        # Giám sát: 1 ảnh chưa đủ
        r = await client.post(f"/api/v1/vat-tu/dong/{dong_id}/nhan-hang", headers=auth_header(giam_sat),
                              json={"ket_qua": "du", "anh_ids": anh[:1]})
        assert r.status_code == 400 and "2 ảnh" in r.json()["detail"]
        # Ảnh của dự án khác không tính
        r = await client.post(f"/api/v1/vat-tu/dong/{dong_id}/nhan-hang", headers=auth_header(giam_sat),
                              json={"ket_qua": "du", "anh_ids": [anh[0], (await _anh(db_session, None, 1))[0]]})
        assert r.status_code == 400
        r = await client.post(f"/api/v1/vat-tu/dong/{dong_id}/nhan-hang", headers=auth_header(giam_sat),
                              json={"ket_qua": "du", "anh_ids": anh})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["trang_thai"] == "da_giao" and d["nhan_ket_qua"] == "du" and len(d["nhan_anh"]) == 2
        assert d["nhan_boi_ten"] == "Giam Sat Test"

    async def test_vuot_khoi_luong_cho_leader_duyet(self, client: AsyncClient, thu_mua, leader_tm, giam_sat, du_an, mau, db_session):  # noqa: F811
        dong_id = await _dong_da_chot(client, thu_mua, du_an, mau)
        r = await client.post(f"/api/v1/vat-tu/dong/{dong_id}/dat-hang", headers=auth_header(thu_mua), json={"so_luong": 12})
        assert r.status_code == 200
        d = r.json()
        assert d["trang_thai"] == "cho_duyet_dat" and "Khối lượng" in d["ly_do_vuot"]
        n = (await db_session.execute(select(Notification).where(Notification.user_id == leader_tm.id))).scalars().all()
        assert any("cần duyệt" in x.title for x in n)
        # Nhân viên Thu mua không tự duyệt được
        r = await client.post(f"/api/v1/vat-tu/dong/{dong_id}/duyet-dat", headers=auth_header(thu_mua), json={"dong_y": True})
        assert r.status_code == 403
        # Từ chối phải có lý do; từ chối → về «đã chốt giá»
        r = await client.post(f"/api/v1/vat-tu/dong/{dong_id}/duyet-dat", headers=auth_header(leader_tm), json={"dong_y": False})
        assert r.status_code == 400
        r = await client.post(f"/api/v1/vat-tu/dong/{dong_id}/duyet-dat", headers=auth_header(leader_tm),
                              json={"dong_y": False, "ly_do": "Đo lại, 10m2 là đủ"})
        assert r.json()["trang_thai"] == "da_chot_gia" and r.json()["tu_choi_dat_ly_do"] == "Đo lại, 10m2 là đủ"
        # Đặt lại vượt → Leader đồng ý
        await client.post(f"/api/v1/vat-tu/dong/{dong_id}/dat-hang", headers=auth_header(thu_mua), json={"so_luong": 11})
        r = await client.post(f"/api/v1/vat-tu/dong/{dong_id}/duyet-dat", headers=auth_header(leader_tm), json={"dong_y": True})
        assert r.json()["trang_thai"] == "da_dat" and r.json()["duyet_dat_boi_ten"] == "Leader Thu Mua"
        # Hàng chờ của Giám sát có dòng này
        r = await client.get("/api/v1/vat-tu/viec-dat-nhan", headers=auth_header(giam_sat))
        assert [x["id"] for x in r.json()["cho_nhan"]] == [dong_id]
        assert r.json()["nhan_cua_toi"] == [dong_id]  # «Việc của tôi» của Giám sát
        r = await client.get("/api/v1/vat-tu/viec-dat-nhan", headers=auth_header(thu_mua))
        assert r.json()["nhan_cua_toi"] == []  # Thu mua chỉ xem

    async def test_vuot_don_gia_va_ngan_sach(self, client: AsyncClient, thu_mua, giam_sat, du_an, mau):  # noqa: F811
        dong_id = await _dong_da_chot(client, thu_mua, du_an, mau, so_luong=40, gia_von=200000)  # 8tr
        r = await client.post(f"/api/v1/vat-tu/dong/{dong_id}/dat-hang", headers=auth_header(thu_mua), json={"don_gia": 210000})
        assert r.json()["trang_thai"] == "cho_duyet_dat" and "Đơn giá" in r.json()["ly_do_vuot"]
        dong2 = await _dong_da_chot(client, thu_mua, du_an, mau, so_luong=15, gia_von=200000)  # +3tr > ngân sách 10tr
        r = await client.post(f"/api/v1/vat-tu/dong/{dong2}/dat-hang", headers=auth_header(thu_mua), json={})
        assert r.json()["trang_thai"] == "cho_duyet_dat" and "ngân sách" in r.json()["ly_do_vuot"]

    async def test_leader_tu_dat_vuot_van_ghi_vet(self, client: AsyncClient, leader_tm, thu_mua, du_an, mau):  # noqa: F811
        dong_id = await _dong_da_chot(client, thu_mua, du_an, mau)
        r = await client.post(f"/api/v1/vat-tu/dong/{dong_id}/dat-hang", headers=auth_header(leader_tm), json={"so_luong": 11})
        assert r.json()["trang_thai"] == "da_dat" and r.json()["ly_do_vuot"]

    async def test_gia_cu_qua_60_ngay_phai_hoi_lai(self, client: AsyncClient, thu_mua, du_an, mau, db_session):  # noqa: F811
        dong_id = await _dong_da_chot(client, thu_mua, du_an, mau)
        d = await db_session.get(DongPhieuVatTu, dong_id)
        d.chot_luc = datetime.utcnow() - timedelta(days=61)
        d.khach_dong_y_luc = datetime.utcnow()
        await db_session.commit()
        r = await client.post(f"/api/v1/vat-tu/dong/{dong_id}/dat-hang", headers=auth_header(thu_mua), json={})
        assert r.status_code == 400 and "60 ngày" in r.json()["detail"]
        r = await client.get(f"/api/v1/vat-tu/du-an/{du_an.id}/dong", headers=auth_header(thu_mua))
        assert next(i for i in r.json()["items"] if i["id"] == dong_id)["gia_cu"] is True

    async def test_giao_thieu_phai_ghi_chu_roi_nhan_bu(self, client: AsyncClient, thu_mua, leader_tm, giam_sat, du_an, mau, db_session):  # noqa: F811
        dong_id = await _dong_da_chot(client, thu_mua, du_an, mau)
        await client.post(f"/api/v1/vat-tu/dong/{dong_id}/dat-hang", headers=auth_header(thu_mua), json={})
        anh = await _anh(db_session, du_an.id, 4)
        r = await client.post(f"/api/v1/vat-tu/dong/{dong_id}/nhan-hang", headers=auth_header(giam_sat),
                              json={"ket_qua": "thieu", "anh_ids": anh[:2]})
        assert r.status_code == 400
        r = await client.post(f"/api/v1/vat-tu/dong/{dong_id}/nhan-hang", headers=auth_header(giam_sat),
                              json={"ket_qua": "thieu", "so_luong_nhan": 7, "ghi_chu": "Thiếu 3m2, vỡ 1 thùng", "anh_ids": anh[:2]})
        assert r.json()["trang_thai"] == "giao_thieu" and r.json()["sl_nhan"] == 7
        n = (await db_session.execute(select(Notification).where(Notification.user_id == leader_tm.id))).scalars().all()
        assert any("THIẾU" in x.title for x in n)
        r = await client.post(f"/api/v1/vat-tu/dong/{dong_id}/nhan-hang", headers=auth_header(giam_sat),
                              json={"ket_qua": "du", "anh_ids": anh[2:]})
        assert r.json()["trang_thai"] == "da_giao" and len(r.json()["nhan_anh"]) == 4
