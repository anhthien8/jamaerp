"""Bảng điều khiển Kinh doanh (13/10/2026) — /dashboard/sales.

Chủ dự án gửi một dashboard mẫu và yêu cầu dựng màn hình quản lý & đánh giá
hiệu quả team sale, làm demo trên tài khoản admin.

Những chỗ dễ sai nhất ở màn hình này, mỗi chỗ một test:
  1. KHÓA CỨNG QUYỀN — màn hình gộp doanh số toàn phòng + xếp hạng từng người,
     lọt ra ngoài admin là lộ bảng lương ngầm.
  2. KHÓA CACHE — thêm tham số `team_id` mà quên đưa vào khóa thì chọn nhóm nào
     cũng ra số của nhóm xem trước đó (cùng lớp lỗi đã vá ở /executive 22/09).
  3. PHỄU KHÔNG ĐƯỢC PHÌNH — lead chỉ lưu trạng thái hiện tại, đếm từng bước
     độc lập là có bước sau nhiều hơn bước trước, nhìn như bảng lỗi.
  4. 4 RỔ CHẤT LƯỢNG PHẢI CỘNG ĐỦ — hụt một lead là tổng data không khớp.
  5. KHÁCH TỈNH ≠ DỮ LIỆU CŨ — 96 lead cũ lưu tên QUẬN của TP.HCM, không được
     gắn oan nhãn «khách tỉnh».
  6. MỤC TIÊU CHIA THEO NGÀY — xem «7 ngày gần nhất» mà so với mục tiêu cả
     tháng thì team nào cũng bết bát.
  7. NHÓM 0 LEAD VẪN PHẢI HIỆN — biến mất khỏi bảng là cách nhanh nhất để một
     nhóm đứng im mà không ai thấy.
"""

from datetime import datetime, timedelta, timezone, date

import pytest
import pytest_asyncio

from app.api.sales_dashboard import (
    SALES_TARGETS_KEY,
    do_sau_pheu,
    muc_tieu_trong_ky,
    phan_loai_data,
    so_thang_phu,
)
from app.cache import cache
from app.middleware.permissions import xoa_cache_quyen
from app.models.contract import Contract
from app.models.lead import Lead
from app.models.project import Project
from app.models.user import Team, User
from app.middleware.auth import hash_password
from tests.conftest import auth_header, _uid

VN = timezone(timedelta(hours=7))
URL = "/api/v1/dashboard/sales"


@pytest.fixture(autouse=True)
def _sach():
    cache.clear_prefix("dashboard")
    xoa_cache_quyen()
    yield
    cache.clear_prefix("dashboard")
    xoa_cache_quyen()


# ── Hàm thuần: phân loại & mục tiêu ─────────────────────────────────────────

TRONG_TAM = {"ho chi minh"}  # đã chuẩn hóa (bỏ dấu, bỏ "tp.")


def test_bon_ro_chat_luong_loai_tru_nhau():
    # Số sai thắng mọi tiêu chí khác: là rác thật
    assert phan_loai_data("Đồng Nai", "duoi_200", "wrong_number", TRONG_TAM) == "khong_dat"
    assert phan_loai_data("Đồng Nai", "tren_500", "reachable", TRONG_TAM) == "khach_tinh"
    assert phan_loai_data("TP. Hồ Chí Minh", "duoi_200", "reachable", TRONG_TAM) == "ngan_sach_thap"
    assert phan_loai_data("TP. Hồ Chí Minh", "tren_500", "reachable", TRONG_TAM) == "dat_tieu_chuan"


def test_du_lieu_cu_ten_quan_khong_bi_goi_la_khach_tinh():
    """96 lead cũ lưu «Q7», «Gò Vấp», «Quận khác» — đều là khách nội thành."""
    for cu in ("Q1", "Q7", "Gò Vấp", "Quận khác", "Bình Thạnh"):
        assert phan_loai_data(cu, None, "reachable", TRONG_TAM) == "dat_tieu_chuan", cu
    # Thiếu khu vực thì cũng không được suy đoán là khách tỉnh
    assert phan_loai_data(None, None, "reachable", TRONG_TAM) == "dat_tieu_chuan"


