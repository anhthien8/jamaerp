"""Dữ liệu gốc Nhà cung cấp sạch (22/11/2026): một NCC một dòng.

- `khoa_ncc`: «Công ty TNHH TM & DV Hiệp Phát», «Cty Hiệp Phát», «Hiệp Phát» là MỘT nhà cung cấp.
- Tạo / đổi tên trùng tên hoặc trùng mã số thuế → 409 nêu đích danh NCC đang có.
- Hạng NCC, «Ngừng dùng», lọc danh sách.
- BGĐ gộp NCC trùng: mọi cột giữ id NCC chuyển sang NCC giữ lại, NCC kia bị xoá.
"""

import json
from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.api.suppliers import _COT_NCC
from app.database import Base
from app.models.audit import AuditLog
from app.models.project import Project
from app.models.supplier import PriceComparison, Supplier, SupplierQuote
from app.models.vat_tu import BaoGiaDongVatTu, DongPhieuVatTu, GiaNhapMauVatTu, MauVatTu
from app.services.ncc import GHI_CHU_TU_TAO, BoNcc, khoa_ncc
from tests.conftest import _uid, auth_header

API = "/api/v1/suppliers"
MOC_CU = datetime(2026, 1, 1, 8, 0, 0)


async def _so_ncc(db) -> int:
    return (await db.execute(select(func.count()).select_from(Supplier))).scalar()


async def _tao(client: AsyncClient, nguoi, **du_lieu):
    return await client.post(API, json=du_lieu, headers=auth_header(nguoi))


async def _sua(client: AsyncClient, nguoi, ncc_id: str, **du_lieu):
    return await client.put(f"{API}/{ncc_id}", json=du_lieu, headers=auth_header(nguoi))


# ── khoa_ncc ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ten", [
    "Hiệp Phát",
    "  CÔNG TY   TNHH Hiệp  Phát ",
    "Cty TNHH MTV TM & DV Hiệp Phát",
    "Cty. CP TM-DV Hiệp Phát",
    "Công ty Cổ phần Thương mại và Dịch vụ Hiệp Phát",
    "Công ty TNHH Một Thành Viên Sản Xuất - Xuất Nhập Khẩu Hiệp Phát",
    "Doanh nghiệp tư nhân Hiệp Phát",
    "DNTN Hiệp Phát",
    "Hộ kinh doanh Hiệp Phát",
    "HKD Hiệp Phát",
    "Cửa hàng Hiệp Phát",
    "SX XNK Hiệp Phát",
    # chữ tắt viết dính, «1 thành viên», dấu chấm cuối tên
    "Cty TNHH TMDV Hiệp Phát",
    "CTCP Hiệp Phát",
    "Công ty TNHH SXTM Hiệp Phát",
    "Cty TMSX - SXTMDV Hiệp Phát",
    "Công ty TNHH 1 thành viên Hiệp Phát",
    "Cty TNHH 1TV Hiệp Phát",
    "CÔNG TY TNHH HIỆP PHÁT.",
    "Hiệp Phát ,. ",
])
def test_khoa_ncc_bo_chu_loai_hinh_dung_dau(ten):
    assert khoa_ncc(ten) == "hiệp phát"


@pytest.mark.parametrize("a, b", [
    ("Hoà Phát", "Hòa Phát"),
    ("Thuỷ Tinh", "Thủy Tinh"),
    ("Quý", "Qúy"),
    ("Khoẻ", "Khỏe"),
    ("Hoá chất Thuý Uỷ", "Hóa chất Thúy Ủy"),
    ("HOÀ PHÁT", "Công ty CP Hòa Phát"),
])
def test_khoa_ncc_khong_ke_kieu_bo_dau(a, b):
    """«oà/òa», «uỷ/ủy»: hai kiểu bỏ dấu đều đúng chính tả, NFC không gộp — bộ gõ kiểu cũ và kiểu mới
    cho ra hai chuỗi khác nhau của CÙNG một tên."""
    assert a != b and khoa_ncc(a) == khoa_ncc(b)
    # chỉ khoá so trùng gộp kiểu bỏ dấu; chữ không thuộc cặp oa/oe/uy thì nguyên vẹn
    assert khoa_ncc("Của Mùa Hoài") == "của mùa hoài"


def test_khoa_ncc_khong_cat_nham():
    # chỉ cắt TRỌN TỪ: «TMall», «CPS» không phải «TM», «CP»
    assert khoa_ncc("TMall Việt Nam") == "tmall việt nam"
    assert khoa_ncc("CPS Tech") == "cps tech"
    # chỉ cắt ở ĐẦU tên — chữ loại hình nằm giữa/cuối là tên riêng
    assert khoa_ncc("Hiệp Phát Thương Mại") == "hiệp phát thương mại"
    # «và» không nối sang chữ loại hình nào → là tên riêng
    assert khoa_ncc("Công ty Và Cộng Sự") == "và cộng sự"
    # «và» đứng ngay sau chữ NGÀNH NGHỀ thì là chữ nối («Thương mại và Xây dựng»), không phải tên riêng
    assert khoa_ncc("Công ty TNHH Thương mại và Xây dựng Hoà Bình") == khoa_ncc("Xây dựng Hòa Bình")
    # tên chỉ gồm chữ loại hình → không để khoá rỗng
    assert khoa_ncc("Công ty Thương mại") == "công ty thương mại"
    assert khoa_ncc(None) == "" and khoa_ncc("   ") == ""


