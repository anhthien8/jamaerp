"""Lương từng người + hoa hồng theo JD (24/10/2026).

Dữ liệu trong test là giả — không dùng tên/lương thật của nhân sự công ty.
"""

import io
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract
from app.models.employee_profile import EmployeeProfile
from app.models.payroll import Commission
from app.models.project import Project
from app.models.user import User
from app.services.attendance_service import period_of, vn_today
from app.services.hoa_hong import loai_hop_dong

from tests.conftest import auth_header, _uid


def _user(role: str, dept: str, ten: str) -> User:
    return User(
        id=_uid(), full_name=ten, email=f"{_uid()[:8]}@test.com", password_hash="x",
        role=role, department=dept, is_active=True,
    )


@pytest_asyncio.fixture
async def doi(db_session: AsyncSession) -> dict[str, User]:
    """Đủ người cho một dự án: sale, TP KD, thiết kế (chủ trì), TP TK, thu mua,
    TP báo giá, giám sát, TP giám sát."""
    d = {
        "sale": _user("data_entry", "SALES", "Sale Giả"),
        "tp_kd": _user("leader", "SALES", "TP KD Giả"),
        "tk": _user("design_leader", "DESIGN", "Chủ Trì Giả"),
        "tp_tk": _user("leader", "DESIGN", "TP TK Giả"),
        "tm": _user("dutoan_thumua", "PURCHASING", "Thu Mua Giả"),
        "tp_bg": _user("dutoan_thumua_leader", "PURCHASING", "TP BG Giả"),
        "gs": _user("operation", "OPS", "Giám Sát Giả"),
        "tp_gs": _user("operation_leader", "OPS", "TP GS Giả"),
    }
    db_session.add_all(d.values())
    await db_session.commit()
    return d


async def _du_an_va_hd(db: AsyncSession, doi: dict, *, kind: str | None = "thi_cong",
                       khach_rieng: bool = False, title: str = "HĐ thi công nhà phố",
                       status: str = "signed") -> Contract:
    p = Project(
        id=_uid(), code=f"JMH-{_uid()[:4]}", name="Nhà giả", client_name="Khách giả",
        stage="construction", status="active", total_value=1_000_000_000, spent=0, progress=0,
        sales_id=doi["sale"].id, designer_id=doi["tk"].id, purchasing_id=doi["tm"].id,
        pm_id=doi["gs"].id, khach_rieng=khach_rieng,
    )
    c = Contract(
        id=_uid(), code=f"HD-{_uid()[:6]}", project_id=p.id, title=title, status=status,
        total_value=1_000_000_000, contract_kind=kind,
        payment_terms={"installments": [
            {"name": "Đợt 1", "percentage": 25, "milestone": "signing", "status": "pending"},
            {"name": "Đợt 2", "percentage": 25, "milestone": "rough_complete", "status": "pending"},
            {"name": "Đợt 3", "percentage": 25, "milestone": "interior_complete", "status": "pending"},
            {"name": "Đợt 4", "percentage": 25, "milestone": "handover", "status": "pending"},
        ]},
    )
    db.add_all([p, c])
    await db.commit()
    return c


async def _hh(db: AsyncSession, contract_id: str) -> list[Commission]:
    # populate_existing thay expire_all: không làm hết hạn các User trong fixture
    return (await db.execute(
        select(Commission).where(Commission.contract_id == contract_id)
        .execution_options(populate_existing=True)
    )).scalars().all()


def _cua(rows, user: User, loai: str) -> list[Commission]:
    return [c for c in rows if c.user_id == user.id and c.type == loai]


