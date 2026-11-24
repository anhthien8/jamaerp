"""R00 mục 8 (15/11/2026): sale gõ tự do cho bot → đoán việc + hẹn + lead của chính người gõ.

POST /api/v1/telegram/lead/doan — CHỈ ĐOÁN, không ghi (bot hỏi lại, bấm «Đúng» mới ghi).
"""
import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.middleware.auth import hash_password
from app.models.lead import Activity, Lead
from app.models.user import User
from app.services import hieu_cau_sale
from app.services.automation import gio_vn_naive
from app.services.hieu_cau_sale import doc_cau, kiem_ai
from app.services.lead_touch import moc_hen_sau, nhan_viec
from tests.conftest import auth_header

URL = "/api/v1/telegram/lead/doan"
THU_BAY = datetime(2026, 11, 14, 10, 30)   # thứ Bảy 14/11/2026, 10:30 giờ VN


def _uid() -> str:
    return str(uuid.uuid4())


# ── Bộ luật: đọc câu ────────────────────────────────────────────────────────


@pytest.mark.parametrize("cau", [
    "gặp anh Nam Vinhomes xong, khách xin 3 ngày",
    "gap anh nam vinhomes xong, khach xin 3 ngay",
])
def test_gap_xong_khach_xin_3_ngay(cau):
    d = doc_cau(cau, THU_BAY)
    assert d.viec == "gap"
    assert d.hen == datetime(2026, 11, 17, 9, 0)
    assert [t.tron for t in d.nguoi] == ["nam"]


def test_hen_gap_chua_dien_ra_khong_tinh_la_da_gap():
    d = doc_cau("hẹn gặp anh Nam chiều mai 3h", THU_BAY)
    assert d.viec == "hen"
    assert d.hen == datetime(2026, 11, 15, 15, 0)
    assert d.plan_type == "offline"


def test_chua_goi_duoc_khong_phai_da_goi():
    assert doc_cau("chưa gọi được anh Tâm", THU_BAY).viec is None


def test_goi_khong_nghe_may_van_la_da_goi():
    assert doc_cau("gọi chị Hoa không nghe máy", THU_BAY).viec == "goi"


def test_goi_khac_goi():
    """«gói» (gói thiết kế) không phải «gọi»."""
    d = doc_cau("khách báo gói thiết kế đắt quá", THU_BAY)
    assert d.viec is None and d.hen is None and d.nguoi == []


def test_anh_nam_la_ten_khong_phai_so_5():
    d = doc_cau("anh Năm ngày mai qua công ty", THU_BAY)
    assert [t.goc for t in d.nguoi] == ["năm"]
    assert d.hen == datetime(2026, 11, 15, 9, 0)   # «mai», không phải «năm ngày»
    assert d.viec == "hen" and d.plan_type == "offline"


def test_chi_mai_la_ten_thu_3_tuan_sau():
    d = doc_cau("đã gọi chị Mai, hẹn thứ 3 tuần sau khảo sát", THU_BAY)
    assert d.viec == "goi"
    assert d.hen == datetime(2026, 11, 17, 9, 0)   # thứ Ba tuần sau, không phải «mai»
    assert d.plan_type == "survey"


def test_duoi_so_va_thu_viet_tat():
    d = doc_cau("đuôi 111 gọi rồi, hẹn t5", THU_BAY)
    assert d.duoi == ["111"] and d.viec == "goi"
    assert d.hen == datetime(2026, 11, 19, 9, 0)


def test_ngay_thang_va_gio_toi():
    assert doc_cau("zoom với chị Lan xong, hẹn 20/11 gửi báo giá", THU_BAY).hen == datetime(2026, 11, 20, 9, 0)
    d = doc_cau("tối nay 8h zoom với anh Hùng", THU_BAY)
    assert d.viec == "hen" and d.plan_type == "online"
    assert d.hen == datetime(2026, 11, 14, 20, 0)


def test_moc_qua_khu_khong_thanh_hen():
    assert doc_cau("tuần trước gặp anh Nam", THU_BAY).hen is None
    d = doc_cau("hôm nay gặp anh Nam", THU_BAY)
    assert d.viec == "gap" and d.hen is None
    # 10/11 đã qua → hiểu là 10/11 năm sau, quá xa → không nhận
    assert doc_cau("gặp anh Nam, hẹn 10/11", THU_BAY).hen is None


