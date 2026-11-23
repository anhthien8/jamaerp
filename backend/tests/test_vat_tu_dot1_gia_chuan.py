"""Vật tư Đợt 1 (22/11/2026) — «đơn giá là hằng số».

Mẫu có giá chuẩn thì bán đúng giá chuẩn (giá sỉ không kéo giá khách), khách duyệt được ngay khi
dòng có giá bán, lời đồng ý có hiệu lực tới khi giá bán đổi, giá chuẩn chỉ Admin ấn định.
"""
import json
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.customer import Customer
from app.models.notification import Notification
from app.models.vat_tu import BaoGiaDongVatTu, DongPhieuVatTu, GiaNhapMauVatTu, MauVatTu
from app.services import vat_tu_sheet
from tests.conftest import _uid, auth_header
from tests.test_vat_tu import du_an, mau, thiet_ke, thu_mua  # noqa: F401 — fixture dùng chung
from tests.test_vat_tu_dat_nhan_hang import ngay_hen

H = "/api/v1/vat-tu"
NCC = {"ncc_ten": "Hiệp Phát"}


@pytest_asyncio.fixture
async def mau_chuan(db_session: AsyncSession, mau) -> MauVatTu:  # noqa: F811
    """Mẫu TM 76006 (nhóm 60x60, hệ số 15%) đã được Giám đốc ấn định giá chuẩn 300.000đ."""
    mau.gia_ban_co_dinh = 300000
    await db_session.commit()
    return mau


@pytest_asyncio.fixture
async def khach(db_session: AsyncSession, du_an) -> Customer:  # noqa: F811
    c = Customer(id=_uid(), name="Anh Bảy", phone="0900000077", type="individual",
                 portal_token=str(uuid.uuid4()), portal_enabled=True)
    db_session.add(c)
    await db_session.flush()
    du_an.customer_id = c.id
    await db_session.commit()
    return c


async def _them(client, user, du_an, mau_id=None, **kw) -> dict:  # noqa: F811
    r = await client.post(f"{H}/du-an/{du_an.id}/dong", headers=auth_header(user),
                          json={"phong": "Bếp", "mau_id": mau_id, "so_luong": 10, **kw})
    assert r.status_code == 201, r.text
    return r.json()


async def _chot(client, user, dong_id, gia_von, **kw) -> dict:
    r = await client.post(f"{H}/dong/{dong_id}/chot", headers=auth_header(user), json={"gia_von": gia_von, **NCC, **kw})
    assert r.status_code == 200, r.text
    return r.json()


async def _dong_y(client, user, dong_id) -> dict:
    r = await client.post(f"{H}/dong/{dong_id}/khach-dong-y", headers=auth_header(user), json={"ghi_chu": "OK qua Zalo"})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
