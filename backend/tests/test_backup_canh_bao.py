"""Cảnh báo sao lưu lỗi / quá 48h (27/10/2026)."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.notification import Notification
from app.services.backup_service import VN_TZ, bao_loi_sao_luu, kiem_tra_sao_luu_cu, set_setting


@pytest.mark.asyncio
async def test_bao_loi_tao_thong_bao_admin(db_session, admin_user):
    await bao_loi_sao_luu(db_session, "pg_dump hỏng")
    ds = (await db_session.execute(select(Notification).where(Notification.type == "backup_loi"))).scalars().all()
    assert ds and ds[0].user_id == admin_user.id


@pytest.mark.asyncio
async def test_kiem_tra_cu(db_session, admin_user):
    await set_setting(db_session, "backup_last_success_at", datetime.now(VN_TZ).isoformat())
    await db_session.commit()
    assert await kiem_tra_sao_luu_cu(db_session) is False
    await set_setting(db_session, "backup_last_success_at", (datetime.now(VN_TZ) - timedelta(hours=50)).isoformat())
    await db_session.commit()
    assert await kiem_tra_sao_luu_cu(db_session) is True
