"""Chế độ thưởng (23/10/2026): hũ doanh số, chuyên cần, Điểm JAMA, chốt kỳ, khách đánh giá."""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.approval import ApprovalRequest
from app.models.attendance import AttendanceRecord
from app.models.contract import Contract
from app.models.customer import Customer
from app.models.danh_gia_khach import DanhGiaKhach
from app.models.payroll import Bonus
from app.models.user import User
from app.services import che_do_thuong as cdt
from app.services.attendance_service import VN_TZ, period_bounds
from tests.conftest import _uid, auth_header


def _u(dept="SALES", team=None, ten="NV"):
    return User(id=_uid(), full_name=ten, email=f"{_uid()}@t.vn", password_hash="x",
                role="data_entry", department=dept, team_id=team, is_active=True)


# ── Hàm thuần ───────────────────────────────────────────────────────────────

def test_hu_cong_don_va_chia_theo_doanh_so():
    cfg = cdt.chuan_hoa_cau_hinh({})["chuong_trinh"]["hu_doanh_so"]
    a, b, c = _u(ten="A"), _u(ten="B"), _u(dept="DESIGN", ten="C")
    hu = cdt.tinh_hu(cfg, 13e9, {a.id: 9e9, b.id: 3e9, None: 1e9}, [a, b, c])
    assert hu["so_moc_dat"] == 2
    assert hu["quy_mo"] == 70_000_000  # 20 + 50 cộng dồn
    assert hu["moc_tiep"]["doanh_so"] == 14.4e9
    assert hu["con_thieu"] == pytest.approx(1.4e9)
    assert hu["chia"][a.id] == pytest.approx(52_500_000)
    assert hu["chia"][b.id] == pytest.approx(17_500_000)
    assert c.id not in hu["chia"]  # phòng Thiết kế không thuộc «phòng nhận»


def test_hu_khong_cong_don_lay_moc_cao_nhat_va_chia_deu():
    cfg = cdt.chuan_hoa_cau_hinh({"chuong_trinh": {"hu_doanh_so": {"cong_don": False, "cach_chia": "chia_deu"}}})
    a, b = _u(), _u()
    hu = cdt.tinh_hu(cfg["chuong_trinh"]["hu_doanh_so"], 15e9, {a.id: 15e9}, [a, b])
    assert hu["quy_mo"] == 100_000_000
    assert hu["chia"][a.id] == hu["chia"][b.id] == pytest.approx(50_000_000)


def test_hu_chua_dat_moc_nao():
    cfg = cdt.chuan_hoa_cau_hinh({})["chuong_trinh"]["hu_doanh_so"]
    hu = cdt.tinh_hu(cfg, 5e9, {}, [_u()])
    assert hu["quy_mo"] == 0 and hu["chia"] == {} and hu["con_thieu"] == 3e9


def test_diem_jama_chia_lai_trong_so_khi_thieu_thanh_phan():
    dj = cdt.chuan_hoa_cau_hinh({})["diem_jama"]
    # SALES 40/20/25/15 — thiếu phản hồi & đánh giá → chỉ còn doanh số 40 + chuyên cần 20
    d = cdt.diem_jama("SALES", {"doanh_so": 100, "chuyen_can": 70, "phan_hoi": None, "danh_gia": None}, dj)
    assert d == pytest.approx(90.0)
    assert cdt.he_so_tu_diem(d, dj) == 1.2
    assert cdt.he_so_tu_diem(75, dj) == 1.0
    assert cdt.he_so_tu_diem(55, dj) == 0.5
    assert cdt.he_so_tu_diem(40, dj) == 0.0
    assert cdt.he_so_tu_diem(None, dj) == 1.0  # chưa đủ số → không phạt
    assert cdt.diem_jama("KHAC", {"chuyen_can": 80}, dj) == 80


def test_chuan_hoa_chan_so_vo_ly():
    c = cdt.chuan_hoa_cau_hinh({"chuong_trinh": {
        "chuyen_can": {"gio_vao_ca": "29:99", "tru_tre": -5, "tre_phut": "abc"},
        "phan_hoi": {"muc_tieu_goi": 500},
        "hu_doanh_so": {"moc": [{"doanh_so": 5e9, "quy": 1}, {"doanh_so": -1, "quy": 9}, "rác"], "pham_vi": "?"},
    }})
    ct = c["chuong_trinh"]
    assert ct["chuyen_can"]["gio_vao_ca"] == "23:59"
    assert ct["chuyen_can"]["tru_tre"] == 0
    assert ct["chuyen_can"]["tre_phut"] == 5
    assert ct["phan_hoi"]["muc_tieu_goi"] == 100
    assert len(ct["hu_doanh_so"]["moc"]) == 1
    assert ct["hu_doanh_so"]["pham_vi"] == "cong_ty"