# ── BoNcc: gõ tên ở Vật tư ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bo_ncc_khop_khong_ke_chu_loai_hinh(db_session):
    ngan = Supplier(id=_uid(), name="Hiệp Phát")
    dai = Supplier(id=_uid(), name="Công ty TNHH Gạch Minh Long")
    db_session.add_all([ngan, dai])
    await db_session.commit()
    truoc = await _so_ncc(db_session)

    bo = BoNcc(db_session)
    assert (await bo.lay("Công ty TNHH TM & DV Hiệp Phát")).id == ngan.id
    assert (await bo.lay("cty hiệp   phát")).id == ngan.id
    assert (await bo.lay("gạch minh long")).id == dai.id
    assert await _so_ncc(db_session) == truoc, "không được tạo NCC trùng"

    # tên mới → tạo, giữ nguyên chữ người dùng gõ; gõ dạng ngắn ngay sau đó vẫn ra NCC vừa tạo
    moi = await bo.lay("Cty Sơn Hà")
    assert moi.name == "Cty Sơn Hà" and moi.notes == GHI_CHU_TU_TAO
    assert (await bo.lay("Sơn Hà")).id == moi.id
    assert await _so_ncc(db_session) == truoc + 1
    # bộ gõ kiểu cũ «Hoà» và kiểu mới «Hòa» là một tên → không tạo NCC thứ hai
    assert (await bo.lay("Hoà Phát")).id == (await bo.lay("Công ty CP Hòa Phát")).id
    assert await _so_ncc(db_session) == truoc + 2
    assert await bo.lay("NCC chưa rõ") is None and await bo.lay("  ") is None


@pytest.mark.asyncio
async def test_bo_ncc_hai_ncc_cung_khoa_thi_cu_nhat_thang(db_session):
    """Dữ liệu trước 22/11 có thể đã trùng: luôn về NCC tạo trước, không tuỳ thứ tự DB trả."""
    moi = Supplier(id=_uid(), name="Cty Hiệp Phát", created_at=datetime(2026, 5, 1))
    cu = Supplier(id=_uid(), name="Công ty TNHH Hiệp Phát", created_at=datetime(2026, 2, 1))
    db_session.add_all([moi, cu])
    await db_session.commit()
    assert (await BoNcc(db_session).lay("hiệp phát")).id == cu.id


@pytest.mark.asyncio
async def test_bo_ncc_go_dung_ten_thi_ra_dung_ncc_do(db_session):
    """Hai NCC cùng khoá mà là hai nơi khác nhau: chọn «Cửa hàng Minh Phát» ở ô gợi ý thì phải ra
    đúng nó, không bị kéo về NCC cùng khoá tạo trước."""
    cong_ty = Supplier(id=_uid(), name="Công ty TNHH Minh Phát", created_at=datetime(2026, 2, 1))
    cua_hang = Supplier(id=_uid(), name="Cửa hàng Minh Phát", created_at=datetime(2026, 5, 1))
    db_session.add_all([cong_ty, cua_hang])
    await db_session.commit()
    truoc = await _so_ncc(db_session)

    bo = BoNcc(db_session)
    assert (await bo.lay("Cửa hàng Minh Phát")).id == cua_hang.id
    assert (await bo.lay("  cửa hàng   MINH phát ")).id == cua_hang.id
    assert (await bo.lay("Công ty TNHH Minh Phát")).id == cong_ty.id
    # không tên nào khớp y hệt → mới về khoá: NCC tạo trước
    assert (await bo.lay("Minh Phát")).id == cong_ty.id
    assert (await bo.lay("Cty Minh Phát")).id == cong_ty.id
    assert await _so_ncc(db_session) == truoc


@pytest.mark.asyncio
async def test_bo_ncc_uu_tien_ncc_dang_dung(db_session):
    """NCC cũ đã «Ngừng dùng» + NCC mới đang dùng cùng khoá: tên gõ ở Vật tư phải về NCC ĐANG DÙNG —
    không thì báo giá, giá vốn, đơn hàng treo vào một NCC mà mọi danh sách đều ẩn."""
    ngung = Supplier(id=_uid(), name="Công ty TNHH Hiệp Phát", is_active=False, created_at=datetime(2026, 2, 1))
    dang_dung = Supplier(id=_uid(), name="Cty Hiệp Phát", created_at=datetime(2026, 5, 1))
    db_session.add_all([ngung, dang_dung])
    await db_session.commit()
    assert (await BoNcc(db_session).lay("hiệp phát")).id == dang_dung.id
    # chỉ còn NCC đã ngừng mang tên đó → vẫn về nó, không tạo NCC trùng
    dang_dung.name = "Daisan"
    await db_session.commit()
    assert (await BoNcc(db_session).lay("hiệp phát")).id == ngung.id
    assert await _so_ncc(db_session) == 2


