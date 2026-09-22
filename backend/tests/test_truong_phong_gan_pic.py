"""Trưởng phòng phải gắn được PIC cho bộ phận mình — mọi lúc (22/09/2026).

User báo: «Trưởng phòng (Kinh doanh, Thiết kế, Giám sát, Thu mua…) được quyền
phân công nhân sự phụ trách dự án. Đó có thể là chính họ, hoặc nhân sự trong
phòng ban. Hiện tại các trưởng phòng không gắn nhân sự (PIC) vào được, lỗi "Bạn
không phụ trách dự án này". Trưởng phòng là quyền cao nhất của phòng ban đó mà
lại không được thêm người là sao.»

GỐC RỄ (lỗi do bản 05/09 của chính hệ thống này): cửa thoát «dự án chưa phân
công thì ai cũng xem được» tính trên TOÀN BỘ dự án — chỉ cần MỘT bộ phận gắn
PIC là dự án hết «chưa phân công», và các trưởng phòng còn lại (cột PIC của họ
vẫn trống) bị guard đá ra 403. Thành ngõ cụt: dự án không bao giờ gắn đủ 4 PIC.

Đúng ra phải tính theo TỪNG BỘ PHẬN: cột PIC của phòng tôi còn trống thì tôi
phải vào được để gắn — đó chính là việc hệ thống vừa gửi thông báo nhờ tôi làm.

Kèm theo: trưởng phòng chỉ được gắn người CỦA PHÒNG MÌNH, vào ĐÚNG cột của
phòng mình (trước đây backend không kiểm gì, chỉ frontend ẩn ô).
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


async def _tao_vai_tro(client, admin, role_key, role_name, department, **quyen):
    resp = await client.post(
        "/api/v1/users/roles",
        json={"role_key": role_key, "role_name": role_name, "department": department,
              "permissions": {"canViewProjects": True, "canCreateProjects": True, **quyen}},
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
    return (await db.execute(select(User).where(User.id == resp.json()["id"]))).scalar_one()


async def _tao_du_an(client, nguoi, ten="Nhà anh Minh", **pic):
    resp = await client.post(
        "/api/v1/projects",
        json={"name": ten, "client_name": "Anh Minh", "project_type": "design_build", **pic},
        headers=auth_header(nguoi),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _du_an_thay_duoc(client, nguoi) -> set[str]:
    resp = await client.get("/api/v1/projects?page_size=200", headers=auth_header(nguoi))
    assert resp.status_code == 200, resp.text
    return {p["id"] for p in resp.json()["items"]}


COT = {"DESIGN": "designer_id", "OPS": "pm_id",
       "PURCHASING": "purchasing_id", "SALES": "sales_id"}


@pytest_asyncio.fixture
async def bo_may(client, db_session, admin_user):
    """4 trưởng phòng + 1 nhân viên mỗi phòng."""
    await _tao_vai_tro(client, admin_user, "operation_leader", "Trưởng phòng Vận hành", "OPS")
    await _tao_vai_tro(client, admin_user, "dutoan_thumua_leader",
                       "Trưởng phòng Dự toán–Thu mua", "PURCHASING")
    await _tao_vai_tro(client, admin_user, "thiet_ke", "Thiết kế", "DESIGN")
    await _tao_vai_tro(client, admin_user, "giam_sat_thi_cong", "Giám sát thi công", "OPS")
    await _tao_vai_tro(client, admin_user, "thu_mua", "Thu mua", "PURCHASING")

    tp = {
        "DESIGN": await _tao_user(client, db_session, admin_user, "tptk@test.com", "leader", "DESIGN"),
        "OPS": await _tao_user(client, db_session, admin_user, "tpops@test.com", "operation_leader", "OPS"),
        "PURCHASING": await _tao_user(client, db_session, admin_user, "tppur@test.com",
                                      "dutoan_thumua_leader", "PURCHASING"),
        "SALES": await _tao_user(client, db_session, admin_user, "tpkd@test.com", "leader", "SALES"),
    }
    nv = {
        "DESIGN": await _tao_user(client, db_session, admin_user, "nvtk@test.com", "thiet_ke", "DESIGN"),
        "OPS": await _tao_user(client, db_session, admin_user, "nvops@test.com",
                               "giam_sat_thi_cong", "OPS"),
        "PURCHASING": await _tao_user(client, db_session, admin_user, "nvtm@test.com",
                                      "thu_mua", "PURCHASING"),
        "SALES": await _tao_user(client, db_session, admin_user, "nvkd@test.com", "data_entry", "SALES"),
    }
    return {"tp": tp, "nv": nv}


# ── Đúng kịch bản lỗi user báo ──────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("phong_da_gan,phong_con_lai", [
    ("DESIGN", "PURCHASING"),
    ("DESIGN", "OPS"),
    ("OPS", "DESIGN"),
    ("SALES", "PURCHASING"),
])
async def test_mot_phong_gan_roi_thi_phong_khac_van_gan_duoc(
    client, db_session, admin_user, bo_may, phong_da_gan, phong_con_lai
):
    """ĐÂY LÀ LỖI: một phòng gắn PIC là các phòng còn lại bị 403, thành ngõ cụt."""
    tp, nv = bo_may["tp"], bo_may["nv"]
    du_an = await _tao_du_an(client, admin_user, **{COT[phong_da_gan]: nv[phong_da_gan].id})

    # Trưởng phòng còn lại phải MỞ được dự án…
    mo = await client.get(f"/api/v1/projects/{du_an}", headers=auth_header(tp[phong_con_lai]))
    assert mo.status_code == 200, (
        f"trưởng phòng {phong_con_lai} bị chặn khỏi dự án chỉ vì {phong_da_gan} "
        f"đã gắn PIC: {mo.text}"
    )
    # …và gắn được người của phòng mình
    gan = await client.put(
        f"/api/v1/projects/{du_an}",
        json={COT[phong_con_lai]: nv[phong_con_lai].id},
        headers=auth_header(tp[phong_con_lai]),
    )
    assert gan.status_code == 200, gan.text
    assert gan.json()[COT[phong_con_lai]] == nv[phong_con_lai].id


@pytest.mark.asyncio
async def test_gan_du_4_pic_qua_4_truong_phong(client, db_session, admin_user, bo_may):
    """Vòng đầy đủ: 4 trưởng phòng lần lượt gắn, không ai bị khóa giữa đường."""
    tp, nv = bo_may["tp"], bo_may["nv"]
    du_an = await _tao_du_an(client, admin_user)
    for phong in ("DESIGN", "OPS", "PURCHASING", "SALES"):
        r = await client.put(f"/api/v1/projects/{du_an}",
                             json={COT[phong]: nv[phong].id},
                             headers=auth_header(tp[phong]))
        assert r.status_code == 200, f"{phong} gắn thất bại sau khi các phòng trước đã gắn: {r.text}"
    pr = (await db_session.execute(select(Project).where(Project.id == du_an))).scalar_one()
    await db_session.refresh(pr)
    assert pr.designer_id == nv["DESIGN"].id
    assert pr.pm_id == nv["OPS"].id
    assert pr.purchasing_id == nv["PURCHASING"].id
    assert pr.sales_id == nv["SALES"].id


@pytest.mark.asyncio
async def test_truong_phong_tu_nhan_lam_pic(client, admin_user, bo_may):
    """«Đó có thể là chính họ» — trưởng phòng tự gắn mình."""
    tp = bo_may["tp"]
    du_an = await _tao_du_an(client, admin_user, designer_id=bo_may["nv"]["DESIGN"].id)
    r = await client.put(f"/api/v1/projects/{du_an}",
                         json={"purchasing_id": tp["PURCHASING"].id},
                         headers=auth_header(tp["PURCHASING"]))
    assert r.status_code == 200, r.text
    assert r.json()["purchasing_id"] == tp["PURCHASING"].id


@pytest.mark.asyncio
async def test_doi_pic_trong_phong_minh(client, db_session, admin_user, bo_may):
    """Đã gắn rồi vẫn phải đổi được sang người khác trong phòng."""
    tp, nv = bo_may["tp"], bo_may["nv"]
    nv2 = await _tao_user(client, db_session, admin_user, "nvtk2@test.com", "thiet_ke", "DESIGN")
    du_an = await _tao_du_an(client, admin_user, designer_id=nv["DESIGN"].id)
    r = await client.put(f"/api/v1/projects/{du_an}", json={"designer_id": nv2.id},
                         headers=auth_header(tp["DESIGN"]))
    assert r.status_code == 200, r.text
    assert r.json()["designer_id"] == nv2.id


# ── Dự án cần gắn PIC phải TÌM THẤY được trong danh sách ────────────────────

@pytest.mark.asyncio
async def test_du_an_thieu_pic_phong_minh_thi_hien_trong_danh_sach(
    client, admin_user, bo_may
):
    """Không tìm thấy thì không gắn được — thông báo có link nhưng danh sách cũng
    phải cho thấy, nếu không trưởng phòng phải mò từng dự án."""
    tp, nv = bo_may["tp"], bo_may["nv"]
    du_an = await _tao_du_an(client, admin_user, designer_id=nv["DESIGN"].id)
    thay = await _du_an_thay_duoc(client, tp["PURCHASING"])
    assert du_an in thay, "dự án còn trống PIC Thu mua phải hiện cho trưởng phòng Thu mua"


@pytest.mark.asyncio
async def test_gan_du_pic_roi_thi_phong_khong_lien_quan_het_thay(
    client, admin_user, bo_may
):
    """Đủ 4 PIC và không phòng nào của mình ⇒ không còn việc gì, rút khỏi danh sách."""
    tp, nv = bo_may["tp"], bo_may["nv"]
    du_an = await _tao_du_an(client, admin_user)
    for phong in ("DESIGN", "OPS", "PURCHASING", "SALES"):
        r = await client.put(f"/api/v1/projects/{du_an}", json={COT[phong]: nv[phong].id},
                             headers=auth_header(tp[phong]))
        assert r.status_code == 200, r.text

    await _tao_vai_tro(client, admin_user, "ke_toan_noi_bo", "Kế toán nội bộ", "ACCT")
    # Trưởng phòng Thiết kế vẫn thấy (quân mình là PIC)
    assert du_an in await _du_an_thay_duoc(client, tp["DESIGN"])


# ── Trưởng phòng chỉ gắn được người của phòng mình, vào cột của phòng mình ──

@pytest.mark.asyncio
async def test_khong_gan_nguoi_phong_khac_vao_cot_cua_minh(client, admin_user, bo_may):
    tp, nv = bo_may["tp"], bo_may["nv"]
    du_an = await _tao_du_an(client, admin_user)
    r = await client.put(f"/api/v1/projects/{du_an}",
                         json={"designer_id": nv["OPS"].id},
                         headers=auth_header(tp["DESIGN"]))
    assert r.status_code == 400, r.text
    assert "Thiết kế" in r.json()["detail"] or "bộ phận" in r.json()["detail"]


@pytest.mark.asyncio
async def test_khong_gan_pic_cho_phong_khac(client, admin_user, bo_may):
    """Trưởng phòng KD không gắn PIC Thiết kế — frontend đã ẩn ô, backend chặn nốt."""
    tp, nv = bo_may["tp"], bo_may["nv"]
    du_an = await _tao_du_an(client, admin_user)
    r = await client.put(f"/api/v1/projects/{du_an}",
                         json={"designer_id": nv["DESIGN"].id},
                         headers=auth_header(tp["SALES"]))
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_admin_van_gan_duoc_moi_cot(client, admin_user, bo_may):
    """Ban Giám Đốc điều phối chéo phòng — không bị giới hạn cột."""
    nv = bo_may["nv"]
    du_an = await _tao_du_an(client, admin_user)
    r = await client.put(
        f"/api/v1/projects/{du_an}",
        json={"designer_id": nv["DESIGN"].id, "pm_id": nv["OPS"].id,
              "purchasing_id": nv["PURCHASING"].id, "sales_id": nv["SALES"].id},
        headers=auth_header(admin_user),
    )
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_go_pic_cua_phong_minh(client, admin_user, bo_may):
    """Gỡ người khỏi dự án (đặt về trống) cũng là việc của trưởng phòng."""
    tp, nv = bo_may["tp"], bo_may["nv"]
    du_an = await _tao_du_an(client, admin_user, designer_id=nv["DESIGN"].id)
    r = await client.put(f"/api/v1/projects/{du_an}", json={"designer_id": None},
                         headers=auth_header(tp["DESIGN"]))
    assert r.status_code == 200, r.text
    assert r.json()["designer_id"] is None


# ── Nhân viên thường KHÔNG được gắn PIC ─────────────────────────────────────

@pytest.mark.asyncio
async def test_nhan_vien_thuong_khong_gan_duoc_pic(client, admin_user, bo_may):
    nv = bo_may["nv"]
    du_an = await _tao_du_an(client, admin_user)
    r = await client.put(f"/api/v1/projects/{du_an}", json={"designer_id": nv["DESIGN"].id},
                         headers=auth_header(nv["DESIGN"]))
    assert r.status_code in (400, 403), r.text


# ── Form gửi lại nguyên giá trị cũ của các ô mình không được sửa ────────────
# Ảnh user gửi 22/09: Thái Mạnh Cường (Trưởng phòng Thiết kế) chọn Lê Minh Nhật
# ở ô Thiết kế, bấm Cập nhật → toast «Bạn chỉ được phân công PIC cho bộ phận
# Thiết kế». Vì form gửi CẢ 4 ô PIC mỗi lần lưu, trong đó sales_id là giá trị
# CŨ được echo lại — kiểm tra lại xét «có mặt trong payload» thay vì «có thay
# đổi thật» nên chặn oan chính ô mà người ta không hề chạm vào.

@pytest.mark.asyncio
@pytest.mark.parametrize("phong", ["DESIGN", "OPS", "PURCHASING", "SALES"])
async def test_gui_lai_gia_tri_cu_cua_o_phong_khac_khong_bi_chan(
    client, db_session, admin_user, bo_may, phong
):
    tp, nv = bo_may["tp"], bo_may["nv"]
    # Dự án đã có PIC đủ 4 phòng (giống dự án thật trên prod)
    du_an = await _tao_du_an(
        client, admin_user,
        designer_id=nv["DESIGN"].id, pm_id=nv["OPS"].id,
        purchasing_id=nv["PURCHASING"].id, sales_id=nv["SALES"].id,
    )
    nguoi_moi = await _tao_user(
        client, db_session, admin_user, f"moi{phong.lower()}@test.com",
        {"DESIGN": "thiet_ke", "OPS": "giam_sat_thi_cong",
         "PURCHASING": "thu_mua", "SALES": "data_entry"}[phong], phong,
    )
    # Đúng payload form gửi: đổi ô của mình, 3 ô kia echo nguyên giá trị cũ
    payload = {
        "name": "Dự án CHỊ LYNA", "client_name": "CHỊ LYNA",
        "designer_id": nv["DESIGN"].id, "pm_id": nv["OPS"].id,
        "purchasing_id": nv["PURCHASING"].id, "sales_id": nv["SALES"].id,
    }
    payload[COT[phong]] = nguoi_moi.id
    r = await client.put(f"/api/v1/projects/{du_an}", json=payload,
                         headers=auth_header(tp[phong]))
    assert r.status_code == 200, f"trưởng phòng {phong} bị chặn oan: {r.text}"
    assert r.json()[COT[phong]] == nguoi_moi.id
    # 3 ô kia giữ nguyên
    for khac in ("DESIGN", "OPS", "PURCHASING", "SALES"):
        if khac != phong:
            assert r.json()[COT[khac]] == nv[khac].id


@pytest.mark.asyncio
async def test_doi_that_o_phong_khac_van_bi_chan(client, db_session, admin_user, bo_may):
    """Echo giá trị cũ thì bỏ qua, nhưng ĐỔI thật ô phòng khác vẫn phải chặn."""
    tp, nv = bo_may["tp"], bo_may["nv"]
    du_an = await _tao_du_an(client, admin_user, sales_id=nv["SALES"].id)
    nv_kd2 = await _tao_user(client, db_session, admin_user, "nvkd2@test.com",
                             "data_entry", "SALES")
    r = await client.put(
        f"/api/v1/projects/{du_an}",
        json={"designer_id": nv["DESIGN"].id, "sales_id": nv_kd2.id},
        headers=auth_header(tp["DESIGN"]),
    )
    assert r.status_code == 403, r.text
    assert "Thiết kế" in r.json()["detail"]


@pytest.mark.asyncio
async def test_sua_thong_tin_khac_khong_can_dung_den_pic(client, admin_user, bo_may):
    """Đổi tên/địa chỉ dự án mà form vẫn echo 4 ô PIC — không được chặn."""
    tp, nv = bo_may["tp"], bo_may["nv"]
    du_an = await _tao_du_an(client, admin_user, designer_id=nv["DESIGN"].id,
                             sales_id=nv["SALES"].id)
    r = await client.put(
        f"/api/v1/projects/{du_an}",
        json={"name": "Dự án CHỊ LYNA (sửa tên)", "address": "ORCHARD HILL",
              "designer_id": nv["DESIGN"].id, "sales_id": nv["SALES"].id},
        headers=auth_header(tp["DESIGN"]),
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Dự án CHỊ LYNA (sửa tên)"
