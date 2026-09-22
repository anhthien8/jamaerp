"""Ba tầng phạm vi dữ liệu + nguyên tắc «chỉ KD và BGĐ được thấy lead» (22/09/2026).

Chủ dự án chốt 2 việc:
  1. Trưởng phòng (mọi bộ phận) xem toàn bộ dữ liệu nhân sự bộ phận mình;
     trưởng nhóm KD — và Chủ trì với bên Thiết kế — xem dữ liệu nhóm mình;
     nhân viên xem của mình. Kiêm nhiệm thì lấy quyền CAO NHẤT.
  2. «Trừ bộ phận kinh doanh và nhân sự thuộc ban giám đốc, không ai được
     quyền thấy lead.»

Lỗi gốc user báo: tài khoản Nguyễn Văn Toàn (Trưởng phòng KD) không xem được
lead của nhân sự. Đo prod 22/09: `is_team_lead()` xếp `leader` NGANG
`sale_leader` rồi lọc theo `team_id`, nên anh Toàn chỉ thấy 141 lead của Đội KD
Văn Toàn thay vì 467 lead của cả 3 đội trong phòng.

Đo prod cùng ngày cho vế 2: vai `operation_leader` (Trưởng phòng Giám sát) đang
được BẬT sẵn «Xem Leads» trong system_settings — mà `operation_leader` là trưởng
phòng nên tầng 'phong_ban' sẽ cho họ thấy lead của cả phòng Giám sát.
"""

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.middleware.permissions import xoa_cache_quyen
from app.models.user import User
from tests.conftest import auth_header


@pytest.fixture(autouse=True)
def _sach_cache_quyen():
    xoa_cache_quyen()
    yield
    xoa_cache_quyen()


async def _tao_vai_tro(client, admin, role_key, role_name, department, **quyen):
    resp = await client.post(
        "/api/v1/users/roles",
        json={"role_key": role_key, "role_name": role_name, "department": department,
              "permissions": {"canViewProjects": True, "canCreateProjects": True, **quyen}},
        headers=auth_header(admin),
    )
    assert resp.status_code == 200, resp.text


async def _tao_user(client, db, admin, email, role, department, team_id=None):
    resp = await client.post(
        "/api/v1/users",
        json={"full_name": f"NV {email.split('@')[0]}", "email": email,
              "password": "secret123", "role": role, "department": department},
        headers=auth_header(admin),
    )
    assert resp.status_code == 200, resp.text
    uid = resp.json()["id"]
    if team_id:
        r = await client.put(f"/api/v1/users/{uid}", json={"team_id": team_id},
                             headers=auth_header(admin))
        assert r.status_code == 200, r.text
    return (await db.execute(select(User).where(User.id == uid))).scalar_one()