@pytest.mark.asyncio
async def test_bo_ncc_hai_ma_so_thue_khac_nhau_la_hai_ncc(db_session):
    """Bỏ chữ loại hình chỉ là ĐOÁN trùng; hai MST hợp lệ khác 10 số đầu là bằng chứng hai pháp nhân."""
    tnhh = Supplier(id=_uid(), name="Công ty TNHH An Phát", ma_so_thue="0302222222")
    db_session.add(tnhh)
    await db_session.commit()

    bo = BoNcc(db_session)
    cp = await bo.lay("CÔNG TY CỔ PHẦN AN PHÁT", "0301111111")
    assert cp.id != tnhh.id and cp.name == "CÔNG TY CỔ PHẦN AN PHÁT" and cp.ma_so_thue == "0301111111"
    assert await _so_ncc(db_session) == 2
    # chi nhánh («-001») cùng 10 số đầu, tên gõ kiểu khác → vẫn là công ty CP, không phải TNHH, không tạo thêm
    assert (await bo.lay("Cty CP An Phát", "0301111111-001")).id == cp.id
    # không có MST để so → khớp theo tên như cũ (NCC tạo trước)
    assert (await bo.lay("Cty An Phát")).id == tnhh.id
    assert (await bo.lay("An Phát", "0302222222-002")).id == tnhh.id
    # tên Y HỆT thì vẫn là NCC đó dù tệp ghi MST khác (đọc nhầm số) — không sinh 2 NCC trùng tên, không ghi đè MST
    assert (await bo.lay("công ty tnhh an phát", "0309999999")).id == tnhh.id
    assert tnhh.ma_so_thue == "0302222222" and await _so_ncc(db_session) == 2
    # bộ đệm của request sau (nạp lại từ DB) cho cùng kết quả
    await db_session.commit()
    bo2 = BoNcc(db_session)
    assert (await bo2.lay("Công ty CP An Phát", "0301111111-001")).id == cp.id
    assert (await bo2.lay("CÔNG TY CỔ PHẦN AN PHÁT")).id == cp.id


# ── Tạo / đổi tên: chặn trùng ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tao_trung_ten_409_neu_ten_ncc_dang_co(client: AsyncClient, db_session, admin_user):
    r = await _tao(client, admin_user, name="  Hiệp   Phát ", phone="0281234567")
    assert r.status_code == 200, r.text
    goc = r.json()
    assert goc["name"] == "Hiệp Phát" and goc["hang"] is None and goc["is_active"] is True

    r = await _tao(client, admin_user, name="Công ty TNHH TM & DV Hiệp Phát")
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert "«Hiệp Phát»" in detail["message"]
    assert detail["supplier_id"] == goc["id"] and detail["supplier_name"] == "Hiệp Phát"
    assert await _so_ncc(db_session) == 1

    # hai kiểu bỏ dấu của cùng một tên («oà» / «òa») cũng là trùng
    assert (await _tao(client, admin_user, name="Hoà Phát")).status_code == 200
    r = await _tao(client, admin_user, name="Công ty CP Hòa Phát")
    assert r.status_code == 409 and "«Hoà Phát»" in r.json()["detail"]["message"]

    assert (await _tao(client, admin_user, name="   ")).status_code == 400


@pytest.mark.asyncio
async def test_tao_trung_ma_so_thue_409_va_chuan_hoa_mst(client: AsyncClient, db_session, admin_user):
    r = await _tao(client, admin_user, name="Gạch Minh Long", ma_so_thue=" 0312 345 678 ")
    assert r.status_code == 200, r.text
    assert r.json()["ma_so_thue"] == "0312345678"

    r = await _tao(client, admin_user, name="Một tên khác hẳn", ma_so_thue="0312345678")
    assert r.status_code == 409, r.text
    assert "0312345678" in r.json()["detail"]["message"] and "«Gạch Minh Long»" in r.json()["detail"]["message"]

    # MST sai dạng → báo rõ, không âm thầm bỏ
    r = await _tao(client, admin_user, name="NCC Mã Sai", ma_so_thue="12345")
    assert r.status_code == 400 and "Mã số thuế" in r.json()["detail"]
    # để trống MST thì không so trùng
    assert (await _tao(client, admin_user, name="NCC A", ma_so_thue="")).json()["ma_so_thue"] is None
    assert (await _tao(client, admin_user, name="NCC B", ma_so_thue=None)).status_code == 200


@pytest.mark.asyncio
async def test_trung_ncc_da_ngung_dung_thi_bao_ro(client: AsyncClient, db_session, admin_user):
    db_session.add(Supplier(id=_uid(), name="Sơn Hà", is_active=False))
    await db_session.commit()
    r = await _tao(client, admin_user, name="Cửa hàng Sơn Hà")
    assert r.status_code == 409
    assert "ngừng dùng" in r.json()["detail"]["message"] and r.json()["detail"]["is_active"] is False

    # có cả NCC đang dùng cùng tên (tạo sau) → báo NCC đang dùng, không mời «mở để dùng lại» cái đã ngừng
    db_session.add(Supplier(id=_uid(), name="Cty Sơn Hà"))
    await db_session.commit()
    r = await _tao(client, admin_user, name="Cửa hàng Sơn Hà")
    assert r.status_code == 409
    assert "«Cty Sơn Hà»" in r.json()["detail"]["message"] and "ngừng dùng" not in r.json()["detail"]["message"]
    assert r.json()["detail"]["is_active"] is True


