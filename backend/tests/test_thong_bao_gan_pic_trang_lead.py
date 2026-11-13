"""Hai lỗi nhân viên báo 13/11/2026.

1. Quản lý gắn nhân viên vào dự án (PIC) — nhân viên không nhận thông báo.
2. Kanban Lead của TP Kinh doanh hiện thẻ trùng: lead nhập hàng loạt có cùng
   `updated_at`, sắp xếp không có khoá phụ nên hai trang liền nhau trả trùng dòng.
"""

from datetime import datetime

import pytest
from sqlalchemy import select

from app.models.lead import Lead
from app.models.notification import Notification
from app.services.automation import _notify
from tests.conftest import auth_header


async def _thong_bao(db, user, loai="project_assigned"):
    rows = await db.execute(
        select(Notification).where(Notification.user_id == user.id, Notification.type == loai)
    )
    return rows.scalars().all()


@pytest.mark.asyncio
async def test_gan_pic_du_an_thi_nguoi_duoc_gan_nhan_thong_bao(
    client, db_session, admin_user, designer_user, project
):
    resp = await client.put(
        f"/api/v1/projects/{project.id}",
        json={"designer_id": designer_user.id},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text

    tb = await _thong_bao(db_session, designer_user)
    assert len(tb) == 1
    assert "Thiết kế" in tb[0].title
    assert tb[0].link == f"/projects?id={project.id}"

    # Lưu lại form (PIC không đổi) → không báo lần hai.
    resp = await client.put(
        f"/api/v1/projects/{project.id}",
        json={"designer_id": designer_user.id, "name": "Đổi tên"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    assert len(await _thong_bao(db_session, designer_user)) == 1


@pytest.mark.asyncio
async def test_tu_gan_minh_lam_pic_thi_khong_tu_bao(client, db_session, admin_user, project):
    resp = await client.put(
        f"/api/v1/projects/{project.id}",
        json={"pm_id": admin_user.id},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    assert await _thong_bao(db_session, admin_user) == []


@pytest.mark.asyncio
async def test_tieu_de_thong_bao_qua_dai_duoc_cat(db_session, designer_user):
    assert await _notify(db_session, designer_user, "system", "x" * 400, "noi dung", telegram=False)
    tb = await _thong_bao(db_session, designer_user, "system")
    assert len(tb[0].title) == 255


@pytest.mark.asyncio
async def test_phan_trang_lead_khong_trung_khi_cung_updated_at(client, db_session, admin_user):
    moc = datetime(2026, 11, 1, 8, 0, 0)
    for i in range(25):
        db_session.add(Lead(
            name=f"Khách {i}", phone=f"09000000{i:02d}", stage="new",
            created_at=moc, updated_at=moc,
        ))
    await db_session.flush()

    da_thay: list[str] = []
    for trang in (1, 2, 3):
        resp = await client.get(
            f"/api/v1/leads?page={trang}&page_size=10", headers=auth_header(admin_user)
        )
        assert resp.status_code == 200, resp.text
        da_thay += [l["id"] for l in resp.json()["items"]]

    assert len(da_thay) == 25
    assert len(set(da_thay)) == 25
