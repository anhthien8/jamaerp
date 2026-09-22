"""Bộ lọc theo kỳ cho Tổng quan (22/09/2026).

User báo: «Ở phần Tổng quan (Dashboard), hãy tạo bộ lọc để lọc dữ liệu theo từng
thời điểm. Hiện tại đang show toàn bộ dữ liệu của Quy trình - dự án.»

Ba điểm dễ sai nhất, mỗi điểm một test:
  1. CACHE — `/dashboard/executive` có `@cached` với khóa chỉ gồm `role`. Thêm
     tham số kỳ mà quên khóa thì mọi kỳ dùng chung một bản cache: đổi bộ lọc mà
     số không nhúc nhích.
  2. MÚI GIỜ — `created_at` lưu theo UTC, công ty làm theo giờ VN (UTC+7). Cắt
     ngày bằng mốc UTC thì lead tạo lúc 0h–7h sáng VN rơi sang ngày hôm trước.
     Quy ước «cắt ngày theo giờ VN» đã có từ module chấm công.
  3. BẢNG HIỆU SUẤT ĐỘI — điều kiện kỳ phải nằm trong ON của outerjoin; để ở
     WHERE thì đội không có lead nào trong kỳ bị loại khỏi bảng thay vì hiện 0.
"""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.api.dashboard import khoang_ngay
from app.cache import cache
from app.middleware.permissions import xoa_cache_quyen
from app.models.lead import Lead
from app.models.project import Project
from app.models.user import Team, User
from tests.conftest import auth_header

VN = timezone(timedelta(hours=7))


@pytest.fixture(autouse=True)
def _sach():
    cache.clear_prefix("dashboard")
    xoa_cache_quyen()
    yield
    cache.clear_prefix("dashboard")
    xoa_cache_quyen()


async def _lead_vao_luc(db, admin, ten, luc_utc: datetime, **truong):
    lead = Lead(name=ten, phone="0901234567", assigned_to=admin.id,
                stage="new", priority="medium", **truong)
    db.add(lead)
    await db.flush()
    lead.created_at = luc_utc
    await db.flush()
    return lead


async def _du_an_vao_luc(db, ma, luc_utc: datetime, **truong):
    pr = Project(code=ma, name=f"Dự án {ma}", client_name="KH", status="active", **truong)
    db.add(pr)
    await db.flush()
    pr.created_at = luc_utc
    await db.flush()
    return pr


# ── Quy đổi ngày ────────────────────────────────────────────────────────────

def test_khoang_ngay_cat_theo_gio_vn():
    dau, het = khoang_ngay("2026-09-10", "2026-09-10")
    # 00:00 ngày 10/09 giờ VN = 17:00 ngày 09/09 UTC
    assert dau == datetime(2026, 9, 9, 17, 0, tzinfo=timezone.utc)
    # Mốc cuối là 00:00 ngày 11/09 giờ VN = 17:00 ngày 10/09 UTC (so sánh `<`)
    assert het == datetime(2026, 9, 10, 17, 0, tzinfo=timezone.utc)


def test_khoang_ngay_nhap_nguoc_thi_tu_dao():
    assert khoang_ngay("2026-09-22", "2026-09-01") == khoang_ngay("2026-09-01", "2026-09-22")


def test_khoang_ngay_de_trong_la_khong_loc():
    assert khoang_ngay(None, None) == (None, None)
    assert khoang_ngay("2026-09-01", None)[1] is None
    assert khoang_ngay(None, "2026-09-01")[0] is None


@pytest.mark.asyncio
async def test_ngay_sai_dinh_dang_bao_ro(client, admin_user):
    resp = await client.get("/api/v1/dashboard/executive?tu=22-09-2026",
                            headers=auth_header(admin_user))
    assert resp.status_code == 400, resp.text
    assert "YYYY-MM-DD" in resp.json()["detail"]


# ── Lọc thật trên số liệu ───────────────────────────────────────────────────

@pytest_asyncio.fixture
async def du_lieu(db_session, admin_user):
    """3 lead + 3 dự án ở 3 mốc: tháng trước, hôm nay, và 0h30 sáng nay giờ VN."""
    hom_nay_vn = datetime.now(VN)
    sang_som_vn = hom_nay_vn.replace(hour=0, minute=30, second=0, microsecond=0)
    thang_truoc = hom_nay_vn - timedelta(days=45)

    await _lead_vao_luc(db_session, admin_user, "Lead cũ",
                        thang_truoc.astimezone(timezone.utc), estimated_budget=100_000_000)
    await _lead_vao_luc(db_session, admin_user, "Lead hôm nay",
                        hom_nay_vn.astimezone(timezone.utc), estimated_budget=200_000_000)
    await _lead_vao_luc(db_session, admin_user, "Lead 0h30 sáng nay",
                        sang_som_vn.astimezone(timezone.utc), estimated_budget=300_000_000)

    await _du_an_vao_luc(db_session, "PRJ-CU", thang_truoc.astimezone(timezone.utc),
                         total_value=1_000_000_000)
    await _du_an_vao_luc(db_session, "PRJ-NAY", hom_nay_vn.astimezone(timezone.utc),
                         total_value=2_000_000_000)
    return {"hom_nay": hom_nay_vn.strftime("%Y-%m-%d"),
            "thang_truoc": thang_truoc.strftime("%Y-%m-%d")}