class TestGiaChuanLaHangSo:
    async def test_dong_y_truoc_khi_chot_van_dat_hang_duoc(self, client: AsyncClient, thu_mua, thiet_ke, sales_user,  # noqa: F811
                                                           du_an, mau_chuan, db_session):  # noqa: F811
        d = await _them(client, thiet_ke, du_an, mau_chuan.id)
        # Có giá bán ngay khi tạo dòng — chưa cần Thu mua chốt giá vốn
        assert d["gia_ban"] == 300000 and d["thanh_tien"] == 3_000_000 and d["trang_thai"] == "khach_chon"
        d = await _dong_y(client, sales_user, d["id"])
        assert d["khach_dong_y_luc"] and d["trang_thai"] == "khach_chon"
        assert (await db_session.get(DongPhieuVatTu, d["id"])).khach_dong_y_boi == sales_user.id
        d = await _chot(client, thu_mua, d["id"], 200000)
        assert d["gia_ban"] == 300000 and d["phan_tram_ap_dung"] is None and d["lai"] == 1_000_000
        assert d["khach_dong_y_luc"], "giá bán không đổi → lời đồng ý trước lúc chốt còn hiệu lực"
        r = await client.post(f"{H}/dong/{d['id']}/dat-hang", headers=auth_header(thu_mua), json={"ngay_giao_hen": ngay_hen()})
        assert r.status_code == 200, r.text
        assert r.json()["trang_thai"] == "da_dat"

    async def test_gia_von_cao_khong_keo_gia_khach_chi_admin_duoc_bao(self, client: AsyncClient, thu_mua, thiet_ke, sales_user,  # noqa: F811
                                                                       admin_user, du_an, mau_chuan, db_session):  # noqa: F811
        d = await _them(client, thiet_ke, du_an, mau_chuan.id)
        await _dong_y(client, sales_user, d["id"])
        # 290.000 × 1,15 = 333.500 > giá chuẩn 300.000: giá khách đứng yên, lời đồng ý không mất
        d = await _chot(client, thu_mua, d["id"], 290000)
        assert d["gia_ban"] == 300000 and d["khach_dong_y_luc"] and d["lai"] == 100_000
        ds = (await db_session.execute(select(Notification).where(Notification.title.like("Giá chuẩn cần xét lại%")))).scalars().all()
        assert [n.user_id for n in ds] == [admin_user.id], "chỉ Admin (Giám đốc) được báo — không Thu mua, không sale"
        n = ds[0]
        assert n.title == "Giá chuẩn cần xét lại · TM 76006" and n.ref_id == f"xet-gia-{mau_chuan.id}"
        assert n.link == "/vat-tu?tab=gia-chuan&loc=duoi_he_so"
        assert "290.000đ" in n.body and "300.000đ" in n.body and "15%" in n.body
        # Sale / thiết kế chỉ nhận tin «Đã chốt giá» với giá BÁN, không có giá vốn
        cua_sale = (await db_session.execute(select(Notification).where(Notification.user_id == sales_user.id))).scalars().all()
        assert cua_sale and all("290" not in (x.body or "") and "Giá chuẩn" not in x.title for x in cua_sale)

    async def test_gia_von_trong_he_so_thi_khong_bao(self, client: AsyncClient, thu_mua, du_an, mau_chuan, db_session):  # noqa: F811
        d = await _them(client, thu_mua, du_an, mau_chuan.id)
        await _chot(client, thu_mua, d["id"], 200000)  # 230.000 ≤ 300.000
        ds = (await db_session.execute(select(Notification).where(Notification.title.like("Giá chuẩn cần xét lại%")))).scalars().all()
        assert ds == []

    async def test_khach_da_dong_y_thi_gia_dong_bang_khi_giam_doc_doi_gia_chuan(self, client: AsyncClient, thu_mua, sales_user,  # noqa: F811
                                                                                 du_an, mau_chuan, db_session):  # noqa: F811
        da_dong_y = await _them(client, thu_mua, du_an, mau_chuan.id)
        chua_dong_y = await _them(client, thu_mua, du_an, mau_chuan.id)
        await _dong_y(client, sales_user, da_dong_y["id"])
        mau_chuan.gia_ban_co_dinh = 350000  # Giám đốc đổi giá chuẩn sau đó
        await db_session.commit()
        d = await _chot(client, thu_mua, da_dong_y["id"], 200000)
        assert d["gia_ban"] == 300000 and d["khach_dong_y_luc"], "khách đã đồng ý 300.000 → giữ nguyên"
        d = await _chot(client, thu_mua, chua_dong_y["id"], 200000)
        assert d["gia_ban"] == 350000 and d["khach_dong_y_luc"] is None, "chưa đồng ý → lấy giá chuẩn hiện tại"

    async def test_mau_chua_co_gia_chuan_van_von_cong_phan_tram(self, client: AsyncClient, thu_mua, sales_user, du_an, mau):  # noqa: F811
        d = await _them(client, thu_mua, du_an, mau.id)
        assert d["gia_ban"] is None
        # Chưa có giá bán thì chưa có gì để khách đồng ý
        r = await client.post(f"{H}/dong/{d['id']}/khach-dong-y", headers=auth_header(sales_user), json={"ghi_chu": "ok"})
        assert r.status_code == 400 and "chưa có giá bán" in r.json()["detail"]
        d = await _chot(client, thu_mua, d["id"], 200000)
        assert d["gia_ban"] == 230000 and d["phan_tram_ap_dung"] == 15 and d["khach_dong_y_luc"] is None
        r = await client.post(f"{H}/dong/{d['id']}/dat-hang", headers=auth_header(thu_mua), json={"ngay_giao_hen": ngay_hen()})
        assert r.status_code == 400 and "Khách chưa đồng ý" in r.json()["detail"]
        await _dong_y(client, sales_user, d["id"])
        # Chốt lại đúng giá cũ → giá bán không đổi → lời đồng ý còn
        d = await _chot(client, thu_mua, d["id"], 200000)
        assert d["gia_ban"] == 230000 and d["khach_dong_y_luc"]
        # Chốt lại giá khác → giá bán đổi → khách phải duyệt lại, chưa đặt hàng được
        d = await _chot(client, thu_mua, d["id"], 210000)
        assert d["gia_ban"] == 241500 and d["khach_dong_y_luc"] is None
        r = await client.post(f"{H}/dong/{d['id']}/dat-hang", headers=auth_header(thu_mua), json={"ngay_giao_hen": ngay_hen()})
        assert r.status_code == 400 and "Khách chưa đồng ý" in r.json()["detail"]

    async def test_doi_mau_tinh_lai_gia(self, client: AsyncClient, thu_mua, sales_user, du_an, mau_chuan, db_session):  # noqa: F811
        cung_gia = MauVatTu(ma="TM 1", nhom="60x60", gia_ban_co_dinh=300000)
        dat_hon = MauVatTu(ma="TM 2", nhom="60x60", gia_ban_co_dinh=350000)
        chua_gia = MauVatTu(ma="TM 3", nhom="60x60")
        db_session.add_all([cung_gia, dat_hon, chua_gia])
        await db_session.commit()
        d = await _them(client, thu_mua, du_an, mau_chuan.id)
        await _dong_y(client, sales_user, d["id"])
        url, h = f"{H}/dong/{d['id']}", auth_header(sales_user)
        r = await client.patch(url, headers=h, json={"mau_id": cung_gia.id})
        assert r.json()["gia_ban"] == 300000 and r.json()["khach_dong_y_luc"], "giá không đổi → còn đồng ý"
        r = await client.patch(url, headers=h, json={"mau_id": dat_hon.id})
        assert r.json()["gia_ban"] == 350000 and r.json()["khach_dong_y_luc"] is None
        r = await client.patch(url, headers=h, json={"mau_id": chua_gia.id})
        assert r.json()["gia_ban"] is None  # mẫu chưa có giá chuẩn, dòng chưa chốt giá vốn
        assert (await client.patch(url, headers=h, json={"mau_id": _uid()})).status_code == 404

    async def test_doi_mau_la_het_chot_gia_von(self, client: AsyncClient, thu_mua, sales_user, du_an, mau_chuan, db_session):  # noqa: F811
        """Đổi mẫu / mã của dòng đã chốt: giá vốn, NCC, báo giá đang chốt là của mẫu CŨ → bỏ, dòng về «hỏi NCC».
        Không suy giá bán mẫu mới từ giá vốn mẫu cũ (sale gõ một mã lạ là đọc ngược ra giá vốn)."""
        cung_gia = MauVatTu(ma="TM 1", nhom="60x60", gia_ban_co_dinh=300000)
        db_session.add(cung_gia)
        await db_session.commit()
        d = await _them(client, thu_mua, du_an, mau_chuan.id)
        await _chot(client, thu_mua, d["id"], 200000)
        await _dong_y(client, sales_user, d["id"])
        url, hs = f"{H}/dong/{d['id']}", auth_header(sales_user)
        dat = {"headers": auth_header(thu_mua), "json": {"ngay_giao_hen": ngay_hen()}}
        # Sale đổi sang mã tự do: KHÔNG ra 230.000 (200.000 × 1,15) — chưa có giá tới khi Thu mua chốt lại
        r = await client.patch(url, headers=hs, json={"mau_id": None, "ma_tu_do": "Gạch ngoài danh mục"})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["gia_ban"] is None and j["thanh_tien"] is None
        assert j["trang_thai"] == "hoi_ncc" and j["khach_dong_y_luc"] is None
        dong = await db_session.get(DongPhieuVatTu, d["id"])
        assert (dong.gia_von, dong.ncc_id, dong.phan_tram_ap_dung, dong.chot_boi, dong.chot_luc, dong.gia_xac_nhan_luc) == (None,) * 6
        bg = (await db_session.execute(select(BaoGiaDongVatTu).where(BaoGiaDongVatTu.dong_id == d["id"]))).scalars().all()
        assert bg == [], "báo giá của mẫu cũ rời khỏi dòng (thành giá nhập của mẫu cũ)"
        gn = (await db_session.execute(select(GiaNhapMauVatTu))).scalars().all()
        assert [(g.mau_id, g.gia) for g in gn] == [(mau_chuan.id, 200000)]
        r = await client.post(f"{H}/dong/{d['id']}/dat-hang", **dat)
        assert r.status_code == 400 and "đã chốt giá" in r.json()["detail"]
        # Đổi về mẫu cũ: có lại giá chuẩn, nhưng giá vốn phải chốt lại
        r = await client.patch(url, headers=hs, json={"mau_id": mau_chuan.id})
        assert r.json()["gia_ban"] == 300000 and r.json()["trang_thai"] == "hoi_ncc"
        # Dòng đã chốt + khách đã đồng ý, đổi sang mẫu khác CÙNG giá chuẩn: giá bán không đổi nên lời đồng ý
        # còn, nhưng không đặt hàng mẫu mới bằng giá vốn / NCC của mẫu cũ được
        await _chot(client, thu_mua, d["id"], 200000)
        await _dong_y(client, sales_user, d["id"])
        r = await client.patch(url, headers=hs, json={"mau_id": cung_gia.id})
        j = r.json()
        assert j["gia_ban"] == 300000 and j["khach_dong_y_luc"] and j["trang_thai"] == "hoi_ncc"
        assert (await client.post(f"{H}/dong/{d['id']}/dat-hang", **dat)).status_code == 400
        assert dong.gia_von is None and dong.ncc_id is None
        # Thu mua (thấy giá vốn) đổi mẫu cũng vậy: không còn giá vốn nào để hiện
        d2 = await _them(client, thu_mua, du_an, mau_chuan.id)
        await _chot(client, thu_mua, d2["id"], 200000)
        r = await client.patch(f"{H}/dong/{d2['id']}", headers=auth_header(thu_mua), json={"mau_id": cung_gia.id})
        j = r.json()
        assert (j["gia_von"], j["ncc_id"], j["lai"], j["trang_thai"]) == (None, None, None, "hoi_ncc")
        assert j["bao_gia"] == []  # báo giá mẫu cũ đã thành giá nhập của mẫu cũ

    async def test_khach_nhan_mau_thay_tren_dong_da_chot_khong_lo_gia_von(self, client: AsyncClient, thu_mua, thiet_ke,  # noqa: F811
                                                                           du_an, mau_chuan, db_session):  # noqa: F811
        chua_gia = MauVatTu(ma="TM 3", nhom="60x60")
        db_session.add(chua_gia)
        await db_session.commit()
        d = await _them(client, thiet_ke, du_an, mau_chuan.id)
        await _chot(client, thu_mua, d["id"], 200000)
        r = await client.patch(f"{H}/dong/{d['id']}", headers=auth_header(thu_mua),
                               json={"trang_thai": "het_hang", "mau_thay_the_id": chua_gia.id})
        assert r.status_code == 200 and r.json()["gia_von"] == 200000  # báo hết hàng chưa đổi mẫu → chưa bỏ gì
        d = await _dong_y(client, thiet_ke, d["id"])
        assert d["trang_thai"] == "hoi_ncc" and d["mau_id"] == chua_gia.id
        assert d["gia_ban"] is None and d["khach_dong_y_luc"] is None, "không phải 230.000 = giá vốn mẫu cũ × 1,15"
        dong = await db_session.get(DongPhieuVatTu, d["id"])
        assert dong.gia_von is None and dong.ncc_id is None and dong.gia_xac_nhan_luc is None

    async def test_giam_doc_doi_gia_chuan_ap_ngay_cho_dong_khach_chua_dong_y(self, client: AsyncClient, admin_user, thu_mua,  # noqa: F811
                                                                              sales_user, du_an, mau_chuan, db_session):  # noqa: F811
        """Giá chuẩn đổi → dòng chưa đặt hàng mà khách chưa đồng ý lấy ngay giá mới. Bấm «khách đồng ý»
        trước hay sau lúc Giám đốc đổi giá không còn cho ra hai giá khác nhau."""
        khac = MauVatTu(ma="TM 9", nhom="60x60", gia_ban_co_dinh=300000)
        db_session.add(khac)
        await db_session.commit()
        ha, ht = auth_header(admin_user), auth_header(thu_mua)
        dat = {"headers": ht, "json": {"ngay_giao_hen": ngay_hen()}}
        da_dong_y = (await _them(client, thu_mua, du_an, mau_chuan.id))["id"]
        await _dong_y(client, sales_user, da_dong_y)
        moi = (await _them(client, thu_mua, du_an, mau_chuan.id))["id"]              # khách chọn, chưa đồng ý
        da_chot = (await _them(client, thu_mua, du_an, mau_chuan.id))["id"]          # đã chốt giá vốn, chưa đồng ý
        await _chot(client, thu_mua, da_chot, 200000)
        da_dat = (await _them(client, thu_mua, du_an, mau_chuan.id))["id"]
        await _dong_y(client, sales_user, da_dat)
        await _chot(client, thu_mua, da_dat, 200000)
        assert (await client.post(f"{H}/dong/{da_dat}/dat-hang", **dat)).json()["trang_thai"] == "da_dat"
        mau_khac = (await _them(client, thu_mua, du_an, khac.id))["id"]
        da_huy = (await _them(client, thu_mua, du_an, mau_chuan.id))["id"]
        assert (await client.patch(f"{H}/dong/{da_huy}", headers=ht, json={"trang_thai": "huy"})).status_code == 200

        async def gia() -> dict:
            items = (await client.get(f"{H}/du-an/{du_an.id}/dong", headers=ht)).json()["items"]
            return {i["id"]: i["gia_ban"] for i in items}

        # Lối 1: Bảng giá chuẩn
        r = await client.put(f"{H}/gia-chuan/{mau_chuan.id}", headers=ha, json={"gia_chuan": 350000})
        assert r.status_code == 200, r.text
        assert await gia() == {moi: 350000, da_chot: 350000,
                               da_dong_y: 300000, da_dat: 300000, mau_khac: 300000, da_huy: 300000}
        log = (await db_session.execute(select(AuditLog).where(AuditLog.action == "vat_tu.gia_chuan"))).scalars().all()
        assert len(log) == 1 and json.loads(log[0].after_json) == {"gia_ban_co_dinh": 350000, "so_dong_doi_gia": 2}
        # Bấm đồng ý SAU khi đổi giá = đồng ý giá mới; chốt rồi đặt hàng đi đúng 350.000
        assert (await _dong_y(client, sales_user, moi))["gia_ban"] == 350000
        d = await _chot(client, thu_mua, moi, 200000)
        assert d["gia_ban"] == 350000 and d["khach_dong_y_luc"]
        r = await client.post(f"{H}/dong/{moi}/dat-hang", **dat)
        assert r.status_code == 200 and r.json()["trang_thai"] == "da_dat" and r.json()["gia_ban"] == 350000
        # Lối 2: Admin sửa mẫu ở Danh mục cũng áp ngay và ghi nhật ký; Thu mua sửa mẫu thì giá chuẩn đứng yên
        co_ban = {"ma": "TM 76006", "nhom": "60x60"}
        r = await client.put(f"{H}/mau/{mau_chuan.id}", headers=ha, json={**co_ban, "gia_ban_co_dinh": 360000})
        assert r.status_code == 200 and (await gia())[da_chot] == 360000
        r = await client.put(f"{H}/mau/{mau_chuan.id}", headers=ht, json={**co_ban, "gia_ban_co_dinh": 1})
        assert r.status_code == 200 and (await gia())[da_chot] == 360000
        log = (await db_session.execute(select(AuditLog).where(AuditLog.action == "vat_tu.gia_chuan")
                                        .order_by(AuditLog.created_at))).scalars().all()
        assert [json.loads(x.after_json)["gia_ban_co_dinh"] for x in log] == [350000, 360000]
        assert json.loads(log[1].before_json) == {"ma": "TM 76006", "gia_ban_co_dinh": 350000}
        # Bỏ giá chuẩn: dòng đã chốt giá vốn → vốn × (1 + % nhóm); dòng chưa chốt → chưa có giá
        chua_chot = (await _them(client, thu_mua, du_an, mau_chuan.id))["id"]
        r = await client.put(f"{H}/gia-chuan/{mau_chuan.id}", headers=ha, json={"gia_chuan": None})
        assert r.status_code == 200, r.text
        g = await gia()
        assert (g[da_chot], g[chua_chot], g[da_dong_y], g[moi]) == (230000, None, 300000, 350000)
        assert (await db_session.get(DongPhieuVatTu, da_chot)).phan_tram_ap_dung == 15

    async def test_tao_mau_co_gia_chuan_cung_ghi_nhat_ky(self, client: AsyncClient, admin_user, thu_mua, db_session):  # noqa: F811
        r = await client.post(f"{H}/mau", headers=auth_header(thu_mua), json={"ma": "X0", "nhom": "80x80", "gia_ban_co_dinh": 1})
        assert r.status_code == 201
        r = await client.post(f"{H}/mau", headers=auth_header(admin_user), json={"ma": "X2", "nhom": "80x80", "gia_ban_co_dinh": 700000})
        assert r.status_code == 201
        log = (await db_session.execute(select(AuditLog).where(AuditLog.action == "vat_tu.gia_chuan"))).scalars().all()
        assert len(log) == 1 and log[0].entity_id == r.json()["id"] and log[0].actor_id == admin_user.id
        assert json.loads(log[0].before_json) == {"ma": "X2", "gia_ban_co_dinh": None}

    async def test_go_tay_ma_trong_danh_muc_thi_gan_mau_va_don_vi_theo_mau(self, client: AsyncClient, thu_mua, sales_user,  # noqa: F811
                                                                           du_an, mau_chuan, db_session):  # noqa: F811
        """Gõ tay đúng mã một mẫu trong danh mục không lách được giá chuẩn; đơn vị của dòng có mẫu đi theo mẫu."""
        khac = MauVatTu(ma="LAV 1", nhom="TBVS", don_vi="cái", gia_ban_co_dinh=900000)
        ngung = MauVatTu(ma="CU 01", nhom="60x60", gia_ban_co_dinh=500000, is_active=False)
        db_session.add_all([khac, ngung])
        await db_session.commit()
        hs = auth_header(sales_user)
        d = await _them(client, sales_user, du_an, ma_tu_do="tm-76006", don_vi="thùng")
        assert d["mau_id"] == mau_chuan.id and d["ma_tu_do"] is None and d["ma"] == "TM 76006"
        assert d["gia_ban"] == 300000 and d["don_vi"] == "m2"
        assert (await _chot(client, thu_mua, d["id"], 200000))["gia_ban"] == 300000, "không thành 200.000 × 1,15"
        # PATCH bỏ mẫu rồi gõ mã của mẫu khác trong danh mục → gắn mẫu đó, giá + đơn vị theo mẫu đó
        d2 = await _them(client, sales_user, du_an, mau_chuan.id)
        r = await client.patch(f"{H}/dong/{d2['id']}", headers=hs, json={"mau_id": None, "ma_tu_do": "lav 1"})
        j = r.json()
        assert r.status_code == 200 and j["mau_id"] == khac.id and j["ma_tu_do"] is None
        assert j["gia_ban"] == 900000 and j["don_vi"] == "cái"
        # Gõ đơn vị khác cho dòng có mẫu: không báo lỗi, máy chủ giữ đơn vị của mẫu; lời đồng ý không mất
        await _dong_y(client, sales_user, d2["id"])
        r = await client.patch(f"{H}/dong/{d2['id']}", headers=hs, json={"don_vi": "thùng", "so_luong": 3})
        j = r.json()
        assert r.status_code == 200 and j["don_vi"] == "cái" and j["so_luong"] == 3 and j["khach_dong_y_luc"]
        # Mã ngoài danh mục (hoặc trùng mã mẫu đã ngừng dùng): vẫn là mã tự do, đơn vị tự do
        for ma in ("Lavabo L-333", "CU 01"):
            d3 = await _them(client, sales_user, du_an, ma_tu_do=ma, don_vi="bộ")
            assert d3["mau_id"] is None and d3["ma_tu_do"] == ma and d3["gia_ban"] is None and d3["don_vi"] == "bộ"
        r = await client.patch(f"{H}/dong/{d3['id']}", headers=hs, json={"don_vi": "thùng"})
        assert r.json()["don_vi"] == "thùng"

    async def test_khach_dong_y_khong_ghi_de_va_khong_ghi_tren_dong_da_dat_da_huy(self, client: AsyncClient, thu_mua, thiet_ke,  # noqa: F811
                                                                                   sales_user, du_an, mau_chuan, khach, db_session):  # noqa: F811
        d = await _them(client, thu_mua, du_an, mau_chuan.id)
        r = await client.post(f"/api/v1/portal/{khach.portal_token}/vat-tu/{d['id']}/dong-y", json={"ghi_chu": "ok"})
        assert r.json()["khach_dong_y_luc"]
        dong = await client.get(f"{H}/du-an/{du_an.id}/dong", headers=auth_header(thu_mua))
        truoc = {k: dong.json()["items"][0][k] for k in ("khach_dong_y_luc", "khach_ghi_chu")}
        assert truoc["khach_ghi_chu"] == "[Khách tự bấm] ok"
        url = f"{H}/dong/{d['id']}/khach-dong-y"

        async def con_nguyen() -> bool:
            x = (await client.get(f"{H}/du-an/{du_an.id}/dong", headers=auth_header(thu_mua))).json()["items"][0]
            khach_tu_bam = (await db_session.get(DongPhieuVatTu, d["id"])).khach_dong_y_boi is None
            return khach_tu_bam and {k: x[k] for k in truoc} == truoc

        # Khách đã đồng ý, không còn gì chờ duyệt: nhân viên bấm lại → trả nguyên trạng, không ghi đè
        r = await client.post(url, headers=auth_header(thiet_ke), json={"ghi_chu": "ghi đè"})
        assert r.status_code == 200 and r.json()["khach_ghi_chu"] == "[Khách tự bấm] ok" and await con_nguyen()
        await _chot(client, thu_mua, d["id"], 200000)
        r = await client.post(f"{H}/dong/{d['id']}/dat-hang", headers=auth_header(thu_mua), json={"ngay_giao_hen": ngay_hen()})
        assert r.json()["trang_thai"] == "da_dat"
        # Đã đặt hàng → 400, lời đồng ý (ai ghi, lúc nào, qua kênh nào) còn nguyên
        r = await client.post(url, headers=auth_header(sales_user), json={})
        assert r.status_code == 400 and "đã đặt hàng" in r.json()["detail"] and await con_nguyen()
        # Dòng đã huỷ → 400
        d2 = await _them(client, thu_mua, du_an, mau_chuan.id)
        await client.patch(f"{H}/dong/{d2['id']}", headers=auth_header(sales_user), json={"trang_thai": "huy"})
        r = await client.post(f"{H}/dong/{d2['id']}/khach-dong-y", headers=auth_header(sales_user), json={})
        assert r.status_code == 400

    async def test_tong_phieu_khong_tinh_dong_da_huy(self, client: AsyncClient, thu_mua, sales_user, du_an, mau_chuan):  # noqa: F811
        a = await _them(client, thu_mua, du_an, mau_chuan.id)              # 10 × 300.000, chưa chốt
        b = await _them(client, thu_mua, du_an, mau_chuan.id)
        await _chot(client, thu_mua, b["id"], 200000)                      # lãi 1.000.000
        ht = auth_header(thu_mua)
        j = (await client.get(f"{H}/du-an/{du_an.id}/dong", headers=ht)).json()
        assert (j["tong_gia_ban"], j["tong_lai"]) == (6_000_000, 1_000_000)
        for x in (a, b):
            assert (await client.patch(f"{H}/dong/{x['id']}", headers=ht, json={"trang_thai": "huy"})).status_code == 200
        j = (await client.get(f"{H}/du-an/{du_an.id}/dong", headers=ht)).json()
        assert len(j["items"]) == 2 and (j["tong_gia_ban"], j["tong_lai"]) == (0, 0)
        assert (await client.get(f"{H}/du-an/{du_an.id}/dong", headers=auth_header(sales_user))).json()["tong_gia_ban"] == 0

    async def test_khach_nhan_mau_thay_gia_theo_mau_moi(self, client: AsyncClient, thu_mua, thiet_ke, du_an, mau_chuan, db_session):  # noqa: F811
        cung_gia = MauVatTu(ma="TM 1", nhom="60x60", gia_ban_co_dinh=300000)
        dat_hon = MauVatTu(ma="TM 2", nhom="60x60", gia_ban_co_dinh=320000)
        db_session.add_all([cung_gia, dat_hon])
        await db_session.commit()
        for thay, gia, con_dong_y in ((cung_gia, 300000, True), (dat_hon, 320000, False)):
            d = await _them(client, thiet_ke, du_an, mau_chuan.id)
            r = await client.patch(f"{H}/dong/{d['id']}", headers=auth_header(thu_mua),
                                   json={"trang_thai": "het_hang", "mau_thay_the_id": thay.id, "ly_do_doi": "NCC ngưng"})
            assert r.status_code == 200, r.text
            d = await _dong_y(client, thiet_ke, d["id"])
            assert d["trang_thai"] == "hoi_ncc" and d["mau_id"] == thay.id and d["gia_ban"] == gia
            # Cú bấm này ghi lời đồng ý; giá đổi theo mẫu mới thì bị xoá để khách duyệt lại GIÁ
            assert bool(d["khach_dong_y_luc"]) is con_dong_y