def test_quy_va_ky():
    assert cdt.quy_cua("2026-11") == ("Q4/2026", date(2026, 10, 1), date(2027, 1, 1))
    assert cdt.ky_truoc("2026-01") == "2025-12"
    assert cdt.ky_sau("2026-12") == "2027-01"
    assert cdt.la_cuoi_quy("2026-09") and not cdt.la_cuoi_quy("2026-10")
    with pytest.raises(ValueError):
        cdt.kiem_tra_ky("2026-13")


# ── API cấu hình ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chi_admin_ke_toan_xem_va_chi_admin_luu(client: AsyncClient, admin_user, accountant_user, sales_user):
    r = await client.get("/api/v1/che-do-thuong", headers=auth_header(sales_user))
    assert r.status_code == 403
    r = await client.get("/api/v1/che-do-thuong", headers=auth_header(accountant_user))
    assert r.status_code == 200
    body = r.json()
    assert body["hieu_luc_tu"] is None
    assert body["cau_hinh"]["chuong_trinh"]["hu_doanh_so"]["moc"][2]["doanh_so"] == 14_400_000_000
    r = await client.put("/api/v1/che-do-thuong", json={"cau_hinh": body["cau_hinh"]},
                         headers=auth_header(accountant_user))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_luu_lan_dau_ap_ngay_lan_sau_ap_ky_sau(client: AsyncClient, admin_user):
    hien_tai = cdt.ky_hien_tai()
    r = await client.put("/api/v1/che-do-thuong", json={"cau_hinh": {}}, headers=auth_header(admin_user))
    assert r.status_code == 200 and r.json()["hieu_luc_tu"] == hien_tai
    cfg = r.json()["cau_hinh"]
    cfg["chuong_trinh"]["chuyen_can"]["thuong_du_cong"] = 700_000
    r = await client.put("/api/v1/che-do-thuong", json={"cau_hinh": cfg}, headers=auth_header(admin_user))
    assert r.json()["hieu_luc_tu"] == cdt.ky_sau(hien_tai)
    # Kỳ này vẫn chạy số cũ; kỳ sau mới 700k
    r = await client.get(f"/api/v1/che-do-thuong?ky={hien_tai}", headers=auth_header(admin_user))
    assert r.json()["cau_hinh"]["chuong_trinh"]["chuyen_can"]["thuong_du_cong"] == 500_000
    r = await client.get(f"/api/v1/che-do-thuong?ky={cdt.ky_sau(hien_tai)}", headers=auth_header(admin_user))
    assert r.json()["cau_hinh"]["chuong_trinh"]["chuyen_can"]["thuong_du_cong"] == 700_000
    assert len(r.json()["lich_su"]) == 2


# ── Bảng thưởng + chốt kỳ ───────────────────────────────────────────────────

async def _hd(db, project, gia_tri, ngay):
    db.add(Contract(id=_uid(), code=f"HD-{uuid.uuid4().hex[:8]}", project_id=project.id, title="HĐ",
                    status="signed", total_value=gia_tri, signed_date=ngay))