def test_cau_hoi_khong_phai_bao_cham():
    assert doc_cau("anh Nam có gói nào rẻ hơn không?", THU_BAY).la_cau_hoi


def test_nhan_viec_kem_thu():
    assert nhan_viec("gap", datetime(2026, 11, 17, 9, 0), None, THU_BAY) == \
        "Đã gặp trực tiếp · hẹn lại 09:00 thứ Ba 17/11"
    assert nhan_viec("hen", datetime(2026, 11, 21, 14, 0), "offline", THU_BAY) == \
        "Hẹn tư vấn offline 14:00 thứ Bảy 21/11"
    assert nhan_viec("goi", datetime(2027, 1, 4, 9, 0), "survey", THU_BAY) == \
        "Đã gọi · hẹn khảo sát 09:00 thứ Hai 04/01/2027"


def test_kiem_ai_bo_ket_qua_sai_khuon():
    assert kiem_ai("không phải dict", THU_BAY) is None
    assert kiem_ai({"la_bao_cham": True, "viec": "nhay_mua"}, THU_BAY) is None
    assert kiem_ai({"la_bao_cham": True, "viec": "khac"}, THU_BAY) == {"la_bao_cham": False}
    # hẹn đã qua / quá xa → bỏ phần hẹn; việc «hen» mà không còn hẹn → None (dùng bộ luật)
    qua = kiem_ai({"la_bao_cham": True, "viec": "gap", "hen_ngay": "2026-11-01"}, THU_BAY)
    assert qua["viec"] == "gap" and qua["hen"] is None
    assert kiem_ai({"la_bao_cham": True, "viec": "hen", "hen_ngay": "2028-01-01"}, THU_BAY) is None
    ok = kiem_ai({"la_bao_cham": True, "viec": "zoom", "hen_ngay": "2026-11-18", "hen_gio": "25:99",
                  "hen_loai": "online", "khach": "chị Mai"}, THU_BAY)
    assert ok["hen"] == datetime(2026, 11, 18, 9, 0) and ok["plan_type"] == "online"


# ── Dò lead qua API ─────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def sale_khac(db_session) -> User:
    u = User(
        id=_uid(), full_name="Sale Khác", email="sale.khac.doan@test.com",
        password_hash=hash_password("x12345678"), role="data_entry",
        department="SALES", is_active=True,
    )
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def ds_lead(db_session, sales_user, sale_khac) -> dict[str, Lead]:
    def lead(ten, sdt, owner, stage="interested", **kw):
        return Lead(id=_uid(), name=ten, phone=sdt, stage=stage, assigned_to=owner.id,
                    created_at=datetime.now(timezone.utc) - timedelta(days=10), **kw)
    ds = {
        "nam": lead("Anh Nam – Vinhomes Ocean Park", "0909000111", sales_user),
        "mai": lead("Chị Mai – Ecopark", "0912345678", sales_user),
        "nam_dau": lead("Anh Năm – Hồ Tây", "0988000222", sales_user),
        "mat": lead("Cô Lan – Gamuda", "0977000333", sales_user, stage="lost"),
        "cua_nguoi_khac": lead("Anh Nam – Vinhomes Smart City", "0909000999", sale_khac),
    }
    db_session.add_all(ds.values())
    await db_session.commit()
    return ds


async def _doan(client, user, text, dung_ai=False):
    r = await client.post(URL, json={"text": text, "dung_ai": dung_ai}, headers=auth_header(user))
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_doan_dung_lead_cua_minh_va_khong_ghi_gi(client, db_session, sales_user, ds_lead):
    kq = await _doan(client, sales_user, "gặp anh Nam Vinhomes xong, khách xin 3 ngày")
    assert kq["la_bao_cham"] and kq["chac_chan"]
    assert kq["viec"] == "gap" and kq["nguon"] == "luat"
    assert kq["ung_vien"][0]["id"] == ds_lead["nam"].id
    assert ds_lead["cua_nguoi_khac"].id not in {u["id"] for u in kq["ung_vien"]}
    assert kq["hen_tiep_luc"] == moc_hen_sau(3).isoformat()
    assert kq["tom_tat"] == nhan_viec("gap", moc_hen_sau(3))
    assert kq["ung_vien"][0]["duoi_sdt"] == "111" and "phone" not in kq["ung_vien"][0]
    # Chỉ đoán: chưa có hoạt động nào được ghi
    so = (await db_session.execute(select(func.count(Activity.id)))).scalar()
    assert so == 0