@pytest.mark.asyncio
class TestChiAdminCaiGiaChuan:
    async def test_tao_sua_mau(self, client: AsyncClient, admin_user, thu_mua, db_session):  # noqa: F811
        r = await client.post(f"{H}/mau", headers=auth_header(thu_mua), json={"ma": "X1", "nhom": "80x80", "gia_ban_co_dinh": 500000})
        assert r.status_code == 201 and r.json()["gia_ban_co_dinh"] is None, "Thu mua gửi giá chuẩn → bỏ qua"
        mau_id = r.json()["id"]
        r = await client.put(f"{H}/mau/{mau_id}", headers=auth_header(admin_user), json={"ma": "X1", "nhom": "80x80", "gia_ban_co_dinh": 500000})
        assert r.status_code == 200 and r.json()["gia_ban_co_dinh"] == 500000
        # Thu mua sửa mẫu (đổi giá chuẩn, hoặc không gửi trường này) → giá chuẩn đang lưu giữ nguyên
        for body in ({"ma": "X1", "nhom": "80x80", "gia_ban_co_dinh": 1}, {"ma": "X1 mới", "nhom": "80x80"}):
            r = await client.put(f"{H}/mau/{mau_id}", headers=auth_header(thu_mua), json=body)
            assert r.status_code == 200 and r.json()["gia_ban_co_dinh"] == 500000
        assert r.json()["ma"] == "X1 mới"
        r = await client.post(f"{H}/mau", headers=auth_header(admin_user), json={"ma": "X2", "nhom": "80x80", "gia_ban_co_dinh": 700000})
        assert r.status_code == 201 and r.json()["gia_ban_co_dinh"] == 700000

    async def test_nhap_sheet(self, client: AsyncClient, admin_user, thu_mua, db_session, monkeypatch):  # noqa: F811
        db_session.add(MauVatTu(ma="CU", nhom="60x60", gia_ban_co_dinh=300000))
        await db_session.commit()

        async def gia_doc_sheet(url, bo_qua_tab=("FROM",)):
            return [{"ma": "CU", "nhom": "60x60", "gia_ban_co_dinh": 111.0}, {"ma": "MOI", "nhom": "60x60", "gia_ban_co_dinh": 222.0}]

        async def gia_chuan() -> dict:
            return {m.ma: m.gia_ban_co_dinh for m in (await db_session.execute(
                select(MauVatTu).execution_options(populate_existing=True))).scalars()}

        monkeypatch.setattr(vat_tu_sheet, "doc_sheet", gia_doc_sheet)
        body = {"url": "https://docs.google.com/spreadsheets/d/abc/edit", "ghi_de": True}
        r = await client.post(f"{H}/mau/import-sheet", headers=auth_header(thu_mua), json=body)
        assert r.status_code == 200, r.text
        assert await gia_chuan() == {"CU": 300000, "MOI": None}, "Thu mua nhập sheet không đụng được giá chuẩn"
        r = await client.post(f"{H}/mau/import-sheet", headers=auth_header(admin_user), json=body)
        assert r.status_code == 200, r.text
        assert await gia_chuan() == {"CU": 111, "MOI": 222}
        log = (await db_session.execute(select(AuditLog).where(AuditLog.action == "vat_tu.gia_chuan"))).scalars().all()
        assert sorted(json.loads(x.after_json)["gia_ban_co_dinh"] for x in log) == [111, 222]
        assert {x.actor_id for x in log} == {admin_user.id}