@pytest.mark.asyncio
async def test_xem_thu_va_chot_ky_sinh_bonus_cho_duyet(
    client: AsyncClient, db_session, admin_user, accountant_user, sales_user, project
):
    ky = cdt.ky_truoc(cdt.ky_hien_tai())
    tu, _ = period_bounds(ky)
    project.sales_id = sales_user.id
    await _hd(db_session, project, 9e9, tu + timedelta(days=3))
    await db_session.commit()

    r = await client.get(f"/api/v1/che-do-thuong/xem-thu?ky={ky}", headers=auth_header(admin_user))
    assert r.status_code == 200
    bang = r.json()
    assert bang["hu"]["so_moc_dat"] == 1 and bang["hu"]["quy_mo"] == 20_000_000
    dong = next(x for x in bang["nguoi"] if x["user_id"] == sales_user.id)
    # Doanh số 9 tỷ / mục tiêu 14,4 tỷ (1 sale) = 62,5 điểm → ×0,5
    assert dong["thanh_phan"]["doanh_so"] == pytest.approx(62.5)
    assert dong["he_so"] == 0.5
    assert dong["tong"] == 10_000_000
    assert all(x["user_id"] != admin_user.id for x in bang["nguoi"])  # BGĐ/admin không tự thưởng

    r = await client.post(f"/api/v1/che-do-thuong/chot?ky={ky}", headers=auth_header(admin_user))
    assert r.status_code == 200, r.text
    don_id = r.json()["approval_id"]
    don = await db_session.get(ApprovalRequest, don_id)
    assert don.type == "bonus_batch" and don.current_approver_id == accountant_user.id
    bonuses = (await db_session.execute(select(Bonus).where(Bonus.approval_id == don_id))).scalars().all()
    assert len(bonuses) == 1 and bonuses[0].status == "pending" and bonuses[0].amount == 10_000_000

    r = await client.post(f"/api/v1/che-do-thuong/chot?ky={ky}", headers=auth_header(admin_user))
    assert r.status_code == 409

    r = await client.post(f"/api/v1/approvals/{don_id}/approve", headers=auth_header(accountant_user))
    assert r.status_code == 200, r.text
    await db_session.refresh(bonuses[0])
    assert bonuses[0].status == "approved"


@pytest.mark.asyncio
async def test_khong_chot_ky_chua_ket_thuc(client: AsyncClient, admin_user):
    r = await client.post(f"/api/v1/che-do-thuong/chot?ky={cdt.ky_hien_tai()}", headers=auth_header(admin_user))
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_ky_luat_va_thu_viec(client: AsyncClient, db_session, admin_user, sales_user, project):
    ky = cdt.ky_truoc(cdt.ky_hien_tai())
    tu, _ = period_bounds(ky)
    project.sales_id = sales_user.id
    await _hd(db_session, project, 15e9, tu + timedelta(days=1))
    await db_session.commit()
    r = await client.put(f"/api/v1/che-do-thuong/loai-tru?ky={ky}", json={"user_ids": [sales_user.id, "khong-ton-tai"]},
                         headers=auth_header(admin_user))
    assert r.json()["user_ids"] == [sales_user.id]
    bang = (await client.get(f"/api/v1/che-do-thuong/xem-thu?ky={ky}", headers=auth_header(admin_user))).json()
    dong = next(x for x in bang["nguoi"] if x["user_id"] == sales_user.id)
    assert dong["tong"] == 0 and any("kỷ luật" in g for g in dong["ghi_chu"])


# ── Chuyên cần ──────────────────────────────────────────────────────────────

def _gio_vn(d: date, h: int, m: int) -> datetime:
    return datetime(d.year, d.month, d.day, h, m, tzinfo=VN_TZ).astimezone(timezone.utc).replace(tzinfo=None)


@pytest.mark.asyncio
async def test_chuyen_can_dem_tre_quen_ra_va_vang(db_session, sales_user):
    ky = cdt.ky_truoc(cdt.ky_hien_tai())
    tu, den = period_bounds(ky)
    ngay_lam = [d for d in cdt._ngay_lam_viec(tu, den)]
    for i, d in enumerate(ngay_lam[:-1]):  # bỏ ngày cuối → 1 ngày vắng không phép
        vao = _gio_vn(d, 8, 20) if i < 2 else _gio_vn(d, 7, 55)  # 2 lần trễ
        db_session.add(AttendanceRecord(
            user_id=sales_user.id, work_date=d, check_in=vao, check_out=vao + timedelta(hours=9),
            source="web", needs_review=(i == 3), note="auto-close: quên checkout" if i == 3 else None,
        ))
    await db_session.commit()
    cfg = cdt.chuan_hoa_cau_hinh({})["chuong_trinh"]["chuyen_can"]
    kq = await cdt.tinh_chuyen_can(db_session, [sales_user], tu, den, cfg)
    r = kq[sales_user.id]
    assert (r["tre"], r["quen_ra"], r["nghi_kp"]) == (2, 1, 1)
    assert r["diem"] == 100 - 2 * 3 - 2 - 15
    assert r["du_cong"] is False


@pytest.mark.asyncio
async def test_chuyen_can_bo_qua_nguoi_chua_cham_cong(db_session, sales_user):
    tu, den = period_bounds(cdt.ky_truoc(cdt.ky_hien_tai()))
    cfg = cdt.chuan_hoa_cau_hinh({})["chuong_trinh"]["chuyen_can"]
    kq = await cdt.tinh_chuyen_can(db_session, [sales_user], tu, den, cfg)
    assert kq[sales_user.id]["co_du_lieu"] is False and kq[sales_user.id]["diem"] is None