@pytest.mark.asyncio
async def test_trung_khoa_nhung_ma_so_thue_khac_thi_la_hai_ncc(client: AsyncClient, db_session, admin_user):
    tnhh = (await _tao(client, admin_user, name="Công ty TNHH An Phát", ma_so_thue="0302222222")).json()
    # không có MST để phân biệt → vẫn coi là trùng
    assert (await _tao(client, admin_user, name="Công ty CP An Phát")).status_code == 409
    # tên Y HỆT thì MST khác cũng không cho: hai NCC cùng tên không ai phân biệt được ở ô gợi ý
    assert (await _tao(client, admin_user, name="công ty  TNHH an phát", ma_so_thue="0301111111")).status_code == 409
    r = await _tao(client, admin_user, name="Công ty CP An Phát", ma_so_thue="0301111111")
    assert r.status_code == 200, r.text
    cp = r.json()
    # chi nhánh cùng 10 số đầu → cùng pháp nhân → vẫn trùng tên
    r = await _tao(client, admin_user, name="An Phát", ma_so_thue="0302222222-001")
    assert r.status_code == 409 and "«Công ty TNHH An Phát»" in r.json()["detail"]["message"]

    # đổi tên: so bằng MST đang lưu của chính NCC (form không gửi lại MST cũng vậy)
    khac = (await _tao(client, admin_user, name="Daisan", ma_so_thue="0303333333")).json()
    r = await _sua(client, admin_user, khac["id"], name="Cửa hàng An Phát")
    assert r.status_code == 200, r.text
    # bỏ MST trong cùng lần sửa → hết bằng chứng → trùng
    r = await _sua(client, admin_user, cp["id"], name="Cty Cổ phần An Phát", ma_so_thue="")
    assert r.status_code == 409, r.text
    assert await _so_ncc(db_session) == 3 and tnhh["id"] != cp["id"]


@pytest.mark.asyncio
async def test_doi_ten_trung_409_con_doi_cach_viet_cua_chinh_no_thi_duoc(client: AsyncClient, db_session, admin_user):
    a = (await _tao(client, admin_user, name="Hiệp Phát", ma_so_thue="0312345678")).json()
    b = (await _tao(client, admin_user, name="Daisan")).json()

    r = await _sua(client, admin_user, b["id"], name="CTY CP hiệp  phát")
    assert r.status_code == 409 and "«Hiệp Phát»" in r.json()["detail"]["message"]
    r = await _sua(client, admin_user, b["id"], ma_so_thue="0312345678")
    assert r.status_code == 409 and "«Hiệp Phát»" in r.json()["detail"]["message"]
    con = (await db_session.execute(select(Supplier.name, Supplier.ma_so_thue).where(Supplier.id == b["id"]))).one()
    assert tuple(con) == ("Daisan", None), "bị 409 thì không được ghi gì"

    # thêm «Công ty TNHH» vào tên của CHÍNH nó — không phải trùng
    r = await _sua(client, admin_user, a["id"], name="Công ty TNHH Hiệp Phát", ma_so_thue="0312345678")
    assert r.status_code == 200 and r.json()["name"] == "Công ty TNHH Hiệp Phát"
    r = await _sua(client, admin_user, b["id"], ma_so_thue="03-12345")
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_ncc_lo_trung_tu_truoc_van_sua_duoc_o_khac(client: AsyncClient, db_session, admin_user):
    """Form sửa gửi lại đủ mọi ô (kể cả tên, MST cũ) — không được vì thế mà kẹt 409/400."""
    a = Supplier(id=_uid(), name="Hiệp Phát", ma_so_thue="0312345678001")  # MST cũ sai dạng
    b = Supplier(id=_uid(), name="Công ty Hiệp Phát")
    db_session.add_all([a, b])
    await db_session.commit()
    r = await _sua(client, admin_user, a.id, name="Hiệp Phát", ma_so_thue="0312345678001", phone="0909000111",
                   rating=None, category=None)
    assert r.status_code == 200, r.text
    assert r.json()["phone"] == "0909000111" and r.json()["ma_so_thue"] == "0312345678001"
    assert r.json()["rating"] == 5.0 and r.json()["category"] == "general", "ô bắt buộc gửi null thì giữ nguyên"

    # MST lưu trước 22/11 còn khoảng trắng, lại trùng NCC khác: form gửi lại nguyên văn → không phải ĐỔI MST
    c = Supplier(id=_uid(), name="Gạch Minh Long", ma_so_thue="0312 345 678")
    d = Supplier(id=_uid(), name="Minh Long Ceramics", ma_so_thue="0312345678")
    db_session.add_all([c, d])
    await db_session.commit()
    a_id, c_id = a.id, c.id
    r = await _sua(client, admin_user, c_id, name="Gạch Minh Long", ma_so_thue="0312 345 678", phone="0909000222")
    assert r.status_code == 200, r.text
    assert r.json()["phone"] == "0909000222" and r.json()["ma_so_thue"] == "0312345678"
    # còn ĐỔI sang MST của NCC khác thì vẫn chặn
    r = await _sua(client, admin_user, a_id, ma_so_thue="0312 345 678")
    assert r.status_code == 409, r.text