@pytest.mark.asyncio
class TestPortalKhachDuyet:
    async def test_co_gia_ban_la_duyet_duoc_truoc_khi_chot(self, client: AsyncClient, thu_mua, du_an, mau, mau_chuan, khach, db_session):  # noqa: F811
        co_gia = await _them(client, thu_mua, du_an, mau_chuan.id)
        chua_gia = await _them(client, thu_mua, du_an, ma_tu_do="Lavabo L-333")
        p = f"/api/v1/portal/{khach.portal_token}"
        rows = {x["id"]: x for x in (await client.get(f"{p}/projects/{du_an.id}/vat-tu")).json()}
        assert rows[co_gia["id"]]["cho_khach_duyet"] is True and rows[co_gia["id"]]["gia_ban"] == 300000
        assert rows[chua_gia["id"]]["cho_khach_duyet"] is False
        for cam in ("gia_von", "ncc_id", "ncc_ten", "phan_tram_ap_dung", "bao_gia", "lai"):
            assert cam not in rows[co_gia["id"]]
        # Dòng chưa có giá: bấm cũng không ghi gì
        r = await client.post(f"{p}/vat-tu/{chua_gia['id']}/dong-y", json={})
        assert r.status_code == 200 and r.json()["khach_dong_y_luc"] is None
        r = await client.post(f"{p}/vat-tu/{co_gia['id']}/dong-y", json={"ghi_chu": "Ok"})
        assert r.status_code == 200 and r.json()["khach_dong_y_luc"] and r.json()["cho_khach_duyet"] is False
        luc = r.json()["khach_dong_y_luc"]
        d = await db_session.get(DongPhieuVatTu, co_gia["id"])
        await db_session.refresh(d)
        assert d.khach_dong_y_boi is None and d.khach_ghi_chu == "[Khách tự bấm] Ok"
        # Thu mua chốt giá vốn SAU đó: khách không phải duyệt lại, đặt hàng được
        await _chot(client, thu_mua, co_gia["id"], 200000)
        rows = {x["id"]: x for x in (await client.get(f"{p}/projects/{du_an.id}/vat-tu")).json()}
        assert rows[co_gia["id"]]["cho_khach_duyet"] is False and rows[co_gia["id"]]["trang_thai"] == "da_chot_gia"
        r = await client.post(f"{H}/dong/{co_gia['id']}/dat-hang", headers=auth_header(thu_mua), json={"ngay_giao_hen": ngay_hen()})
        assert r.status_code == 200 and r.json()["trang_thai"] == "da_dat"
        # Bấm lại khi không còn gì chờ duyệt → không ghi đè lời đồng ý cũ
        r = await client.post(f"{p}/vat-tu/{co_gia['id']}/dong-y", json={"ghi_chu": "lần 2"})
        assert r.status_code == 200 and r.json()["khach_dong_y_luc"] == luc
        await db_session.refresh(d)
        assert d.khach_ghi_chu == "[Khách tự bấm] Ok"

    async def test_khach_nhan_mau_thay_tren_portal_gia_doi_thi_duyet_lai(self, client: AsyncClient, thu_mua, du_an, mau_chuan, khach, db_session):  # noqa: F811
        dat_hon = MauVatTu(ma="TM 2", nhom="60x60", gia_ban_co_dinh=320000)
        db_session.add(dat_hon)
        await db_session.commit()
        d = await _them(client, thu_mua, du_an, mau_chuan.id)
        r = await client.patch(f"{H}/dong/{d['id']}", headers=auth_header(thu_mua),
                               json={"trang_thai": "het_hang", "mau_thay_the_id": dat_hon.id})
        assert r.status_code == 200, r.text
        p = f"/api/v1/portal/{khach.portal_token}"
        r = await client.post(f"{p}/vat-tu/{d['id']}/dong-y", json={})
        j = r.json()
        assert j["trang_thai"] == "hoi_ncc" and j["gia_ban"] == 320000 and j["thay_the"] is None
        assert j["khach_dong_y_luc"] is None and j["cho_khach_duyet"] is True, "nhận mẫu thay nhưng giá đổi → duyệt giá mới"
        r = await client.post(f"{p}/vat-tu/{d['id']}/dong-y", json={})
        assert r.json()["khach_dong_y_luc"] and r.json()["cho_khach_duyet"] is False

    async def test_portal_nhan_mau_thay_tren_dong_da_chot_khong_suy_gia_tu_gia_von_cu(self, client: AsyncClient, thu_mua, du_an,  # noqa: F811
                                                                                       mau_chuan, khach, db_session):  # noqa: F811
        chua_gia = MauVatTu(ma="TM 3", nhom="60x60")
        db_session.add(chua_gia)
        await db_session.commit()
        d = await _them(client, thu_mua, du_an, mau_chuan.id)
        await _chot(client, thu_mua, d["id"], 200000)
        r = await client.patch(f"{H}/dong/{d['id']}", headers=auth_header(thu_mua),
                               json={"trang_thai": "het_hang", "mau_thay_the_id": chua_gia.id})
        assert r.status_code == 200, r.text
        r = await client.post(f"/api/v1/portal/{khach.portal_token}/vat-tu/{d['id']}/dong-y", json={})
        j = r.json()
        assert r.status_code == 200 and j["trang_thai"] == "hoi_ncc" and j["thay_the"] is None
        assert j["gia_ban"] is None and j["thanh_tien"] is None, "không hiện 230.000 = giá vốn mẫu cũ × 1,15 cho khách"
        assert j["cho_khach_duyet"] is False and j["khach_dong_y_luc"] is None  # chưa có giá → chưa có gì để duyệt
        dong = await db_session.get(DongPhieuVatTu, d["id"])
        assert dong.gia_von is None and dong.ncc_id is None
