"""Siết quyền theo feedback nhân viên 21/10/2026 + ma trận V3 chốt 22/10/2026.

Feedback 21/10: «nhân viên thấy toàn bộ dự án ở Kanban». Rà backend thấy thêm
các lỗ cùng loại: ai đăng nhập cũng sửa được đầu việc bất kỳ, tạo/sửa hợp đồng,
xem/sửa mọi dự toán, xem toàn bộ danh sách khách hàng.

Chốt V3 22/10: duyệt báo giá = TP Báo giá (`dutoan_thumua_leader`); xác nhận
thu tiền = Kế toán; bảng giá chỉ Admin sửa; vai `supervisor` ngừng cấp mới,
gộp vào TP Giám sát (`operation_leader`).
"""

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.middleware.permissions import xoa_cache_quyen
from app.models.customer import Customer
from app.models.project import Task
from app.models.user import User
from tests.conftest import auth_header


@pytest.fixture(autouse=True)
def _sach_cache_quyen():
    xoa_cache_quyen()
    yield
    xoa_cache_quyen()


async def _tao_vai_tro(client, admin, role_key, role_name, department, **perms):
    resp = await client.post(
        "/api/v1/users/roles",
        json={"role_key": role_key, "role_name": role_name, "department": department,
              "permissions": {"canViewProjects": True, **perms}},
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


async def _tao_du_an(client, admin, code, **pic):
    resp = await client.post(
        "/api/v1/projects",
        json={"code": code, "name": f"Dự án {code}", "client_name": "KH test", **pic},
        headers=auth_header(admin),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _tao_task(client, admin, project_id, title="Việc test"):
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": title, "stage": "construction"},
        headers=auth_header(admin),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


@pytest_asyncio.fixture
async def bo_may(client, db_session, admin_user):
    await _tao_vai_tro(client, admin_user, "giam_sat_thi_cong", "Giám sát thi công", "OPS")
    await _tao_vai_tro(client, admin_user, "operation_leader", "TP Giám sát", "OPS",
                       canEditTasks=True, canCreateTasks=True)
    await _tao_vai_tro(client, admin_user, "dutoan_thumua_leader", "TP Báo giá", "PURCHASING")
    u = {
        "gs": await _tao_user(client, db_session, admin_user, "gs@test.com", "giam_sat_thi_cong", "OPS"),
        "gs2": await _tao_user(client, db_session, admin_user, "gs2@test.com", "giam_sat_thi_cong", "OPS"),
        "gs_tp": await _tao_user(client, db_session, admin_user, "gstp@test.com", "operation_leader", "OPS"),
        "bg_tp": await _tao_user(client, db_session, admin_user, "bgtp@test.com", "dutoan_thumua_leader", "PURCHASING"),
    }
    pid = await _tao_du_an(client, admin_user, "PRJ-GS", pm_id=u["gs"].id)
    return {"u": u, "pid": pid}


async def _du_an_tren_kanban(client, user) -> set[str]:
    resp = await client.get("/api/v1/projects/pipeline/kanban", headers=auth_header(user))
    assert resp.status_code == 200, resp.text
    return {p["id"] for cot in resp.json() for p in cot["projects"]}


# ── Feedback 2: Kanban theo phạm vi ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_kanban_khong_lo_du_an_ngoai_pham_vi(client, admin_user, sales_user, bo_may):
    pid = bo_may["pid"]
    assert pid in await _du_an_tren_kanban(client, admin_user)
    assert pid in await _du_an_tren_kanban(client, bo_may["u"]["gs"]), "PIC phải thấy dự án mình"
    assert pid in await _du_an_tren_kanban(client, bo_may["u"]["gs_tp"]), "TP Giám sát thấy dự án phòng mình"
    assert pid not in await _du_an_tren_kanban(client, sales_user), "sale không phụ trách thì không thấy"
    assert pid not in await _du_an_tren_kanban(client, bo_may["u"]["gs2"]), "giám sát khác không thấy"


# ── Sửa đầu việc ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_nguoi_ngoai_khong_sua_duoc_dau_viec(client, admin_user, sales_user, bo_may):
    tid = await _tao_task(client, admin_user, bo_may["pid"])
    for nguoi in (sales_user, bo_may["u"]["gs2"]):
        resp = await client.put(f"/api/v1/projects/tasks/{tid}/status",
                                json={"status": "done"}, headers=auth_header(nguoi))
        assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_pic_va_truong_phong_sua_duoc_dau_viec(client, admin_user, bo_may):
    tid = await _tao_task(client, admin_user, bo_may["pid"])
    resp = await client.put(f"/api/v1/projects/tasks/{tid}/status",
                            json={"status": "in_progress"}, headers=auth_header(bo_may["u"]["gs"]))
    assert resp.status_code == 200, resp.text
    resp = await client.put(f"/api/v1/projects/tasks/{tid}/status",
                            json={"status": "done"}, headers=auth_header(bo_may["u"]["gs_tp"]))
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_nguoi_duoc_giao_sua_trang_thai_nhung_khong_tu_doi_han(
    client, db_session, admin_user, bo_may
):
    """Người được giao cập nhật tiến độ việc của mình, nhưng không tự đổi hạn."""
    tid = await _tao_task(client, admin_user, bo_may["pid"])
    gs2 = bo_may["u"]["gs2"]
    task = await db_session.get(Task, tid)
    task.assigned_to = gs2.id
    await db_session.commit()

    resp = await client.put(f"/api/v1/projects/tasks/{tid}/status",
                            json={"status": "in_progress"}, headers=auth_header(gs2))
    assert resp.status_code == 200, resp.text
    pid = bo_may["pid"]
    resp = await client.put(f"/api/v1/projects/{pid}/tasks/{tid}/due-date",
                            json={"due_date": None}, headers=auth_header(gs2))
    assert resp.status_code == 403, resp.text


# ── Hợp đồng ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_khong_co_o_tao_hop_dong_thi_403(client, admin_user, project, bo_may):
    """Vai không bật ô «Tạo Hợp đồng» — trước 22/10 gọi API thẳng vẫn tạo được."""
    resp = await client.post(
        "/api/v1/contracts",
        json={"code": "HD-V3-01", "project_id": project.id, "title": "HD giám sát"},
        headers=auth_header(bo_may["u"]["gs"]),
    )
    assert resp.status_code == 403, resp.text
    resp = await client.post(
        "/api/v1/contracts",
        json={"code": "HD-V3-01", "project_id": project.id, "title": "HD giám sát"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text


# ── Dự toán ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_du_toan_chi_nguoi_lap_sua(client, admin_user, bo_may):
    gs, gs2 = bo_may["u"]["gs"], bo_may["u"]["gs2"]
    resp = await client.post("/api/v1/estimations",
                             json={"floor_count": 1, "area_sqm": 50},
                             headers=auth_header(gs))
    assert resp.status_code == 201, resp.text
    eid = resp.json()["id"]

    assert (await client.get(f"/api/v1/estimations/{eid}", headers=auth_header(gs))).status_code == 200
    assert (await client.get(f"/api/v1/estimations/{eid}", headers=auth_header(gs2))).status_code == 403
    assert (await client.post(f"/api/v1/estimations/{eid}/submit", headers=auth_header(gs2))).status_code == 403
    ds = (await client.get("/api/v1/estimations", headers=auth_header(gs2))).json()["items"]
    assert eid not in {e["id"] for e in ds}
    assert (await client.get(f"/api/v1/estimations/{eid}", headers=auth_header(admin_user))).status_code == 200


@pytest.mark.asyncio
async def test_du_toan_khong_gan_vao_du_an_ngoai_pham_vi(client, bo_may):
    resp = await client.post("/api/v1/estimations",
                             json={"project_id": bo_may["pid"], "floor_count": 1, "area_sqm": 50},
                             headers=auth_header(bo_may["u"]["gs2"]))
    assert resp.status_code == 403, resp.text


# ── Khách hàng ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_danh_sach_khach_theo_pham_vi(client, db_session, admin_user, bo_may):
    db_session.add(Customer(name="Khách lẻ không gắn gì", phone="0900000001"))
    await db_session.commit()

    def ten(r):
        return {c["name"] for c in r.json()["items"]}

    resp = await client.get("/api/v1/customers", headers=auth_header(admin_user))
    assert "Khách lẻ không gắn gì" in ten(resp)
    resp = await client.get("/api/v1/customers", headers=auth_header(bo_may["u"]["gs2"]))
    assert resp.status_code == 200
    assert "Khách lẻ không gắn gì" not in ten(resp)


# ── Chốt V3: người duyệt / bảng giá / bỏ supervisor ─────────────────────────

@pytest.mark.asyncio
async def test_duyet_bao_gia_la_tp_bao_gia(client, admin_user, bo_may):
    r = await client.post("/api/v1/quotations", json={"type": "design", "title": "BG V3"},
                          headers=auth_header(admin_user))
    assert r.status_code == 200, r.text
    qid = r.json()["id"]
    r = await client.post(f"/api/v1/quotations/{qid}/approve", headers=auth_header(bo_may["u"]["gs_tp"]))
    assert r.status_code == 403, "TP Giám sát không duyệt báo giá"
    r = await client.post(f"/api/v1/quotations/{qid}/approve", headers=auth_header(bo_may["u"]["bg_tp"]))
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_truong_phong_kd_khong_xac_nhan_thu_tien(client, db_session, admin_user, project):
    tp = await _tao_user(client, db_session, admin_user, "tpkd@test.com", "leader", "SALES")
    r = await client.post("/api/v1/contracts",
                          json={"code": "HD-V3-02", "project_id": project.id, "title": "HD thu tiền"},
                          headers=auth_header(admin_user))
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    r = await client.put(f"/api/v1/contracts/{cid}/payments/0", json={}, headers=auth_header(tp))
    assert r.status_code == 403, "chỉ Kế toán/Admin xác nhận tiền về"


@pytest.mark.asyncio
async def test_bang_gia_chi_admin_sua(client, designer_user):
    r = await client.post("/api/v1/instant-quote/price-items",
                          json={"code": "X1", "name": "Hạng mục", "category": "khac",
                                "price_basic": 1, "price_standard": 2, "price_premium": 3},
                          headers=auth_header(designer_user))
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_khong_tao_moi_duoc_vai_supervisor(client, admin_user):
    r = await client.post(
        "/api/v1/users",
        json={"full_name": "GS mới", "email": "gsmoi@test.com", "password": "secret123",
              "role": "supervisor", "department": "OPS"},
        headers=auth_header(admin_user),
    )
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_tai_khoan_supervisor_cu_van_sua_duoc_thong_tin(client, admin_user, designer_user):
    r = await client.put(f"/api/v1/users/{designer_user.id}",
                         json={"full_name": "GS cũ đổi tên", "role": "supervisor"},
                         headers=auth_header(admin_user))
    assert r.status_code == 200, r.text
