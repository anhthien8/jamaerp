"""Khách hàng theo người chăm sóc (24/11/2026).

Chủ dự án: «nhân viên chỉ thấy khách của họ, trưởng phòng thấy khách phòng họ; hiện
khách thuộc về ai chăm sóc; doanh thu mang lại kèm trạng thái (đã chốt / đang chốt /
tiềm năng)».

Trước bản này ai có ô «Sửa Khách hàng» là thấy toàn bộ khách — sale (`data_entry`)
có sẵn ô đó nên mọi sale thấy khách của nhau; còn chi tiết một khách thì chặn theo
danh sách vai trò cứng, mở được khách bất kỳ bằng id.
"""

import uuid

import pytest
import pytest_asyncio

from app.middleware.auth import hash_password
from app.middleware.permissions import xoa_cache_quyen
from app.models.customer import Customer
from app.models.lead import Lead
from app.models.project import Project
from app.models.user import User
from tests.conftest import auth_header

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _sach_cache_quyen():
    xoa_cache_quyen()
    yield
    xoa_cache_quyen()


async def _user(db, email, role, department, ten=None) -> User:
    u = User(id=str(uuid.uuid4()), full_name=ten or f"NV {email.split('@')[0]}", email=email,
             password_hash=hash_password("secret123"), role=role, department=department, is_active=True)
    db.add(u)
    await db.commit()
    return u


async def _lead(db, sale: User | None, stage="new", **kw) -> Lead:
    lead = Lead(id=str(uuid.uuid4()), name="Lead", phone=f"09{uuid.uuid4().int % 10**8:08d}",
                stage=stage, assigned_to=sale.id if sale else None, **kw)
    db.add(lead)
    await db.commit()
    return lead


async def _khach(db, ten, **kw) -> Customer:
    c = Customer(id=str(uuid.uuid4()), name=ten, phone="0934655611", **kw)
    db.add(c)
    await db.commit()
    return c


async def _du_an(db, khach: Customer, **kw) -> Project:
    p = Project(id=str(uuid.uuid4()), code=f"P-{uuid.uuid4().hex[:6]}", name="Nhà phố",
                client_name=khach.name, customer_id=khach.id, **kw)
    db.add(p)
    await db.commit()
    return p


async def _ten_khach(client, nguoi) -> set[str]:
    r = await client.get("/api/v1/customers", headers=auth_header(nguoi))
    assert r.status_code == 200, r.text
    return {c["name"] for c in r.json()["items"]}


@pytest_asyncio.fixture
async def bo_khach(db_session, admin_user, sales_user):
    """Sale A (fixture sales_user) và sale B cùng phòng KD, mỗi người một khách qua lead;
    thêm một khách vô chủ và một khách của phòng Thiết kế."""
    db = db_session
    sale_b = await _user(db, "saleb@test.com", "data_entry", "SALES", "Sale B")
    tp_kd = await _user(db, "tpkd@test.com", "leader", "SALES", "Trưởng phòng KD")
    thiet_ke = await _user(db, "tk@test.com", "supervisor", "DESIGN", "Họa sĩ")
    khach_a = await _khach(db, "Khách của A", lead_id=(await _lead(db, sales_user)).id)
    khach_b = await _khach(db, "Khách của B", lead_id=(await _lead(db, sale_b)).id)
    vo_chu = await _khach(db, "Khách vô chủ")
    khach_tk = await _khach(db, "Khách phòng thiết kế")
    await _du_an(db, khach_tk, designer_id=thiet_ke.id)
    return {"sale_b": sale_b, "tp_kd": tp_kd, "thiet_ke": thiet_ke,
            "khach_a": khach_a, "khach_b": khach_b, "vo_chu": vo_chu, "khach_tk": khach_tk}


# ── Phạm vi xem ─────────────────────────────────────────────────────────────

async def test_nhan_vien_chi_thay_khach_cua_minh(client, sales_user, bo_khach):
    """Sale có sẵn ô «Sửa Khách hàng» — ô đó KHÔNG còn mở toàn bộ danh sách."""
    assert await _ten_khach(client, sales_user) == {"Khách của A"}
    assert await _ten_khach(client, bo_khach["sale_b"]) == {"Khách của B"}


async def test_truong_phong_thay_khach_ca_phong(client, db_session, bo_khach):
    """TP KD: khách của mọi sale trong phòng + khách của dự án CHƯA có sale (để còn phân người).
    Trưởng phòng khác: chỉ khách có dự án thuộc phòng mình, không thấy khách mới ở mức lead."""
    ten = await _ten_khach(client, bo_khach["tp_kd"])
    assert {"Khách của A", "Khách của B", "Khách phòng thiết kế"} <= ten
    assert "Khách vô chủ" not in ten

    tp_gs = await _user(db_session, "tpgs@test.com", "operation_leader", "OPS", "TP Giám sát")
    ten = await _ten_khach(client, tp_gs)
    assert "Khách phòng thiết kế" in ten, "dự án chưa có giám sát → TP Giám sát thấy để phân công"
    assert not ({"Khách của A", "Khách của B", "Khách vô chủ"} & ten)


async def test_ban_giam_doc_va_ke_toan_thay_het(client, admin_user, accountant_user, bo_khach):
    tat_ca = {"Khách của A", "Khách của B", "Khách vô chủ", "Khách phòng thiết kế"}
    assert await _ten_khach(client, admin_user) == tat_ca
    assert await _ten_khach(client, accountant_user) == tat_ca


