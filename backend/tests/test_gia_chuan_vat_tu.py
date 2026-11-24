"""Bảng giá chuẩn (22/11/2026): gác quyền theo vai, bộ lọc, gộp giá nhập mới nhất của từng NCC
từ hai nguồn, giá gợi ý / mức lời / cờ «chưa có» – «dưới hệ số», đặt giá chuẩn, nạp và xoá giá nhập."""

import json
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.auth import hash_password
from app.models.audit import AuditLog
from app.models.supplier import Supplier
from app.models.user import User
from app.models.vat_tu import BaoGiaDongVatTu, DongPhieuVatTu, GiaNhapMauVatTu, GiaNhomVatTu, MauVatTu
from app.services.gia_nhap_vat_tu import gia_nhap_theo_mau
from tests.conftest import _uid, auth_header

URL = "/api/v1/vat-tu/gia-chuan"


def _truoc(ngay: int) -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=ngay)


async def _nguoi(db: AsyncSession, role: str, department: str) -> User:
    u = User(id=_uid(), full_name=f"{role} {department}", email=f"{_uid()}@test.com", password_hash=hash_password("x"),
             role=role, department=department, is_active=True)
    db.add(u)
    await db.commit()
    return u


@pytest_asyncio.fixture
async def thu_mua(db_session: AsyncSession) -> User:
    return await _nguoi(db_session, "data_entry", "PURCHASING")


@pytest_asyncio.fixture
async def thu_mua_2(db_session: AsyncSession) -> User:
    return await _nguoi(db_session, "data_entry", "PURCHASING")


@pytest_asyncio.fixture
async def ncc(db_session: AsyncSession) -> dict[str, Supplier]:
    ds = {
        "an": Supplier(id=_uid(), name="NCC An"),
        "binh": Supplier(id=_uid(), name="NCC Bình", hang="chinh"),
        "cuong": Supplier(id=_uid(), name="NCC Cường"),
        "ngung": Supplier(id=_uid(), name="NCC Đã Ngừng", is_active=False),
    }
    db_session.add_all(ds.values())
    await db_session.commit()
    return ds


@pytest_asyncio.fixture
async def bang(db_session: AsyncSession, ncc) -> dict[str, MauVatTu]:
    """5 mẫu: dưới hệ số · đúng hệ số · chưa có giá chuẩn (có giá NCC) · chưa có gì · đã ngừng."""
    ds = {
        "duoi": MauVatTu(id=_uid(), ma="A-01", hang="Taicera", nhom="60x60", gia_von_gan_nhat=200000,
                         gia_von_cap_nhat_luc=_truoc(10), ncc_gan_nhat_ten="NCC An", gia_ban_co_dinh=220000,
                         gia_tham_khao=280000),
        "du": MauVatTu(id=_uid(), ma="A-02", hang="Taicera", nhom="60x60", gia_von_gan_nhat=200000,
                       gia_von_cap_nhat_luc=_truoc(70), gia_ban_co_dinh=230000),
        "chua": MauVatTu(id=_uid(), ma="B-01", ten="Gach van da", hang="Viglacera", nhom="80x80"),
        "trong": MauVatTu(id=_uid(), ma="C-01", hang="Inax", nhom="TBVS", don_vi="cái"),
        "ngung": MauVatTu(id=_uid(), ma="Z-99", nhom="60x60", is_active=False),
    }
    db_session.add_all(ds.values())
    db_session.add_all([GiaNhomVatTu(nhom="60x60", phan_tram_lai=15), GiaNhomVatTu(nhom="80x80", phan_tram_lai=20)])
    db_session.add_all([
        GiaNhapMauVatTu(mau_id=ds["chua"].id, supplier_id=ncc["an"].id, gia=190000, created_at=_truoc(3)),
        GiaNhapMauVatTu(mau_id=ds["chua"].id, supplier_id=ncc["binh"].id, gia=180000, created_at=_truoc(2)),
    ])
    await db_session.commit()
    return ds