@pytest.mark.asyncio
async def test_doi_ten_ncc_sua_luon_ten_chep_o_mau_va_bao_gia(client: AsyncClient, db_session, admin_user):
    """Mẫu và báo giá chép tên NCC, form sửa mẫu gửi lại tên chép đó cho BoNcc. Tên cũ nằm lại
    thì lần sửa mẫu kế tiếp sinh ra một NCC mới mang tên cũ — NCC trùng quay lại."""
    s = Supplier(id=_uid(), name="Hiep Phat")
    khac = Supplier(id=_uid(), name="Daisan")
    du_an = Project(id=_uid(), code="JMH-TEN1", name="Nhà đổi tên", client_name="K", status="active", total_value=1)
    db_session.add_all([s, khac, du_an])
    await db_session.flush()
    mau = MauVatTu(id=_uid(), ma="HP-TEN", ncc_gan_nhat_id=s.id, ncc_gan_nhat_ten=s.name, updated_at=MOC_CU)
    mau_khac = MauVatTu(id=_uid(), ma="DS-TEN", ncc_gan_nhat_id=khac.id, ncc_gan_nhat_ten=khac.name)
    dong = DongPhieuVatTu(id=_uid(), project_id=du_an.id, mau_id=mau.id, so_luong=1, ncc_id=s.id, updated_at=MOC_CU)
    db_session.add_all([mau, mau_khac, dong])
    await db_session.flush()
    bao_gia = BaoGiaDongVatTu(id=_uid(), dong_id=dong.id, supplier_id=s.id, ncc_ten=s.name, gia=1000)
    bao_gia_khac = BaoGiaDongVatTu(id=_uid(), dong_id=dong.id, supplier_id=khac.id, ncc_ten=khac.name, gia=1100)
    db_session.add_all([bao_gia, bao_gia_khac])
    await db_session.commit()
    s_id, khac_id = s.id, khac.id

    async def cot(*cots, id_):
        return tuple((await db_session.execute(select(*cots).where(cots[0].class_.id == id_))).one())

    # sửa ô khác (form gửi kèm tên cũ) → không đụng gì tới bảng vật tư
    assert (await _sua(client, admin_user, s_id, name="Hiep Phat", phone="0909")).status_code == 200
    assert await cot(MauVatTu.ncc_gan_nhat_ten, id_=mau.id) == ("Hiep Phat",)

    r = await _sua(client, admin_user, s_id, name="Hiệp Phát")
    assert r.status_code == 200, r.text
    assert await cot(MauVatTu.ncc_gan_nhat_id, MauVatTu.ncc_gan_nhat_ten, MauVatTu.updated_at, id_=mau.id) == (
        s_id, "Hiệp Phát", MOC_CU)
    assert await cot(BaoGiaDongVatTu.supplier_id, BaoGiaDongVatTu.ncc_ten, id_=bao_gia.id) == (s_id, "Hiệp Phát")
    assert await cot(DongPhieuVatTu.ncc_id, DongPhieuVatTu.updated_at, id_=dong.id) == (s_id, MOC_CU)
    # NCC khác: nguyên vẹn
    assert await cot(MauVatTu.ncc_gan_nhat_id, MauVatTu.ncc_gan_nhat_ten, id_=mau_khac.id) == (khac_id, "Daisan")
    assert await cot(BaoGiaDongVatTu.supplier_id, BaoGiaDongVatTu.ncc_ten, id_=bao_gia_khac.id) == (khac_id, "Daisan")
    # tên chép đã theo tên mới → BoNcc ra đúng NCC cũ, không tạo thêm
    ten_chep = (await cot(MauVatTu.ncc_gan_nhat_ten, id_=mau.id))[0]
    assert (await BoNcc(db_session).lay(ten_chep)).id == s_id
    assert await _so_ncc(db_session) == 2


# ── Hạng, ngừng dùng, lọc danh sách ────────────────────────────────────────

@pytest.mark.asyncio
async def test_sua_hang_ngung_dung_va_cac_o_lien_he(client: AsyncClient, db_session, admin_user):
    s = (await _tao(client, admin_user, name="Daisan", hang="thu")).json()
    assert s["hang"] == "thu"

    r = await _sua(client, admin_user, s["id"], hang="chinh", zalo="0909123456", region="Bình Dương",
                   contact_name="Chị Hoa", phone="0281112223", email="hoa@daisan.vn", address="KCN Sóng Thần")
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["hang"], j["zalo"], j["region"], j["contact_name"], j["phone"], j["email"], j["address"]) == (
        "chinh", "0909123456", "Bình Dương", "Chị Hoa", "0281112223", "hoa@daisan.vn", "KCN Sóng Thần")

    r = await _sua(client, admin_user, s["id"], hang="hang_la")
    assert r.status_code == 400 and "Hạng" in r.json()["detail"]
    assert (await _tao(client, admin_user, name="NCC Hạng Sai", hang="vip")).status_code == 400

    j = (await _sua(client, admin_user, s["id"], hang=None, is_active=False)).json()
    assert j["hang"] is None and j["is_active"] is False
    j = (await _sua(client, admin_user, s["id"], is_active=True)).json()
    assert j["is_active"] is True and j["zalo"] == "0909123456", "ô không gửi thì giữ nguyên"