def test_khu_vuc_so_khop_khong_can_dau():
    assert phan_loai_data("dong nai", None, None, TRONG_TAM) == "khach_tinh"
    assert phan_loai_data("ho chi minh", None, None, TRONG_TAM) == "dat_tieu_chuan"


def test_do_sau_pheu_luon_bao_trum_buoc_duoi():
    """Lead đã ký phải được đếm ở MỌI bước phía trước, kể cả khi thiếu dữ liệu."""
    da_ky = {"stage": "signed_design", "contact_status": None, "last_contacted_at": None,
             "survey_date": None, "co_activity": False, "co_bao_gia": False}
    assert do_sau_pheu(da_ky) == 7
    moi = {"stage": "new", "contact_status": None, "last_contacted_at": None,
           "survey_date": None, "co_activity": False, "co_bao_gia": False}
    assert do_sau_pheu(moi) == 0
    # Đã khảo sát nhưng stage còn 'new' → vẫn tính là đã đi tới bước khảo sát
    khao_sat = {**moi, "survey_date": datetime.now(timezone.utc)}
    assert do_sau_pheu(khao_sat) == 4


def test_muc_tieu_chia_theo_so_ngay_cua_ky():
    # Cả tháng 9 (30 ngày) = đúng 1 tháng mục tiêu
    assert muc_tieu_trong_ky(300, date(2026, 9, 1), date(2026, 9, 30)) == pytest.approx(300)
    # 10 ngày trong tháng 30 ngày = 1/3 mục tiêu
    assert muc_tieu_trong_ky(300, date(2026, 9, 1), date(2026, 9, 10)) == pytest.approx(100.0)
    # Bắc qua 2 tháng: 1 ngày của tháng 9 + cả tháng 10 (31 ngày)
    hai_thang = muc_tieu_trong_ky(310, date(2026, 9, 30), date(2026, 10, 31))
    assert hai_thang == pytest.approx(310 / 30 + 310)
    assert so_thang_phu(date(2026, 10, 1), date(2026, 10, 31)) == pytest.approx(1.0)


def test_muc_tieu_khong_am_khi_ky_nguoc_hoac_bang_khong():
    assert muc_tieu_trong_ky(300, date(2026, 9, 10), date(2026, 9, 1)) == 0
    assert muc_tieu_trong_ky(0, date(2026, 9, 1), date(2026, 9, 30)) == 0


# ── Dữ liệu dựng sẵn ────────────────────────────────────────────────────────

async def _lead(db, *, ten, luc, nguoi=None, nhom=None, stage="new", **truong):
    l = Lead(name=ten, phone="0901234567", stage=stage, priority="medium",
             assigned_to=nguoi, team_id=nhom, **truong)
    db.add(l)
    await db.flush()
    l.created_at = luc
    await db.flush()
    return l


@pytest_asyncio.fixture
async def phong_kd(db_session):
    """2 nhóm KD; nhóm B cố ý KHÔNG có lead nào để canh bug «nhóm biến mất»."""
    a = Team(id=_uid(), name="Nhóm A", code="SA", department="SALES")
    b = Team(id=_uid(), name="Nhóm B", code="SB", department="SALES")
    db_session.add_all([a, b])
    await db_session.flush()
    sale = User(id=_uid(), full_name="Sale A1", email="sale.a1@test.com",
                password_hash=hash_password("x"), role="data_entry",
                department="SALES", team_id=a.id, is_active=True)
    db_session.add(sale)
    await db_session.commit()
    return {"a": a, "b": b, "sale": sale}


