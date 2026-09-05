"""Phạm vi xem dự án theo bộ phận (05/09/2026).

User báo 2 việc: (1) form dự án không cho phân công Thiết kế / Báo giá–Thu mua /
Giám sát, chỉ có Kinh doanh; (2) mỗi bộ phận phải xem được dự án mình phụ trách,
trưởng phòng xem toàn bộ dự án của bộ phận mình — giống luồng đã làm cho KD.

Đo prod trước khi sửa: 113 dự án, sales_id đủ 113 nhưng pm_id/designer_id = 0,
và `list_projects` KHÔNG lọc gì — mọi tài khoản thấy toàn bộ.

Chốt với chủ dự án 05/09: trưởng phòng thật sự = DESIGN `leader`,
OPS `operation_leader`, PURCHASING `dutoan_thumua_leader`, SALES `leader`/
`sale_leader`. Chủ trì thiết kế (`design_leader`, `2d_leader`) KHÔNG tính.
Kế toán giữ quyền xem toàn bộ (đối chiếu công nợ/P&L).
"""

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.middleware.permissions import xoa_cache_quyen
from app.models.project import Project
from app.models.user import User
from tests.conftest import auth_header


@pytest.fixture(autouse=True)
def _sach_cache_quyen():
    xoa_cache_quyen()
    yield
    xoa_cache_quyen()


async def _tao_vai_tro(client, admin, role_key, role_name, department):
    resp = await client.post(
        "/api/v1/users/roles",
        json={"role_key": role_key, "role_name": role_name, "department": department,
              "permissions": {"canViewProjects": True, "canCreateProjects": True}},
        headers=auth_header(admin),
    )
    assert resp.status_code == 200, resp.text


async def _tao_user(client, db, admin, email, role, department):
    resp = await client.post(
        "/api/v1/users",
        json={"full_name": f"NV {email.split('@')[0]}", "email": email,
              "password": "secret123", "role": role, "department": department},
        headers=auth_header(admin),
    )
    assert resp.status_code == 200, resp.text
    uid = resp.json()["id"]
    return (await db.execute(select(User).where(User.id == uid))).scalar_one()