async def _thu(client, kt: User, c: Contract, idx: int, status: str = "paid", paid_date: str = "2026-10-05"):
    r = await client.put(
        f"/api/v1/contracts/{c.id}/payments/{idx}",
        json={"status": status, "paid_date": paid_date}, headers=auth_header(kt),
    )
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
class TestHoaHongSale:
    async def test_sale_1pt_moi_dot_va_tp_kd_0_2pt(self, client, db_session, accountant_user, doi):
        c = await _du_an_va_hd(db_session, doi)
        await _thu(client, accountant_user, c, 0)
        rows = await _hh(db_session, c.id)
        sale = _cua(rows, doi["sale"], "hh_sale")
        assert len(sale) == 1
        assert sale[0].commission_amount == 2_500_000  # 1% × 250tr
        assert sale[0].period == "2026-10" and sale[0].status == "pending"
        tp = _cua(rows, doi["tp_kd"], "hh_tp_kd")
        assert tp[0].commission_amount == 500_000  # 0,2% × 250tr

    async def test_khach_rieng_2pt(self, client, db_session, accountant_user, doi):
        c = await _du_an_va_hd(db_session, doi, khach_rieng=True)
        await _thu(client, accountant_user, c, 0)
        sale = _cua(await _hh(db_session, c.id), doi["sale"], "hh_sale")
        assert sale[0].commission_amount == 5_000_000

    async def test_tich_lai_khong_nhan_doi(self, client, db_session, accountant_user, doi):
        c = await _du_an_va_hd(db_session, doi)
        await _thu(client, accountant_user, c, 0)
        await _thu(client, accountant_user, c, 0)
        assert len(_cua(await _hh(db_session, c.id), doi["sale"], "hh_sale")) == 1

    async def test_bo_tich_go_dong_chua_duyet(self, client, db_session, accountant_user, doi):
        c = await _du_an_va_hd(db_session, doi)
        await _thu(client, accountant_user, c, 0)
        await _thu(client, accountant_user, c, 0, status="pending")
        assert await _hh(db_session, c.id) == []

    async def test_admin_lam_sale_khong_co_hoa_hong(self, client, db_session, accountant_user, admin_user, doi):
        c = await _du_an_va_hd(db_session, doi)
        p = await db_session.get(Project, c.project_id)
        p.sales_id = admin_user.id
        await db_session.commit()
        await _thu(client, accountant_user, c, 0)
        rows = await _hh(db_session, c.id)
        assert not [r for r in rows if r.type in ("hh_sale", "hh_tp_kd")]


@pytest.mark.asyncio
class TestHoaHongThietKe:
    async def test_cho_dot_2_moi_mo(self, client, db_session, accountant_user, doi):
        c = await _du_an_va_hd(db_session, doi)
        await _thu(client, accountant_user, c, 0)
        tk = _cua(await _hh(db_session, c.id), doi["tk"], "hh_thiet_ke")
        assert tk[0].status == "cho_moc" and tk[0].period is None
        assert tk[0].commission_amount == 1_250_000  # chủ trì 0,5% × 250tr

        await _thu(client, accountant_user, c, 1, paid_date="2026-11-03")
        rows = await _hh(db_session, c.id)
        tk = _cua(rows, doi["tk"], "hh_thiet_ke")
        assert len(tk) == 2 and all(x.status == "pending" and x.period == "2026-11" for x in tk)
        assert all(x.period == "2026-11" for x in _cua(rows, doi["tp_tk"], "hh_tp_thiet_ke"))

    async def test_dot_3_cho_nghiem_thu(self, client, db_session, accountant_user, admin_user, doi):
        c = await _du_an_va_hd(db_session, doi)
        for i in range(3):
            await _thu(client, accountant_user, c, i)
        dot3 = [x for x in _cua(await _hh(db_session, c.id), doi["tk"], "hh_thiet_ke") if x.installment_idx == 2]
        assert dot3[0].status == "cho_moc"

        r = await client.put(f"/api/v1/contracts/{c.id}", json={"status": "completed"},
                             headers=auth_header(admin_user))
        assert r.status_code == 200, r.text
        rows = await _hh(db_session, c.id)
        assert not [x for x in rows if x.status == "cho_moc"]

    async def test_hd_thiet_ke_khong_tinh_thiet_ke(self, client, db_session, accountant_user, doi):
        c = await _du_an_va_hd(db_session, doi, kind="thiet_ke")
        await _thu(client, accountant_user, c, 1)
        rows = await _hh(db_session, c.id)
        assert not [x for x in rows if x.type in ("hh_thiet_ke", "hh_tp_thiet_ke")]
        assert _cua(rows, doi["sale"], "hh_sale")  # sale vẫn ăn trên HĐ thiết kế

    async def test_doan_loai_theo_tieu_de(self):
        c = Contract(code="X", title="HỢP ĐỒNG THIẾT KẾ NỘI THẤT 2026", contract_kind=None)
        assert loai_hop_dong(c) == "thiet_ke"
        c.title = "HỢP ĐỒNG THI CÔNG CẢI TẠO"
        assert loai_hop_dong(c) == "thi_cong"

    async def test_cho_moc_khong_duyet_duoc(self, client, db_session, accountant_user, doi):
        c = await _du_an_va_hd(db_session, doi)
        await _thu(client, accountant_user, c, 0)
        tk = _cua(await _hh(db_session, c.id), doi["tk"], "hh_thiet_ke")[0]
        r = await client.put(f"/api/v1/accounting/commissions/{tk.id}", json={"status": "approved"},
                             headers=auth_header(accountant_user))
        assert r.status_code == 409