@pytest_asyncio.fixture
async def du_lieu(db_session, phong_kd):
    """9 lead trong tháng này: 6 đạt chuẩn ở các độ sâu khác nhau + 3 rác."""
    a, sale = phong_kd["a"], phong_kd["sale"]
    nay = datetime.now(VN).replace(hour=10, minute=0, second=0, microsecond=0)
    utc = nay.astimezone(timezone.utc)
    chung = {"nguoi": sale.id, "nhom": a.id, "region": "TP. Hồ Chí Minh"}

    await _lead(db_session, ten="Mới tinh", luc=utc, **chung)
    await _lead(db_session, ten="Gọi không được", luc=utc, contact_status="unreachable", **chung)
    await _lead(db_session, ten="Kết nối được", luc=utc, contact_status="reachable", **chung)
    await _lead(db_session, ten="Đang tư vấn", luc=utc, stage="interested",
                contact_status="reachable", **chung)
    await _lead(db_session, ten="Đã khảo sát", luc=utc, stage="interested",
                contact_status="reachable", survey_date=utc, **chung)
    await _lead(db_session, ten="Đã thắng", luc=utc, stage="signed_design",
                contact_status="reachable", survey_date=utc,
                design_contract_value=500_000_000, **chung)
    # 3 rổ rác, mỗi rổ 1 lead
    await _lead(db_session, ten="Khách tỉnh", luc=utc, nguoi=sale.id, nhom=a.id,
                region="Đồng Nai", contact_status="reachable")
    await _lead(db_session, ten="Ngân sách thấp", luc=utc, nguoi=sale.id, nhom=a.id,
                region="TP. Hồ Chí Minh", ngan_sach_khoang="duoi_200")
    await _lead(db_session, ten="Số sai", luc=utc, nguoi=sale.id, nhom=a.id,
                region="TP. Hồ Chí Minh", contact_status="wrong_number")

    pr = Project(id=_uid(), code="PRJ-SD1", name="Dự án demo", client_name="KH",
                 status="active", project_type="design_build", sales_id=sale.id,
                 total_value=800_000_000)
    db_session.add(pr)
    await db_session.flush()
    db_session.add(Contract(id=_uid(), code="HD-SD1", project_id=pr.id,
                            title="HĐ thiết kế", status="signed",
                            total_value=800_000_000, signed_date=nay.date()))
    await db_session.commit()
    return {"nay": nay.date()}


# ── Quyền ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chi_admin_vao_duoc(client, sales_user, accountant_user, admin_user):
    for u in (sales_user, accountant_user):
        r = await client.get(URL, headers=auth_header(u))
        assert r.status_code == 403, f"{u.role} không được xem: {r.text}"
    assert (await client.get(URL, headers=auth_header(admin_user))).status_code == 200


@pytest.mark.asyncio
async def test_khong_dang_nhap_thi_401(client):
    assert (await client.get(URL)).status_code in (401, 403)


@pytest.mark.asyncio
async def test_muc_tieu_cung_bi_khoa_o_admin(client, sales_user):
    r = await client.get(f"{URL}/muc-tieu", headers=auth_header(sales_user))
    assert r.status_code == 403
    r = await client.put(f"{URL}/muc-tieu", headers=auth_header(sales_user), json={
        "doanh_thu_thang": 1, "hd_thiet_ke_thang": 1, "hd_thi_cong_thang": 1,
        "khach_khao_sat_thang": 1, "ty_le_lien_he_toi_thieu": 90,
    })
    assert r.status_code == 403


# ── Số liệu ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ky_mac_dinh_la_thang_nay(client, admin_user, du_lieu):
    d = (await client.get(URL, headers=auth_header(admin_user))).json()
    hom_nay = datetime.now(VN).date()
    assert d["ky"]["tu"] == hom_nay.replace(day=1).isoformat()
    assert d["ky"]["den"] == hom_nay.isoformat()