async def _tong_quan(client, nguoi, **tham_so):
    duoi = "&".join(f"{k}={v}" for k, v in tham_so.items() if v)
    resp = await client.get(f"/api/v1/dashboard/executive{'?' + duoi if duoi else ''}",
                            headers=auth_header(nguoi))
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_khong_loc_thi_giu_nguyen_hanh_vi_cu(client, admin_user, du_lieu):
    """Mặc định «Mọi lúc» phải ra y như trước khi có bộ lọc."""
    kq = await _tong_quan(client, admin_user)
    assert kq["total_leads"] == 3
    assert kq["total_contracts"] == 2


@pytest.mark.asyncio
async def test_loc_hom_nay_chi_con_so_cua_hom_nay(client, admin_user, du_lieu):
    kq = await _tong_quan(client, admin_user, tu=du_lieu["hom_nay"], den=du_lieu["hom_nay"])
    assert kq["total_leads"] == 2, "phải gồm cả lead tạo lúc 0h30 sáng nay giờ VN"
    assert kq["total_contracts"] == 1
    assert kq["total_contract_value"] == 2_000_000_000
    assert kq["pipeline_value"] == 500_000_000, "200tr + 300tr của 2 lead hôm nay"


@pytest.mark.asyncio
async def test_lead_0h30_sang_khong_bi_tinh_sang_hom_truoc(client, admin_user, du_lieu):
    """Đúng cái bẫy múi giờ: 0h30 VN = 17h30 hôm trước theo UTC."""
    hom_qua = (datetime.now(VN) - timedelta(days=1)).strftime("%Y-%m-%d")
    kq = await _tong_quan(client, admin_user, tu=hom_qua, den=hom_qua)
    assert kq["total_leads"] == 0, "lead 0h30 sáng nay KHÔNG được rơi vào hôm qua"


@pytest.mark.asyncio
async def test_doi_bo_loc_thi_so_phai_doi_theo(client, admin_user, du_lieu):
    """Cache keyed theo role — thiếu kỳ trong khóa là đổi bộ lọc mà số không đổi."""
    tat_ca = await _tong_quan(client, admin_user)
    chi_hom_nay = await _tong_quan(client, admin_user,
                                   tu=du_lieu["hom_nay"], den=du_lieu["hom_nay"])
    lai_tat_ca = await _tong_quan(client, admin_user)
    assert tat_ca["total_leads"] == 3
    assert chi_hom_nay["total_leads"] == 2, "cache đang trả lại kết quả của kỳ trước"
    assert lai_tat_ca["total_leads"] == 3, "quay về «Mọi lúc» phải ra lại số cũ"


@pytest.mark.asyncio
async def test_phieu_quy_trinh_theo_ky(client, admin_user, du_lieu):
    kq = await _tong_quan(client, admin_user, tu=du_lieu["hom_nay"], den=du_lieu["hom_nay"])
    assert sum(kq["stage_funnel"].values()) == 2


@pytest.mark.asyncio
async def test_doi_khong_co_lead_trong_ky_van_hien_trong_bang(
    client, db_session, admin_user, du_lieu
):
    """Điều kiện kỳ phải ở ON của outerjoin: đội 0 lead vẫn phải có mặt."""
    db_session.add(Team(name="Đội KD Trống", code="KDT", department="SALES"))
    await db_session.flush()
    kq = await _tong_quan(client, admin_user, tu=du_lieu["hom_nay"], den=du_lieu["hom_nay"])
    ten_doi = {t["team"] for t in kq["team_performance"]}
    assert "Đội KD Trống" in ten_doi, "đội không có lead trong kỳ bị loại khỏi bảng"
    trong = next(t for t in kq["team_performance"] if t["team"] == "Đội KD Trống")
    assert trong["total_leads"] == 0


# ── Tổng quan cá nhân ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tong_quan_ca_nhan_cung_loc_theo_ky(client, admin_user, du_lieu, sales_user):
    resp = await client.get("/api/v1/dashboard/personal", headers=auth_header(admin_user))
    assert resp.status_code == 200, resp.text
    tat_ca = resp.json()["total_active_leads"]

    resp = await client.get(
        f"/api/v1/dashboard/personal?tu={du_lieu['hom_nay']}&den={du_lieu['hom_nay']}",
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["total_active_leads"] < tat_ca, "lọc kỳ phải thu hẹp số lead"


@pytest.mark.asyncio
async def test_kpi_tuan_khong_doi_theo_bo_loc(client, admin_user, du_lieu):
    """«KPI tuần này» là chỉ tiêu của tuần hiện tại — đổi theo kỳ là sai tên gọi."""
    a = await client.get("/api/v1/dashboard/personal", headers=auth_header(admin_user))
    b = await client.get(
        f"/api/v1/dashboard/personal?tu={du_lieu['thang_truoc']}&den={du_lieu['thang_truoc']}",
        headers=auth_header(admin_user),
    )
    assert a.json()["weekly_kpis"] == b.json()["weekly_kpis"]