@pytest.mark.asyncio
async def test_danh_sach_loc_hang_va_an_ncc_da_ngung(client: AsyncClient, db_session, admin_user):
    db_session.add_all([
        Supplier(id=_uid(), name="A Chính", hang="chinh"),
        Supplier(id=_uid(), name="B Dự phòng", hang="du_phong"),
        Supplier(id=_uid(), name="C Chưa xếp"),
        Supplier(id=_uid(), name="D Chính đã ngừng", hang="chinh", is_active=False),
    ])
    await db_session.commit()
    h = auth_header(admin_user)

    async def ten(**params):
        r = await client.get(API, params=params, headers=h)
        assert r.status_code == 200, r.text
        return [x["name"] for x in r.json()["items"]]

    r = await client.get(API, params={"page_size": 500}, headers=h)
    assert r.status_code == 200 and r.json()["total"] == 3
    assert all("hang" in x and x["is_active"] is True for x in r.json()["items"])
    assert await ten() == ["A Chính", "B Dự phòng", "C Chưa xếp"]
    assert await ten(include_inactive="true") == ["A Chính", "B Dự phòng", "C Chưa xếp", "D Chính đã ngừng"]
    assert await ten(hang="chinh") == ["A Chính"]
    assert await ten(hang="chinh", include_inactive="true") == ["A Chính", "D Chính đã ngừng"]
    assert await ten(hang="chua_xep") == ["C Chưa xếp"]
    assert await ten(is_active="false") == ["D Chính đã ngừng"]
    assert (await client.get(API, params={"page_size": 501}, headers=h)).status_code == 422

    # Trang NCC tải lần lượt từng trang: tên trùng nhau phải có thứ tự cố định (theo id), không thì
    # Postgres có thể trả một NCC ở cả hai trang và bỏ sót NCC kia
    db_session.add_all([Supplier(id="zz-trung-ten", name="Trùng Tên"), Supplier(id="aa-trung-ten", name="Trùng Tên")])
    await db_session.commit()
    ids = []
    for trang in (4, 5):
        r = await client.get(API, params={"page": trang, "page_size": 1}, headers=h)
        ids += [x["id"] for x in r.json()["items"]]
    assert ids == ["aa-trung-ten", "zz-trung-ten"]


# ── Gộp NCC trùng ──────────────────────────────────────────────────────────

def test_gop_phu_moi_cot_giu_id_ncc():
    """SQLite của test không gác khoá ngoại: sót một cột là prod (Postgres) báo lỗi khi xoá NCC nguồn,
    hoặc tệ hơn — cột không khai FK thì mồ côi im lặng. Thêm cột trỏ tới suppliers.id mà quên
    thêm vào `_COT_NCC` thì test này đỏ."""
    da_phu = {(cot.class_.__tablename__, cot.key) for cot, _ in _COT_NCC}
    tro_toi_ncc = {
        (bang.name, cot.name)
        for bang in Base.metadata.tables.values() for cot in bang.columns
        for fk in cot.foreign_keys if fk.target_fullname == "suppliers.id"
    }
    assert tro_toi_ncc, "metadata chưa nạp model"
    assert tro_toi_ncc <= da_phu, f"gộp NCC bỏ sót: {tro_toi_ncc - da_phu}"
    # hai cột giữ id NCC nhưng không khai khoá ngoại
    assert {("supplier_quotes", "supplier_id"), ("price_comparisons", "best_supplier_id")} <= da_phu