async def _tao_du_an(client, admin, code, **pic):
    resp = await client.post(
        "/api/v1/projects",
        json={"code": code, "name": f"Dự án {code}", "client_name": "KH test", **pic},
        headers=auth_header(admin),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _ma_du_an_thay_duoc(client, user) -> set[str]:
    resp = await client.get("/api/v1/projects?page_size=200", headers=auth_header(user))
    assert resp.status_code == 200, resp.text
    return {p["id"] for p in resp.json()["items"]}


@pytest_asyncio.fixture
async def bo_may(client, db_session, admin_user):
    """4 bộ phận, mỗi bộ phận 1 nhân viên + 1 trưởng phòng, mỗi người 1 dự án."""
    for rk, rn, dept in [
        ("thiet_ke", "Thiết kế", "DESIGN"),
        ("leader", "Trưởng phòng Thiết kế", "DESIGN"),
        ("design_leader", "Chủ trì thiết kế", "DESIGN"),
        ("giam_sat_thi_cong", "Giám sát thi công", "OPS"),
        ("operation_leader", "Trưởng phòng Vận hành", "OPS"),
        ("thu_mua", "Thu mua", "PURCHASING"),
        ("dutoan_thumua_leader", "Trưởng phòng Dự toán–Thu mua", "PURCHASING"),
    ]:
        if rk != "leader":  # 'leader' là vai trò hệ thống, không tạo custom
            await _tao_vai_tro(client, admin_user, rk, rn, dept)

    u = {}
    u["tk"] = await _tao_user(client, db_session, admin_user, "tk@test.com", "thiet_ke", "DESIGN")
    u["tk_tp"] = await _tao_user(client, db_session, admin_user, "tktp@test.com", "leader", "DESIGN")
    u["tk_chutri"] = await _tao_user(client, db_session, admin_user, "chutri@test.com", "design_leader", "DESIGN")
    u["gs"] = await _tao_user(client, db_session, admin_user, "gs@test.com", "giam_sat_thi_cong", "OPS")
    u["gs_tp"] = await _tao_user(client, db_session, admin_user, "gstp@test.com", "operation_leader", "OPS")
    u["tm"] = await _tao_user(client, db_session, admin_user, "tm@test.com", "thu_mua", "PURCHASING")
    u["tm_tp"] = await _tao_user(client, db_session, admin_user, "tmtp@test.com", "dutoan_thumua_leader", "PURCHASING")

    p = {}
    p["tk"] = await _tao_du_an(client, admin_user, "PRJ-TK", designer_id=u["tk"].id)
    p["gs"] = await _tao_du_an(client, admin_user, "PRJ-GS", pm_id=u["gs"].id)
    p["tm"] = await _tao_du_an(client, admin_user, "PRJ-TM", purchasing_id=u["tm"].id)
    p["trong"] = await _tao_du_an(client, admin_user, "PRJ-TRONG")
    return {"u": u, "p": p}


# ── Phần 1: form phải gán được PIC cả 4 bộ phận ─────────────────────────────

@pytest.mark.asyncio
async def test_tao_du_an_gan_duoc_ca_4_pic(client, db_session, admin_user, bo_may):
    u = bo_may["u"]
    pid = await _tao_du_an(
        client, admin_user, "PRJ-4PIC",
        pm_id=u["gs"].id, designer_id=u["tk"].id,
        purchasing_id=u["tm"].id, sales_id=admin_user.id,
    )
    pr = (await db_session.execute(select(Project).where(Project.id == pid))).scalar_one()
    assert pr.pm_id == u["gs"].id
    assert pr.designer_id == u["tk"].id
    assert pr.purchasing_id == u["tm"].id, "cột PIC Báo giá–Thu mua trước đây KHÔNG tồn tại"
    assert pr.sales_id == admin_user.id


@pytest.mark.asyncio
async def test_sua_du_an_doi_duoc_pic(client, db_session, admin_user, bo_may):
    u, p = bo_may["u"], bo_may["p"]
    resp = await client.put(
        f"/api/v1/projects/{p['trong']}",
        json={"designer_id": u["tk"].id, "purchasing_id": u["tm"].id},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["designer_id"] == u["tk"].id
    assert resp.json()["purchasing_id"] == u["tm"].id


# ── Phần 2: nhân viên chỉ thấy dự án MÌNH phụ trách ─────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("nguoi,du_an_cua_minh", [
    ("tk", "tk"), ("gs", "gs"), ("tm", "tm"),
])
async def test_nhan_vien_chi_thay_du_an_cua_minh(client, bo_may, nguoi, du_an_cua_minh):
    u, p = bo_may["u"], bo_may["p"]
    thay = await _ma_du_an_thay_duoc(client, u[nguoi])
    assert p[du_an_cua_minh] in thay, "phải thấy dự án mình phụ trách"
    khac = [v for k, v in p.items() if k not in (du_an_cua_minh, "trong")]
    assert not (set(khac) & thay), "KHÔNG được thấy dự án của bộ phận khác"
    assert p["trong"] in thay, "dự án CHƯA phân công thì vẫn hiện cho mọi người"


# ── Phần 2: trưởng phòng thấy TOÀN BỘ dự án của bộ phận mình ────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("tp,du_an_phong", [
    ("tk_tp", "tk"), ("gs_tp", "gs"), ("tm_tp", "tm"),
])
async def test_truong_phong_thay_du_an_ca_bo_phan(client, bo_may, tp, du_an_phong):
    u, p = bo_may["u"], bo_may["p"]
    thay = await _ma_du_an_thay_duoc(client, u[tp])
    assert p[du_an_phong] in thay, "trưởng phòng phải thấy dự án của quân mình"
    khac = [v for k, v in p.items() if k not in (du_an_phong, "trong")]
    assert not (set(khac) & thay), "nhưng KHÔNG thấy dự án bộ phận khác"


@pytest.mark.asyncio
async def test_chu_tri_thiet_ke_khong_phai_truong_phong(client, bo_may):
    """Chốt 05/09: design_leader là CHỦ TRÌ, chỉ thấy dự án mình phụ trách."""
    u, p = bo_may["u"], bo_may["p"]
    thay = await _ma_du_an_thay_duoc(client, u["tk_chutri"])
    assert p["tk"] not in thay, "chủ trì không được xem toàn phòng như trưởng phòng"


# ── Dự án CHƯA phân công thì không được biến mất khỏi màn hình ──────────────
# Đo prod ngay sau khi bật lọc: 113 dự án nhưng pm_id/designer_id/purchasing_id
# đều = 0 và 108/113 sales_id trỏ vào tài khoản admin → 50 nhân sự thấy màn hình
# trống. Chốt 05/09: chưa phân công thì giữ nguyên như cũ.