@pytest.mark.asyncio
class TestHoaHongKyVaNghiemThu:
    async def test_ky_va_nghiem_thu(self, client, db_session, admin_user, doi):
        c = await _du_an_va_hd(db_session, doi, status="draft")
        r = await client.put(f"/api/v1/contracts/{c.id}", json={"status": "signed"}, headers=auth_header(admin_user))
        assert r.status_code == 200, r.text
        rows = await _hh(db_session, c.id)
        tm = _cua(rows, doi["tm"], "hh_thu_mua")
        assert tm[0].commission_amount == 500_000  # 0,1% × 1 tỷ × 50%
        assert tm[0].period != period_of(vn_today())  # JD: kỳ lương tiếp theo
        assert _cua(rows, doi["tp_bg"], "hh_tp_bao_gia")[0].commission_amount == 1_000_000
        assert not _cua(rows, doi["gs"], "hh_giam_sat")
        # Bản cũ cộng cứng 3%/2% cho sale lúc ký — không còn
        assert not [x for x in rows if x.type in ("design_commission", "construction_commission")]

        r = await client.put(f"/api/v1/contracts/{c.id}", json={"status": "completed"}, headers=auth_header(admin_user))
        assert r.status_code == 200, r.text
        rows = await _hh(db_session, c.id)
        assert len(_cua(rows, doi["tm"], "hh_thu_mua")) == 2
        assert _cua(rows, doi["gs"], "hh_giam_sat")[0].commission_amount == 5_000_000
        assert _cua(rows, doi["tp_gs"], "hh_tp_giam_sat")[0].commission_amount == 2_000_000

    async def test_chon_loai_hd_khi_tao(self, client, db_session, admin_user, doi):
        c = await _du_an_va_hd(db_session, doi)
        r = await client.post("/api/v1/contracts", json={
            "code": f"HD-{_uid()[:5]}", "project_id": c.project_id, "title": "HĐ",
            "total_value": 100, "contract_kind": "thiet_ke",
        }, headers=auth_header(admin_user))
        assert r.status_code == 200, r.text
        assert r.json()["contract_kind"] == "thiet_ke"


@pytest.mark.asyncio
class TestKhachRieng:
    async def test_chi_tp_kd_va_bgd_doi_duoc(self, client, db_session, admin_user, doi):
        c = await _du_an_va_hd(db_session, doi)
        url = f"/api/v1/projects/{c.project_id}"
        r = await client.put(url, json={"khach_rieng": True}, headers=auth_header(doi["sale"]))
        assert r.status_code == 403
        r = await client.put(url, json={"khach_rieng": True}, headers=auth_header(doi["tp_kd"]))
        assert r.status_code == 200, r.text
        assert r.json()["khach_rieng"] is True
        r = await client.put(url, json={"khach_rieng": False}, headers=auth_header(admin_user))
        assert r.status_code == 200 and r.json()["khach_rieng"] is False


