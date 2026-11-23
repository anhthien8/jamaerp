"""Vật tư Đợt 1 (22/11/2026) — chốt giá để lại bằng chứng, đặt hàng có ngày hẹn và trần ngân sách,
dòng đã đặt không sửa lặng lẽ, nhận hàng giữ lịch sử, sale không bao giờ nhận giá vốn / NCC."""
import json
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.payroll import Transaction
from app.models.project import Project
from app.models.supplier import Supplier
from app.models.vat_tu import BaoGiaDongVatTu, DongPhieuVatTu, GiaNhapMauVatTu, MauVatTu, NhanHangVatTu
from app.services.attendance_service import vn_today
from tests.conftest import _uid, auth_header
from tests.test_vat_tu import du_an, mau, thiet_ke, thu_mua  # noqa: F401 — fixture dùng chung
from tests.test_vat_tu_dat_nhan_hang import _anh, _dong_da_chot, giam_sat, leader_tm, ngay_hen  # noqa: F401

H = "/api/v1/vat-tu"


async def _them(client, user, du_an, **kw) -> str:  # noqa: F811
    r = await client.post(f"{H}/du-an/{du_an.id}/dong", headers=auth_header(user), json={"phong": "Bếp", "so_luong": 10, **kw})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _dat(client, user, dong_id, **kw):
    return await client.post(f"{H}/dong/{dong_id}/dat-hang", headers=auth_header(user), json={"ngay_giao_hen": ngay_hen(), **kw})


def _gan(a: datetime, b: datetime, giay: int = 5) -> bool:
    return abs((a - b).total_seconds()) < giay


# ── 2. Chốt giá phải kèm NCC và để lại bằng chứng ─────────────────────────