# ── Hũ trên Tổng quan ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_hu_chi_hien_cho_kinh_doanh(client: AsyncClient, admin_user, sales_user, designer_user):
    r = await client.get("/api/v1/che-do-thuong/hu", headers=auth_header(sales_user))
    assert r.json()["hien"] is True and len(r.json()["moc"]) == 4
    r = await client.get("/api/v1/che-do-thuong/hu", headers=auth_header(designer_user))
    assert r.json() == {"hien": False}


@pytest.mark.asyncio
async def test_bao_moc_lan_dau_im_lang(db_session, admin_user, project, monkeypatch):
    gui = []

    async def fake_send(chat, text):
        gui.append(text)

    import app.services.telegram_notify as tn
    monkeypatch.setattr(tn, "send_telegram", fake_send)
    from app.services.automation import set_automation_setting
    await set_automation_setting(db_session, "telegram_group_chat_id", "-100123")
    await _hd(db_session, project, 9e9, datetime.now(VN_TZ).date())
    await db_session.commit()
    assert (await cdt.bao_moc_moi(db_session))["bo_qua"] == "ghi_nhan_lan_dau"
    assert gui == []
    await _hd(db_session, project, 4e9, datetime.now(VN_TZ).date())
    await db_session.commit()
    assert (await cdt.bao_moc_moi(db_session)) == {"da_bao": 2}
    assert len(gui) == 1 and "MỐC 2" in gui[0] and "đ" not in gui[0].split("Quỹ")[0][-5:]


# ── Khách đánh giá trên portal ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_portal_danh_gia(client: AsyncClient, db_session, admin_user, sales_user, project):
    cust = Customer(id=_uid(), name="Khách", phone="0900000077", type="individual",
                    portal_token=str(uuid.uuid4()), portal_enabled=True)
    db_session.add(cust)
    await db_session.flush()
    project.customer_id = cust.id
    project.sales_id = sales_user.id
    await db_session.commit()
    base = f"/api/v1/portal/{cust.portal_token}/projects/{project.id}/danh-gia"

    r = await client.get(base)
    assert r.status_code == 200
    moc = {m["ma"]: m for m in r.json()["moc"]}
    assert moc["ky_hd_tk"]["mo"] is False and moc["ban_giao"]["mo"] is False
    assert {d["id"] for d in r.json()["doi_ngu"]} == {sales_user.id, admin_user.id}

    r = await client.post(base, json={"moc": "ky_hd_tk", "so_sao": 5})
    assert r.status_code == 400  # chưa ký HĐ

    await _hd(db_session, project, 1e9, date.today())
    await db_session.commit()
    r = await client.post(base, json={"moc": "ky_hd_tk", "so_sao": 5, "nhan_xet": "Tư vấn kỹ",
                                      "khen_user_id": sales_user.id})
    assert r.status_code == 200, r.text
    r = await client.post(base, json={"moc": "ky_hd_tk", "so_sao": 1})
    assert r.status_code == 409
    r = await client.post(base, json={"moc": "ky_hd_tk", "so_sao": 9})
    assert r.status_code == 422

    dg = (await db_session.execute(select(DanhGiaKhach))).scalars().one()
    assert dg.khen_user_id == sales_user.id

    cfg = cdt.chuan_hoa_cau_hinh({})["chuong_trinh"]["danh_gia"]
    hom_nay = datetime.now(VN_TZ).date()
    kq, tom_tat = await cdt.tinh_danh_gia(db_session, hom_nay - timedelta(days=1), hom_nay + timedelta(days=1), cfg)
    assert kq[sales_user.id]["thuong_du_an"] == pytest.approx(1_500_000)  # 3tr chia 2 người
    assert kq[sales_user.id]["thuong_khen"] == 300_000
    assert tom_tat[0]["dat"] is True


@pytest.mark.asyncio
async def test_portal_danh_gia_token_khac_bi_chan(client: AsyncClient, db_session, project):
    cust = Customer(id=_uid(), name="Người lạ", phone="0900000078", type="individual",
                    portal_token=str(uuid.uuid4()), portal_enabled=True)
    db_session.add(cust)
    await db_session.commit()
    r = await client.get(f"/api/v1/portal/{cust.portal_token}/projects/{project.id}/danh-gia")
    assert r.status_code == 403