@pytest.mark.asyncio
class TestLuongTungNguoi:
    async def test_bang_luong_lay_luong_hd_va_bhxh(self, client, db_session, accountant_user, doi):
        u = doi["gs"]
        r = await client.put(f"/api/v1/hr/employees/{u.id}/profile", json={
            "contract_salary": 12_000_000, "insurance_salary": 6_000_000, "allowance_monthly": 1_500_000,
        }, headers=auth_header(accountant_user))
        assert r.status_code == 200, r.text
        period = "2031-01"
        r = await client.post(f"/api/v1/payroll/generate?period={period}", headers=auth_header(accountant_user))
        assert r.status_code == 200, r.text
        rows = (await client.get(f"/api/v1/payroll?period={period}", headers=auth_header(accountant_user))).json()["items"]
        row = next(x for x in rows if x["user_id"] == u.id)
        assert row["base_salary"] == 12_000_000
        assert row["allowance"] == 1_500_000
        assert row["bhxh_employee"] == 630_000  # 10,5% × 6tr (mức tham gia BHXH, không phải 12tr)

    async def test_sua_ho_so_khong_xoa_luong(self, client, db_session, accountant_user, doi):
        u = doi["sale"]
        h = auth_header(accountant_user)
        await client.put(f"/api/v1/hr/employees/{u.id}/profile", json={"contract_salary": 8_000_000}, headers=h)
        await client.put(f"/api/v1/hr/employees/{u.id}/profile", json={"address": "Đâu đó"}, headers=h)
        prof = (await client.get(f"/api/v1/hr/employees/{u.id}/profile", headers=h)).json()["profile"]
        assert prof["contract_salary"] == 8_000_000 and prof["address"] == "Đâu đó"

    async def test_sale_khong_sua_luong_minh(self, client, doi):
        u = doi["sale"]
        r = await client.put(f"/api/v1/hr/employees/{u.id}/profile", json={"contract_salary": 99_000_000},
                             headers=auth_header(u))
        assert r.status_code == 403


def _xlsx(rows: list[list]) -> bytes:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["DANH SÁCH NHÂN SỰ"])
    ws.append(["STT", "HỌ VÀ TÊN", "CHỨC DANH", "PHÒNG BAN", "NĂM SINH", "CCCD", "SỐ ĐIỆN THOẠI",
               "MÃ SỐ THUẾ", "MÃ SỐ BHXH", "NGÀY ĐÓNG BHXH", "NGÀY KÝ HĐLĐ", "THỜI HẠN HĐLĐ",
               "MỨC LƯƠNG KÝ HĐLĐ", "MỨC LƯƠNG THAM GIA BHXH"])
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.mark.asyncio
class TestNhapExcel:
    async def _gui(self, client, user, data: bytes, apply: bool):
        return await client.post(
            "/api/v1/hr/employees/import-excel",
            files={"file": ("ns.xlsx", data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"apply": "true" if apply else "false"},
            headers=auth_header(user),
        )

    async def test_xem_truoc_roi_ap_dung(self, client, db_session, accountant_user, doi):
        data = _xlsx([
            [1, "sale giả", "NVKD", "KINH DOANH", "01/02/1995", "001095000000", "0900000000",
             "8000000000", "", "03/2025", "01/03/2025, 01/03/2026", "1 năm", 8_000_000, 5_000_000],
            [2, "Người Không Có", "NV", "M&E", "", "", "", "", "", "", "", "1 năm", 9_000_000, None],
        ])
        r = await self._gui(client, accountant_user, data, apply=False)
        assert r.status_code == 200, r.text
        kq = r.json()
        assert kq["tong_dong"] == 2 and len(kq["khop"]) == 1
        assert kq["khong_khop"][0]["ten"] == "Người Không Có"
        assert "Lương HĐ" in kq["khop"][0]["o_thay_doi"]
        uid = doi["sale"].id
        prof = (await db_session.execute(select(EmployeeProfile).where(EmployeeProfile.user_id == uid)
                                         .execution_options(populate_existing=True))).scalar_one_or_none()
        assert prof is None  # xem trước không ghi

        r = await self._gui(client, accountant_user, data, apply=True)
        assert r.status_code == 200 and r.json()["da_ap_dung"]
        prof = (await db_session.execute(select(EmployeeProfile).where(EmployeeProfile.user_id == uid)
                                         .execution_options(populate_existing=True))).scalar_one()
        assert prof.contract_salary == 8_000_000 and prof.insurance_salary == 5_000_000
        assert prof.contract_signed_date == date(2026, 3, 1)  # ký lại → lấy lần cuối
        assert prof.contract_end_date == date(2027, 2, 28)
        assert prof.contract_type == "fixed_1y"
        assert prof.insurance_start_date == date(2025, 3, 1)
        assert prof.date_of_birth == date(1995, 2, 1)

        # Nhập lại: không còn gì đổi
        r = await self._gui(client, accountant_user, data, apply=False)
        assert r.json()["se_cap_nhat"] == 0

    async def test_chi_hr_duoc_nhap(self, client, doi):
        r = await self._gui(client, doi["tp_kd"], _xlsx([]), apply=False)
        assert r.status_code == 403

    async def test_sai_mau(self, client, accountant_user):
        r = await self._gui(client, accountant_user, b"khong phai excel", apply=False)
        assert r.status_code == 422