async def _tao_doi(client, admin, name, code):
    resp = await client.post("/api/v1/users/teams", json={"name": name, "code": code},
                             headers=auth_header(admin))
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _tao_lead(client, admin, ten, nguoi_id):
    resp = await client.post(
        "/api/v1/leads",
        json={"name": ten, "phone": "0901234567", "assigned_to": nguoi_id},
        headers=auth_header(admin),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _lead_thay_duoc(client, nguoi) -> set[str]:
    resp = await client.get("/api/v1/leads?page_size=200", headers=auth_header(nguoi))
    assert resp.status_code == 200, resp.text
    return {l["id"] for l in resp.json()["items"]}


@pytest_asyncio.fixture
async def phong_kd(client, db_session, admin_user):
    """Phòng KD: 1 trưởng phòng + 2 đội, mỗi đội 1 trưởng nhóm + 1 sale."""
    await _tao_vai_tro(client, admin_user, "sale_leader", "Trưởng nhóm KD", "SALES",
                       canViewLeads=True)
    doi_a = await _tao_doi(client, admin_user, "Đội KD A", "KDA")
    doi_b = await _tao_doi(client, admin_user, "Đội KD B", "KDB")

    u = {}
    # Trưởng phòng KD cố ý ĐƯỢC xếp vào đội A: kiểm luật «kiêm nhiệm thì lấy
    # quyền cao nhất» — phải thấy cả đội B chứ không bị bó trong đội A.
    u["tp"] = await _tao_user(client, db_session, admin_user, "tpkd@test.com", "leader", "SALES", doi_a)
    u["tn_a"] = await _tao_user(client, db_session, admin_user, "tna@test.com", "sale_leader", "SALES", doi_a)
    u["sale_a"] = await _tao_user(client, db_session, admin_user, "salea@test.com", "data_entry", "SALES", doi_a)
    u["tn_b"] = await _tao_user(client, db_session, admin_user, "tnb@test.com", "sale_leader", "SALES", doi_b)
    u["sale_b"] = await _tao_user(client, db_session, admin_user, "saleb@test.com", "data_entry", "SALES", doi_b)

    lead = {}
    for khoa in ("sale_a", "sale_b", "tn_a", "tn_b"):
        lead[khoa] = await _tao_lead(client, admin_user, f"KH {khoa}", u[khoa].id)
    return {"u": u, "lead": lead, "doi_a": doi_a, "doi_b": doi_b}


# ── Tầng 1: trưởng phòng xem toàn bộ bộ phận ────────────────────────────────

@pytest.mark.asyncio
async def test_truong_phong_kd_thay_lead_ca_bo_phan(client, phong_kd):
    """Đúng lỗi user báo: trưởng phòng phải thấy lead của MỌI đội trong phòng."""
    u, lead = phong_kd["u"], phong_kd["lead"]
    thay = await _lead_thay_duoc(client, u["tp"])
    assert set(lead.values()) <= thay, "trưởng phòng KD phải thấy lead của cả 2 đội"


@pytest.mark.asyncio
async def test_kiem_nhiem_thi_lay_quyen_cao_nhat(client, phong_kd):
    """Trưởng phòng ĐANG ở đội A vẫn phải thấy lead đội B (không bị bó theo đội)."""
    u, lead = phong_kd["u"], phong_kd["lead"]
    assert u["tp"].team_id == phong_kd["doi_a"], "tiền đề: trưởng phòng có xếp đội"
    thay = await _lead_thay_duoc(client, u["tp"])
    assert lead["sale_b"] in thay, "kiêm nhiệm ⇒ ưu tiên tầng trưởng phòng"


@pytest.mark.asyncio
async def test_truong_phong_thay_du_sdt_ca_bo_phan(client, phong_kd):
    u, lead = phong_kd["u"], phong_kd["lead"]
    resp = await client.get(f"/api/v1/leads/{lead['sale_b']}", headers=auth_header(u["tp"]))
    assert resp.status_code == 200, resp.text
    assert "***" not in (resp.json()["phone"] or ""), "trưởng phòng cần đủ SĐT để kiểm tra"


# ── Tầng 2: trưởng nhóm chỉ xem nhóm mình ───────────────────────────────────

@pytest.mark.asyncio
async def test_truong_nhom_chi_thay_lead_nhom_minh(client, phong_kd):
    u, lead = phong_kd["u"], phong_kd["lead"]
    thay = await _lead_thay_duoc(client, u["tn_a"])
    assert {lead["sale_a"], lead["tn_a"]} <= thay, "phải thấy lead của quân mình"
    assert lead["sale_b"] not in thay, "KHÔNG được thấy lead đội khác"


@pytest.mark.asyncio
async def test_truong_nhom_mo_lead_doi_khac_bi_chan(client, phong_kd):
    """Guard chi tiết phải khớp danh sách — không có cảnh «thấy mà mở ra 403»."""
    u, lead = phong_kd["u"], phong_kd["lead"]
    resp = await client.get(f"/api/v1/leads/{lead['sale_b']}", headers=auth_header(u["tn_a"]))
    assert resp.status_code == 403
    resp = await client.get(f"/api/v1/leads/{lead['sale_a']}", headers=auth_header(u["tn_a"]))
    assert resp.status_code == 200


# ── Tầng 3: nhân viên chỉ xem của mình ──────────────────────────────────────

@pytest.mark.asyncio
async def test_nhan_vien_chi_thay_lead_cua_minh(client, phong_kd):
    u, lead = phong_kd["u"], phong_kd["lead"]
    thay = await _lead_thay_duoc(client, u["sale_a"])
    assert thay == {lead["sale_a"]}, "sale chỉ thấy đúng lead gắn cho mình"


# ── Nguyên tắc 22/09: ngoài KD và BGĐ thì KHÔNG ai thấy lead ────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("role_key,ten,dept", [
    ("thiet_ke", "Thiết kế", "DESIGN"),
    ("thu_mua", "Thu mua", "PURCHASING"),
    ("giam_sat_thi_cong", "Giám sát thi công", "OPS"),
])
async def test_bo_phan_khac_khong_thay_lead_du_da_tich_quyen(
    client, db_session, admin_user, phong_kd, role_key, ten, dept
):
    """Tích «Xem Leads» cho bộ phận khác cũng KHÔNG lọt — chặn cứng theo bộ phận."""
    await _tao_vai_tro(client, admin_user, role_key, ten, dept, canViewLeads=True)
    nguoi = await _tao_user(client, db_session, admin_user, f"{role_key}@test.com", role_key, dept)
    assert await _lead_thay_duoc(client, nguoi) == set(), f"{dept} không được thấy lead nào"