@pytest.mark.asyncio
async def test_bon_ro_cong_du_tong_data(client, admin_user, du_lieu):
    d = (await client.get(URL, headers=auth_header(admin_user))).json()
    cl = d["chat_luong_data"]
    assert cl["tong"] == 9
    assert sum(r["so_luong"] for r in cl["ro"]) == cl["tong"]
    theo_ma = {r["ma"]: r["so_luong"] for r in cl["ro"]}
    assert theo_ma == {"dat_tieu_chuan": 6, "khach_tinh": 1,
                       "ngan_sach_thap": 1, "khong_dat": 1}


@pytest.mark.asyncio
async def test_pheu_thu_hep_dan_va_chi_tinh_data_dat_chuan(client, admin_user, du_lieu):
    d = (await client.get(URL, headers=auth_header(admin_user))).json()
    pheu = d["pheu"]
    assert [b["ma"] for b in pheu][0] == "data"
    assert pheu[0]["so_luong"] == 6, "gốc phễu = data đạt chuẩn, không phải tổng data"
    so = [b["so_luong"] for b in pheu]
    assert so == sorted(so, reverse=True), f"phễu phình ở đâu đó: {so}"
    assert pheu[-1]["ma"] == "ky_hd" and pheu[-1]["so_luong"] == 1
    assert pheu[0]["phan_tram_goc"] == 100.0


@pytest.mark.asyncio
async def test_nhom_khong_co_lead_van_hien_mot_dong(client, admin_user, du_lieu, phong_kd):
    d = (await client.get(URL, headers=auth_header(admin_user))).json()
    ten = {n["nhom"] for n in d["hieu_suat_nhom"]}
    assert "Nhóm B" in ten, "nhóm 0 lead bị rụng khỏi bảng"
    b = next(n for n in d["hieu_suat_nhom"] if n["nhom"] == "Nhóm B")
    assert b["data_nhan"] == 0 and b["doanh_so"] == 0


@pytest.mark.asyncio
async def test_doanh_thu_lay_tu_hop_dong_da_ky(client, admin_user, du_lieu):
    d = (await client.get(URL, headers=auth_header(admin_user))).json()
    dt = next(k for k in d["kpi"] if k["ma"] == "doanh_thu")
    assert dt["thuc_te"] == 800_000_000
    # Mục tiêu kỳ phải NHỎ HƠN mục tiêu tháng vì tháng chưa hết
    assert dt["muc_tieu"] <= dt["muc_tieu_thang"]
    assert dt["muc_tieu_tien_do"] <= dt["muc_tieu"]


@pytest.mark.asyncio
async def test_hop_dong_nhap_cua_ky_khac_khong_lot_vao(client, admin_user, du_lieu, db_session):
    thang_truoc = (datetime.now(VN).date().replace(day=1) - timedelta(days=5))
    pr = Project(id=_uid(), code="PRJ-OLD", name="Dự án cũ", client_name="KH",
                 status="active", total_value=1)
    db_session.add(pr)
    await db_session.flush()
    db_session.add(Contract(id=_uid(), code="HD-OLD", project_id=pr.id, title="HĐ cũ",
                            status="signed", total_value=9_000_000_000,
                            signed_date=thang_truoc))
    await db_session.commit()
    cache.clear_prefix("dashboard")
    d = (await client.get(URL, headers=auth_header(admin_user))).json()
    dt = next(k for k in d["kpi"] if k["ma"] == "doanh_thu")
    assert dt["thuc_te"] == 800_000_000, "hợp đồng tháng trước lọt vào kỳ này"
    # ...nhưng vẫn phải xuất hiện ở biểu đồ 6 tháng
    assert any(x["thuc_te"] == 9_000_000_000 for x in d["doanh_so_theo_thang"])