@pytest.mark.asyncio
async def test_go_khong_dau_van_ra(client, sales_user, ds_lead):
    kq = await _doan(client, sales_user, "gap anh nam vinhomes xong")
    assert kq["chac_chan"] and kq["ung_vien"][0]["id"] == ds_lead["nam"].id


@pytest.mark.asyncio
async def test_nam_co_dau_khac_nam(client, sales_user, ds_lead):
    kq = await _doan(client, sales_user, "anh Năm Hồ Tây gọi rồi")
    assert kq["chac_chan"] and kq["viec"] == "goi"
    assert kq["ung_vien"][0]["id"] == ds_lead["nam_dau"].id


@pytest.mark.asyncio
async def test_so_dien_thoai_va_duoi_so(client, sales_user, ds_lead):
    kq = await _doan(client, sales_user, "0912 345 678 gọi rồi")
    assert kq["chac_chan"] and kq["ung_vien"][0]["id"] == ds_lead["mai"].id
    kq = await _doan(client, sales_user, "đuôi 678 hẹn mai")
    assert kq["viec"] == "hen" and kq["ung_vien"][0]["id"] == ds_lead["mai"].id
    assert kq["hen_tiep_luc"] == moc_hen_sau(1).isoformat()


@pytest.mark.asyncio
async def test_sdt_la_de_luong_tao_lead_lo(client, sales_user, ds_lead):
    kq = await _doan(client, sales_user, "0977111222 gọi rồi, khách cần thiết kế căn hộ")
    assert kq["la_bao_cham"] is False


@pytest.mark.asyncio
async def test_khong_phai_bao_cham(client, sales_user, ds_lead):
    for cau in ("khách báo gói thiết kế đắt quá", "anh Nam có gói nào rẻ hơn không?", "ok"):
        assert (await _doan(client, sales_user, cau))["la_bao_cham"] is False, cau


@pytest.mark.asyncio
async def test_chu_rong_tra_goi_y_lead_dang_cham(client, sales_user, ds_lead):
    kq = await _doan(client, sales_user, "")
    ids = {g["id"] for g in kq["goi_y"]}
    assert kq["la_bao_cham"] is False
    assert {ds_lead["nam"].id, ds_lead["mai"].id, ds_lead["nam_dau"].id} <= ids
    assert ds_lead["mat"].id not in ids and ds_lead["cua_nguoi_khac"].id not in ids


@pytest.mark.asyncio
async def test_nguoi_khac_chi_thay_lead_cua_ho(client, sale_khac, designer_user, ds_lead):
    kq = await _doan(client, sale_khac, "gặp anh Nam Vinhomes xong")
    assert [u["id"] for u in kq["ung_vien"]] == [ds_lead["cua_nguoi_khac"].id]
    # Không thuộc Kinh doanh/BGĐ → không dò gì
    kq = await _doan(client, designer_user, "gặp anh Nam Vinhomes xong")
    assert kq["la_bao_cham"] is False and kq["ung_vien"] == [] and kq["goi_y"] == []


# ── AI đọc lại câu ──────────────────────────────────────────────────────────


def _gia_ai(monkeypatch, tra_ve):
    goi = []

    async def co_ai():
        return True

    async def llm_gia(messages, **kw):
        goi.append(messages)
        noi_dung = tra_ve if isinstance(tra_ve, str) else json.dumps(tra_ve)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=noi_dung))])

    monkeypatch.setattr(hieu_cau_sale, "llm_available", co_ai)
    monkeypatch.setattr(hieu_cau_sale, "llm_complete", llm_gia)
    return goi


