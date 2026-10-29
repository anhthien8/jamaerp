"""Vật tư Đợt 1 (25/10/2026): danh mục mẫu, % lãi, phiếu chọn theo dự án, hỏi giá NCC,
gác giá vốn theo vai, nhập Google Sheet."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.vat_tu import tinh_gia_ban
from app.middleware.auth import hash_password
from app.models.notification import Notification
from app.models.project import Project
from app.models.user import User
from app.models.vat_tu import BaoGiaDongVatTu, DongPhieuVatTu, GiaNhomVatTu, MauVatTu
from app.services import vat_tu_sheet
from tests.conftest import _uid, auth_header


@pytest_asyncio.fixture
async def thu_mua(db_session: AsyncSession) -> User:
    u = User(id=_uid(), full_name="Thu Mua Test", email="thumua@test.com", password_hash=hash_password("x"),
             role="data_entry", department="PURCHASING", is_active=True)
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def thiet_ke(db_session: AsyncSession) -> User:
    u = User(id=_uid(), full_name="Thiet Ke Test", email="thietke@test.com", password_hash=hash_password("x"),
             role="data_entry", department="DESIGN", is_active=True)
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def du_an(db_session: AsyncSession, admin_user, thiet_ke, sales_user) -> Project:
    p = Project(id=_uid(), code="JMH-VT1", name="Nhà anh Bảy", client_name="Anh Bảy", stage="design",
                status="active", total_value=1, pm_id=admin_user.id, designer_id=thiet_ke.id, sales_id=sales_user.id)
    db_session.add(p)
    await db_session.commit()
    return p


@pytest_asyncio.fixture
async def mau(db_session: AsyncSession) -> MauVatTu:
    m = MauVatTu(ma="TM 76006", hang="Taicera", nhom="60x60", be_mat="Bóng", gia_tham_khao=280000)
    db_session.add(m)
    db_session.add(GiaNhomVatTu(nhom="60x60", phan_tram_lai=15))
    await db_session.commit()
    return m


def test_tinh_gia_ban_ap_cai_lai_hon():
    assert tinh_gia_ban(200000, 15, None) == (230000, 15)
    assert tinh_gia_ban(200000, 15, 250000) == (250000, None)   # giá cố định lãi hơn
    assert tinh_gia_ban(200000, 15, 210000) == (230000, 15)     # % lãi hơn


@pytest.mark.asyncio
class TestDanhMuc:
    async def test_sale_khong_thay_gia_von(self, client: AsyncClient, sales_user, thu_mua, mau):
        r = await client.get("/api/v1/vat-tu/mau", headers=auth_header(sales_user))
        assert r.status_code == 200
        body = r.json()
        assert body["thay_gia_von"] is False
        item = body["items"][0]
        assert item["ma"] == "TM 76006"
        assert "gia_tham_khao" not in item and "gia_von_gan_nhat" not in item and "ncc_gan_nhat_ten" not in item
        r = await client.get("/api/v1/vat-tu/mau", headers=auth_header(thu_mua))
        assert r.json()["items"][0]["gia_tham_khao"] == 280000

    async def test_chi_thu_mua_tao_mau(self, client: AsyncClient, sales_user, thu_mua):
        body = {"ma": "X1", "nhom": "80x80", "hang": "Viglacera"}
        assert (await client.post("/api/v1/vat-tu/mau", headers=auth_header(sales_user), json=body)).status_code == 403
        assert (await client.post("/api/v1/vat-tu/mau", headers=auth_header(thu_mua), json=body)).status_code == 201

    async def test_cai_gia_chi_admin(self, client: AsyncClient, admin_user, thu_mua, sales_user):
        body = [{"nhom": "60x60", "phan_tram_lai": 12}, {"nhom": "TBVS", "phan_tram_lai": 10}]
        assert (await client.put("/api/v1/vat-tu/cai-gia", headers=auth_header(thu_mua), json=body)).status_code == 403
        assert (await client.put("/api/v1/vat-tu/cai-gia", headers=auth_header(admin_user), json=body)).status_code == 200
        assert (await client.get("/api/v1/vat-tu/cai-gia", headers=auth_header(sales_user))).status_code == 403
        r = await client.get("/api/v1/vat-tu/cai-gia", headers=auth_header(thu_mua))
        assert {x["nhom"]: x["phan_tram_lai"] for x in r.json()} == {"60x60": 12, "TBVS": 10}


@pytest.mark.asyncio
class TestPhieuVaChotGia:
    async def test_luong_day_du(self, client: AsyncClient, admin_user, thiet_ke, sales_user, thu_mua, du_an, mau, db_session):
        # 1. Thiết kế (PIC) ghi mẫu khách chọn
        r = await client.post(f"/api/v1/vat-tu/du-an/{du_an.id}/dong", headers=auth_header(thiet_ke),
                              json={"phong": "Phòng khách", "hang_muc": "Gạch sàn", "mau_id": mau.id, "so_luong": 42.5})
        assert r.status_code == 201, r.text
        dong = r.json()
        assert dong["trang_thai"] == "khach_chon" and dong["ma"] == "TM 76006" and "gia_von" not in dong
        # Dòng gõ mã tự do
        r2 = await client.post(f"/api/v1/vat-tu/du-an/{du_an.id}/dong", headers=auth_header(sales_user),
                               json={"phong": "WC1", "ma_tu_do": "Lavabo Inax L-333", "so_luong": 1, "don_vi": "cái"})
        assert r2.status_code == 201
        # Thiếu cả mẫu và mã → 400
        assert (await client.post(f"/api/v1/vat-tu/du-an/{du_an.id}/dong", headers=auth_header(sales_user),
                                  json={"phong": "WC1"})).status_code == 400

        # 2. Thu mua thấy bảng cần hỏi giá; sale thì không
        assert (await client.get("/api/v1/vat-tu/can-hoi-gia", headers=auth_header(sales_user))).status_code == 403
        r = await client.get("/api/v1/vat-tu/can-hoi-gia", headers=auth_header(thu_mua))
        assert len(r.json()["items"]) == 2 and r.json()["items"][0]["project_code"] == "JMH-VT1"

        # 3. Ghi 2 báo giá → dòng sang hoi_ncc; sale không ghi được
        assert (await client.post(f"/api/v1/vat-tu/dong/{dong['id']}/bao-gia", headers=auth_header(sales_user),
                                  json={"ncc_ten": "Hiệp Phát", "gia": 200000})).status_code == 403
        r = await client.post(f"/api/v1/vat-tu/dong/{dong['id']}/bao-gia", headers=auth_header(thu_mua),
                              json={"ncc_ten": "Hiệp Phát", "gia": 200000})
        assert r.status_code == 201 and r.json()["trang_thai"] == "hoi_ncc"
        r = await client.post(f"/api/v1/vat-tu/dong/{dong['id']}/bao-gia", headers=auth_header(thu_mua),
                              json={"ncc_ten": "Daisan", "gia": 190000, "ngay_giao": "3 ngày"})
        bao_gia = r.json()["bao_gia"]
        assert [b["ncc_ten"] for b in bao_gia] == ["Daisan", "Hiệp Phát"]  # rẻ nhất lên đầu
        re_nhat = bao_gia[0]["id"]

        # 4. Chốt theo báo giá rẻ nhất → giá bán = 190000 × 1.15
        r = await client.post(f"/api/v1/vat-tu/dong/{dong['id']}/chot", headers=auth_header(thu_mua), json={"bao_gia_id": re_nhat})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["trang_thai"] == "da_chot_gia" and d["gia_von"] == 190000 and d["gia_ban"] == 218500
        assert d["phan_tram_ap_dung"] == 15 and d["lai"] == round(28500 * 42.5)
        # Giá gần nhất ghi về mẫu
        await db_session.refresh(mau)
        assert mau.gia_von_gan_nhat == 190000 and mau.ncc_gan_nhat_ten == "Daisan"
        # Báo PIC thiết kế + KD (trừ người chốt)
        ds = (await db_session.execute(select(Notification).where(Notification.type == "vat_tu"))).scalars().all()
        assert {n.user_id for n in ds} == {thiet_ke.id, sales_user.id, admin_user.id}
        assert "218.500đ" in ds[0].body

        # 5. Thiết kế xem phiếu: thấy giá bán, không thấy giá vốn/NCC/lãi/báo giá
        r = await client.get(f"/api/v1/vat-tu/du-an/{du_an.id}/dong", headers=auth_header(thiet_ke))
        body = r.json()
        assert body["thay_gia_von"] is False and body["co_the_chot"] is False and "tong_lai" not in body
        chot = next(i for i in body["items"] if i["id"] == dong["id"])
        assert chot["gia_ban"] == 218500 and chot["thanh_tien"] == round(218500 * 42.5)
        for cam in ("gia_von", "ncc_ten", "lai", "bao_gia", "phan_tram_ap_dung"):
            assert cam not in chot
        # Admin thấy đủ
        r = await client.get(f"/api/v1/vat-tu/du-an/{du_an.id}/dong", headers=auth_header(admin_user))
        assert r.json()["tong_lai"] == round(28500 * 42.5)
        assert next(i for i in r.json()["items"] if i["id"] == dong["id"])["ncc_ten"] == "Daisan"  # gõ tay → tự tạo NCC

    async def test_chot_bang_gia_co_dinh_khi_lai_hon(self, client: AsyncClient, thu_mua, du_an, mau, db_session):
        mau.gia_ban_co_dinh = 300000
        await db_session.commit()
        r = await client.post(f"/api/v1/vat-tu/du-an/{du_an.id}/dong", headers=auth_header(thu_mua),
                              json={"phong": "Bếp", "mau_id": mau.id, "so_luong": 10})
        dong_id = r.json()["id"]
        r = await client.post(f"/api/v1/vat-tu/dong/{dong_id}/chot", headers=auth_header(thu_mua),
                              json={"gia_von": 200000, "ncc_ten": "Hiệp Phát"})
        assert r.status_code == 200
        assert r.json()["gia_ban"] == 300000 and r.json()["phan_tram_ap_dung"] is None

    async def test_het_hang_doi_ma_khach_dong_y(self, client: AsyncClient, thu_mua, thiet_ke, du_an, mau, db_session):
        thay = MauVatTu(ma="TM 76009", hang="Taicera", nhom="60x60")
        db_session.add(thay)
        await db_session.commit()
        r = await client.post(f"/api/v1/vat-tu/du-an/{du_an.id}/dong", headers=auth_header(thiet_ke),
                              json={"phong": "Phòng ngủ", "mau_id": mau.id, "so_luong": 20})
        dong_id = r.json()["id"]
        h = auth_header(thu_mua)
        # Hết hàng mà không kèm mẫu thay → 400
        assert (await client.patch(f"/api/v1/vat-tu/dong/{dong_id}", headers=h, json={"trang_thai": "het_hang"})).status_code == 400
        # Thiết kế không được tự đánh «hết hàng»
        assert (await client.patch(f"/api/v1/vat-tu/dong/{dong_id}", headers=auth_header(thiet_ke),
                                   json={"trang_thai": "het_hang", "mau_thay_the_id": thay.id})).status_code == 403
        r = await client.patch(f"/api/v1/vat-tu/dong/{dong_id}", headers=h,
                               json={"trang_thai": "het_hang", "mau_thay_the_id": thay.id, "ly_do_doi": "NCC ngưng sản xuất"})
        assert r.status_code == 200 and r.json()["ma_thay_the"] == "TM 76009"
        # Thiết kế chuyển sang chờ khách duyệt, rồi bấm «Khách đã đồng ý»
        r = await client.patch(f"/api/v1/vat-tu/dong/{dong_id}", headers=auth_header(thiet_ke), json={"trang_thai": "cho_khach_duyet_lai"})
        assert r.status_code == 200
        r = await client.post(f"/api/v1/vat-tu/dong/{dong_id}/khach-dong-y", headers=auth_header(thiet_ke), json={"ghi_chu": "Khách OK qua Zalo"})
        d = r.json()
        assert d["trang_thai"] == "hoi_ncc" and d["mau_id"] == thay.id and d["ma"] == "TM 76009" and d["ma_thay_the"] is None
        assert d["khach_dong_y_luc"] and d["khach_ghi_chu"] == "Khách OK qua Zalo"

    async def test_nguoi_ngoai_du_an_403(self, client: AsyncClient, du_an, db_session):
        la = User(id=_uid(), full_name="Nguoi La", email="la@test.com", password_hash=hash_password("x"),
                  role="data_entry", department="SALES", is_active=True)
        db_session.add(la)
        await db_session.commit()
        assert (await client.get(f"/api/v1/vat-tu/du-an/{du_an.id}/dong", headers=auth_header(la))).status_code == 403

    async def test_xoa_dong_da_chot_chi_admin(self, client: AsyncClient, admin_user, thu_mua, du_an, mau):
        r = await client.post(f"/api/v1/vat-tu/du-an/{du_an.id}/dong", headers=auth_header(thu_mua), json={"phong": "A", "mau_id": mau.id})
        dong_id = r.json()["id"]
        await client.post(f"/api/v1/vat-tu/dong/{dong_id}/chot", headers=auth_header(thu_mua), json={"gia_von": 100000})
        assert (await client.delete(f"/api/v1/vat-tu/dong/{dong_id}", headers=auth_header(thu_mua))).status_code == 400
        assert (await client.delete(f"/api/v1/vat-tu/dong/{dong_id}", headers=auth_header(admin_user))).status_code == 204


# ── Nhập Google Sheet ─────────────────────────────────────────────────────

CSV_30X30 = (
    'STT,"MÃ (NẾU CÓ) \n(vd: 7x60 (cm)- TM 76006)",THƯƠNG HIỆU,HÌNH ẢNH,TÍNH CHẤT (BÓNG/MỜ/NHÁM),TÌNH TRẠNG,ĐƠN GIÁ (M2),NCC,GHI CHÚ ,LINK MAP\n'
    '1,Gạch sân 30x30,Taicera,,NHÁM,CÒN HÀNG,"280,000",Daisan,,\n'
    '2,, Viglacera,,BÓNG,CÒN HÀNG,"150,000",Hiệp Phát,,\n'
    '3,,,,,,,,,\n'
)


def test_doc_csv_sheet():
    ds = vat_tu_sheet.doc_csv(CSV_30X30, "30X30")
    assert len(ds) == 2
    assert ds[0] == {"ma": "Gạch sân 30x30", "hang": "Taicera", "nhom": "30X30", "be_mat": "NHÁM", "tinh_trang": "CÒN HÀNG",
                     "gia_tham_khao": 280000.0, "ncc_gan_nhat_ten": "Daisan", "ghi_chu": None, "anh_url": None}
    assert ds[1]["ma"] == "Viglacera (chưa có mã)" and ds[1]["hang"] == "Viglacera"
    assert vat_tu_sheet.lay_id_sheet("https://docs.google.com/spreadsheets/d/18GYuZmBC_x/edit?gid=0") == "18GYuZmBC_x"


@pytest.mark.asyncio
async def test_import_sheet_vao_danh_muc(client: AsyncClient, thu_mua, sales_user, db_session, monkeypatch):
    async def gia_doc_sheet(url, bo_qua_tab=("FROM",)):
        return vat_tu_sheet.doc_csv(CSV_30X30, "30X30") + vat_tu_sheet.doc_csv(CSV_30X30.replace("Gạch sân 30x30", "TM 606"), "60x60")

    monkeypatch.setattr(vat_tu_sheet, "doc_sheet", gia_doc_sheet)
    url = "https://docs.google.com/spreadsheets/d/abc/edit"
    assert (await client.post("/api/v1/vat-tu/mau/import-sheet", headers=auth_header(sales_user), json={"url": url})).status_code == 403
    r = await client.post("/api/v1/vat-tu/mau/import-sheet", headers=auth_header(thu_mua), json={"url": url})
    assert r.status_code == 200 and {k: r.json()[k] for k in ("doc_duoc", "them", "sua")} == {"doc_duoc": 4, "them": 4, "sua": 0}
    # Nhập lại: không trùng; nhóm mới có % lãi mặc định 15
    r = await client.post("/api/v1/vat-tu/mau/import-sheet", headers=auth_header(thu_mua), json={"url": url})
    assert r.json() == {"doc_duoc": 4, "them": 0, "sua": 0, "ncc_moi": 0}
    nhom = (await client.get("/api/v1/vat-tu/nhom", headers=auth_header(thu_mua))).json()
    assert {n["nhom"]: (n["so_mau"], n["phan_tram_lai"]) for n in nhom} == {"30X30": (2, 15), "60x60": (2, 15)}
    r = await client.get("/api/v1/vat-tu/mau", headers=auth_header(sales_user), params={"q": "tm 6"})
    assert [i["ma"] for i in r.json()["items"]] == ["TM 606"]


# ── Bot nhập báo giá từ tệp (25/10/2026) ──────────────────────────────────

from app.services import vat_tu_bao_gia_tep as tep  # noqa: E402


def test_khop_ma_bo_khoang_trang_va_gach():
    dong = [{"dong_id": "d1", "ma": "TM 76006", "phong": "Khách"}, {"dong_id": "d2", "ma": "TM 76006", "phong": "Bếp"},
            {"dong_id": "d3", "ma": "6A01 / 6A02", "phong": "WC"}]
    items = [{"ma": "tm-76006", "gia": 185000.0, "con_hang": True, "don_vi": None, "ghi_chu": None},
             {"ma": "XYZ", "gia": 1.0, "con_hang": True, "don_vi": None, "ghi_chu": None},
             {"ma": "TM76006", "gia": None, "con_hang": False, "don_vi": None, "ghi_chu": None}]
    khop, khong = tep.khop_ma(items, dong)
    assert [k["dong_id"] for k in khop] == ["d1", "d2"]      # một mã → hai phòng
    assert [k["ma"] for k in khong] == ["XYZ", "TM76006"]    # mã lạ + không có giá


def test_chuan_hoa_gia_viet():
    out = tep._chuan_hoa('{"ncc_ten": " Hiệp Phát ", "items": [{"ma": "A1", "gia": "185.000đ"}, {"ma": "A2", "gia": "liên hệ", "con_hang": false}, {"gia": 5}]}')
    assert out["ncc_ten"] == "Hiệp Phát"
    assert out["items"][0]["gia"] == 185000 and out["items"][0]["con_hang"] is True
    assert out["items"][1]["gia"] is None and out["items"][1]["con_hang"] is False
    assert len(out["items"]) == 2  # dòng không có mã bị bỏ


def test_tep_sang_chu_xlsx_va_tu_choi_word():
    import io

    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Mã", "Giá", "Tình trạng"])
    ws.append(["TM 76006", 185000, "Còn hàng"])
    buf = io.BytesIO()
    wb.save(buf)
    loai, chu = tep.tep_sang_chu(buf.getvalue(), "baogia.xlsx", None)
    assert loai == "xlsx" and "TM 76006 | 185000 | Còn hàng" in chu
    with pytest.raises(tep.TepError):
        tep.tep_sang_chu(b"x", "hopdong.docx", None)
    assert tep.tep_sang_chu(b"\xff\xd8", "anh.jpg", "image/jpeg") == ("image", "")


@pytest.mark.asyncio
async def test_bot_trich_roi_ghi_bao_gia(client: AsyncClient, thu_mua, sales_user, thiet_ke, du_an, mau, db_session, monkeypatch):
    # Phiếu có 1 dòng mẫu TM 76006
    r = await client.post(f"/api/v1/vat-tu/du-an/{du_an.id}/dong", headers=auth_header(thiet_ke),
                          json={"phong": "Phòng khách", "mau_id": mau.id, "so_luong": 40})
    dong_id = r.json()["id"]

    async def _tai(file_id):
        return b"ma,gia\nTM 76006,185000\nLA-9,99000\n"

    async def _trich(chu):
        assert "TM 76006" in chu
        return {"ncc_ten": "Hiệp Phát", "items": [
            {"ma": "TM-76006", "gia": 185000.0, "con_hang": True, "don_vi": "m2", "ghi_chu": None},
            {"ma": "LA-9", "gia": 99000.0, "con_hang": True, "don_vi": None, "ghi_chu": None},
        ]}
    monkeypatch.setattr(tep, "tai_tep_telegram", _tai)
    monkeypatch.setattr(tep, "trich_tu_chu", _trich)

    body = {"project_id": du_an.id, "file_id": "F1", "file_name": "baogia.csv"}
    # Sale không được nhập báo giá
    assert (await client.post("/api/v1/vat-tu/bot/trich-bao-gia", headers=auth_header(sales_user), json=body)).status_code == 403
    r = await client.post("/api/v1/vat-tu/bot/trich-bao-gia", headers=auth_header(thu_mua), json=body)
    assert r.status_code == 200, r.text
    xem = r.json()
    assert xem["ncc_ten"] == "Hiệp Phát" and xem["so_doc_duoc"] == 2
    assert len(xem["khop"]) == 1 and xem["khop"][0]["dong_id"] == dong_id and xem["khop"][0]["phong"] == "Phòng khách"
    assert xem["khong_khop"][0]["ma"] == "LA-9"
    # Chưa ghi gì cho tới khi xác nhận
    assert (await db_session.execute(select(func.count()).select_from(BaoGiaDongVatTu))).scalar_one() == 0

    r = await client.post("/api/v1/vat-tu/bot/ghi-bao-gia", headers=auth_header(thu_mua), json={
        "nguon": "tệp baogia.csv",
        "items": [{"dong_id": dong_id, "ncc_ten": "Hiệp Phát", "gia": 185000, "con_hang": True}],
    })
    assert r.status_code == 201 and r.json() == {"ghi": 1, "tao": 0, "loi": []}
    db_session.expire_all()
    bg = (await db_session.execute(select(BaoGiaDongVatTu))).scalar_one()
    assert bg.gia == 185000 and "baogia.csv" in bg.ghi_chu and "Thu Mua Test" in bg.ghi_chu
    assert (await db_session.get(DongPhieuVatTu, dong_id)).trang_thai == "hoi_ncc"


@pytest.mark.asyncio
async def test_bot_du_an_chua_co_phieu_tao_dong_tu_bao_gia(client: AsyncClient, thu_mua, du_an, mau, db_session, monkeypatch):
    """Dự án chưa có phiếu → xem trước «dòng sẽ tạo»; bấm Ghi mới tạo dòng + báo giá."""
    async def _tai(file_id):
        return b"ma,gia\nTM 76006,185000\nLA-9,99000\nHH-1,lien he\n"

    async def _trich(chu):
        return {"ncc_ten": "Hiệp Phát", "items": [
            {"ma": "tm76006", "gia": 185000.0, "con_hang": True, "don_vi": None, "ghi_chu": None, "so_luong": 40, "phong": "WC1"},
            {"ma": "LA-9", "gia": 99000.0, "con_hang": True, "don_vi": "bộ", "ghi_chu": None, "so_luong": None, "phong": None},
            {"ma": "HH-1", "gia": None, "con_hang": True, "don_vi": None, "ghi_chu": None},
        ]}
    monkeypatch.setattr(tep, "tai_tep_telegram", _tai)
    monkeypatch.setattr(tep, "trich_tu_chu", _trich)

    r = await client.post("/api/v1/vat-tu/bot/trich-bao-gia", headers=auth_header(thu_mua),
                          json={"project_id": du_an.id, "file_id": "F", "file_name": "a.csv"})
    assert r.status_code == 200, r.text
    xem = r.json()
    assert xem["so_dong_phieu"] == 0 and xem["khop"] == []
    tao = {t["ma"]: t for t in xem["tao_moi"]}
    assert set(tao) == {mau.ma, "LA-9"}  # mã khớp danh mục lấy đúng mã mẫu
    assert tao[mau.ma]["co_trong_danh_muc"] and not tao["LA-9"]["co_trong_danh_muc"]
    assert tao["LA-9"]["phong"] == "Chung"
    assert [k["ma"] for k in xem["khong_khop"]] == ["HH-1"]
    # Chưa ghi gì
    assert (await db_session.execute(select(func.count()).select_from(DongPhieuVatTu))).scalar_one() == 0

    r = await client.post("/api/v1/vat-tu/bot/ghi-bao-gia", headers=auth_header(thu_mua), json={
        "nguon": "tệp a.csv", "project_id": du_an.id, "items": [],
        "tao_dong": [{**{k: t.get(k) for k in ("ma", "phong", "so_luong", "don_vi", "gia", "con_hang")}, "ncc_ten": "Hiệp Phát"}
                     for t in xem["tao_moi"]],
    })
    assert r.status_code == 201, r.text
    assert r.json()["tao"] == 2 and r.json()["ghi"] == 2
    mau_id = mau.id
    db_session.expire_all()
    ds = {(d.mau_id, d.ma_tu_do): d for d in (await db_session.execute(select(DongPhieuVatTu))).scalars()}
    d_mau, d_tu_do = ds[(mau_id, None)], ds[(None, "LA-9")]
    assert d_mau.phong == "WC1" and d_mau.so_luong == 40 and d_mau.trang_thai == "hoi_ncc"
    assert d_tu_do.so_luong == 1 and d_tu_do.don_vi == "bộ"
    assert (await db_session.execute(select(func.count()).select_from(BaoGiaDongVatTu))).scalar_one() == 2


@pytest.mark.asyncio
async def test_bot_ghi_bao_gia_rong_400(client: AsyncClient, thu_mua):
    r = await client.post("/api/v1/vat-tu/bot/ghi-bao-gia", headers=auth_header(thu_mua), json={"items": []})
    assert r.status_code == 400


# ── Bot nhập phát sinh gửi khách (30/10/2026) ───────────────────────────────

def test_chuan_hoa_phat_sinh_tu_tinh_tien_va_giam_tru():
    kq = tep.chuan_hoa_phat_sinh({"khach_hang": "Anh Bảy", "tieu_de": "PHÁT SINH NGÀY 5/10/2026", "tong_file": "7.600.000",
                                  "items": [
        {"hang_muc": "Tủ bếp trên", "dvt": "md", "kl": "3,8", "sl": 1, "don_gia": "2.500.000", "thanh_tien": "9.000.000"},
        {"hang_muc": "Đá bếp (CĐT cấp)", "dvt": "md", "kl": 2, "sl": -1, "don_gia": 900000, "thanh_tien": None},
        {"hang_muc": "Tầng 1-lửng 3.80"},  # diễn giải không giá → bỏ
    ]})
    tt = [it["thanh_tien"] for it in kq["items"]]
    assert tt == [9_500_000, -1_800_000]  # tự tính KL×SL×đơn giá, không tin số trong tệp
    assert kq["tong_file"] == 7_600_000


def test_ten_khop_khach():
    assert tep.ten_khop("Anh Bảy", "Bao gia phat sinh - A Bay.xlsx") is True
    assert tep.ten_khop("Anh Bảy", "BG phat sinh chi Lan.xlsx", None) is False
    assert tep.ten_khop("Anh Bảy", "anh.jpg", None) is False
    assert tep.ten_khop(None, "x.xlsx") is None


@pytest.mark.asyncio
async def test_bot_phat_sinh_tao_phu_luc_va_dong_vat_tu(client: AsyncClient, admin_user, du_an, db_session, monkeypatch):
    from app.models.contract import Contract

    hd = Contract(id=_uid(), code="HD-VT1", project_id=du_an.id, title="Thi công", status="signed",
                  total_value=500_000_000, contract_kind="thi_cong", payment_terms={"installments": []})
    db_session.add(hd)
    await db_session.commit()
    hd_id, du_an_id = hd.id, du_an.id
    h = auth_header(admin_user)

    async def _tai(file_id):
        return b"x"

    async def _trich(chu, prompt=None, chuan=None):
        assert prompt is tep._PROMPT_PHAT_SINH
        return chuan({"khach_hang": "Chị Lan", "tieu_de": "Phát sinh 5/10", "tong_file": 7_700_000, "items": [
            {"hang_muc": "Tủ bếp trên", "dvt": "md", "kl": 3.8, "sl": 1, "don_gia": 2_500_000},
            {"hang_muc": "Đá bếp", "dvt": "md", "kl": 2, "sl": -1, "don_gia": 900_000},
        ]})
    monkeypatch.setattr(tep, "tai_tep_telegram", _tai)
    monkeypatch.setattr(tep, "trich_tu_chu", _trich)
    monkeypatch.setattr(tep, "tep_sang_chu", lambda d, f, m: ("xlsx", "x"))

    r = await client.post("/api/v1/vat-tu/bot/trich-phat-sinh", headers=auth_header(admin_user),
                          json={"project_id": du_an.id, "file_id": "F", "file_name": "BG phat sinh chi Lan.xlsx"})
    assert r.status_code == 200, r.text
    xem = r.json()
    assert xem["tong"] == 7_700_000 and not xem["lech_tong"]
    assert xem["khop_khach"] is False  # tệp tên chị Lan, dự án anh Bảy → cảnh báo
    assert xem["so_dong_mua"] == 1 and [c["code"] for c in xem["hop_dong"]] == ["HD-VT1"]

    r = await client.post("/api/v1/vat-tu/bot/ghi-phat-sinh", headers=auth_header(admin_user), json={
        "project_id": du_an_id, "contract_id": hd_id, "tieu_de": xem["tieu_de"], "items": xem["items"], "nguon": "a.xlsx"})
    assert r.status_code == 201, r.text
    assert r.json()["phu_luc"]["code"] == "HD-VT1-PL1" and r.json()["tao_dong"] == 1
    db_session.expire_all()
    pl = (await db_session.execute(select(Contract).where(Contract.parent_contract_id == hd_id))).scalar_one()
    assert pl.status == "draft" and pl.total_value == 7_700_000 and "Tủ bếp trên" in pl.notes
    d = (await db_session.execute(select(DongPhieuVatTu))).scalar_one()
    assert d.hang_muc == "Tủ bếp trên" and d.so_luong == 3.8 and d.trang_thai == "khach_chon" and d.phong == "Phát sinh"

    # Tệp gửi lần sau = bản mới nhất → CẬP NHẬT phụ lục nháp đó, không tạo PL2.
    # Dòng Thu mua đã hỏi giá thì giữ; dòng chưa đụng thì làm lại theo tệp mới.
    d.trang_thai = "hoi_ncc"
    await db_session.commit()
    r = await client.post("/api/v1/vat-tu/bot/trich-phat-sinh", headers=h,
                          json={"project_id": du_an_id, "file_id": "F", "file_name": "a.xlsx"})
    assert r.json()["hop_dong"][0]["cap_nhat"]["code"] == "HD-VT1-PL1"
    items2 = xem["items"] + [{"hang_muc": "Kệ tivi", "dvt": "cái", "kl": None, "sl": 2, "don_gia": 3_000_000,
                              "thanh_tien": 6_000_000}]
    r = await client.post("/api/v1/vat-tu/bot/ghi-phat-sinh", headers=h, json={
        "project_id": du_an_id, "contract_id": hd_id, "tieu_de": "Phát sinh 8/10", "items": items2})
    assert r.status_code == 201, r.text
    kq = r.json()
    assert kq["cap_nhat"] and kq["phu_luc"]["code"] == "HD-VT1-PL1" and kq["gia_tri_cu"] == 7_700_000
    assert kq["tao_dong"] == 1 and kq["giu_dong"] == 1  # chỉ thêm Kệ tivi; Tủ bếp Thu mua đang hỏi giá → giữ
    db_session.expire_all()
    ds_pl = (await db_session.execute(select(Contract).where(Contract.parent_contract_id == hd_id))).scalars().all()
    assert len(ds_pl) == 1 and ds_pl[0].total_value == 13_700_000 and ds_pl[0].title == "Phát sinh 8/10"
    ten = sorted(x.hang_muc for x in (await db_session.execute(select(DongPhieuVatTu))).scalars())
    assert ten == ["Kệ tivi", "Tủ bếp trên"]

    # Khách đã ký PL1 → tệp sau là đợt phát sinh MỚI → PL2
    ds_pl[0].status = "signed"
    await db_session.commit()
    r = await client.post("/api/v1/vat-tu/bot/ghi-phat-sinh", headers=h, json={
        "project_id": du_an_id, "contract_id": hd_id, "tieu_de": "Phát sinh 20/10", "items": items2[:1]})
    assert r.json()["phu_luc"]["code"] == "HD-VT1-PL2" and not r.json()["cap_nhat"]



@pytest.mark.asyncio
async def test_bot_baogia_nhan_ra_bao_gia_gui_khach(client: AsyncClient, thu_mua, du_an, monkeypatch):
    """Gửi báo giá JAMA→khách vào /baogia (NCC) → không trích như NCC, báo bot chuyển luồng phát sinh."""
    async def _tai(file_id):
        return b"x"

    async def _trich(*a, **k):
        raise AssertionError("không được trích như báo giá NCC")
    monkeypatch.setattr(tep, "tai_tep_telegram", _tai)
    monkeypatch.setattr(tep, "trich_tu_chu", _trich)
    monkeypatch.setattr(tep, "tep_sang_chu", lambda d, f, m: ("xlsx", "STT | Hạng mục | ĐVT | KL | SL | Đơn giá | Thành tiền"))
    r = await client.post("/api/v1/vat-tu/bot/trich-bao-gia", headers=auth_header(thu_mua),
                          json={"project_id": du_an.id, "file_id": "F", "file_name": "JAMA_BÁO_GIÁ_TỔNG_HỢP_CHỊ_LAN.xlsx"})
    assert r.status_code == 200, r.text
    assert r.json()["la_bao_gia_khach"] is True


def test_la_bao_gia_khach():
    assert tep.la_bao_gia_khach("JAMA_BÁO_GIÁ_TỔNG_HỢP_CHỊ_LAN_8_10_2026.xlsx", "")
    assert tep.la_bao_gia_khach("x.xlsx", "A PHÁT SINH NGÀY 5/10 | Hạng mục | Thành tiền")
    assert not tep.la_bao_gia_khach("baogia_hiepphat.xlsx", "Mã SP | Tên hàng | ĐVT | Đơn giá")


def test_chi_sheet_phat_sinh_va_don_gia_am():
    from app.services.vat_tu_bao_gia_tep import chi_sheet_phat_sinh, chuan_hoa_phat_sinh
    chu = "## Sheet: KÝ HĐ\nBẢNG BÁO GIÁ\nTủ bếp | 1 | 9000000\n## Sheet: PS 05.10.2026 Chốt\nBẢNG BÁO GIÁ PHÁT SINH\nGạch | 1\n"
    r = chi_sheet_phat_sinh(chu)
    assert "PS 05.10" in r and "KÝ HĐ" not in r and "Tủ bếp" not in r
    assert chi_sheet_phat_sinh("## Sheet: A\nx") == "## Sheet: A\nx"  # 1 sheet → giữ nguyên
    # Tệp ghi dấu âm ở ĐƠN GIÁ (SL dương) vẫn là giảm trừ
    kq = chuan_hoa_phat_sinh({"items": [{"hang_muc": "Gia cố (ban đầu)", "kl": 8.6, "sl": 2, "don_gia": -950000},
                                         {"hang_muc": "Gia cố (thực tế)", "kl": 9.8, "sl": 1, "don_gia": 950000}]})
    assert [i["thanh_tien"] for i in kq["items"]] == [-16_340_000, 9_310_000]
