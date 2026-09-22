"""Nút «Tạo dự án mới» + thông báo trưởng phòng gắn PIC (22/09/2026).

User báo «trưởng phòng không thêm nhân viên vào được trong phần dự án». Đo thật
trên prod bằng 3 tài khoản trưởng phòng (Thiết kế / Giám sát / Báo giá–Thu mua):
gắn PIC qua API đều **OK** — không phải lỗi quyền. Lỗi thật là nút TẠO dự án:

    POST /projects  {name, client_name, project_type}   →  422 «thiếu code»

vì form không có ô mã dự án mà `ProjectCreate.code` lại bắt buộc, và khối
`catch {}` ở frontend nuốt thông báo nên chỉ hiện «Lỗi khi tạo dự án». Hệ quả:
153 dự án trên prod đều sinh tự động từ «Deal thắng», chưa ai tạo tay được lần
nào ⇒ trưởng phòng không có dự án mới nào để vào gắn PIC.

Luồng chốt 22/09: tạo dự án → thông báo trưởng phòng → trưởng phòng gắn PIC.
"""

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.middleware.permissions import xoa_cache_quyen
from app.models.notification import Notification
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
    return (await db.execute(
        select(User).where(User.id == resp.json()["id"])
    )).scalar_one()


# Y HỆT payload nút «Tạo dự án mới» gửi: không có `code`
PAYLOAD_FORM = {
    "name": "Nhà anh Minh Q7",
    "client_name": "Anh Minh",
    "project_type": "design_build",
}


@pytest_asyncio.fixture
async def ba_truong_phong(client, db_session, admin_user):
    await _tao_vai_tro(client, admin_user, "operation_leader", "Trưởng phòng Vận hành", "OPS")
    await _tao_vai_tro(client, admin_user, "dutoan_thumua_leader",
                       "Trưởng phòng Dự toán–Thu mua", "PURCHASING")
    await _tao_vai_tro(client, admin_user, "thiet_ke", "Thiết kế", "DESIGN")
    return {
        "tk": await _tao_user(client, db_session, admin_user, "tptk@test.com", "leader", "DESIGN"),
        "ops": await _tao_user(client, db_session, admin_user, "tpops@test.com",
                               "operation_leader", "OPS"),
        "pur": await _tao_user(client, db_session, admin_user, "tppur@test.com",
                               "dutoan_thumua_leader", "PURCHASING"),
    }


# ── Lỗi chặn đường: form không gửi mã dự án ─────────────────────────────────

@pytest.mark.asyncio
async def test_tao_du_an_khong_can_ma(client, db_session, admin_user):
    """Đúng payload của form — trước bản này trả 422 «thiếu code»."""
    resp = await client.post("/api/v1/projects", json=PAYLOAD_FORM, headers=auth_header(admin_user))
    assert resp.status_code == 200, resp.text
    ma = resp.json()["code"]
    assert ma and ma.startswith("PRJ-"), f"phải tự sinh mã, nhận được {ma!r}"