async def _lay(client: AsyncClient, user: User, **params) -> dict:
    r = await client.get(URL, headers=auth_header(user), params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _theo_ma(body: dict) -> dict[str, dict]:
    return {x["ma"]: x for x in body["items"]}


@pytest.mark.asyncio
class TestQuyen:
    async def test_chi_thu_mua_va_admin_doc_duoc(self, client: AsyncClient, db_session, admin_user, sales_user,
                                                 designer_user, thu_mua, bang, ncc):
        """Bảng toàn giá vốn + NCC + mức lời: sale, thiết kế, giám sát, cả TRƯỞNG PHÒNG Kinh doanh /
        Thiết kế và executive (những vai `xem_gia_von` cho qua) đều bị chặn ở mọi endpoint."""
        mau_id = bang["chua"].id
        g = GiaNhapMauVatTu(id=_uid(), mau_id=mau_id, supplier_id=ncc["an"].id, gia=1, created_by=thu_mua.id)
        db_session.add(g)
        await db_session.commit()
        cam = [sales_user, designer_user, await _nguoi(db_session, "data_entry", "DESIGN"),
               await _nguoi(db_session, "leader", "SALES"), await _nguoi(db_session, "leader", "DESIGN"),
               await _nguoi(db_session, "executive", "EXEC"), await _nguoi(db_session, "accountant", "ACCT")]
        for u in cam:
            h = auth_header(u)
            assert (await client.get(URL, headers=h)).status_code == 403, u.full_name
            assert (await client.put(f"{URL}/{mau_id}", headers=h, json={"gia_chuan": 1})).status_code == 403
            r = await client.post(f"{URL}/{mau_id}/gia-nhap", headers=h, json={"supplier_id": ncc["an"].id, "gia": 1})
            assert r.status_code == 403
            assert (await client.delete(f"{URL}/gia-nhap/{g.id}", headers=h)).status_code == 403
        assert (await client.get(URL)).status_code in (401, 403)  # chưa đăng nhập
        assert (await _lay(client, thu_mua))["co_the_sua_gia_chuan"] is False
        assert (await _lay(client, admin_user))["co_the_sua_gia_chuan"] is True
        assert await db_session.get(GiaNhapMauVatTu, g.id) is not None
        assert (await db_session.get(MauVatTu, mau_id)).gia_ban_co_dinh is None

    async def test_thu_mua_doc_duoc_nhung_khong_dat_gia_chuan(self, client: AsyncClient, db_session, admin_user, thu_mua, bang):
        mau_id = bang["duoi"].id
        r = await client.put(f"{URL}/{mau_id}", headers=auth_header(thu_mua), json={"gia_chuan": 999000})
        assert r.status_code == 403
        assert (await db_session.get(MauVatTu, mau_id)).gia_ban_co_dinh == 220000
        r = await client.put(f"{URL}/{mau_id}", headers=auth_header(admin_user), json={"gia_chuan": 240000})
        assert r.status_code == 200, r.text
        assert r.json()["gia_chuan"] == 240000
        assert (await db_session.get(MauVatTu, mau_id)).gia_ban_co_dinh == 240000


@pytest.mark.asyncio
class TestBang:
    async def test_gia_goi_y_muc_loi_va_co(self, client: AsyncClient, thu_mua, bang):
        body = await _lay(client, thu_mua)
        assert [x["ma"] for x in body["items"]] == ["A-01", "A-02", "B-01", "C-01"]  # mẫu đã ngừng không hiện
        assert (body["tong"], body["so_chua_co"], body["so_duoi_he_so"], body["total"]) == (4, 2, 1, 4)
        m = _theo_ma(body)
        # Giá vốn 200k × (1 + 15%) = 230k; giá chuẩn 220k chỉ lời 10% → dưới hệ số
        duoi = m["A-01"]
        assert (duoi["gia_chuan"], duoi["he_so"], duoi["gia_nhap_moc"], duoi["gia_goi_y"]) == (220000, 15, 200000, 230000)
        assert (duoi["muc_loi_pct"], duoi["chua_co"], duoi["duoi_he_so"]) == (10.0, False, True)
        assert duoi["gia_tham_khao"] == 280000
        assert duoi["gia_nhap_gan_nhat"]["gia"] == 200000 and duoi["gia_nhap_gan_nhat"]["ncc_ten"] == "NCC An"
        assert duoi["gia_nhap_gan_nhat"]["cu"] is False
        # Giá chuẩn đúng bằng giá gợi ý → không tính là dưới hệ số; giá vốn 70 ngày → «giá cũ»
        du = m["A-02"]
        assert (du["muc_loi_pct"], du["chua_co"], du["duoi_he_so"]) == (15.0, False, False)
        assert du["gia_nhap_gan_nhat"]["cu"] is True
        # Chưa từng chốt → mốc = giá NCC thấp nhất (180k), nhóm 80x80 hệ số 20% → gợi ý 216k
        chua = m["B-01"]
        assert (chua["gia_chuan"], chua["he_so"], chua["gia_nhap_moc"], chua["gia_goi_y"]) == (None, 20, 180000, 216000)
        assert (chua["muc_loi_pct"], chua["chua_co"], chua["duoi_he_so"]) == (None, True, False)
        assert chua["gia_nhap_gan_nhat"] is None
        assert [(g["ncc_ten"], g["gia"], g["hang"]) for g in chua["gia_nhap"]] == [("NCC Bình", 180000, "chinh"), ("NCC An", 190000, None)]
        # Không có giá nào → không gợi ý được; nhóm chưa cài % lãi → hệ số mặc định 15
        trong = m["C-01"]
        assert (trong["he_so"], trong["gia_nhap_moc"], trong["gia_goi_y"], trong["muc_loi_pct"]) == (15, None, None, None)
        assert (trong["chua_co"], trong["duoi_he_so"], trong["gia_nhap"], trong["don_vi"]) == (True, False, [], "cái")

    async def test_mau_chua_chot_van_bi_xet_duoi_he_so_theo_gia_ncc(self, client: AsyncClient, admin_user, bang):
        """Mẫu chưa có giá vốn gần nhất: cờ «dưới hệ số» tính theo giá NCC thấp nhất, kể cả ở bộ đếm."""
        mau_id = bang["chua"].id
        r = await client.put(f"{URL}/{mau_id}", headers=auth_header(admin_user), json={"gia_chuan": 200000})
        assert (r.json()["muc_loi_pct"], r.json()["duoi_he_so"]) == (11.1, True)   # 200k / 180k
        body = await _lay(client, admin_user, loc="duoi_he_so")
        assert [x["ma"] for x in body["items"]] == ["A-01", "B-01"]
        assert (body["tong"], body["so_chua_co"], body["so_duoi_he_so"], body["total"]) == (4, 1, 2, 2)

    async def test_loc_tim_va_phan_trang(self, client: AsyncClient, thu_mua, bang):
        body = await _lay(client, thu_mua, loc="chua_co")
        assert [x["ma"] for x in body["items"]] == ["B-01", "C-01"]
        # Bộ đếm trên các nút lọc không đổi theo nút đang bấm; `total` là số dòng của nút đang bấm
        assert (body["tong"], body["so_chua_co"], body["so_duoi_he_so"], body["total"]) == (4, 2, 1, 2)
        body = await _lay(client, thu_mua, loc="duoi_he_so")
        assert [x["ma"] for x in body["items"]] == ["A-01"] and body["total"] == 1
        body = await _lay(client, thu_mua, nhom="60x60")
        assert [x["ma"] for x in body["items"]] == ["A-01", "A-02"]
        assert (body["tong"], body["so_chua_co"], body["so_duoi_he_so"]) == (2, 0, 1)
        assert [x["ma"] for x in (await _lay(client, thu_mua, q="b-01"))["items"]] == ["B-01"]        # theo mã
        assert [x["ma"] for x in (await _lay(client, thu_mua, q="van da"))["items"]] == ["B-01"]      # theo tên
        assert (await _lay(client, thu_mua, q="khong-co-ma-nay"))["tong"] == 0
        body = await _lay(client, thu_mua, page=2, page_size=3)
        assert [x["ma"] for x in body["items"]] == ["C-01"]
        assert (body["total"], body["page"], body["page_size"]) == (4, 2, 3)
        h = auth_header(thu_mua)
        assert (await client.get(URL, headers=h, params={"page_size": 101})).status_code == 422
        assert (await client.get(URL, headers=h, params={"loc": "linh_tinh"})).status_code == 422


@pytest.mark.asyncio
class TestGopGiaNhap:
    async def test_moi_ncc_mot_gia_moi_nhat_tu_ca_hai_nguon(self, client: AsyncClient, db_session, project, thu_mua, bang, ncc):
        m, khac = bang["trong"], bang["du"]
        d = DongPhieuVatTu(id=_uid(), project_id=project.id, mau_id=m.id)
        d_khac = DongPhieuVatTu(id=_uid(), project_id=project.id, mau_id=khac.id)
        nhap_binh = GiaNhapMauVatTu(id=_uid(), mau_id=m.id, supplier_id=ncc["binh"].id, gia=205000, created_at=_truoc(5),
                                    ghi_chu="Giá tại kho", created_by=thu_mua.id)

        def bao(dong, s, gia, ngay=None, **kw):
            b = BaoGiaDongVatTu(dong_id=dong.id, supplier_id=s.id if s else None, ncc_ten=s.name if s else "NCC gõ tay",
                                gia=gia, **kw)
            if ngay is not None:
                b.created_at = _truoc(ngay)
            return b

        db_session.add_all([
            d, d_khac, nhap_binh,
            # An: giá nhập nạp tay 100 ngày trước, rồi báo giá trong dự án 10 ngày trước → lấy báo giá
            GiaNhapMauVatTu(mau_id=m.id, supplier_id=ncc["an"].id, gia=200000, created_at=_truoc(100)),
            bao(d, ncc["an"], 190000, 10, nguon="tep"),
            # Bình: báo giá dự án 30 ngày trước, rồi giá nhập nạp tay 5 ngày trước → lấy giá nhập
            bao(d, ncc["binh"], 210000, 30),
            # Cường: chỉ có một giá nhập đã 70 ngày → vẫn hiện, gắn nhãn giá cũ
            GiaNhapMauVatTu(mau_id=m.id, supplier_id=ncc["cuong"].id, gia=150000, created_at=_truoc(70)),
            # Bị loại: NCC đã ngừng dùng · báo giá gõ tay chưa gắn NCC
            GiaNhapMauVatTu(mau_id=m.id, supplier_id=ncc["ngung"].id, gia=100000),
            bao(d, ncc["ngung"], 99000),
            bao(d, None, 90000),
            # Báo giá của dòng mang mẫu KHÁC → thuộc mẫu khác (created_at mặc định của model)
            bao(d_khac, ncc["an"], 50000),
        ])
        await db_session.commit()

        kq = await gia_nhap_theo_mau(db_session, [m.id, khac.id, bang["duoi"].id])
        assert set(kq) == {m.id, khac.id}                                    # mẫu không có giá thì không có khoá
        assert [(g["ncc_ten"], g["gia"], g["nguon"], g["cu"]) for g in kq[m.id]] == [
            ("NCC Cường", 150000, "tay", True), ("NCC An", 190000, "tep", False), ("NCC Bình", 205000, "tay", False),
        ]
        an, binh = kq[m.id][1], kq[m.id][2]
        assert (an["supplier_id"], an["gia_nhap_id"], an["created_by"]) == (ncc["an"].id, None, None)
        assert (binh["gia_nhap_id"], binh["created_by"], binh["ghi_chu"], binh["hang"]) == (nhap_binh.id, thu_mua.id, "Giá tại kho", "chinh")
        assert all(g["luc"].tzinfo is None for ds in kq.values() for g in ds)
        assert [(g["ncc_ten"], g["gia"]) for g in kq[khac.id]] == [("NCC An", 50000)]
        assert await gia_nhap_theo_mau(db_session, []) == {}

        # Qua API: mốc của mẫu chưa từng chốt = giá thấp nhất trong các giá mới nhất (150k, không phải 100k/90k)
        x = _theo_ma(await _lay(client, thu_mua))["C-01"]
        assert [g["gia"] for g in x["gia_nhap"]] == [150000, 190000, 205000]
        assert (x["gia_nhap_moc"], x["gia_goi_y"]) == (150000, 172500)
        assert [g["xoa_duoc"] for g in x["gia_nhap"]] == [False, False, True]   # chỉ dòng chính mình nạp
        # Mẫu đã có giá vốn gần nhất thì mốc vẫn là giá vốn đó, dù có NCC báo rẻ hơn
        assert _theo_ma(await _lay(client, thu_mua))["A-02"]["gia_nhap_moc"] == 200000

    async def test_chot_lai_gia_da_nho_khong_thanh_gia_moi(self, db_session, project, bang, ncc):
        """Thu mua gõ lại đúng giá đã nhớ để chốt: dòng «chot» máy ghi hôm nay, nhưng bằng chứng vẫn là
        ngày cũ (`gia_xac_nhan_luc` của dòng phiếu) → bảng giá chuẩn phải gắn nhãn «giá cũ»."""
        m = bang["trong"]
        d = DongPhieuVatTu(id=_uid(), project_id=project.id, mau_id=m.id, gia_xac_nhan_luc=_truoc(80))
        d2 = DongPhieuVatTu(id=_uid(), project_id=project.id, mau_id=m.id, gia_xac_nhan_luc=_truoc(80))

        def bao(dong, s, gia, nguon, duoc_chon):
            return BaoGiaDongVatTu(dong_id=dong.id, supplier_id=s.id, ncc_ten=s.name, gia=gia, nguon=nguon, duoc_chon=duoc_chon)

        db_session.add_all([
            d, d2,
            bao(d, ncc["an"], 200000, "chot", True),        # đang là giá chốt của dòng → ngày bằng chứng của dòng
            bao(d2, ncc["binh"], 210000, "chot", False),    # dòng chốt đã bị thay → chỉ còn ngày của chính nó
            bao(d2, ncc["cuong"], 220000, "tay", True),     # báo giá thường: ngày ghi báo giá
        ])
        await db_session.commit()
        kq = (await gia_nhap_theo_mau(db_session, [m.id]))[m.id]
        assert [(g["ncc_ten"], g["cu"]) for g in kq] == [("NCC An", True), ("NCC Bình", False), ("NCC Cường", False)]
        assert kq[0]["luc"] < _truoc(79)


@pytest.mark.asyncio
class TestDatGiaChuan:
    async def test_admin_dat_bo_va_ghi_audit(self, client: AsyncClient, db_session, project, admin_user, bang):
        m = bang["chua"]

        def dong_moi(**kw) -> DongPhieuVatTu:
            return DongPhieuVatTu(id=_uid(), project_id=project.id, mau_id=m.id, gia_ban=111000, **kw)

        dong = dong_moi(trang_thai="da_chot_gia")                                  # chưa đặt, khách chưa đồng ý
        da_dong_y = dong_moi(trang_thai="da_chot_gia", khach_dong_y_luc=_truoc(1))
        da_dat = dong_moi(trang_thai="da_dat")
        mau_khac = DongPhieuVatTu(id=_uid(), project_id=project.id, mau_id=bang["du"].id, gia_ban=111000)
        db_session.add_all([dong, da_dong_y, da_dat, mau_khac])
        await db_session.commit()
        h = auth_header(admin_user)

        r = await client.put(f"{URL}/{m.id}", headers=h, json={"gia_chuan": 250000})
        assert r.status_code == 200, r.text
        x = r.json()
        assert (x["id"], x["gia_chuan"], x["chua_co"], x["duoi_he_so"], x["gia_goi_y"]) == (m.id, 250000, False, False, 216000)
        assert (await db_session.get(MauVatTu, m.id)).gia_ban_co_dinh == 250000
        # Dòng chưa đặt hàng mà khách chưa đồng ý lấy ngay giá mới; dòng khách đã đồng ý, dòng đã đặt
        # hàng và dòng của mẫu khác không bị đụng
        for x in (dong, da_dong_y, da_dat, mau_khac):
            await db_session.refresh(x)
        assert (dong.gia_ban, dong.trang_thai) == (250000, "da_chot_gia")
        assert (da_dong_y.gia_ban, da_dat.gia_ban, mau_khac.gia_ban) == (111000, 111000, 111000)
        assert da_dong_y.khach_dong_y_luc is not None
        log = (await db_session.execute(select(AuditLog).where(AuditLog.action == "vat_tu.gia_chuan"))).scalars().all()
        assert len(log) == 1 and log[0].entity_id == m.id and log[0].actor_id == admin_user.id
        assert json.loads(log[0].before_json)["gia_ban_co_dinh"] is None
        assert json.loads(log[0].after_json) == {"gia_ban_co_dinh": 250000, "so_dong_doi_gia": 1}

        # Gửi lại đúng giá cũ → không ghi thêm audit
        assert (await client.put(f"{URL}/{m.id}", headers=h, json={"gia_chuan": 250000})).status_code == 200
        # null = bỏ giá chuẩn
        r = await client.put(f"{URL}/{m.id}", headers=h, json={"gia_chuan": None})
        assert r.status_code == 200 and r.json()["gia_chuan"] is None and r.json()["chua_co"] is True
        assert (await db_session.get(MauVatTu, m.id)).gia_ban_co_dinh is None
        await db_session.refresh(dong)
        assert dong.gia_ban is None, "bỏ giá chuẩn, dòng chưa chốt giá vốn → chưa có giá bán"
        so_log = (await db_session.execute(
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "vat_tu.gia_chuan"))).scalar_one()
        assert so_log == 2

    async def test_gia_khong_hop_le(self, client: AsyncClient, db_session, admin_user, bang):
        m, h = bang["duoi"], auth_header(admin_user)
        for sai in (0, -5):
            r = await client.put(f"{URL}/{m.id}", headers=h, json={"gia_chuan": sai})
            assert r.status_code == 400 and "lớn hơn 0" in r.json()["detail"]
        assert (await client.put(f"{URL}/{m.id}", headers=h, json={})).status_code == 422   # thiếu trường ≠ bỏ giá
        assert (await client.put(f"{URL}/{_uid()}", headers=h, json={"gia_chuan": 1000})).status_code == 404
        assert (await db_session.get(MauVatTu, m.id)).gia_ban_co_dinh == 220000