@pytest.mark.asyncio
async def test_gop_chuyen_moi_bang_bu_o_trong_xoa_nguon_ghi_nhat_ky(client: AsyncClient, db_session, admin_user):
    nguon = Supplier(id=_uid(), name="Cty Hiệp Phát", phone="0909000111", zalo="0909000111", category="stone",
                     ma_so_thue="0312345678", ten_cong_ty="CÔNG TY TNHH HIỆP PHÁT", chiet_khau_pct=5,
                     notes="Giao trong ngày", hang="chinh", address="Địa chỉ của nguồn")
    dich = Supplier(id=_uid(), name="Hiệp Phát", address="12 Lê Lợi, Q1", notes=GHI_CHU_TU_TAO)
    khac = Supplier(id=_uid(), name="Daisan")
    du_an = Project(id=_uid(), code="JMH-GOP1", name="Nhà gộp", client_name="K", status="active", total_value=1)
    db_session.add_all([nguon, dich, khac, du_an])
    await db_session.flush()
    mau = MauVatTu(id=_uid(), ma="HP-60", ncc_gan_nhat_id=nguon.id, ncc_gan_nhat_ten=nguon.name, updated_at=MOC_CU)
    mau_khac = MauVatTu(id=_uid(), ma="DS-60", ncc_gan_nhat_id=khac.id, ncc_gan_nhat_ten=khac.name)
    dong = DongPhieuVatTu(id=_uid(), project_id=du_an.id, mau_id=mau.id, so_luong=10, ncc_id=nguon.id,
                          gia_von=100000, updated_at=MOC_CU)
    dong_khac = DongPhieuVatTu(id=_uid(), project_id=du_an.id, ma_tu_do="X", so_luong=1, ncc_id=khac.id)
    db_session.add_all([mau, mau_khac, dong, dong_khac])
    await db_session.flush()
    bao_gia = BaoGiaDongVatTu(id=_uid(), dong_id=dong.id, supplier_id=nguon.id, ncc_ten=nguon.name, gia=100000)
    bao_gia_khac = BaoGiaDongVatTu(id=_uid(), dong_id=dong.id, supplier_id=khac.id, ncc_ten=khac.name, gia=110000)
    gia_nhap = GiaNhapMauVatTu(id=_uid(), mau_id=mau.id, supplier_id=nguon.id, gia=98000)
    bao_gia_kho = SupplierQuote(id=_uid(), supplier_id=nguon.id, material_name="Gạch 60x60", unit_price=99000)
    so_gia = PriceComparison(id=_uid(), material_name="Gạch 60x60", best_supplier_id=nguon.id)
    db_session.add_all([bao_gia, bao_gia_khac, gia_nhap, bao_gia_kho, so_gia])
    await db_session.commit()
    nguon_id, dich_id, khac_id = nguon.id, dich.id, khac.id

    r = await client.post(f"{API}/{nguon_id}/gop/{dich_id}", headers=auth_header(admin_user))
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["supplier"]["id"] == dich_id and j["supplier"]["name"] == "Hiệp Phát"
    assert j["ten_khac_khoa"] is False, "«Cty Hiệp Phát» gõ lại vẫn ra «Hiệp Phát» — không cần cảnh báo"
    assert j["da_chuyen"] == {"dong_phieu_vat_tu": 1, "mau_vat_tu": 1, "bao_gia_dong_vat_tu": 1,
                              "gia_nhap_mau_vat_tu": 1, "supplier_quotes": 1, "price_comparisons": 1}

    # Đọc thẳng từng cột trong DB (không qua object đang nằm trong session)
    async def cot(*cots, id_):
        return tuple((await db_session.execute(select(*cots).where(cots[0].class_.id == id_))).one())

    assert await cot(DongPhieuVatTu.ncc_id, DongPhieuVatTu.updated_at, id_=dong.id) == (dich_id, MOC_CU), \
        "gộp NCC không phải Thu mua cập nhật dự án — updated_at của dòng phải đứng yên"
    assert await cot(MauVatTu.ncc_gan_nhat_id, MauVatTu.ncc_gan_nhat_ten, MauVatTu.updated_at, id_=mau.id) == (
        dich_id, "Hiệp Phát", MOC_CU)
    assert await cot(BaoGiaDongVatTu.supplier_id, BaoGiaDongVatTu.ncc_ten, id_=bao_gia.id) == (dich_id, "Hiệp Phát")
    assert await cot(GiaNhapMauVatTu.supplier_id, id_=gia_nhap.id) == (dich_id,)
    assert await cot(SupplierQuote.supplier_id, id_=bao_gia_kho.id) == (dich_id,)
    assert await cot(PriceComparison.best_supplier_id, id_=so_gia.id) == (dich_id,)
    # NCC không liên quan: nguyên vẹn
    assert await cot(DongPhieuVatTu.ncc_id, id_=dong_khac.id) == (khac_id,)
    assert await cot(MauVatTu.ncc_gan_nhat_id, MauVatTu.ncc_gan_nhat_ten, id_=mau_khac.id) == (khac_id, "Daisan")
    assert await cot(BaoGiaDongVatTu.supplier_id, BaoGiaDongVatTu.ncc_ten, id_=bao_gia_khac.id) == (khac_id, "Daisan")

    # NCC nguồn bị xoá; NCC giữ lại được bù ô trống, ô đã có thì không bị ghi đè
    con = set((await db_session.execute(select(Supplier.id))).scalars())
    assert con == {dich_id, khac_id}
    s = j["supplier"]
    assert (s["phone"], s["zalo"], s["ma_so_thue"], s["hang"]) == ("0909000111", "0909000111", "0312345678", "chinh")
    assert s["ten_cong_ty"] == "CÔNG TY TNHH HIỆP PHÁT", "MST lấy của nguồn thì tên pháp lý đi theo"
    assert (s["category"], s["chiet_khau_pct"], s["notes"]) == ("stone", 5, "Giao trong ngày")
    assert s["address"] == "12 Lê Lợi, Q1"
    assert await cot(Supplier.phone, Supplier.notes, Supplier.address, id_=dich_id) == (
        "0909000111", "Giao trong ngày", "12 Lê Lợi, Q1")
    assert (await client.get(f"{API}/{nguon_id}", headers=auth_header(admin_user))).status_code == 404

    nk = (await db_session.execute(select(AuditLog).where(AuditLog.action == "supplier.gop"))).scalar_one()
    assert nk.entity_type == "supplier" and nk.entity_id == dich_id and nk.actor_id == admin_user.id
    assert "Cty Hiệp Phát" in nk.before_json and nguon_id in nk.before_json, "phải chụp lại NCC bị xoá"
    assert "Cty Hiệp Phát" in nk.note and "Hiệp Phát" in nk.after_json
    # Đủ để dựng lại tay: id từng dòng đã chuyển (sau gộp chúng lẫn với dòng của NCC giữ lại)
    # + NCC giữ lại trông thế nào TRƯỚC khi được bù ô trống
    sau = json.loads(nk.after_json)
    assert sau["id_da_chuyen"] == {
        "dong_phieu_vat_tu": [dong.id], "mau_vat_tu": [mau.id], "bao_gia_dong_vat_tu": [bao_gia.id],
        "gia_nhap_mau_vat_tu": [gia_nhap.id], "supplier_quotes": [bao_gia_kho.id], "price_comparisons": [so_gia.id]}
    assert sau["da_chuyen"] == j["da_chuyen"]
    truoc_bu = sau["dich_truoc_khi_bu"]
    assert (truoc_bu["id"], truoc_bu["phone"], truoc_bu["ma_so_thue"], truoc_bu["notes"]) == (
        dich_id, None, None, GHI_CHU_TU_TAO)

    # ten_khac_khoa = False nghĩa là: tên vừa xoá gõ lại ở Vật tư thì về NCC giữ lại, không tạo lại NCC trùng
    assert (await BoNcc(db_session).lay("Cty Hiệp Phát")).id == dich_id
    assert await _so_ncc(db_session) == 2