@pytest.mark.asyncio
async def test_truong_phong_bo_phan_khac_cung_khong_thay_lead(
    client, db_session, admin_user, phong_kd
):
    """Chỗ dễ lọt nhất: `operation_leader` là TRƯỞNG PHÒNG nên tầng 'phong_ban'
    sẽ cho họ thấy lead của cả phòng Giám sát nếu không chặn theo bộ phận.
    Trên prod vai này đang được bật sẵn «Xem Leads»."""
    await _tao_vai_tro(client, admin_user, "operation_leader", "Trưởng phòng Vận hành",
                       "OPS", canViewLeads=True, canViewHR=True)
    tp_ops = await _tao_user(client, db_session, admin_user, "tpops@test.com",
                             "operation_leader", "OPS")
    assert await _lead_thay_duoc(client, tp_ops) == set()
    # Và mở thẳng chi tiết một lead cũng phải bị chặn
    resp = await client.get(f"/api/v1/leads/{phong_kd['lead']['sale_a']}",
                            headers=auth_header(tp_ops))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_ke_toan_khong_thay_lead(client, phong_kd, accountant_user):
    assert await _lead_thay_duoc(client, accountant_user) == set()


@pytest.mark.asyncio
async def test_ngoai_kd_khong_tao_duoc_lead(client, db_session, admin_user):
    await _tao_vai_tro(client, admin_user, "thiet_ke", "Thiết kế", "DESIGN", canViewLeads=True)
    nguoi = await _tao_user(client, db_session, admin_user, "tk2@test.com", "thiet_ke", "DESIGN")
    resp = await client.post("/api/v1/leads", json={"name": "KH lậu", "phone": "0909999999"},
                             headers=auth_header(nguoi))
    assert resp.status_code == 403, "bộ phận ngoài KD không được tạo lead"


@pytest.mark.asyncio
async def test_ngoai_kd_khong_xuat_duoc_csv(client, db_session, admin_user):
    await _tao_vai_tro(client, admin_user, "thu_mua", "Thu mua", "PURCHASING", canViewLeads=True)
    nguoi = await _tao_user(client, db_session, admin_user, "tm2@test.com", "thu_mua", "PURCHASING")
    resp = await client.get("/api/v1/leads/export", headers=auth_header(nguoi))
    assert resp.status_code == 403


# ── Các màn khác phải cùng một phạm vi với danh sách ────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("duong_dan", [
    "/api/v1/leads/pipeline/stats",
    "/api/v1/leads/pipeline/kanban",
])
async def test_thong_ke_va_kanban_cung_pham_vi(client, db_session, admin_user, phong_kd, duong_dan):
    """Thống kê/kanban từng chép tay bộ lọc riêng — nay dùng chung một hàm."""
    await _tao_vai_tro(client, admin_user, "thiet_ke", "Thiết kế", "DESIGN", canViewLeads=True)
    tk = await _tao_user(client, db_session, admin_user, "tk3@test.com", "thiet_ke", "DESIGN")
    resp = await client.get(duong_dan, headers=auth_header(tk))
    assert resp.status_code == 200, resp.text
    ket_qua = resp.json()
    if isinstance(ket_qua, dict):
        assert ket_qua.get("total_leads", 0) == 0, f"{duong_dan} vẫn lọt số liệu lead"
    else:
        assert all(c["count"] == 0 for c in ket_qua), f"{duong_dan} vẫn lọt lead"


@pytest.mark.asyncio
async def test_workload_truong_phong_gom_ca_bo_phan(client, phong_kd):
    u = phong_kd["u"]
    resp = await client.get("/api/v1/leads/workload", headers=auth_header(u["tp"]))
    assert resp.status_code == 200, resp.text
    ten = {r["user_id"] for r in resp.json()}
    assert {u["sale_a"].id, u["sale_b"].id} <= ten, "trưởng phòng thấy workload cả phòng"

    resp = await client.get("/api/v1/leads/workload", headers=auth_header(u["tn_a"]))
    ten_nhom = {r["user_id"] for r in resp.json()}
    assert u["sale_a"].id in ten_nhom
    assert u["sale_b"].id not in ten_nhom, "trưởng nhóm chỉ thấy workload nhóm mình"