async def test_khach_cua_du_an_vo_chu_khong_lo_cho_moi_nguoi(client, db_session, sales_user, bo_khach):
    """Dự án chưa phân công PIC thì ai cũng thấy dự án — nhưng khách của nó không phải «khách của tôi»."""
    await _du_an(db_session, bo_khach["vo_chu"])
    assert "Khách vô chủ" not in await _ten_khach(client, sales_user)


async def test_pic_du_an_thay_khach_cua_du_an(client, bo_khach):
    assert await _ten_khach(client, bo_khach["thiet_ke"]) == {"Khách phòng thiết kế"}


async def test_khach_tu_tao_tay_van_thay(client, sales_user, bo_khach):
    """Tạo khách tay (chưa lead, chưa dự án): người tạo phải còn thấy, và đứng tên chăm sóc."""
    r = await client.post("/api/v1/customers", json={"name": "Khách tự tạo", "phone": "0908887776"},
                          headers=auth_header(sales_user))
    assert r.status_code == 200, r.text
    assert "Khách tự tạo" in await _ten_khach(client, sales_user)
    assert "Khách tự tạo" not in await _ten_khach(client, bo_khach["sale_b"])
    assert "Khách tự tạo" in await _ten_khach(client, bo_khach["tp_kd"])
    ct = await client.get(f"/api/v1/customers/{r.json()['id']}", headers=auth_header(sales_user))
    assert ct.json()["cham_soc_ten"] == sales_user.full_name


# ── Chi tiết & sửa cùng phạm vi với danh sách ───────────────────────────────

async def test_chi_tiet_va_sua_khach_nguoi_khac_bi_chan(client, sales_user, bo_khach):
    cua_b = bo_khach["khach_b"].id
    assert (await client.get(f"/api/v1/customers/{cua_b}", headers=auth_header(sales_user))).status_code == 404
    r = await client.put(f"/api/v1/customers/{cua_b}", json={"notes": "sửa trộm"},
                         headers=auth_header(sales_user))
    assert r.status_code == 404, r.text

    cua_a = bo_khach["khach_a"].id
    assert (await client.get(f"/api/v1/customers/{cua_a}", headers=auth_header(sales_user))).status_code == 200
    r = await client.put(f"/api/v1/customers/{cua_a}", json={"notes": "khách quen"},
                         headers=auth_header(sales_user))
    assert r.status_code == 200, r.text


# ── Người chăm sóc ──────────────────────────────────────────────────────────

async def test_hien_nguoi_cham_soc(client, db_session, admin_user, sales_user, bo_khach):
    """Sale của lead → sale của dự án → để trống khi chưa có ai."""
    await _du_an(db_session, bo_khach["vo_chu"], sales_id=bo_khach["sale_b"].id)
    r = await client.get("/api/v1/customers", headers=auth_header(admin_user))
    theo_ten = {c["name"]: c for c in r.json()["items"]}
    assert theo_ten["Khách của A"]["cham_soc_ten"] == sales_user.full_name
    assert theo_ten["Khách của A"]["cham_soc_id"] == sales_user.id
    assert theo_ten["Khách vô chủ"]["cham_soc_ten"] == "Sale B"
    assert theo_ten["Khách phòng thiết kế"].get("cham_soc_ten") is None


# ── Trạng thái doanh thu ────────────────────────────────────────────────────

async def test_trang_thai_doanh_thu(client, db_session, admin_user, sales_user):
    db = db_session
    da_chot = await _khach(db, "Đã chốt")
    await _du_an(db, da_chot, total_value=15_000_000)
    dam_phan = await _khach(db, "Đang chốt", lead_id=(
        await _lead(db, sales_user, stage="potential", deal_value=200_000_000)).id)
    moi = await _khach(db, "Tiềm năng", lead_id=(
        await _lead(db, sales_user, stage="interested", estimated_budget=80_000_000)).id)
    mat = await _khach(db, "Đã mất", lead_id=(await _lead(db, sales_user, stage="lost")).id)
    huy = await _khach(db, "Đã hủy")
    await _du_an(db, huy, total_value=50_000_000, status="cancelled")
    await _khach(db, "Chưa có gì")

    r = await client.get("/api/v1/customers", headers=auth_header(admin_user))
    k = {c["name"]: c for c in r.json()["items"]}
    assert (k["Đã chốt"]["trang_thai_doanh_thu"], k["Đã chốt"]["doanh_thu"]) == ("da_chot", 15_000_000)
    assert (k["Đang chốt"]["trang_thai_doanh_thu"], k["Đang chốt"]["doanh_thu_du_kien"]) == ("dang_chot", 200_000_000)
    assert k["Đang chốt"]["doanh_thu"] == 0, "chưa thắng deal thì chưa tính là doanh thu"
    assert (k["Tiềm năng"]["trang_thai_doanh_thu"], k["Tiềm năng"]["doanh_thu_du_kien"]) == ("tiem_nang", 80_000_000)
    assert k["Đã mất"]["trang_thai_doanh_thu"] == "da_mat"
    assert (k["Đã hủy"]["trang_thai_doanh_thu"], k["Đã hủy"]["doanh_thu"]) == ("da_huy", 0)
    assert k["Chưa có gì"]["trang_thai_doanh_thu"] is None

    ct = await client.get(f"/api/v1/customers/{dam_phan.id}", headers=auth_header(admin_user))
    assert ct.json()["trang_thai_doanh_thu"] == "dang_chot"
    assert moi.id and mat.id