@pytest.mark.asyncio
async def test_ma_tu_sinh_khong_trung_nhau(client, admin_user):
    ma = set()
    for i in range(5):
        resp = await client.post(
            "/api/v1/projects",
            json={**PAYLOAD_FORM, "name": f"Dự án {i}"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200, resp.text
        ma.add(resp.json()["code"])
    assert len(ma) == 5, "mã dự án phải duy nhất"


@pytest.mark.asyncio
async def test_ma_tu_nhap_bi_trung_thi_bao_ro(client, admin_user):
    """Gửi mã tay mà trùng thì phải nói rõ, không để 500 vì vướng unique index."""
    r1 = await client.post("/api/v1/projects", json={**PAYLOAD_FORM, "code": "PRJ-TAY-001"},
                           headers=auth_header(admin_user))
    assert r1.status_code == 200, r1.text
    r2 = await client.post("/api/v1/projects", json={**PAYLOAD_FORM, "code": "PRJ-TAY-001"},
                           headers=auth_header(admin_user))
    assert r2.status_code == 400
    assert "đã tồn tại" in r2.json()["detail"]


@pytest.mark.asyncio
async def test_truong_phong_tao_duoc_du_an(client, ba_truong_phong):
    """Cả 3 trưởng phòng đều phải tạo được — họ là người mở dự án cho phòng mình."""
    for ten, nguoi in ba_truong_phong.items():
        resp = await client.post(
            "/api/v1/projects",
            json={**PAYLOAD_FORM, "name": f"Dự án của {ten}"},
            headers=auth_header(nguoi),
        )
        assert resp.status_code == 200, f"{ten}: {resp.text}"


# ── Thông báo cho trưởng phòng ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_du_an_moi_nhac_moi_truong_phong(client, db_session, admin_user, ba_truong_phong):
    resp = await client.post("/api/v1/projects", json=PAYLOAD_FORM, headers=auth_header(admin_user))
    assert resp.status_code == 200, resp.text
    du_an_id = resp.json()["id"]

    tb = (await db_session.execute(
        select(Notification).where(Notification.ref_id == du_an_id)
    )).scalars().all()
    nhan = {t.user_id for t in tb}
    assert nhan == {n.id for n in ba_truong_phong.values()}, (
        "đúng 3 trưởng phòng được nhắc, không nhắc ai khác"
    )
    assert all(t.type == "project_created" for t in tb)
    assert all(du_an_id in (t.link or "") for t in tb), "bấm vào phải mở đúng dự án"


@pytest.mark.asyncio
async def test_khong_nhac_bo_phan_da_co_pic(client, db_session, admin_user, ba_truong_phong):
    """Nhắc cả 4 phòng kể cả phòng đã gán xong thì thông báo thành tiếng ồn."""
    await _tao_vai_tro(client, admin_user, "giam_sat_thi_cong", "Giám sát thi công", "OPS")
    gs = await _tao_user(client, db_session, admin_user, "gs@test.com",
                         "giam_sat_thi_cong", "OPS")
    resp = await client.post(
        "/api/v1/projects", json={**PAYLOAD_FORM, "pm_id": gs.id},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    tb = (await db_session.execute(
        select(Notification).where(Notification.ref_id == resp.json()["id"])
    )).scalars().all()
    nhan = {t.user_id for t in tb}
    assert ba_truong_phong["ops"].id not in nhan, "phòng Giám sát đã có PIC ⇒ khỏi nhắc"
    assert {ba_truong_phong["tk"].id, ba_truong_phong["pur"].id} <= nhan


@pytest.mark.asyncio
async def test_nguoi_tu_tao_khong_tu_nhac_minh(client, db_session, ba_truong_phong):
    tp_tk = ba_truong_phong["tk"]
    resp = await client.post("/api/v1/projects", json=PAYLOAD_FORM, headers=auth_header(tp_tk))
    assert resp.status_code == 200, resp.text
    tb = (await db_session.execute(
        select(Notification).where(Notification.ref_id == resp.json()["id"])
    )).scalars().all()
    assert tp_tk.id not in {t.user_id for t in tb}


# ── Sau khi tạo, trưởng phòng gắn được PIC ngay (đủ vòng luồng) ─────────────

@pytest.mark.asyncio
async def test_tron_vong_tao_roi_gan_pic(client, db_session, admin_user, ba_truong_phong):
    await _tao_vai_tro(client, admin_user, "thiet_ke2", "Thiết kế 2", "DESIGN")
    nv = await _tao_user(client, db_session, admin_user, "nvtk@test.com", "thiet_ke2", "DESIGN")

    tao = await client.post("/api/v1/projects", json=PAYLOAD_FORM, headers=auth_header(admin_user))
    assert tao.status_code == 200, tao.text
    du_an_id = tao.json()["id"]

    gan = await client.put(f"/api/v1/projects/{du_an_id}", json={"designer_id": nv.id},
                           headers=auth_header(ba_truong_phong["tk"]))
    assert gan.status_code == 200, gan.text
    assert gan.json()["designer_id"] == nv.id

    pr = (await db_session.execute(
        select(Project).where(Project.id == du_an_id)
    )).scalar_one()
    await db_session.refresh(pr)
    assert pr.designer_id == nv.id