# ── Dự án: tầng nhóm cho KD, chủ trì Thiết kế vẫn là «của mình» ─────────────

async def _tao_du_an(client, admin, code, **pic):
    resp = await client.post(
        "/api/v1/projects",
        json={"code": code, "name": f"Dự án {code}", "client_name": "KH test", **pic},
        headers=auth_header(admin),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _du_an_thay_duoc(client, nguoi) -> set[str]:
    resp = await client.get("/api/v1/projects?page_size=200", headers=auth_header(nguoi))
    assert resp.status_code == 200, resp.text
    return {p["id"] for p in resp.json()["items"]}


@pytest.mark.asyncio
async def test_truong_nhom_kd_thay_du_an_cua_nhom_minh(client, admin_user, phong_kd):
    u = phong_kd["u"]
    da_a = await _tao_du_an(client, admin_user, "PRJ-A", sales_id=u["sale_a"].id)
    da_b = await _tao_du_an(client, admin_user, "PRJ-B", sales_id=u["sale_b"].id)

    thay_tn_a = await _du_an_thay_duoc(client, u["tn_a"])
    assert da_a in thay_tn_a, "trưởng nhóm thấy dự án của quân mình"
    assert da_b not in thay_tn_a, "nhưng không thấy dự án đội khác"

    thay_tp = await _du_an_thay_duoc(client, u["tp"])
    assert {da_a, da_b} <= thay_tp, "trưởng phòng thấy dự án cả phòng"


@pytest.mark.asyncio
async def test_chu_tri_thiet_ke_chi_thay_du_an_minh_phu_trach(client, db_session, admin_user):
    """Chốt 22/09: Chủ trì là vai trưởng nhóm, NHƯNG phòng Thiết kế trên prod chỉ
    có đúng 1 team = cả phòng (16 người). Lọc theo team_id ở đó = mở bằng cả
    phòng, nên chủ trì lọc theo DỰ ÁN MÌNH PHỤ TRÁCH."""
    await _tao_vai_tro(client, admin_user, "design_leader", "Chủ trì thiết kế", "DESIGN")
    await _tao_vai_tro(client, admin_user, "thiet_ke", "Thiết kế", "DESIGN")
    phong_tk = await _tao_doi(client, admin_user, "Phòng Thiết Kế", "PTK")
    chu_tri = await _tao_user(client, db_session, admin_user, "chutri@test.com",
                              "design_leader", "DESIGN", phong_tk)
    nv_tk = await _tao_user(client, db_session, admin_user, "nvtk@test.com",
                            "thiet_ke", "DESIGN", phong_tk)

    da_minh = await _tao_du_an(client, admin_user, "PRJ-CT", designer_id=chu_tri.id)
    da_nguoi_khac = await _tao_du_an(client, admin_user, "PRJ-NV", designer_id=nv_tk.id)

    thay = await _du_an_thay_duoc(client, chu_tri)
    assert da_minh in thay
    assert da_nguoi_khac not in thay, "chủ trì KHÔNG được xem như trưởng phòng"


@pytest.mark.asyncio
async def test_truong_phong_thiet_ke_van_thay_ca_phong(client, db_session, admin_user):
    await _tao_vai_tro(client, admin_user, "thiet_ke", "Thiết kế", "DESIGN")
    phong_tk = await _tao_doi(client, admin_user, "Phòng Thiết Kế", "PTK")
    tp_tk = await _tao_user(client, db_session, admin_user, "tptk@test.com",
                            "leader", "DESIGN", phong_tk)
    nv_tk = await _tao_user(client, db_session, admin_user, "nvtk2@test.com",
                            "thiet_ke", "DESIGN", phong_tk)
    da = await _tao_du_an(client, admin_user, "PRJ-TK2", designer_id=nv_tk.id)
    assert da in await _du_an_thay_duoc(client, tp_tk)


# ── Trang Phân quyền không lưu được ô «Xem Leads» cho bộ phận ngoài KD ──────

@pytest.mark.asyncio
async def test_tao_vai_tro_ngoai_kd_thi_tat_quyen_lead(client, db_session, admin_user):
    """Tích «Xem Leads» cho vai trò bộ phận khác → lưu về TẮT, không để giao diện
    hiện một đằng mà trải nghiệm một nẻo (đúng ca `operation_leader` trên prod)."""
    resp = await client.post(
        "/api/v1/users/roles",
        json={"role_key": "ky_thuat", "role_name": "Kỹ thuật", "department": "OPS",
              "permissions": {"canViewLeads": True, "leadsScope": "team",
                              "canViewProjects": True}},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    luu = resp.json()["role"]["permissions"]
    assert luu["canViewLeads"] is False
    assert luu["leadsScope"] == "none"
    assert luu["canViewProjects"] is True, "các quyền khác giữ nguyên"


@pytest.mark.asyncio
async def test_vai_tro_kinh_doanh_van_bat_duoc_quyen_lead(client, admin_user):
    resp = await client.post(
        "/api/v1/users/roles",
        json={"role_key": "cskh2", "role_name": "Admin CSKH 2", "department": "SALES",
              "permissions": {"canViewLeads": True, "leadsScope": "all"}},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"]["permissions"]["canViewLeads"] is True


@pytest.mark.asyncio
async def test_sua_quyen_vai_tro_ngoai_kd_cung_bi_tat(client, db_session, admin_user):
    await _tao_vai_tro(client, admin_user, "thu_mua3", "Thu mua 3", "PURCHASING")
    resp = await client.put(
        "/api/v1/users/permissions/roles/thu_mua3",
        json={"permissions": {"canViewLeads": True}},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["permissions"]["canViewLeads"] is False


# ── Danh sách Nhân sự cũng theo 3 tầng ─────────────────────────────────────

async def _nhan_su_thay_duoc(client, nguoi) -> set[str]:
    resp = await client.get("/api/v1/users?page_size=200", headers=auth_header(nguoi))
    assert resp.status_code == 200, resp.text
    kq = resp.json()
    items = kq["items"] if isinstance(kq, dict) else kq
    return {u["id"] for u in items}


@pytest.mark.asyncio
async def test_truong_phong_thay_nhan_su_ca_bo_phan(client, db_session, admin_user, phong_kd):
    """«Trưởng phòng thấy toàn bộ dữ liệu của nhân sự của mình» — kể cả đội khác."""
    u = phong_kd["u"]
    thay = await _nhan_su_thay_duoc(client, u["tp"])
    assert {u["sale_a"].id, u["sale_b"].id, u["tn_a"].id, u["tn_b"].id} <= thay


@pytest.mark.asyncio
async def test_truong_phong_khong_thay_nhan_su_phong_khac(client, db_session, admin_user, phong_kd):
    await _tao_vai_tro(client, admin_user, "thiet_ke9", "Thiết kế 9", "DESIGN")
    nv_tk = await _tao_user(client, db_session, admin_user, "tk9@test.com", "thiet_ke9", "DESIGN")
    thay = await _nhan_su_thay_duoc(client, phong_kd["u"]["tp"])
    assert nv_tk.id not in thay, "trưởng phòng KD không xem hồ sơ nhân sự phòng Thiết kế"


@pytest.mark.asyncio
async def test_truong_nhom_chi_thay_nhan_su_nhom_minh(client, db_session, admin_user, phong_kd):
    """Trưởng nhóm CÓ «Xem Nhân sự» thì phạm vi là nhóm mình.

    Lưu ý: vai `sale_leader` trên prod đang KHÔNG bật «Xem Nhân sự» nên thực tế
    họ không vào được trang này — test dựng riêng một vai trưởng nhóm có bật, để
    khóa phần PHẠM VI chứ không phải phần được/không được vào.
    """
    # Bật «Xem Nhân sự» cho ĐÚNG vai `sale_leader` — tầng phạm vi tra theo
    # role_key (VAI_TRO_TRUONG_NHOM) nên không thay bằng role_key khác được.
    resp = await client.put(
        "/api/v1/users/permissions/roles/sale_leader",
        json={"permissions": {"canViewHR": True}}, headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    xoa_cache_quyen()
    thay = await _nhan_su_thay_duoc(client, phong_kd["u"]["tn_a"])
    assert phong_kd["u"]["sale_a"].id in thay
    assert phong_kd["u"]["sale_b"].id not in thay, "trưởng nhóm chỉ thấy quân đội mình"