@pytest.mark.asyncio
class TestGiaNhap:
    async def test_nap_theo_ncc_co_san_va_theo_ten_go(self, client: AsyncClient, db_session, thu_mua, bang, ncc):
        m, h = bang["trong"], auth_header(thu_mua)
        r = await client.post(f"{URL}/{m.id}/gia-nhap", headers=h,
                              json={"supplier_id": ncc["an"].id, "gia": 300000, "ghi_chu": "  Chưa VAT  "})
        assert r.status_code == 201, r.text
        x = r.json()
        assert (x["id"], x["gia_nhap_moc"], x["gia_goi_y"]) == (m.id, 300000, 345000)
        g = x["gia_nhap"][0]
        assert (g["supplier_id"], g["ncc_ten"], g["gia"], g["nguon"], g["ghi_chu"], g["cu"], g["xoa_duoc"]) == (
            ncc["an"].id, "NCC An", 300000, "tay", "Chưa VAT", False, True)
        row = await db_session.get(GiaNhapMauVatTu, g["gia_nhap_id"])
        assert (row.mau_id, row.supplier_id, row.nguon, row.created_by) == (m.id, ncc["an"].id, "tay", thu_mua.id)

        # Gõ tên: NCC chưa có thì tự tạo; gõ lại (khác hoa thường) thì dùng lại NCC đó
        r = await client.post(f"{URL}/{m.id}/gia-nhap", headers=h, json={"ncc_ten": "Gạch Mới Hoàng Gia", "gia": 280000})
        assert r.status_code == 201, r.text
        r = await client.post(f"{URL}/{m.id}/gia-nhap", headers=h, json={"ncc_ten": "gạch mới hoàng gia", "gia": 270000})
        assert r.status_code == 201, r.text
        moi = (await db_session.execute(select(Supplier).where(Supplier.name == "Gạch Mới Hoàng Gia"))).scalars().all()
        assert len(moi) == 1
        # Mỗi NCC một dòng = giá mới nhất (270k), hai lần nạp vẫn còn đủ trong lịch sử
        assert [(g["ncc_ten"], g["gia"]) for g in r.json()["gia_nhap"]] == [("Gạch Mới Hoàng Gia", 270000), ("NCC An", 300000)]
        so = (await db_session.execute(select(func.count()).select_from(GiaNhapMauVatTu).where(
            GiaNhapMauVatTu.supplier_id == moi[0].id))).scalar_one()
        assert so == 2

    async def test_tu_choi(self, client: AsyncClient, db_session, thu_mua, bang, ncc):
        m, h = bang["trong"], auth_header(thu_mua)
        url = f"{URL}/{m.id}/gia-nhap"
        r = await client.post(url, headers=h, json={"gia": 100000})
        assert r.status_code == 400 and "nhà cung cấp" in r.json()["detail"]
        assert (await client.post(url, headers=h, json={"ncc_ten": "   ", "gia": 100000})).status_code == 400
        r = await client.post(url, headers=h, json={"supplier_id": ncc["ngung"].id, "gia": 100000})
        assert r.status_code == 400 and "ngừng dùng" in r.json()["detail"]
        r = await client.post(url, headers=h, json={"ncc_ten": "ncc đã ngừng", "gia": 100000})   # gõ trúng tên NCC đã ngừng
        assert r.status_code == 400 and "ngừng dùng" in r.json()["detail"]
        assert (await client.post(url, headers=h, json={"supplier_id": _uid(), "gia": 100000})).status_code == 404
        for sai in (0, -1):
            r = await client.post(url, headers=h, json={"supplier_id": ncc["an"].id, "gia": sai})
            assert r.status_code == 400 and "lớn hơn 0" in r.json()["detail"]
        r = await client.post(f"{URL}/{_uid()}/gia-nhap", headers=h, json={"supplier_id": ncc["an"].id, "gia": 100000})
        assert r.status_code == 404
        so = (await db_session.execute(select(func.count()).select_from(GiaNhapMauVatTu).where(
            GiaNhapMauVatTu.mau_id == m.id))).scalar_one()
        assert so == 0

    async def test_xoa_chi_nguoi_nap_hoac_admin(self, client: AsyncClient, db_session, admin_user, thu_mua, thu_mua_2, bang, ncc):
        m = bang["trong"]
        ids = []
        for gia in (300000, 310000):
            r = await client.post(f"{URL}/{m.id}/gia-nhap", headers=auth_header(thu_mua),
                                  json={"supplier_id": ncc["an"].id, "gia": gia})
            ids.append(next(g["gia_nhap_id"] for g in r.json()["gia_nhap"] if g["gia"] == gia))
        # Thu mua khác: thấy dòng nhưng không xoá được
        x = _theo_ma(await _lay(client, thu_mua_2))["C-01"]
        assert [g["xoa_duoc"] for g in x["gia_nhap"]] == [False]
        assert (await client.delete(f"{URL}/gia-nhap/{ids[1]}", headers=auth_header(thu_mua_2))).status_code == 403
        assert await db_session.get(GiaNhapMauVatTu, ids[1]) is not None
        # Người nạp xoá dòng mới nhất → giá trước đó của cùng NCC hiện lại
        assert (await client.delete(f"{URL}/gia-nhap/{ids[1]}", headers=auth_header(thu_mua))).status_code == 204
        x = _theo_ma(await _lay(client, admin_user))["C-01"]
        assert [(g["gia"], g["xoa_duoc"]) for g in x["gia_nhap"]] == [(300000, True)]   # admin xoá được dòng của người khác
        assert (await client.delete(f"{URL}/gia-nhap/{ids[0]}", headers=auth_header(admin_user))).status_code == 204
        assert (await client.delete(f"{URL}/gia-nhap/{ids[0]}", headers=auth_header(admin_user))).status_code == 404
        assert _theo_ma(await _lay(client, admin_user))["C-01"]["gia_nhap"] == []
        so_log = (await db_session.execute(
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "vat_tu.xoa_gia_nhap"))).scalar_one()
        assert so_log == 2