@pytest.mark.asyncio
async def test_ai_doc_lai_cau_chi_nhan_chu_cua_sale(client, sales_user, ds_lead, monkeypatch):
    ngay = (gio_vn_naive() + timedelta(days=2)).date()
    goi = _gia_ai(monkeypatch, {
        "la_bao_cham": True, "viec": "zoom", "khach": "chị Mai Ecopark",
        "hen_ngay": ngay.isoformat(), "hen_gio": "14:00", "hen_loai": "offline",
    })
    kq = await _doan(client, sales_user, "xong buổi online với chị Mai rồi, 2 hôm nữa 2h chiều qua công ty", dung_ai=True)
    assert kq["nguon"] == "ai" and kq["viec"] == "zoom" and kq["plan_type"] == "offline"
    assert kq["hen_tiep_luc"] == datetime(ngay.year, ngay.month, ngay.day, 14, 0).isoformat()
    assert kq["ung_vien"][0]["id"] == ds_lead["mai"].id
    # AI chỉ nhận câu của sale, không nhận danh sách lead
    gui_ai = json.dumps(goi, ensure_ascii=False)
    for rieng in ("Ocean Park", "Hồ Tây", "Gamuda", "Ecopark", "0912"):
        assert rieng not in gui_ai, rieng


@pytest.mark.asyncio
async def test_ai_tra_sai_thi_dung_bo_luat(client, sales_user, ds_lead, monkeypatch):
    _gia_ai(monkeypatch, "xin lỗi, tôi không hiểu")
    kq = await _doan(client, sales_user, "gặp anh Nam Vinhomes xong, khách xin 3 ngày", dung_ai=True)
    assert kq["nguon"] == "luat" and kq["viec"] == "gap"
    assert kq["hen_tiep_luc"] == moc_hen_sau(3).isoformat()


@pytest.mark.asyncio
async def test_ai_bao_khong_phai_bao_cham(client, sales_user, ds_lead, monkeypatch):
    _gia_ai(monkeypatch, {"la_bao_cham": False, "viec": "khac"})
    kq = await _doan(client, sales_user, "gặp anh Nam Vinhomes xong", dung_ai=True)
    assert kq["la_bao_cham"] is False


@pytest.mark.asyncio
async def test_khong_co_model_ai_van_chay_bo_luat(client, sales_user, ds_lead):
    # Môi trường test không có khoá AI → llm_available() False → không gọi AI
    kq = await _doan(client, sales_user, "gặp anh Nam Vinhomes xong", dung_ai=True)
    assert kq["nguon"] == "luat" and kq["chac_chan"]


# ── /touch trả nhãn + link mở lead cho bot ───────────────────────────────────


@pytest.mark.asyncio
async def test_touch_tra_nhan_va_link_mo_erp(client, sales_user, ds_lead):
    lead = ds_lead["nam"]
    r = await client.post(f"/api/v1/telegram/lead/{lead.id}/touch",
                          json={"viec": "gap", "hen_sau_ngay": 3}, headers=auth_header(sales_user))
    assert r.status_code == 200, r.text
    kq = r.json()
    assert kq["nhan"] == nhan_viec("gap", moc_hen_sau(3))
    assert kq["lead"]["mo_erp"].startswith("https://")
    assert kq["lead"]["mo_erp"].endswith(f"/leads?id={lead.id}")


# ── Rà soát 23/11: câu dễ hiểu sai ───────────────────────────────────────────


@pytest.mark.parametrize("cau", [
    "tối qua gặp anh Nam Vinhomes, anh ưng mẫu", "3 hôm trước gặp anh Nam Vinhomes",
    "hôm qua 3h chiều gặp chị Mai Ecopark", "cách đây 2 ngày gặp chị Mai Ecopark",
])
def test_ke_chuyen_da_qua_la_da_gap_khong_thanh_hen(cau):
    d = doc_cau(cau, THU_BAY)
    assert d.viec == "gap" and d.hen is None


def test_ve_qua_khu_khong_lam_mat_hen_o_ve_sau():
    d = doc_cau("1 tuần trước gặp anh Nam, hẹn thứ 3 tuần sau", THU_BAY)
    assert d.viec == "gap" and d.hen == datetime(2026, 11, 17, 9, 0)
    assert doc_cau("anh Nam qua công ty rồi", THU_BAY).viec == "vp"