@pytest.mark.asyncio
async def test_du_an_chua_phan_cong_thi_ai_cung_thay(client, bo_may):
    u, p = bo_may["u"], bo_may["p"]
    for nguoi in ("tk", "gs", "tm", "tk_chutri"):
        thay = await _ma_du_an_thay_duoc(client, u[nguoi])
        assert p["trong"] in thay, f"{nguoi} phải thấy dự án chưa phân công"
    resp = await client.get(f"/api/v1/projects/{p['trong']}", headers=auth_header(u["tk"]))
    assert resp.status_code == 200, "và mở chi tiết được, không 403"


@pytest.mark.asyncio
async def test_pic_sai_bo_phan_van_tinh_la_chua_phan_cong(client, admin_user, bo_may):
    """Hình dạng dữ liệu THẬT trên prod: sales_id trỏ vào tài khoản admin (EXEC).

    Nếu tính «chưa phân công» theo NULL thì 108 dự án kiểu này biến mất khỏi màn
    hình cả công ty. Người trong cột phải ĐÚNG bộ phận mới tính là đã phân công.
    """
    u = bo_may["u"]
    pid = await _tao_du_an(client, admin_user, "PRJ-SALESADMIN", sales_id=admin_user.id)
    thay = await _ma_du_an_thay_duoc(client, u["tk"])
    assert pid in thay, "sales_id trỏ người ngoài phòng KD ⇒ vẫn coi là chưa phân công"


@pytest.mark.asyncio
async def test_gan_pic_xong_thi_nguoi_khac_het_thay(client, admin_user, bo_may):
    """Vừa gắn PIC là dự án tự động chỉ còn người phụ trách + trưởng phòng thấy."""
    u, p = bo_may["u"], bo_may["p"]
    assert p["trong"] in await _ma_du_an_thay_duoc(client, u["gs"])
    resp = await client.put(
        f"/api/v1/projects/{p['trong']}",
        json={"designer_id": u["tk"].id},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    assert p["trong"] not in await _ma_du_an_thay_duoc(client, u["gs"]), "giám sát hết thấy"
    assert p["trong"] in await _ma_du_an_thay_duoc(client, u["tk"]), "thiết kế được gắn thì thấy"
    assert p["trong"] in await _ma_du_an_thay_duoc(client, u["tk_tp"]), "trưởng phòng TK thấy"


# ── Kế toán / admin giữ toàn quyền xem ──────────────────────────────────────

@pytest.mark.asyncio
async def test_ke_toan_va_admin_xem_toan_bo(client, bo_may, admin_user, accountant_user):
    p = bo_may["p"]
    for nguoi in (admin_user, accountant_user):
        thay = await _ma_du_an_thay_duoc(client, nguoi)
        assert set(p.values()) <= thay, f"{nguoi.role} phải thấy toàn bộ dự án"


# ── Guard chi tiết phải khớp danh sách ──────────────────────────────────────

@pytest.mark.asyncio
async def test_mo_chi_tiet_du_an_ngoai_pham_vi_bi_chan(client, bo_may):
    u, p = bo_may["u"], bo_may["p"]
    resp = await client.get(f"/api/v1/projects/{p['gs']}", headers=auth_header(u["tk"]))
    assert resp.status_code == 403, "thiết kế không mở được dự án của giám sát"
    resp = await client.get(f"/api/v1/projects/{p['tk']}", headers=auth_header(u["tk"]))
    assert resp.status_code == 200, "nhưng dự án của chính mình thì mở được"


@pytest.mark.asyncio
async def test_duoc_giao_dau_viec_thi_xem_duoc_du_an(client, db_session, bo_may, admin_user):
    """Người không phải PIC nhưng được giao 1 đầu việc vẫn phải xem được dự án."""
    u, p = bo_may["u"], bo_may["p"]
    resp = await client.post(
        f"/api/v1/projects/{p['gs']}/tasks",
        json={"title": "Vẽ lại chi tiết", "stage": "design", "assigned_to": u["tk"].id},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    thay = await _ma_du_an_thay_duoc(client, u["tk"])
    assert p["gs"] in thay, "được giao việc trong dự án thì phải thấy dự án đó"
    resp = await client.get(f"/api/v1/projects/{p['gs']}", headers=auth_header(u["tk"]))
    assert resp.status_code == 200
