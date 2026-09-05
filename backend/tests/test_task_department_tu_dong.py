"""Task phải mang phòng ban để dropdown «Đảm nhận» lọc đúng người (05/09/2026).

User báo: ở trang Dự án, mục «Đảm nhận» của MỌI đầu việc hiện toàn bộ nhân sự,
kể cả task Báo giá cũng hiện thiết kế / thi công / sale.

Gốc rễ (đo prod chỉ đọc): 2128/2128 task có department NULL. 19 task tự sinh khi
lead thắng deal chỉ đặt `stage`; FE lọc theo `department` với nhánh «không có
phòng ban → cho mọi người» nên ai cũng lọt. Nay:
  - task tự sinh: department = stage (acceptance → construction)
  - task tạo tay bỏ trống phòng ban: suy từ stage, không để NULL
  - migration u01 backfill tồn đọng (kiểm riêng bằng SQL trên SQLite)
"""

import pytest
from sqlalchemy import select, text

from app.models.project import Project, Task, task_department_for_stage
from tests.conftest import auth_header


def test_map_giai_doan_sang_phong_ban():
    assert task_department_for_stage("design") == "design"
    assert task_department_for_stage("quotation") == "quotation"
    assert task_department_for_stage("procurement") == "procurement"
    assert task_department_for_stage("construction") == "construction"
    assert task_department_for_stage("acceptance") == "construction", "nghiệm thu do đội thi công làm"
    assert task_department_for_stage(None) is None


@pytest.mark.asyncio
async def test_thang_deal_sinh_task_co_du_phong_ban(client, db_session, admin_user):
    """Đúng kịch bản user báo: 19 task tự sinh KHÔNG được có department NULL."""
    resp = await client.post(
        "/api/v1/leads",
        json={"name": "Chị Hoa", "phone": "0901112233"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    lead_id = resp.json()["id"]
    resp = await client.put(
        f"/api/v1/leads/{lead_id}/stage",
        json={"new_stage": "signed_design"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text

    project = (await db_session.execute(select(Project).where(Project.lead_id == lead_id))).scalar_one()
    tasks = (await db_session.execute(select(Task).where(Task.project_id == project.id))).scalars().all()
    assert len(tasks) >= 19
    thieu = [t.title for t in tasks if not t.department]
    assert thieu == [], f"task thiếu phòng ban: {thieu}"
    for t in tasks:
        assert t.department == task_department_for_stage(t.stage), (t.title, t.stage, t.department)
    # Task báo giá phải thuộc phòng «quotation» — không phải thiết kế hay sale
    bao_gia = [t for t in tasks if t.stage == "quotation"]
    assert bao_gia and all(t.department == "quotation" for t in bao_gia)


@pytest.mark.asyncio
async def test_tao_task_tay_bo_trong_phong_ban_thi_suy_tu_stage(client, admin_user, project):
    resp = await client.post(
        f"/api/v1/projects/{project.id}/tasks",
        json={"title": "Dự toán vật tư", "stage": "quotation"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["department"] == "quotation"

    # Chọn tay thì tôn trọng lựa chọn, không ghi đè
    resp = await client.post(
        f"/api/v1/projects/{project.id}/tasks",
        json={"title": "Đối chiếu công nợ", "stage": "acceptance", "department": "accounting"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["department"] == "accounting"


@pytest.mark.asyncio
async def test_backfill_u01_chi_dung_dong_null(db_session, project):
    """Chạy đúng câu SQL của migration u01 trên SQLite test: NULL → theo stage,
    dòng đã có phòng ban giữ nguyên."""
    db_session.add_all([
        Task(project_id=project.id, title="a", stage="quotation", department=None, order=1),
        Task(project_id=project.id, title="b", stage="acceptance", department=None, order=2),
        Task(project_id=project.id, title="c", stage="design", department="accounting", order=3),
    ])
    await db_session.flush()
    await db_session.execute(text(
        "UPDATE tasks SET department = CASE stage WHEN 'acceptance' THEN 'construction' ELSE stage END "
        "WHERE department IS NULL AND stage IS NOT NULL"
    ))
    rows = {t.title: t.department for t in (await db_session.execute(
        select(Task).where(Task.project_id == project.id, Task.title.in_(["a", "b", "c"]))
    )).scalars().all()}
    assert rows == {"a": "quotation", "b": "construction", "c": "accounting"}
