"""Vật tư Đợt 1 — các lỗi lượt kiểm lại cuối tìm ra (23/11/2026)."""
from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.supplier import Supplier
from app.models.vat_tu import BaoGiaDongVatTu, DongPhieuVatTu, GiaNhapMauVatTu, MauVatTu
from app.services.ncc import BoNcc
from tests.conftest import _uid, auth_header
from tests.test_vat_tu import du_an, mau, thiet_ke, thu_mua  # noqa: F401 — fixture dùng chung

H = "/api/v1/vat-tu"


async def _them(client, user, du_an, **kw) -> dict:  # noqa: F811
    r = await client.post(f"{H}/du-an/{du_an.id}/dong", headers=auth_header(user), json={"phong": "Bếp", "so_luong": 10, **kw})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.asyncio
async def test_doi_mau_chuyen_bao_gia_ve_gia_nhap_cua_mau_cu(client: AsyncClient, thu_mua, thiet_ke, du_an,  # noqa: F811
                                                            mau, db_session):  # noqa: F811
    """Đổi mẫu trên dòng: báo giá NCC của mẫu cũ không nằm lại trên dòng mẫu mới (Bảng giá chuẩn và
    «chốt theo báo giá» sẽ hiểu nhầm là giá mẫu mới) — nó thành giá nhập của mẫu CŨ."""
    moi = MauVatTu(ma="TM 99999", nhom="60x60")
    db_session.add(moi)
    await db_session.commit()
    mau_cu_id, moi_id, h_tm = mau.id, moi.id, auth_header(thu_mua)
    d = await _them(client, thiet_ke, du_an, mau_id=mau_cu_id)
    r = await client.post(f"{H}/dong/{d['id']}/bao-gia", headers=auth_header(thu_mua), json={"ncc_ten": "Hiệp Phát", "gia": 111111})
    assert r.status_code == 201, r.text
    bg_id = r.json()["bao_gia"][0]["id"]

    r = await client.patch(f"{H}/dong/{d['id']}", headers=auth_header(thiet_ke), json={"mau_id": moi_id})
    assert r.status_code == 200, r.text
    db_session.expire_all()
    assert (await db_session.execute(select(BaoGiaDongVatTu).where(BaoGiaDongVatTu.dong_id == d["id"]))).first() is None
    gn = (await db_session.execute(select(GiaNhapMauVatTu))).scalars().all()
    assert [(g.mau_id, g.gia) for g in gn] == [(mau_cu_id, 111111)]
    # Báo giá cũ không còn chốt được cho dòng mẫu mới
    r = await client.post(f"{H}/dong/{d['id']}/chot", headers=h_tm, json={"bao_gia_id": bg_id})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_dong_y_khi_chua_co_gia_bi_chan_va_gia_chuan_van_toi(client: AsyncClient, thiet_ke, admin_user,  # noqa: F811
                                                                    du_an, mau, db_session):  # noqa: F811
    d = await _them(client, thiet_ke, du_an, mau_id=mau.id)  # mẫu chưa có giá chuẩn → chưa có giá bán
    assert d["gia_ban"] is None
    r = await client.post(f"{H}/dong/{d['id']}/khach-dong-y", headers=auth_header(thiet_ke), json={"ghi_chu": "ok"})
    assert r.status_code == 400 and r.json()["detail"] == "Dòng chưa có giá bán — chưa có gì để khách đồng ý"
    # Dữ liệu cũ: lời đồng ý nằm trên dòng chưa có giá → Giám đốc đặt giá chuẩn vẫn phải tới dòng đó
    dong = await db_session.get(DongPhieuVatTu, d["id"])
    dong.khach_dong_y_luc = datetime(2026, 11, 1)
    await db_session.commit()
    r = await client.put(f"{H}/gia-chuan/{mau.id}", headers=auth_header(admin_user), json={"gia_chuan": 300000})
    assert r.status_code == 200, r.text
    db_session.expire_all()
    dong = await db_session.get(DongPhieuVatTu, d["id"])
    assert dong.gia_ban == 300000 and dong.khach_dong_y_luc is None


@pytest.mark.asyncio
async def test_bo_ncc_ten_y_het_nhung_da_ngung_thi_ve_ncc_dang_dung(db_session):
    ngung = Supplier(id=_uid(), name="Hiệp Phát", is_active=False, created_at=datetime(2026, 2, 1))
    dang_dung = Supplier(id=_uid(), name="Công ty TNHH Hiệp Phát", created_at=datetime(2026, 5, 1))
    db_session.add_all([ngung, dang_dung])
    await db_session.commit()
    assert (await BoNcc(db_session).lay("Hiệp Phát")).id == dang_dung.id
    # Không còn NCC đang dùng cùng khoá → vẫn về NCC đã ngừng, không tạo trùng
    dang_dung.name = "Daisan"
    await db_session.commit()
    assert (await BoNcc(db_session).lay("Hiệp Phát")).id == ngung.id