@pytest.mark.parametrize("cau,ngay", [
    ("hẹn 5 tháng 12 gặp anh Nam", datetime(2026, 12, 5, 9, 0)),
    ("hẹn mùng 1 tháng sau gặp anh Nam", datetime(2026, 12, 1, 9, 0)),
    ("ngày 20 tháng 11 gặp anh Nam", datetime(2026, 11, 20, 9, 0)),
])
def test_ngay_lich_khong_phai_n_thang(cau, ngay):
    assert doc_cau(cau, THU_BAY).hen == ngay


@pytest.mark.parametrize("cau", [
    "thu 2 dot roi", "khách ở tòa T5 Times City, gặp rồi", "lần thứ 2 gọi không nghe máy",
    "cọc 1/2 rồi", "gặp anh Nam ở 12/5 Lê Lợi",
])
def test_khong_phai_ngay_hen(cau):
    assert doc_cau(cau, THU_BAY).hen is None


def test_hen_t5_van_la_thu_nam():
    assert doc_cau("hẹn t5 gặp anh Nam", THU_BAY).hen == datetime(2026, 11, 19, 9, 0)


@pytest.mark.parametrize("cau", [
    "gặp anh Nam chưa được", "anh Nam hoãn gặp", "khách huỷ buổi gặp", "zoom với chị Lan không thành",
])
def test_gap_khong_thanh_khong_ghi_la_da_gap(cau):
    assert doc_cau(cau, THU_BAY).viec is None


def test_goi_khong_duoc_van_la_da_goi_va_lam_o_cong_ty_khong_phai_len_vp():
    assert doc_cau("gọi anh Nam không được", THU_BAY).viec == "goi"
    assert doc_cau("làm ở công ty Viettel, gọi rồi", THU_BAY).viec == "goi"


@pytest.mark.asyncio
async def test_duoi_so_trung_nhieu_lead_thi_hoi_chon(client, db_session, sales_user, ds_lead):
    db_session.add(Lead(id=_uid(), name="Anh Hùng – Times City", phone="0904555111", stage="interested",
                        assigned_to=sales_user.id, created_at=datetime.now(timezone.utc)))
    await db_session.commit()
    kq = await _doan(client, sales_user, "đuôi 111 gọi rồi")
    assert kq["la_bao_cham"] and kq["chac_chan"] is False
    assert {u["duoi_sdt"] for u in kq["ung_vien"][:2]} == {"111"}
    assert (await _doan(client, sales_user, "đuôi 678 gọi rồi"))["chac_chan"] is True


@pytest.mark.asyncio
async def test_chu_co_dau_trung_ten_khong_dau_chi_goi_y(client, sale_khac, ds_lead):
    """«anh Năm» (có dấu) ≈ lead «Anh Nam»: gợi ý được nhưng không CHẮC — sale phải chọn."""
    kq = await _doan(client, sale_khac, "anh Năm gọi rồi")
    assert kq["la_bao_cham"] and kq["chac_chan"] is False
    assert kq["ung_vien"][0]["id"] == ds_lead["cua_nguoi_khac"].id
    # Gõ không dấu thì vẫn chắc
    assert (await _doan(client, sale_khac, "anh nam vinhomes goi roi"))["chac_chan"] is True


def test_kiem_ai_khong_vo_khi_sai_kieu():
    assert kiem_ai({"la_bao_cham": True, "viec": ["goi"]}, THU_BAY) is None
    assert kiem_ai({"viec": "goi"}, THU_BAY) is None  # thiếu la_bao_cham → bộ luật
    assert kiem_ai({"la_bao_cham": "true", "viec": "goi"}, THU_BAY)["viec"] == "goi"
    assert kiem_ai({"la_bao_cham": "false", "viec": "goi"}, THU_BAY) == {"la_bao_cham": False}


@pytest.mark.asyncio
async def test_ai_khong_nhan_so_dien_thoai(client, sales_user, ds_lead, monkeypatch):
    goi = _gia_ai(monkeypatch, {"la_bao_cham": True, "viec": "goi", "khach": ""})
    kq = await _doan(client, sales_user, "0912 345 678 gọi rồi, đuôi 678", dung_ai=True)
    assert kq["ung_vien"][0]["id"] == ds_lead["mai"].id
    gui_ai = json.dumps(goi, ensure_ascii=False)
    assert "0912" not in gui_ai and "345" not in gui_ai and "678" not in gui_ai and "[SĐT]" in gui_ai
