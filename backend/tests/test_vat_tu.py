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
        assert next(i for i in r.json()["items"] if i["id"] == dong["id"])["ncc_ten"] is None  # NCC gõ tay, không có id

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
    assert r.status_code == 200 and r.json() == {"doc_duoc": 4, "them": 4, "sua": 0}
    # Nhập lại: không trùng; nhóm mới có % lãi mặc định 15
    r = await client.post("/api/v1/vat-tu/mau/import-sheet", headers=auth_header(thu_mua), json={"url": url})
    assert r.json() == {"doc_duoc": 4, "them": 0, "sua": 0}
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
    assert r.status_code == 201 and r.json() == {"ghi": 1, "loi": []}
    db_session.expire_all()
    bg = (await db_session.execute(select(BaoGiaDongVatTu))).scalar_one()
    assert bg.gia == 185000 and "baogia.csv" in bg.ghi_chu and "Thu Mua Test" in bg.ghi_chu
    assert (await db_session.get(DongPhieuVatTu, dong_id)).trang_thai == "hoi_ncc"


@pytest.mark.asyncio
async def test_bot_trich_du_an_chua_co_phieu_400(client: AsyncClient, thu_mua, du_an):
    r = await client.post("/api/v1/vat-tu/bot/trich-bao-gia", headers=auth_header(thu_mua),
                          json={"project_id": du_an.id, "file_id": "F", "file_name": "a.xlsx"})
    assert r.status_code == 400 and "chưa có dòng" in r.json()["detail"]