@pytest.mark.asyncio
async def test_hop_dong_cu_van_lay_duoc_khi_chon_dung_ky_cua_no(
    client, admin_user, du_lieu, db_session
):
    """Truy vấn hợp đồng có chặn dưới để khỏi kéo cả lịch sử; chặn đó không
    được cắt mất hợp đồng khi người dùng chọn đúng kỳ xa trong quá khứ."""
    xua = datetime.now(VN).date().replace(day=15) - timedelta(days=700)
    pr = Project(id=_uid(), code="PRJ-XUA", name="Dự án xưa", client_name="KH",
                 status="active", total_value=1)
    db_session.add(pr)
    await db_session.flush()
    db_session.add(Contract(id=_uid(), code="HD-XUA", project_id=pr.id, title="HĐ xưa",
                            status="signed", total_value=7_000_000_000,
                            signed_date=xua))
    await db_session.commit()
    cache.clear_prefix("dashboard")

    # Kỳ mặc định (tháng này): không được thấy
    d = (await client.get(URL, headers=auth_header(admin_user))).json()
    assert next(k for k in d["kpi"] if k["ma"] == "doanh_thu")["thuc_te"] == 800_000_000

    # Chọn đúng tháng của nó: phải thấy
    dau = xua.replace(day=1).isoformat()
    cuoi = (xua.replace(day=28)).isoformat()
    d = (await client.get(f"{URL}?tu={dau}&den={cuoi}",
                          headers=auth_header(admin_user))).json()
    assert next(k for k in d["kpi"] if k["ma"] == "doanh_thu")["thuc_te"] == 7_000_000_000


@pytest.mark.asyncio
async def test_canh_bao_sla_24h_dem_lead_chua_lien_he(client, admin_user, du_lieu, db_session,
                                                      phong_kd):
    hai_ngay = datetime.now(timezone.utc) - timedelta(days=2)
    await _lead(db_session, ten="Bỏ quên 2 ngày", luc=hai_ngay,
                nguoi=phong_kd["sale"].id, nhom=phong_kd["a"].id,
                region="TP. Hồ Chí Minh")
    await db_session.commit()
    cache.clear_prefix("dashboard")
    d = (await client.get(URL, headers=auth_header(admin_user))).json()
    sla = next((c for c in d["canh_bao"] if c["ma"] == "sla_24h"), None)
    assert sla and sla["so_luong"] >= 1
    assert d["canh_bao"][0]["muc_do"] == "gap", "cảnh báo gấp phải nằm trên đầu"


@pytest.mark.asyncio
async def test_khoi_de_xuat_them_co_mat(client, admin_user, du_lieu):
    d = (await client.get(URL, headers=auth_header(admin_user))).json()
    for khoi in ("toc_do_pipeline", "ton_kho_lead", "theo_nguon", "du_bao",
                 "ly_do_mat", "theo_ngan_sach"):
        assert khoi in d, khoi
    assert sum(r["tong"] for r in d["theo_ngan_sach"]) == d["chat_luong_data"]["tong"]
    assert d["du_bao"]["du_bao_co_trong_so"] <= d["du_bao"]["gia_tri_pipeline"]


# ── Cache ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_khoa_cache_gom_ca_nhom(client, admin_user, du_lieu, phong_kd):
    """Bug cũ ở /executive: thiếu tham số trong khóa → đổi lọc mà số đứng im."""
    toan_phong = (await client.get(URL, headers=auth_header(admin_user))).json()
    rieng_b = (await client.get(f"{URL}?team_id={phong_kd['b'].id}",
                                headers=auth_header(admin_user))).json()
    assert toan_phong["chat_luong_data"]["tong"] == 9
    assert rieng_b["chat_luong_data"]["tong"] == 0, "cache trả số của toàn phòng"
    assert rieng_b["team_id"] == phong_kd["b"].id


