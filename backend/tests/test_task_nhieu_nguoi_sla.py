"""Một đầu việc NHIỀU người đảm nhận + nhắc quá hạn / vượt SLA (13/10/2026).

Yêu cầu chủ dự án: «khu vực Người Đảm Nhận công việc có thể thêm nhiều người…
đảm bảo thông báo công việc được gửi đi cho từng nhân sự/tài khoản khi (1) gắn
tag, PIC công việc (2) task quá hạn (3) task vi phạm SLA đã thống nhất».

Chốt thiết kế: mọi người đảm nhận NGANG VAI; nhắc người làm trước, trễ quá số
ngày leo thang thì nhắc thêm trưởng phòng & PM dự án; kênh = trong app + Telegram.

Các bài dưới đây canh đúng những chỗ dễ vỡ lại:
  - thêm người thứ 2 không được đẩy người thứ 1 ra (bản cũ chỉ có 1 cột)
  - TỪNG người phải có bản ghi thông báo riêng, không phải chỉ người đầu nhóm
  - một sự thật «trễ» chỉ bắn MỘT loại thông báo (quá hạn ĐÈ vượt SLA)
  - người thứ 2–3 phải thấy việc của mình (truy vấn cũ chỉ đọc `assigned_to`)
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.models.notification import Notification
from app.models.project import Task, TaskAssignee, dieu_kien_task_cua_nguoi
from app.models.user import User
from app.services.task_sla import (
    luu_cau_hinh_sla,
    run_task_overdue_alerts,
    run_task_sla_alerts,
)
from app.middleware.auth import hash_password
from tests.conftest import auth_header

pytestmark = pytest.mark.asyncio


async def _mot_task(db_session, project) -> Task:
    return (
        await db_session.execute(select(Task).where(Task.project_id == project.id).limit(1))
    ).scalars().first()


async def _ids_dam_nhan(db_session, task_id: str) -> set[str]:
    rows = await db_session.execute(
        select(TaskAssignee.user_id).where(TaskAssignee.task_id == task_id)
    )
    return set(rows.scalars().all())


async def _dem_thong_bao(db_session, user_id: str, loai: str) -> int:
    return (await db_session.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id, Notification.type == loai
        )
    )).scalar() or 0


# ---------------------------------------------------------------------------
# (1) Gắn tag / PIC công việc
# ---------------------------------------------------------------------------

async def test_giao_nhieu_nguoi_thi_tung_nguoi_duoc_thong_bao(
    client, db_session, admin_user, sales_user, designer_user, project
):
    task = await _mot_task(db_session, project)

    resp = await client.put(
        f"/api/v1/projects/{project.id}/tasks/{task.id}/assign",
        json={"assignee_ids": [sales_user.id, designer_user.id]},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    assert set(resp.json()["assignee_ids"]) == {sales_user.id, designer_user.id}
    # Cột cũ giữ người đầu nhóm để truy vấn cũ không gãy
    assert resp.json()["assigned_to"] == sales_user.id

    assert await _ids_dam_nhan(db_session, task.id) == {sales_user.id, designer_user.id}
    for u in (sales_user, designer_user):
        assert await _dem_thong_bao(db_session, u.id, "task_assigned") == 1, (
            f"{u.full_name} không nhận được thông báo giao việc"
        )


async def test_them_nguoi_khong_day_nguoi_cu_ra(
    client, db_session, admin_user, sales_user, designer_user, project
):
    task = await _mot_task(db_session, project)
    h = auth_header(admin_user)
    url = f"/api/v1/projects/{project.id}/tasks/{task.id}/assign"

    assert (await client.put(url, json={"assignee_ids": [sales_user.id]}, headers=h)).status_code == 200
    resp = await client.put(url, json={"assignee_ids": [sales_user.id, designer_user.id]}, headers=h)
    assert resp.status_code == 200, resp.text
    assert set(resp.json()["assignee_ids"]) == {sales_user.id, designer_user.id}
    # Người cũ không bị nhắc lại lần hai cho cùng một đầu việc
    assert await _dem_thong_bao(db_session, sales_user.id, "task_assigned") == 1
    assert await _dem_thong_bao(db_session, designer_user.id, "task_assigned") == 1


async def test_bo_mot_nguoi_khoi_nhom(
    client, db_session, admin_user, sales_user, designer_user, project
):
    task = await _mot_task(db_session, project)
    h = auth_header(admin_user)
    url = f"/api/v1/projects/{project.id}/tasks/{task.id}/assign"

    await client.put(url, json={"assignee_ids": [sales_user.id, designer_user.id]}, headers=h)
    resp = await client.put(url, json={"assignee_ids": [designer_user.id]}, headers=h)
    assert resp.status_code == 200, resp.text
    assert resp.json()["assignee_ids"] == [designer_user.id]
    assert resp.json()["assigned_to"] == designer_user.id
    assert await _ids_dam_nhan(db_session, task.id) == {designer_user.id}

    # Gỡ hết người cũng phải được (trả việc về hàng chờ)
    resp = await client.put(url, json={"assignee_ids": []}, headers=h)
    assert resp.status_code == 200, resp.text
    assert resp.json()["assignee_ids"] == []
    assert resp.json()["assigned_to"] is None


async def test_tao_task_kem_nguoi_lam_cung_thong_bao(
    client, db_session, admin_user, sales_user, designer_user, project
):
    """Trước 13/10 đường tạo việc gán thẳng vào model nên người được giao không hay."""
    resp = await client.post(
        f"/api/v1/projects/{project.id}/tasks",
        json={
            "title": "Dựng phối cảnh ban công",
            "stage": "design",
            "assignee_ids": [sales_user.id, designer_user.id],
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    assert set(resp.json()["assignee_ids"]) == {sales_user.id, designer_user.id}
    for u in (sales_user, designer_user):
        assert await _dem_thong_bao(db_session, u.id, "task_assigned") == 1


async def test_gan_viec_khi_du_an_chua_nap_san(
    client, db_session, admin_user, sales_user, designer_user, project
):
    """Chạy thật endpoint /assign vỡ 13/10/2026 mà cả bộ test vẫn xanh.

    Lý do: test dùng chung session với fixture nên `project` đã nằm trong bộ nhớ
    session, đọc `task.project` lấy được luôn mà không cần truy vấn. Ngoài đời
    route chỉ nạp đúng đầu việc ⇒ đọc quan hệ là lazy-load giữa async rồi vỡ
    (MissingGreenlet). Đẩy dự án ra khỏi bộ nhớ session để test đi đúng đường thật.
    """
    task = await _mot_task(db_session, project)
    task_id, du_an_id = task.id, project.id
    db_session.expunge(project)
    db_session.expunge(task)

    resp = await client.put(
        f"/api/v1/projects/{du_an_id}/tasks/{task_id}/assign",
        json={"assignee_ids": [sales_user.id, designer_user.id]},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    assert set(resp.json()["assignee_ids"]) == {sales_user.id, designer_user.id}
    for u in (sales_user, designer_user):
        assert await _dem_thong_bao(db_session, u.id, "task_assigned") == 1


async def test_nguoi_thu_hai_van_thay_viec_cua_minh(
    client, db_session, admin_user, sales_user, designer_user, project
):
    """`assigned_to` chỉ chứa 1 người; mọi chỗ lọc việc theo người phải đọc cả
    bảng `task_assignees`, nếu không người thứ 2 mất việc khỏi mọi báo cáo."""
    task = await _mot_task(db_session, project)
    await client.put(
        f"/api/v1/projects/{project.id}/tasks/{task.id}/assign",
        json={"assignee_ids": [sales_user.id, designer_user.id]},
        headers=auth_header(admin_user),
    )

    for u in (sales_user, designer_user):
        rows = await db_session.execute(select(Task).where(dieu_kien_task_cua_nguoi(u.id)))
        assert [t.id for t in rows.scalars().all()] == [task.id], (
            f"{u.full_name} không thấy đầu việc của mình"
        )


# ---------------------------------------------------------------------------
# (2) + (3) Quá hạn & vượt SLA
# ---------------------------------------------------------------------------

async def _gan_nhom(db_session, task: Task, *users: User) -> None:
    for u in users:
        db_session.add(TaskAssignee(id=str(uuid.uuid4()), task_id=task.id, user_id=u.id))
    task.assigned_to = users[0].id if users else None
    await db_session.commit()
    # Session của test đã nạp sẵn quan hệ `assignees` (rỗng) của đầu việc này;
    # thêm hàng trực tiếp không làm nó mới lại nên job sẽ đọc nhóm cũ. Worker
    # thật dùng session mới nên không gặp, test thì phải xoá nhớ tay.
    db_session.expire(task, ["assignees"])


async def _truong_phong_thiet_ke(db_session) -> User:
    u = User(
        id=str(uuid.uuid4()),
        full_name="Trưởng phòng Thiết kế",
        email=f"tp-{uuid.uuid4().hex[:6]}@test.com",
        password_hash=hash_password("x12345"),
        role="leader",
        department="DESIGN",
        is_active=True,
    )
    db_session.add(u)
    await db_session.commit()
    return u


async def test_viec_qua_han_nhac_tung_nguoi_roi_leo_thang(
    db_session, admin_user, sales_user, designer_user, project
):
    truong_phong = await _truong_phong_thiet_ke(db_session)
    task = await _mot_task(db_session, project)
    task.status = "in_progress"
    task.department = "design"
    task.started_at = datetime.now(timezone.utc) - timedelta(days=20)
    task.due_date = datetime.now(timezone.utc) - timedelta(days=5)
    await _gan_nhom(db_session, task, sales_user, designer_user)

    assert await run_task_overdue_alerts(db_session) >= 2
    await db_session.commit()

    for u in (sales_user, designer_user):
        assert await _dem_thong_bao(db_session, u.id, "task_overdue") == 1, (
            f"{u.full_name} không được nhắc việc quá hạn"
        )
    # Trễ 5 ngày > ngưỡng leo thang (2) ⇒ trưởng phòng + PM dự án cũng nhận
    assert await _dem_thong_bao(db_session, truong_phong.id, "task_escalated") == 1
    assert await _dem_thong_bao(db_session, admin_user.id, "task_escalated") == 1, (
        "PM dự án phải biết việc đang kẹt"
    )


async def test_tre_it_hon_nguong_thi_chua_leo_thang(
    db_session, admin_user, sales_user, project
):
    truong_phong = await _truong_phong_thiet_ke(db_session)
    task = await _mot_task(db_session, project)
    task.status = "in_progress"
    task.department = "design"
    task.due_date = datetime.now(timezone.utc) - timedelta(hours=10)  # trễ < 1 ngày
    await _gan_nhom(db_session, task, sales_user)

    await run_task_overdue_alerts(db_session)
    await db_session.commit()

    assert await _dem_thong_bao(db_session, sales_user.id, "task_overdue") == 1
    assert await _dem_thong_bao(db_session, truong_phong.id, "task_escalated") == 0
    assert await _dem_thong_bao(db_session, admin_user.id, "task_escalated") == 0


async def test_vuot_sla_khi_chua_co_han_chot(
    db_session, sales_user, designer_user, project
):
    task = await _mot_task(db_session, project)
    task.title = "2D Concept"           # chuẩn 3 ngày
    task.department = "design"
    task.status = "in_progress"
    task.due_date = None
    task.started_at = datetime.now(timezone.utc) - timedelta(days=10)
    task.sla_due_at = None              # để job tự điền (dữ liệu cũ)
    await _gan_nhom(db_session, task, sales_user, designer_user)

    assert await run_task_sla_alerts(db_session) >= 2
    await db_session.commit()

    await db_session.refresh(task)
    assert task.sla_due_at is not None, "job phải điền mốc SLA cho việc đã bắt đầu"
    for u in (sales_user, designer_user):
        assert await _dem_thong_bao(db_session, u.id, "task_sla_breach") == 1


async def test_da_qua_han_chot_thi_khong_bao_vuot_sla_nua(
    db_session, sales_user, project
):
    """Một sự thật «trễ» chỉ bắn một thông báo — tránh dội đôi mỗi ngày."""
    task = await _mot_task(db_session, project)
    task.title = "2D Concept"
    task.department = "design"
    task.status = "in_progress"
    task.started_at = datetime.now(timezone.utc) - timedelta(days=10)
    task.sla_due_at = datetime.now(timezone.utc) - timedelta(days=7)
    task.due_date = datetime.now(timezone.utc) - timedelta(days=2)
    await _gan_nhom(db_session, task, sales_user)

    assert await run_task_sla_alerts(db_session) == 0
    await db_session.commit()
    assert await _dem_thong_bao(db_session, sales_user.id, "task_sla_breach") == 0


async def test_tat_sla_trong_cai_dat_thi_ngung_nhac(db_session, sales_user, project):
    task = await _mot_task(db_session, project)
    task.title = "2D Concept"
    task.status = "in_progress"
    task.started_at = datetime.now(timezone.utc) - timedelta(days=10)
    task.sla_due_at = datetime.now(timezone.utc) - timedelta(days=7)
    task.due_date = None
    await _gan_nhom(db_session, task, sales_user)

    await luu_cau_hinh_sla(db_session, bat=False)
    await db_session.commit()

    assert await run_task_sla_alerts(db_session) == 0
    assert await _dem_thong_bao(db_session, sales_user.id, "task_sla_breach") == 0


async def test_viec_xong_thi_khong_nhac_nua(db_session, sales_user, project):
    task = await _mot_task(db_session, project)
    task.status = "done"
    task.due_date = datetime.now(timezone.utc) - timedelta(days=9)
    await _gan_nhom(db_session, task, sales_user)

    assert await run_task_overdue_alerts(db_session) == 0
    assert await _dem_thong_bao(db_session, sales_user.id, "task_overdue") == 0


async def test_cau_hinh_sla_doi_duoc_trong_cai_dat(client, db_session, admin_user):
    resp = await client.get("/api/v1/automation/task-sla", headers=auth_header(admin_user))
    assert resp.status_code == 200, resp.text
    assert resp.json()["dau_viec"]["2D Concept"] == 3

    resp = await client.put(
        "/api/v1/automation/task-sla",
        json={"dau_viec": {"2D Concept": 6}, "leo_thang_ngay": 4},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["dau_viec"]["2D Concept"] == 6
    assert resp.json()["leo_thang_ngay"] == 4
    # Các đầu việc không sửa vẫn giữ mặc định
    assert resp.json()["dau_viec"]["3D Render"] == 5

    resp = await client.put(
        "/api/v1/automation/task-sla",
        json={"dau_viec": {"2D Concept": 999}},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 400


async def test_sla_chi_admin_bgd_doi_duoc(client, sales_user):
    assert (await client.get(
        "/api/v1/automation/task-sla", headers=auth_header(sales_user)
    )).status_code == 403


# ---------------------------------------------------------------------------
# Đồng hồ SLA mở khi nào
# ---------------------------------------------------------------------------

async def test_chuyen_dang_lam_thi_mo_dong_ho_sla(client, db_session, admin_user, project):
    task = (await db_session.execute(
        select(Task).where(Task.project_id == project.id, Task.status == "not_started").limit(1)
    )).scalars().first()
    assert task.started_at is None

    resp = await client.put(
        f"/api/v1/projects/tasks/{task.id}/status",
        json={"status": "in_progress"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text

    await db_session.refresh(task)
    assert task.started_at is not None, "việc đang làm mà không có mốc bắt đầu thì SLA không đo được"
    assert task.sla_due_at is not None


async def test_doi_nguoi_giua_duong_khong_lam_sla_dem_lai(
    client, db_session, admin_user, sales_user, designer_user, project
):
    task = await _mot_task(db_session, project)
    url = f"/api/v1/projects/{project.id}/tasks/{task.id}/assign"
    h = auth_header(admin_user)

    await client.put(url, json={"assignee_ids": [sales_user.id]}, headers=h)
    await db_session.refresh(task)
    moc_dau = task.started_at
    han_dau = task.sla_due_at
    assert moc_dau is not None and han_dau is not None

    await client.put(url, json={"assignee_ids": [designer_user.id]}, headers=h)
    await db_session.refresh(task)
    assert task.started_at == moc_dau, "đổi người không được dịch mốc bắt đầu"
    assert task.sla_due_at == han_dau