@pytest.mark.asyncio
class TestChotGiaCoBangChung:
    async def test_chot_khong_kem_ncc_400(self, client: AsyncClient, thu_mua, du_an, mau, db_session):  # noqa: F811
        dong_id = await _them(client, thu_mua, du_an, mau_id=mau.id)
        url, h = f"{H}/dong/{dong_id}/chot", auth_header(thu_mua)
        for body in ({"gia_von": 200000}, {"gia_von": 200000, "ncc_ten": "   "}, {"gia_von": 200000, "ncc_ten": "NCC chưa rõ"}):
            r = await client.post(url, headers=h, json=body)
            assert r.status_code == 400 and r.json()["detail"] == "Chốt giá phải kèm nhà cung cấp", body
        assert (await client.post(url, headers=h, json={"gia_von": 200000, "supplier_id": _uid()})).status_code == 404
        # Báo giá từ tệp mà bot không đọc ra NCC → chốt qua báo giá đó cũng không được
        await client.post(f"{H}/bot/ghi-bao-gia", headers=h, json={"items": [{"dong_id": dong_id, "ncc_ten": "NCC chưa rõ", "gia": 150000}]})
        bg = (await db_session.execute(select(BaoGiaDongVatTu).where(BaoGiaDongVatTu.dong_id == dong_id))).scalar_one()
        r = await client.post(url, headers=h, json={"bao_gia_id": bg.id})
        assert r.status_code == 400 and r.json()["detail"] == "Chốt giá phải kèm nhà cung cấp"
        d = await db_session.get(DongPhieuVatTu, dong_id)
        await db_session.refresh(d)
        assert d.trang_thai == "hoi_ncc" and d.gia_von is None and d.ncc_id is None

    async def test_chot_go_tay_tu_ghi_mot_bao_gia_chot(self, client: AsyncClient, thu_mua, du_an, mau, db_session):  # noqa: F811
        dong_id = await _them(client, thu_mua, du_an, mau_id=mau.id)
        h = auth_header(thu_mua)
        r = await client.post(f"{H}/dong/{dong_id}/chot", headers=h, json={"gia_von": 200000, "ncc_ten": "Hiệp Phát"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert len(d["bao_gia"]) == 1
        bg = d["bao_gia"][0]
        assert bg["nguon"] == "chot" and bg["duoc_chon"] is True and bg["gia"] == 200000
        assert bg["supplier_id"] == d["ncc_id"] and bg["ncc_ten"] == "Hiệp Phát" == d["ncc_ten"]
        dong = await db_session.get(BaoGiaDongVatTu, bg["id"])
        assert dong.created_by == thu_mua.id
        assert _gan(datetime.fromisoformat(d["gia_xac_nhan_luc"]), datetime.utcnow())
        # Ghi tay một báo giá khác rồi chốt theo nó → chỉ còn MỘT dòng được chọn
        r = await client.post(f"{H}/dong/{dong_id}/bao-gia", headers=h, json={"ncc_ten": "Daisan", "gia": 190000})
        tay = next(b for b in r.json()["bao_gia"] if b["nguon"] == "tay")
        r = await client.post(f"{H}/dong/{dong_id}/chot", headers=h, json={"bao_gia_id": tay["id"]})
        d = r.json()
        assert d["gia_von"] == 190000 and d["ncc_ten"] == "Daisan"
        assert [b["nguon"] for b in d["bao_gia"] if b["duoc_chon"]] == ["tay"] and len(d["bao_gia"]) == 2
        # Gõ tay lần nữa → thêm một dòng «chot» mới, bỏ chọn các dòng khác
        r = await client.post(f"{H}/dong/{dong_id}/chot", headers=h, json={"gia_von": 180000, "ncc_ten": "daisan"})
        d = r.json()
        assert [(b["nguon"], b["gia"]) for b in d["bao_gia"] if b["duoc_chon"]] == [("chot", 180000)] and len(d["bao_gia"]) == 3
        assert d["ncc_ten"] == "Daisan"  # gõ «daisan» khớp NCC đã có, không tạo trùng

    async def test_chot_lai_gia_dang_nho_khong_lam_moi_bang_chung(self, client: AsyncClient, thu_mua, sales_user, du_an, db_session):  # noqa: F811
        cu = datetime.utcnow() - timedelta(days=70)
        ncc = Supplier(id=_uid(), name="Hiệp Phát")
        m = MauVatTu(ma="TM 70", nhom="60x60", gia_von_gan_nhat=200000, ncc_gan_nhat_id=ncc.id,
                     ncc_gan_nhat_ten="Hiệp Phát", gia_von_cap_nhat_luc=cu)
        db_session.add_all([ncc, m])
        await db_session.commit()
        dong_id = await _them(client, thu_mua, du_an, mau_id=m.id)
        h = auth_header(thu_mua)
        # Chốt một chạm theo «giá gần nhất» đã 70 ngày tuổi: ngày bằng chứng vẫn là ngày cũ
        r = await client.post(f"{H}/dong/{dong_id}/chot", headers=h, json={"gia_von": 200000, "supplier_id": ncc.id})
        assert r.status_code == 200, r.text
        d = r.json()
        assert _gan(datetime.fromisoformat(d["gia_xac_nhan_luc"]), cu) and d["gia_cu"] is True
        await db_session.refresh(m)
        assert _gan(m.gia_von_cap_nhat_luc, cu), "ghi nhớ ở mẫu cũng giữ ngày bằng chứng, không thành «hôm nay»"
        chot_row = next(b for b in d["bao_gia"] if b["nguon"] == "chot")
        assert _gan(datetime.fromisoformat(chot_row["created_at"]), cu), "dòng báo giá «chot» mang ngày bằng chứng"
        await client.post(f"{H}/dong/{dong_id}/khach-dong-y", headers=auth_header(sales_user), json={})
        r = await _dat(client, thu_mua, dong_id)
        assert r.status_code == 400 and "60 ngày" in r.json()["detail"]
        # Chốt lại y giá đó (gõ tay, hoặc bấm lại dòng «chot» cũ) vẫn không qua được luật 60 ngày
        await client.post(f"{H}/dong/{dong_id}/chot", headers=h, json={"gia_von": 200000, "supplier_id": ncc.id})
        assert (await _dat(client, thu_mua, dong_id)).status_code == 400
        await client.post(f"{H}/dong/{dong_id}/chot", headers=h, json={"bao_gia_id": chot_row["id"]})
        assert (await _dat(client, thu_mua, dong_id)).status_code == 400
        # Hỏi lại NCC → ghi báo giá MỚI → chốt theo báo giá đó: bằng chứng mới, đặt được
        r = await client.post(f"{H}/dong/{dong_id}/bao-gia", headers=h, json={"supplier_id": ncc.id, "gia": 200000})
        moi = next(b for b in r.json()["bao_gia"] if b["nguon"] == "tay")
        r = await client.post(f"{H}/dong/{dong_id}/chot", headers=h, json={"bao_gia_id": moi["id"]})
        assert r.json()["gia_cu"] is False and r.json()["khach_dong_y_luc"], "giá bán không đổi → lời đồng ý còn"
        r = await _dat(client, thu_mua, dong_id)
        assert r.status_code == 200 and r.json()["trang_thai"] == "da_dat"
        await db_session.refresh(m)
        assert _gan(m.gia_von_cap_nhat_luc, datetime.utcnow())

    async def test_gia_dang_nho_chua_ro_ncc_go_lai_kem_ten_ncc_van_la_gia_cu(self, client: AsyncClient, thu_mua, sales_user,  # noqa: F811
                                                                              du_an, db_session):  # noqa: F811
        """Chốt trước 22/11 không kèm NCC để lại: mẫu nhớ giá + ngày nhưng NCC rỗng; dòng đã chốt mà `ncc_id` rỗng.
        Gõ lại đúng giá đó kèm một tên NCC không phải bằng chứng mới — luật 60 ngày vẫn chặn."""
        cu = datetime.utcnow() - timedelta(days=90)
        for nho_ten in (None, "Hiệp Phát"):  # mẫu chỉ nhớ tên NCC (chưa nối id) cũng vậy
            m = MauVatTu(ma=f"TM 71{nho_ten or ''}", nhom="60x60", gia_von_gan_nhat=200000, gia_von_cap_nhat_luc=cu,
                         ncc_gan_nhat_ten=nho_ten)
            db_session.add(m)
            await db_session.commit()
            dong_id = await _them(client, thu_mua, du_an, mau_id=m.id)
            r = await client.post(f"{H}/dong/{dong_id}/chot", headers=auth_header(thu_mua), json={"gia_von": 200000, "ncc_ten": "Hiệp Phát"})
            assert r.status_code == 200, r.text
            assert _gan(datetime.fromisoformat(r.json()["gia_xac_nhan_luc"]), cu) and r.json()["gia_cu"] is True
            await client.post(f"{H}/dong/{dong_id}/khach-dong-y", headers=auth_header(sales_user), json={})
            r = await _dat(client, thu_mua, dong_id)
            assert r.status_code == 400 and "60 ngày" in r.json()["detail"]
        # Dòng mã tự do chốt từ trước, chưa có NCC: chốt lại đúng giá kèm NCC cũng giữ ngày cũ
        dong_id = await _them(client, thu_mua, du_an, ma_tu_do="Lavabo L-333", don_vi="cái")
        url = f"{H}/dong/{dong_id}/chot"
        await client.post(url, headers=auth_header(thu_mua), json={"gia_von": 900000, "ncc_ten": "Inax"})
        d = await db_session.get(DongPhieuVatTu, dong_id)
        d.ncc_id, d.gia_xac_nhan_luc = None, cu
        await db_session.commit()
        r = await client.post(url, headers=auth_header(thu_mua), json={"gia_von": 900000, "ncc_ten": "Inax"})
        assert _gan(datetime.fromisoformat(r.json()["gia_xac_nhan_luc"]), cu) and r.json()["gia_cu"] is True
        assert r.json()["ncc_ten"] == "Inax"

    async def test_dong_ma_tu_do_chot_lai_cung_gia_cung_ncc_giu_ngay(self, client: AsyncClient, thu_mua, du_an, db_session):  # noqa: F811
        dong_id = await _them(client, thu_mua, du_an, ma_tu_do="Lavabo L-333", don_vi="cái")
        url, h = f"{H}/dong/{dong_id}/chot", auth_header(thu_mua)
        r = await client.post(url, headers=h, json={"gia_von": 900000, "ncc_ten": "Inax"})
        assert r.json()["gia_cu"] is False
        cu = datetime.utcnow() - timedelta(days=70)
        d = await db_session.get(DongPhieuVatTu, dong_id)
        d.gia_xac_nhan_luc = cu
        await db_session.commit()
        r = await client.post(url, headers=h, json={"gia_von": 900000, "ncc_ten": "Inax"})
        assert _gan(datetime.fromisoformat(r.json()["gia_xac_nhan_luc"]), cu) and r.json()["gia_cu"] is True
        # Đổi NCC hoặc đổi giá = thông tin mới → bằng chứng mới
        r = await client.post(url, headers=h, json={"gia_von": 900000, "ncc_ten": "Toto"})
        assert r.json()["gia_cu"] is False
        d.gia_xac_nhan_luc = cu
        await db_session.commit()
        r = await client.post(url, headers=h, json={"gia_von": 880000, "ncc_ten": "Toto"})
        assert r.json()["gia_cu"] is False


# ── 3. Đặt hàng ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestDatHang:
    async def test_phai_co_ngay_ncc_hen_giao(self, client: AsyncClient, thu_mua, sales_user, du_an, mau, db_session):  # noqa: F811
        dong_id = await _dong_da_chot(client, thu_mua, du_an, mau)
        url, h = f"{H}/dong/{dong_id}/dat-hang", auth_header(thu_mua)
        r = await client.post(url, headers=h, json={})
        assert r.status_code == 400 and r.json()["detail"] == "Chọn ngày NCC hẹn giao"
        hom_qua = (vn_today() - timedelta(days=1)).isoformat()
        r = await client.post(url, headers=h, json={"ngay_giao_hen": hom_qua})
        assert r.status_code == 400 and "trước hôm nay" in r.json()["detail"]
        assert (await db_session.get(DongPhieuVatTu, dong_id)).trang_thai == "da_chot_gia"
        r = await client.post(url, headers=h, json={"ngay_giao_hen": vn_today().isoformat()})  # hẹn giao ngay hôm nay: được
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ngay_giao_hen"] == d["ngay_giao_hen_dau"] == vn_today().isoformat() and d["tre_hen"] is False
        # Qua ngày hẹn mà hàng chưa về đủ → trễ hẹn; sale cũng thấy (không lộ gì về giá)
        dong = await db_session.get(DongPhieuVatTu, dong_id)
        dong.ngay_giao_hen = vn_today() - timedelta(days=1)
        await db_session.commit()
        for u in (thu_mua, sales_user):
            items = (await client.get(f"{H}/du-an/{du_an.id}/dong", headers=auth_header(u))).json()["items"]
            assert items[0]["tre_hen"] is True and items[0]["ngay_giao_hen"] == hom_qua

    async def test_dong_huy_sau_khi_dat_giu_nguyen_lam_lich_su(self, client: AsyncClient, admin_user, thu_mua, leader_tm,  # noqa: F811
                                                               sales_user, du_an, mau, db_session):  # noqa: F811
        """Dòng đã từng đặt hàng rồi huỷ: không mở lại, không xoá, không đổi mẫu / số lượng — lời hẹn giao,
        NCC, khối lượng đặt của đơn đã huỷ còn nguyên để chấm NCC. Cần mua lại thì tạo dòng mới."""
        khac = MauVatTu(ma="TM 2", nhom="60x60")
        db_session.add(khac)
        await db_session.commit()
        dong_id = await _dong_da_chot(client, thu_mua, du_an, mau)
        r = await _dat(client, thu_mua, dong_id, ngay_giao_hen=ngay_hen(3))
        assert r.json()["trang_thai"] == "da_dat"
        url = f"{H}/dong/{dong_id}"
        r = await client.patch(url, headers=auth_header(leader_tm), json={"trang_thai": "huy", "huy_ly_do": "NCC báo trễ"})
        assert r.status_code == 200, r.text
        for u in (sales_user, thu_mua, leader_tm, admin_user):
            h = auth_header(u)
            for tt in ("khach_chon", "hoi_ncc") if u is not sales_user else ("khach_chon",):  # «hỏi NCC» là bước của Thu mua
                r = await client.patch(url, headers=h, json={"trang_thai": tt})
                assert r.status_code == 400 and "không mở lại" in r.json()["detail"], (u.role, tt)
            r = await client.delete(url, headers=h)
            assert r.status_code == 400 and "không xoá được" in r.json()["detail"], u.role
            for body in ({"so_luong": 3}, {"mau_id": khac.id}, {"ma_tu_do": "Mã khác"}, {"don_vi": "thùng"}):
                r = await client.patch(url, headers=h, json=body)
                assert r.status_code == 400 and "tạo dòng mới" in r.json()["detail"], (u.role, body)
        r = await client.post(f"{url}/chot", headers=auth_header(thu_mua), json={"gia_von": 190000, "ncc_ten": "Daisan"})
        assert r.status_code == 400
        # Ghi chú vẫn sửa được; đơn đã huỷ còn nguyên dấu vết
        r = await client.patch(url, headers=auth_header(thu_mua), json={"ghi_chu": "Đặt lại ở dòng mới"})
        d = r.json()
        assert r.status_code == 200 and d["trang_thai"] == "huy" and d["huy_ly_do"] == "NCC báo trễ"
        assert d["ngay_giao_hen"] == d["ngay_giao_hen_dau"] == ngay_hen(3)
        assert (d["sl_dat"], d["gia_dat"], d["ncc_ten"], d["mau_id"], d["so_luong"]) == (10, 200000, "Hiệp Phát", mau.id, 10)
        # Dòng huỷ khi CHƯA từng đặt hàng (kể cả đơn vượt bị Leader từ chối) thì mở lại / xoá như cũ
        chua_dat = await _dong_da_chot(client, thu_mua, du_an, mau)
        assert (await _dat(client, thu_mua, chua_dat, so_luong=12)).json()["trang_thai"] == "cho_duyet_dat"
        r = await client.post(f"{H}/dong/{chua_dat}/duyet-dat", headers=auth_header(leader_tm), json={"dong_y": False, "ly_do": "Đo lại"})
        assert r.json()["trang_thai"] == "da_chot_gia" and r.json()["sl_dat"] is None
        u2 = f"{H}/dong/{chua_dat}"
        assert (await client.patch(u2, headers=auth_header(sales_user), json={"trang_thai": "huy"})).status_code == 200
        r = await client.patch(u2, headers=auth_header(sales_user), json={"trang_thai": "khach_chon"})
        assert r.status_code == 200 and r.json()["huy_luc"] is None and r.json()["huy_ly_do"] is None
        assert (await client.patch(u2, headers=auth_header(sales_user), json={"trang_thai": "huy"})).status_code == 200
        assert (await client.delete(u2, headers=auth_header(admin_user))).status_code == 204

    async def test_dong_chot_cu_chua_co_ncc_phai_chot_lai_kem_ncc_moi_dat_duoc(self, client: AsyncClient, thu_mua, du_an, mau, db_session):  # noqa: F811
        dong_id = await _dong_da_chot(client, thu_mua, du_an, mau)
        d = await db_session.get(DongPhieuVatTu, dong_id)
        d.ncc_id = None  # dòng chốt trước 22/11: lúc đó chốt giá không bắt buộc NCC
        await db_session.commit()
        r = await _dat(client, thu_mua, dong_id)
        assert r.status_code == 400 and "chưa có nhà cung cấp" in r.json()["detail"]
        assert d.trang_thai == "da_chot_gia" and d.sl_dat is None and d.ngay_giao_hen is None
        r = await client.post(f"{H}/dong/{dong_id}/chot", headers=auth_header(thu_mua), json={"gia_von": 200000, "ncc_ten": "Hiệp Phát"})
        assert r.status_code == 200 and r.json()["khach_dong_y_luc"], "giá bán không đổi → không phải hỏi lại khách"
        r = await _dat(client, thu_mua, dong_id)
        assert r.status_code == 200 and r.json()["trang_thai"] == "da_dat" and r.json()["ncc_ten"] == "Hiệp Phát"

    async def test_don_gia_go_thap_khong_lam_ngan_sach_con_du(self, client: AsyncClient, thu_mua, du_an, mau, db_session):  # noqa: F811
        """Trần ngân sách tính theo giá vốn ĐÃ CHỐT khi đơn giá gõ lúc đặt thấp hơn — cả đơn đang đặt lẫn
        các đơn đã đặt trước đó (gõ 1đ không làm ngân sách «còn dư» cho các đơn sau)."""
        du_an.budget_total = 1_000_000
        await db_session.commit()
        a = await _dong_da_chot(client, thu_mua, du_an, mau, so_luong=100, gia_von=200000)  # 20tr theo giá chốt
        r = await _dat(client, thu_mua, a, don_gia=1)
        d = r.json()
        assert d["trang_thai"] == "cho_duyet_dat" and d["gia_dat"] == 1
        assert d["ly_do_vuot"] == "Tổng chi phí dự án 20.000.000đ vượt ngân sách 1.000.000đ"
        du_an.budget_total = 30_000_000
        await db_session.commit()
        b = await _dong_da_chot(client, thu_mua, du_an, mau, so_luong=75, gia_von=200000)   # +15tr → 35tr > 30tr
        d = (await _dat(client, thu_mua, b)).json()
        assert d["trang_thai"] == "cho_duyet_dat"
        assert d["ly_do_vuot"] == "Tổng chi phí dự án 35.000.000đ vượt ngân sách 30.000.000đ"

    async def test_ngan_sach_la_tran_moi_chi_phi_tru_material(self, client: AsyncClient, thu_mua, giam_sat, du_an, mau, db_session):  # noqa: F811
        """Ngân sách 10tr = trần TOÀN BỘ chi phí dự án: vật tư đã đặt + đơn này + khoản chi khác.
        Giao dịch chi loại «material» (trả tiền NCC) không cộng — đã nằm trong vật tư đã đặt."""
        def gd(loai, so_tien, trang_thai="completed", kieu="expense"):
            return Transaction(id=_uid(), code=f"GD-{_uid()[:6]}", type=kieu, category=loai, description="x", amount=so_tien,
                               project_id=du_an.id, status=trang_thai, date=datetime.utcnow())
        db_session.add_all([gd("material", 5_000_000), gd("labor", 9_000_000, "cancelled"),
                            gd("construction_contract", 50_000_000, kieu="income")])
        await db_session.commit()
        a = await _dong_da_chot(client, thu_mua, du_an, mau, so_luong=30, gia_von=200000)  # 6tr
        r = await _dat(client, thu_mua, a)
        assert r.json()["trang_thai"] == "da_dat", "6tr ≤ 10tr: chi «material» 5tr, chi đã huỷ, khoản THU đều không tính"
        db_session.add(gd("labor", 3_000_000))
        await db_session.commit()
        b = await _dong_da_chot(client, thu_mua, du_an, mau, so_luong=10, gia_von=200000)  # +2tr; 6 + 2 + nhân công 3 = 11tr
        r = await _dat(client, thu_mua, b)
        d = r.json()
        assert d["trang_thai"] == "cho_duyet_dat"
        assert d["ly_do_vuot"] == "Tổng chi phí dự án 11.000.000đ vượt ngân sách 10.000.000đ"


# ── 4. Dòng đã đặt hàng không sửa lặng lẽ ─────────────────────────────────

@pytest.mark.asyncio
class TestDongDaDat:
    async def test_khong_sua_khong_xoa_chi_leader_huy_co_ly_do(self, client: AsyncClient, admin_user, thu_mua, leader_tm, sales_user,  # noqa: F811
                                                               du_an, mau, db_session):  # noqa: F811
        khac = MauVatTu(ma="TM 2", nhom="60x60")
        db_session.add(khac)
        await db_session.commit()
        dong_id = await _dong_da_chot(client, thu_mua, du_an, mau)
        assert (await _dat(client, thu_mua, dong_id)).json()["trang_thai"] == "da_dat"
        du_an_id = du_an.id
        assert float((await db_session.get(Project, du_an_id)).spent) == 2_000_000
        url = f"{H}/dong/{dong_id}"
        for body in ({"so_luong": 12}, {"mau_id": khac.id}, {"ma_tu_do": "Mã khác"}, {"don_vi": "thùng"},
                     {"mau_thay_the_id": khac.id}, {"ma_thay_the": "Mã thay"}):
            for u in (thu_mua, leader_tm, admin_user):
                r = await client.patch(url, headers=auth_header(u), json=body)
                assert r.status_code == 400 and "đã đặt hàng" in r.json()["detail"], (body, u.role)
        # Gửi lại đúng giá trị cũ kèm trường không khoá → không tính là sửa
        r = await client.patch(url, headers=auth_header(thu_mua), json={"so_luong": 10, "ghi_chu": "Giao giờ hành chính"})
        assert r.status_code == 200 and r.json()["ghi_chu"] == "Giao giờ hành chính" and r.json()["trang_thai"] == "da_dat"
        # Không lùi trạng thái; huỷ: người thường 403, Leader thiếu lý do 400
        assert (await client.patch(url, headers=auth_header(thu_mua), json={"trang_thai": "hoi_ncc"})).status_code == 400
        assert (await client.patch(url, headers=auth_header(leader_tm), json={"trang_thai": "khach_chon"})).status_code == 400
        for u in (thu_mua, sales_user):
            r = await client.patch(url, headers=auth_header(u), json={"trang_thai": "huy", "huy_ly_do": "Khách đổi ý"})
            assert r.status_code == 403, u.department
        for body in ({"trang_thai": "huy"}, {"trang_thai": "huy", "huy_ly_do": "   "}):
            r = await client.patch(url, headers=auth_header(leader_tm), json=body)
            assert r.status_code == 400 and "lý do" in r.json()["detail"]
        for u in (thu_mua, leader_tm, admin_user):
            r = await client.delete(url, headers=auth_header(u))
            assert r.status_code == 400 and "đã đặt hàng" in r.json()["detail"]
        assert (await db_session.get(DongPhieuVatTu, dong_id)).trang_thai == "da_dat"
        # Leader huỷ kèm lý do → ghi vết + nhật ký kiểm toán + chi phí dự án giảm
        r = await client.patch(url, headers=auth_header(leader_tm), json={"trang_thai": "huy", "huy_ly_do": "  Khách đổi sang gạch khác "})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["trang_thai"] == "huy" and d["huy_ly_do"] == "Khách đổi sang gạch khác"
        assert d["huy_boi_ten"] == "Leader Thu Mua" and d["huy_luc"]
        log = (await db_session.execute(select(AuditLog).where(AuditLog.action == "vat_tu.huy_dong"))).scalar_one()
        assert log.entity_id == dong_id and log.actor_id == leader_tm.id
        assert '"da_dat"' in log.before_json and "Khách đổi sang gạch khác" in log.after_json
        p = (await db_session.execute(select(Project).where(Project.id == du_an_id)
                                      .execution_options(populate_existing=True))).scalar_one()
        assert float(p.spent) == 0

    async def test_hang_da_giao_du_khong_huy_duoc(self, client: AsyncClient, thu_mua, leader_tm, giam_sat, du_an, mau, db_session):  # noqa: F811
        dong_id = await _dong_da_chot(client, thu_mua, du_an, mau)
        await _dat(client, thu_mua, dong_id)
        r = await client.post(f"{H}/dong/{dong_id}/nhan-hang", headers=auth_header(giam_sat),
                              json={"ket_qua": "du", "anh_ids": await _anh(db_session, du_an.id, 2)})
        assert r.json()["trang_thai"] == "da_giao"
        r = await client.patch(f"{H}/dong/{dong_id}", headers=auth_header(leader_tm), json={"trang_thai": "huy", "huy_ly_do": "nhầm"})
        assert r.status_code == 400 and "đã giao" in r.json()["detail"]

    async def test_dong_chua_dat_huy_nhu_cu_va_ghi_vet(self, client: AsyncClient, thu_mua, sales_user, du_an, mau, db_session):  # noqa: F811
        dong_id = await _them(client, thu_mua, du_an, mau_id=mau.id)
        r = await client.patch(f"{H}/dong/{dong_id}", headers=auth_header(sales_user), json={"trang_thai": "huy"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["trang_thai"] == "huy" and d["huy_luc"] and d["huy_boi_ten"] == sales_user.full_name and d["huy_ly_do"] is None
        assert (await db_session.execute(select(AuditLog).where(AuditLog.action == "vat_tu.huy_dong"))).first() is None
        assert (await client.delete(f"{H}/dong/{dong_id}", headers=auth_header(sales_user))).status_code == 204

    async def test_huy_dong_giao_thieu_thi_dong_o_so_da_nhan(self, client: AsyncClient, admin_user, thu_mua, leader_tm,  # noqa: F811
                                                             giam_sat, du_an, mau, db_session):  # noqa: F811
        """Hàng đã về 4/10 rồi Leader huỷ phần còn lại: dòng đóng ở 4 (đã giao), tiền 4 đơn vị đã nhận còn
        trong chi phí dự án; lý do huỷ + nhật ký ghi lại phần bị bỏ."""
        async def chi_phi() -> float:
            p = (await db_session.execute(select(Project).where(Project.id == du_an_id)
                                          .execution_options(populate_existing=True))).scalar_one()
            return float(p.spent)

        du_an_id = du_an.id
        dong_id = await _dong_da_chot(client, thu_mua, du_an, mau)   # 10 × 200.000
        await _dat(client, thu_mua, dong_id)
        url = f"{H}/dong/{dong_id}"
        r = await client.post(f"{url}/nhan-hang", headers=auth_header(giam_sat), json={
            "ket_qua": "thieu", "so_luong_nhan": 4, "ghi_chu": "Về 4", "anh_ids": await _anh(db_session, du_an_id, 2)})
        assert r.json()["trang_thai"] == "giao_thieu" and await chi_phi() == 2_000_000
        r = await client.patch(url, headers=auth_header(leader_tm), json={"trang_thai": "huy", "huy_ly_do": "NCC hết hàng"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["trang_thai"] == "da_giao" and d["so_luong"] == d["sl_dat"] == d["sl_nhan"] == 4
        assert d["huy_ly_do"] == "NCC hết hàng" and d["huy_boi_ten"] == "Leader Thu Mua" and d["huy_luc"]
        assert len(d["nhan_lich_su"]) == 1 and d["thanh_tien"] == 4 * d["gia_ban"] and d["tre_hen"] is False
        assert await chi_phi() == 800_000, "4 đơn vị đã nhận × 200.000 — không về 0"
        log = (await db_session.execute(select(AuditLog).where(AuditLog.action == "vat_tu.huy_dong"))).scalar_one()
        assert json.loads(log.before_json)["sl_dat"] == 10
        assert json.loads(log.after_json) == {"trang_thai": "da_giao", "sl_dat": 4, "huy_ly_do": "NCC hết hàng"}
        # Dòng đã đóng = đã giao: không huỷ tiếp, không xoá
        r = await client.patch(url, headers=auth_header(leader_tm), json={"trang_thai": "huy", "huy_ly_do": "lần nữa"})
        assert r.status_code == 400 and "đã giao" in r.json()["detail"]
        assert (await client.delete(url, headers=auth_header(admin_user))).status_code == 400
        # Giao thiếu mà CHƯA về gì: huỷ hẳn (chi phí của dòng về 0), vẫn giữ làm lịch sử — không xoá được
        dong_2 = await _dong_da_chot(client, thu_mua, du_an, mau)
        await _dat(client, thu_mua, dong_2)
        r = await client.post(f"{H}/dong/{dong_2}/nhan-hang", headers=auth_header(giam_sat), json={
            "ket_qua": "thieu", "so_luong_nhan": 0, "ghi_chu": "Xe chưa tới", "anh_ids": await _anh(db_session, du_an_id, 2)})
        assert r.json()["trang_thai"] == "giao_thieu" and await chi_phi() == 2_800_000
        r = await client.patch(f"{H}/dong/{dong_2}", headers=auth_header(leader_tm), json={"trang_thai": "huy", "huy_ly_do": "NCC hết hàng"})
        assert r.status_code == 200 and r.json()["trang_thai"] == "huy" and len(r.json()["nhan_lich_su"]) == 1
        assert await chi_phi() == 800_000
        r = await client.delete(f"{H}/dong/{dong_2}", headers=auth_header(admin_user))
        assert r.status_code == 400 and "không xoá được" in r.json()["detail"]

    async def test_xoa_dong_giu_bao_gia_ncc_lam_gia_nhap_theo_mau(self, client: AsyncClient, thu_mua, sales_user, du_an, mau, db_session):  # noqa: F811
        """Sale xoá được dòng đang hỏi giá, nhưng báo giá NCC của dòng (căn cứ của Bảng giá chuẩn) không mất theo."""
        dong_id = await _them(client, sales_user, du_an, mau_id=mau.id)
        mau_id, ht = mau.id, auth_header(thu_mua)
        r = await client.post(f"{H}/dong/{dong_id}/bao-gia", headers=ht, json={"ncc_ten": "Hiệp Phát", "gia": 200000, "ghi_chu": "Chưa VAT"})
        bg = r.json()["bao_gia"][0]
        await client.post(f"{H}/bot/ghi-bao-gia", headers=ht, json={"items": [{"dong_id": dong_id, "ncc_ten": "NCC chưa rõ", "gia": 150000}]})
        assert (await client.delete(f"{H}/dong/{dong_id}", headers=auth_header(sales_user))).status_code == 204
        assert (await db_session.execute(select(BaoGiaDongVatTu))).first() is None
        g = (await db_session.execute(select(GiaNhapMauVatTu))).scalars().all()
        assert len(g) == 1, "báo giá không rõ NCC thì không có gì để giữ"
        assert (g[0].mau_id, g[0].supplier_id, g[0].gia, g[0].nguon, g[0].ghi_chu, g[0].created_by) == (
            mau_id, bg["supplier_id"], 200000, "tay", "Chưa VAT", thu_mua.id)
        assert g[0].created_at.tzinfo is None and _gan(g[0].created_at, datetime.fromisoformat(bg["created_at"]).replace(tzinfo=None))
        x = (await client.get(f"{H}/gia-chuan", headers=ht)).json()["items"][0]
        assert [(n["ncc_ten"], n["gia"]) for n in x["gia_nhap"]] == [("Hiệp Phát", 200000)]
        log = (await db_session.execute(select(AuditLog).where(AuditLog.action == "vat_tu.xoa_dong"))).scalar_one()
        truoc = json.loads(log.before_json)
        assert (truoc["ten"], truoc["so_bao_gia"], truoc["giu_lam_gia_nhap"]) == ("TM 76006", 2, 1)
        # Dòng mã tự do: không có mẫu để gắn giá nhập → xoá như cũ
        tu_do = await _them(client, sales_user, du_an, ma_tu_do="Lavabo L-333", don_vi="cái")
        await client.post(f"{H}/dong/{tu_do}/bao-gia", headers=ht, json={"ncc_ten": "Inax", "gia": 900000})
        assert (await client.delete(f"{H}/dong/{tu_do}", headers=auth_header(sales_user))).status_code == 204
        assert len((await db_session.execute(select(GiaNhapMauVatTu))).scalars().all()) == 1

    async def test_don_vuot_dang_cho_duyet_cung_la_dong_da_dat(self, client: AsyncClient, thu_mua, leader_tm, du_an, mau, db_session):  # noqa: F811
        """Đơn vượt đang chờ Leader duyệt cũng đã cam kết với NCC: không sửa, không xoá, chỉ Leader huỷ."""
        dong_id = await _dong_da_chot(client, thu_mua, du_an, mau)
        assert (await _dat(client, thu_mua, dong_id, so_luong=12)).json()["trang_thai"] == "cho_duyet_dat"
        du_an_id, url = du_an.id, f"{H}/dong/{dong_id}"
        assert (await client.patch(url, headers=auth_header(thu_mua), json={"so_luong": 12})).status_code == 400
        assert (await client.delete(url, headers=auth_header(thu_mua))).status_code == 400
        r = await client.patch(url, headers=auth_header(thu_mua), json={"trang_thai": "huy", "huy_ly_do": "Đặt nhầm"})
        assert r.status_code == 403
        r = await client.patch(url, headers=auth_header(leader_tm), json={"trang_thai": "huy", "huy_ly_do": "Đặt nhầm"})
        assert r.status_code == 200 and r.json()["trang_thai"] == "huy" and r.json()["huy_ly_do"] == "Đặt nhầm"
        p = (await db_session.execute(select(Project).where(Project.id == du_an_id)
                                      .execution_options(populate_existing=True))).scalar_one()
        assert float(p.spent) == 0


# ── 5. Nhận hàng giữ lịch sử ──────────────────────────────────────────────

@pytest.mark.asyncio
class TestNhanHangLichSu:
    async def test_moi_lan_nhan_mot_dong_lich_su(self, client: AsyncClient, thu_mua, sales_user, giam_sat, du_an, mau, db_session):  # noqa: F811
        dong_id = await _dong_da_chot(client, thu_mua, du_an, mau)
        await _dat(client, thu_mua, dong_id)
        anh = await _anh(db_session, du_an.id, 6)
        url, h = f"{H}/dong/{dong_id}/nhan-hang", auth_header(giam_sat)
        co_ban = {"ket_qua": "thieu", "ghi_chu": "Thiếu", "anh_ids": anh[:2]}
        assert (await client.post(url, headers=h, json={**co_ban, "so_luong_nhan": 7, "ly_do_loi": "be_vo"})).status_code == 400
        assert (await client.post(url, headers=h, json={**co_ban, "so_luong_nhan": 10})).status_code == 400  # đã đủ → chọn «Đủ»
        assert (await db_session.execute(select(NhanHangVatTu))).first() is None, "lần gọi bị từ chối không để lại lịch sử"
        r = await client.post(url, headers=h, json={**co_ban, "so_luong_nhan": 7, "ly_do_loi": "hu_hong"})
        assert r.status_code == 200, r.text
        ls = r.json()["nhan_lich_su"]
        assert len(ls) == 1 and ls[0]["ket_qua"] == "thieu" and ls[0]["sl_lan_nay"] == 7 and ls[0]["sl_luy_ke"] == 7
        assert ls[0]["ly_do_loi"] == "hu_hong" and ls[0]["ly_do_loi_nhan"] == "Hư hỏng, bể vỡ"
        assert ls[0]["boi_ten"] == "Giam Sat Test" and ls[0]["luc"] and ls[0]["ghi_chu"] == "Thiếu"
        # Lần sau: tổng đã về không được ít hơn lần trước
        r = await client.post(url, headers=h, json={**co_ban, "so_luong_nhan": 5, "anh_ids": anh[2:4]})
        assert r.status_code == 400 and "ít hơn lần trước" in r.json()["detail"]
        r = await client.post(url, headers=h, json={**co_ban, "so_luong_nhan": 9, "anh_ids": anh[2:4]})
        assert r.status_code == 200 and r.json()["sl_nhan"] == 9 and r.json()["trang_thai"] == "giao_thieu"
        r = await client.post(url, headers=h, json={"ket_qua": "du", "anh_ids": anh[4:]})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["trang_thai"] == "da_giao" and d["sl_nhan"] == 10 and len(d["nhan_anh"]) == 6
        assert [(x["ket_qua"], x["sl_lan_nay"], x["sl_luy_ke"]) for x in d["nhan_lich_su"]] == [("thieu", 7, 7), ("thieu", 2, 9), ("du", 1, 10)]
        rows = (await db_session.execute(select(NhanHangVatTu).order_by(NhanHangVatTu.luc))).scalars().all()
        assert [r_.boi for r_ in rows] == [giam_sat.id] * 3 and all(r_.luc.tzinfo is None for r_ in rows)
        import json
        assert [json.loads(r_.anh_ids) for r_ in rows] == [anh[:2], anh[2:4], anh[4:]], "mỗi dòng giữ ảnh của ĐÚNG lần đó"
        # Sale xem được lịch sử nhận hàng (không có gì về giá)
        items = (await client.get(f"{H}/du-an/{du_an.id}/dong", headers=auth_header(sales_user))).json()["items"]
        assert len(items[0]["nhan_lich_su"]) == 3

    async def test_ly_do_loi_de_trong_la_khong_ghi_loi(self, client: AsyncClient, thu_mua, giam_sat, du_an, mau, db_session):  # noqa: F811
        dong_id = await _dong_da_chot(client, thu_mua, du_an, mau)
        await _dat(client, thu_mua, dong_id)
        r = await client.post(f"{H}/dong/{dong_id}/nhan-hang", headers=auth_header(giam_sat),
                              json={"ket_qua": "du", "ly_do_loi": "", "anh_ids": await _anh(db_session, du_an.id, 2)})
        assert r.status_code == 200, r.text
        ls = r.json()["nhan_lich_su"]
        assert len(ls) == 1 and ls[0]["ly_do_loi"] is None and ls[0]["ly_do_loi_nhan"] is None


# ── 6. Việc nhỏ ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestViecNho:
    async def test_can_hoi_gia_viec_gap_len_dau(self, client: AsyncClient, thu_mua, du_an, mau):  # noqa: F811
        khong_han = await _them(client, thu_mua, du_an, mau_id=mau.id)
        xa = await _them(client, thu_mua, du_an, mau_id=mau.id, can_ngay=ngay_hen(10))
        gap = await _them(client, thu_mua, du_an, mau_id=mau.id, can_ngay=ngay_hen(2))
        khong_han_2 = await _them(client, thu_mua, du_an, mau_id=mau.id)
        items = (await client.get(f"{H}/can-hoi-gia", headers=auth_header(thu_mua))).json()["items"]
        assert [i["id"] for i in items] == [gap, xa, khong_han, khong_han_2]

    async def test_goi_y_ncc_kem_hang_ncc_chinh_len_truoc(self, client: AsyncClient, admin_user, du_an, mau, db_session):  # noqa: F811
        ds = {ten: Supplier(id=_uid(), name=ten, hang=hang) for ten, hang in
              (("Chưa xếp", None), ("Chính", "chinh"), ("Dự phòng", "du_phong"), ("Đang thử", "thu"))}
        d = DongPhieuVatTu(id=_uid(), project_id=du_an.id, mau_id=mau.id, so_luong=1)
        db_session.add_all([*ds.values(), d])
        await db_session.flush()
        # NCC chưa xếp hạng rẻ nhất, NCC chính đắt nhất — hạng vẫn quyết định thứ tự
        for ten, gia in (("Chưa xếp", 80000), ("Chính", 120000), ("Dự phòng", 100000), ("Đang thử", 90000)):
            db_session.add(BaoGiaDongVatTu(dong_id=d.id, supplier_id=ds[ten].id, ncc_ten=ten, gia=gia))
        await db_session.commit()
        j = (await client.get(f"{H}/mau/{mau.id}/goi-y-ncc", headers=auth_header(admin_user))).json()
        assert [(x["ncc_ten"], x["hang"]) for x in j["items"]] == [
            ("Chính", "chinh"), ("Dự phòng", "du_phong"), ("Đang thử", "thu"), ("Chưa xếp", None)]
        assert j["goi_y"]["ncc_ten"] == "Chính"

    async def test_goi_y_ncc_xep_theo_gia_sau_chiet_khau(self, client: AsyncClient, admin_user, du_an, mau, db_session):  # noqa: F811
        a = Supplier(id=_uid(), name="NCC A", chiet_khau_pct=20)   # 110k → 88k sau CK
        b = Supplier(id=_uid(), name="NCC B", chiet_khau_pct=0)    # 95k
        db_session.add_all([a, b])
        await db_session.flush()
        d = DongPhieuVatTu(id=_uid(), project_id=du_an.id, mau_id=mau.id, so_luong=10)
        cu = DongPhieuVatTu(id=_uid(), project_id=du_an.id, mau_id=mau.id, so_luong=100, gia_von=90000, ncc_id=b.id,
                            trang_thai="da_dat")
        db_session.add_all([d, cu])
        await db_session.flush()
        db_session.add_all([
            BaoGiaDongVatTu(dong_id=d.id, supplier_id=a.id, ncc_ten="NCC A", gia=110000),
            BaoGiaDongVatTu(dong_id=d.id, supplier_id=b.id, ncc_ten="NCC B", gia=95000),
        ])
        await db_session.commit()
        j = (await client.get(f"{H}/mau/{mau.id}/goi-y-ncc", headers=auth_header(admin_user))).json()
        assert set(j) == {"items", "goi_y"}
        assert j["goi_y"]["ncc_ten"] == "NCC A" and j["goi_y"]["gia_sau_ck"] == 88000
        assert j["items"][1]["da_mua"] == 9_000_000


# ── Sale / thiết kế không bao giờ nhận giá vốn, NCC, báo giá, lãi ──────────

CAM = ("gia_von", "ncc_id", "ncc_ten", "phan_tram_ap_dung", "gia_dat", "lai", "bao_gia", "gia_cu", "gia_xac_nhan_luc",
       "gia_von_gan_nhat", "gia_tham_khao", "ncc_gan_nhat_id", "ncc_gan_nhat_ten", "gia_von_cap_nhat_luc", "gia_gan_nhat_cu")


@pytest.mark.asyncio
async def test_sale_thiet_ke_khong_bao_gio_nhan_gia_von_ncc_bao_gia_lai(client: AsyncClient, thu_mua, thiet_ke, sales_user,  # noqa: F811
                                                                        giam_sat, du_an, mau, db_session):  # noqa: F811
    """Đi hết vòng đời một dòng; mọi phản hồi tới sale/thiết kế đều không có giá vốn, NCC, báo giá, % lãi."""
    mau.gia_ban_co_dinh = 300000
    await db_session.commit()
    hs, ht = auth_header(sales_user), auth_header(thu_mua)
    tra_ve: list = []

    def soi(r):
        assert r.status_code in (200, 201), r.text
        tra_ve.append(r)
        return r.json()

    dong_id = soi(await client.post(f"{H}/du-an/{du_an.id}/dong", headers=hs, json={"phong": "Bếp", "mau_id": mau.id, "so_luong": 10}))["id"]
    await client.post(f"{H}/dong/{dong_id}/bao-gia", headers=ht, json={"ncc_ten": "Nhà Cung Cấp Bí Mật", "gia": 123456})
    soi(await client.post(f"{H}/dong/{dong_id}/khach-dong-y", headers=hs, json={}))
    await client.post(f"{H}/dong/{dong_id}/chot", headers=ht, json={"gia_von": 290111, "ncc_ten": "Nhà Cung Cấp Bí Mật"})
    soi(await client.patch(f"{H}/dong/{dong_id}", headers=auth_header(thiet_ke), json={"ghi_chu": "Ốp tới trần"}))
    r = await client.post(f"{H}/dong/{dong_id}/dat-hang", headers=ht, json={"ngay_giao_hen": ngay_hen(), "don_gia": 290222})
    assert r.json()["trang_thai"] == "cho_duyet_dat" and "290.222đ" in r.json()["ly_do_vuot"]
    soi(await client.get(f"{H}/du-an/{du_an.id}/dong", headers=hs))  # đang chờ duyệt: lý do vượt chứa giá vốn
    d = await db_session.get(DongPhieuVatTu, dong_id)
    d.trang_thai = "da_dat"
    await db_session.commit()
    await client.post(f"{H}/dong/{dong_id}/nhan-hang", headers=auth_header(giam_sat), json={
        "ket_qua": "thieu", "so_luong_nhan": 6, "ghi_chu": "Thiếu 4", "anh_ids": await _anh(db_session, du_an.id, 2)})
    for u in (sales_user, thiet_ke):
        body = soi(await client.get(f"{H}/du-an/{du_an.id}/dong", headers=auth_header(u)))
        assert body["thay_gia_von"] is False and "tong_lai" not in body
        dong = body["items"][0]
        assert dong["gia_ban"] == 300000 and dong["ngay_giao_hen"] and len(dong["nhan_lich_su"]) == 1  # cái họ ĐƯỢC thấy
        assert dong["dat_boi"] == thu_mua.id and dong["dat_boi_ten"] == "Thu Mua Test"  # ai đặt đơn: mọi vai đều thấy
    soi(await client.get(f"{H}/viec-dat-nhan", headers=hs))
    soi(await client.get(f"{H}/mau", headers=hs))
    for r in tra_ve:
        for bi_mat in ("Bí Mật", "123456", "123.456", "290111", "290.111", "290222", "290.222"):
            assert bi_mat not in r.text, (r.request.url.path, bi_mat)
        j = r.json()
        for dong in (j.get("items") or j.get("cho_nhan") or [j]) if isinstance(j, dict) else []:
            for cam in CAM:
                assert cam not in dong, (r.request.url.path, cam)
            assert dong.get("ly_do_vuot") is None
    # Các lối chỉ dành cho Thu mua / Ban giám đốc
    for u in (sales_user, thiet_ke):
        h = auth_header(u)
        assert (await client.get(f"{H}/can-hoi-gia", headers=h)).status_code == 403
        assert (await client.get(f"{H}/ncc", headers=h)).status_code == 403
        assert (await client.get(f"{H}/mau/{mau.id}/goi-y-ncc", headers=h)).status_code == 403
        assert (await client.post(f"{H}/dong/{dong_id}/chot", headers=h, json={"gia_von": 1, "ncc_ten": "X"})).status_code == 403
        assert (await client.post(f"{H}/dong/{dong_id}/bao-gia", headers=h, json={"ncc_ten": "X", "gia": 1})).status_code == 403
        assert (await client.post(f"{H}/dong/{dong_id}/dat-hang", headers=h, json={"ngay_giao_hen": ngay_hen()})).status_code == 403