@pytest.mark.asyncio
async def test_khoa_cache_gom_ca_ky(client, admin_user, du_lieu):
    hom_nay = datetime.now(VN).date()
    nay = (await client.get(f"{URL}?tu={hom_nay}&den={hom_nay}",
                            headers=auth_header(admin_user))).json()
    xua = (hom_nay - timedelta(days=400)).isoformat()
    cu = (await client.get(f"{URL}?tu={xua}&den={xua}",
                           headers=auth_header(admin_user))).json()
    assert nay["chat_luong_data"]["tong"] == 9
    assert cu["chat_luong_data"]["tong"] == 0


@pytest.mark.asyncio
async def test_nhom_khong_ton_tai_bao_404(client, admin_user, du_lieu):
    r = await client.get(f"{URL}?team_id=khong-co-that", headers=auth_header(admin_user))
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_ngay_sai_dinh_dang_bao_ro(client, admin_user):
    r = await client.get(f"{URL}?tu=13-10-2026", headers=auth_header(admin_user))
    assert r.status_code == 400 and "YYYY-MM-DD" in r.json()["detail"]


# ── Thiết lập mục tiêu ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_luu_muc_tieu_thi_phan_tram_doi_ngay(client, admin_user, du_lieu, db_session):
    """Lưu mục tiêu mà không xóa cache thì người sửa thấy % cũ đứng im 2 phút."""
    truoc = (await client.get(URL, headers=auth_header(admin_user))).json()
    pct_truoc = next(k for k in truoc["kpi"] if k["ma"] == "doanh_thu")["phan_tram"]

    r = await client.put(f"{URL}/muc-tieu", headers=auth_header(admin_user), json={
        "doanh_thu_thang": 1_000_000_000, "hd_thiet_ke_thang": 2,
        "hd_thi_cong_thang": 1, "khach_khao_sat_thang": 10,
        "ty_le_lien_he_toi_thieu": 80, "khu_vuc_trong_tam": ["TP. Hồ Chí Minh"],
        "theo_nhom": {},
    })
    assert r.status_code == 200, r.text
    assert r.json()["doanh_thu_thang"] == 1_000_000_000

    sau = (await client.get(URL, headers=auth_header(admin_user))).json()
    pct_sau = next(k for k in sau["kpi"] if k["ma"] == "doanh_thu")["phan_tram"]
    assert pct_sau != pct_truoc, "cache không được xóa sau khi lưu mục tiêu"

    from app.models.notification import SystemSetting
    assert (await db_session.get(SystemSetting, SALES_TARGETS_KEY)) is not None


@pytest.mark.asyncio
async def test_muc_tieu_thieu_khoa_thi_lay_mac_dinh(client, admin_user, db_session):
    """Bản ghi cũ/thiếu trường không được làm sập màn hình."""
    from app.models.notification import SystemSetting
    db_session.add(SystemSetting(key=SALES_TARGETS_KEY, value='{"doanh_thu_thang": 5}'))
    await db_session.commit()
    d = (await client.get(f"{URL}/muc-tieu", headers=auth_header(admin_user))).json()
    assert d["doanh_thu_thang"] == 5
    assert d["hd_thiet_ke_thang"] == 24  # mặc định


@pytest.mark.asyncio
async def test_muc_tieu_hong_json_khong_lam_sap(client, admin_user, db_session):
    from app.models.notification import SystemSetting
    db_session.add(SystemSetting(key=SALES_TARGETS_KEY, value="{không phải json"))
    await db_session.commit()
    assert (await client.get(URL, headers=auth_header(admin_user))).status_code == 200


@pytest.mark.asyncio
async def test_ty_le_lien_he_khong_bi_chia_theo_ngay(client, admin_user, du_lieu):
    """Ngưỡng sàn ≥90% là NGƯỠNG, không phải chỉ tiêu cộng dồn theo ngày."""
    d = (await client.get(URL, headers=auth_header(admin_user))).json()
    tl = next(k for k in d["kpi"] if k["ma"] == "ty_le_lien_he")
    assert tl["la_nguong"] is True
    assert tl["muc_tieu"] == tl["muc_tieu_thang"] == tl["muc_tieu_tien_do"] == 90