@pytest.mark.asyncio
async def test_gop_ten_phap_ly_khong_roi_ma_so_thue_cua_no(client: AsyncClient, db_session, admin_user):
    """Tên công ty là tên THEO mã số thuế: NCC giữ lại đã có MST khác thì không nhận tên pháp lý của nguồn
    (trụ sở và chi nhánh «-001», hai công ty cùng thương hiệu)."""
    nguon = Supplier(id=_uid(), name="Hiep Phat", ma_so_thue="0312345678-001", ten_cong_ty="CHI NHÁNH CÔNG TY HIỆP PHÁT",
                     phone="0909000111")
    dich = Supplier(id=_uid(), name="Hiệp Phát", ma_so_thue="0312345678")
    cung_mst = Supplier(id=_uid(), name="Cty Daisan", ma_so_thue="0301111111", ten_cong_ty="CÔNG TY CP DAISAN")
    dich_cung_mst = Supplier(id=_uid(), name="Daisan", ma_so_thue="0301 111 111")
    db_session.add_all([nguon, dich, cung_mst, dich_cung_mst])
    await db_session.commit()
    h = auth_header(admin_user)

    r = await client.post(f"{API}/{nguon.id}/gop/{dich.id}", headers=h)
    assert r.status_code == 200, r.text
    s = r.json()["supplier"]
    assert (s["ma_so_thue"], s["ten_cong_ty"], s["phone"]) == ("0312345678", None, "0909000111")
    assert r.json()["ten_khac_khoa"] is True, "«Hiep Phat» gõ lại sẽ tạo NCC mới — phải báo cho BGĐ"

    r = await client.post(f"{API}/{cung_mst.id}/gop/{dich_cung_mst.id}", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["supplier"]["ten_cong_ty"] == "CÔNG TY CP DAISAN", "cùng MST (khác cách viết) thì nhận"


@pytest.mark.asyncio
async def test_gop_ghi_chu_may_tu_dien_khong_phai_thong_tin(client: AsyncClient, db_session, admin_user):
    """NCC tự tạo mang ghi chú máy điền (BoNcc, hoặc migration a17 — câu chữ khác nhau): khi gộp
    coi như ô trống — không giữ nó thay cho ghi chú thật, cũng không chép nó sang NCC giữ lại."""
    ghi_chu_a17 = "Tự tạo từ tên NCC ở Vật tư — bổ sung liên hệ sau"
    co_that = Supplier(id=_uid(), name="Cty Hiệp Phát", notes="Giao trong ngày")
    tu_tao_a17 = Supplier(id=_uid(), name="Hiệp Phát", notes=ghi_chu_a17)
    tu_tao = Supplier(id=_uid(), name="Cty Daisan", notes=GHI_CHU_TU_TAO)
    trong = Supplier(id=_uid(), name="Daisan")
    db_session.add_all([co_that, tu_tao_a17, tu_tao, trong])
    await db_session.commit()
    h = auth_header(admin_user)

    r = await client.post(f"{API}/{co_that.id}/gop/{tu_tao_a17.id}", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["supplier"]["notes"] == "Giao trong ngày"
    r = await client.post(f"{API}/{tu_tao.id}/gop/{trong.id}", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["supplier"]["notes"] is None and r.json()["supplier"]["category"] == "general"


@pytest.mark.asyncio
async def test_gop_chi_admin_cung_id_400_khong_co_404(client: AsyncClient, db_session, admin_user, designer_user, sales_user):
    a = Supplier(id=_uid(), name="Hiệp Phát")
    b = Supplier(id=_uid(), name="Cty Hiệp Phát")
    db_session.add_all([a, b])
    await db_session.commit()

    # designer_user = supervisor: có ô «Sửa Nhà cung cấp» (sửa được) nhưng KHÔNG được gộp
    assert (await _sua(client, designer_user, b.id, phone="0909")).status_code == 200
    for nguoi in (designer_user, sales_user):
        r = await client.post(f"{API}/{b.id}/gop/{a.id}", headers=auth_header(nguoi))
        assert r.status_code == 403, r.text
    assert (await client.post(f"{API}/{b.id}/gop/{a.id}")).status_code in (401, 403)
    assert await _so_ncc(db_session) == 2

    h = auth_header(admin_user)
    r = await client.post(f"{API}/{a.id}/gop/{a.id}", headers=h)
    assert r.status_code == 400
    assert (await client.post(f"{API}/{_uid()}/gop/{a.id}", headers=h)).status_code == 404
    assert (await client.post(f"{API}/{b.id}/gop/{_uid()}", headers=h)).status_code == 404
    assert await _so_ncc(db_session) == 2, "lỗi thì không được xoá gì"
    assert (await db_session.execute(select(func.count()).select_from(AuditLog)
                                     .where(AuditLog.action == "supplier.gop"))).scalar() == 0
