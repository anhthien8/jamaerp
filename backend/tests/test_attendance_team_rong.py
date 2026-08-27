"""Bảng công team với leader CHƯA xếp đội (QC 27/08/2026).

qc-all-roles bắt được trên prod: leader chưa thuộc đội nào mở trang Chấm công →
GET /attendance/team trả 400 «Bạn chưa thuộc team nào». FE gộp lời gọi này trong
Promise.all với bảng công CÁ NHÂN nên 400 làm toast lỗi đỏ che luôn phần cá nhân
vốn tải được. Nay trả 200 với items rỗng — FE tự ẩn bảng team khi không có dòng.
"""

import pytest

from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_leader_chua_xep_doi_nhan_bang_rong_thay_vi_400(client, db_session, admin_user):
    resp = await client.post(
        "/api/v1/users",
        json={
            "full_name": "Leader Chưa Đội", "email": "leader-teamless@test.com",
            "password": "secret123", "role": "leader", "department": "SALES",
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    from sqlalchemy import select
    from app.models.user import User
    leader = (await db_session.execute(
        select(User).where(User.id == resp.json()["id"])
    )).scalar_one()
    assert leader.team_id is None

    resp = await client.get("/api/v1/attendance/team?period=2026-08", headers=auth_header(leader))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["items"] == []
    assert body["period"] == "2026-08"
