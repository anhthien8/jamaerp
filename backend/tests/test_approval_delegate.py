"""Ủy quyền duyệt khi vắng — đi qua endpoint POST/GET /approvals/delegate."""

from datetime import datetime, timedelta, timezone

from app.models.notification import Notification
import pytest
from sqlalchemy import select

from tests.conftest import auth_header
from tests.test_scale_trackb import _make_user

URL = "/api/v1/approvals/delegate"


def _until(days: int = 2) -> str:
    # Giống frontend gửi: ISO có múi giờ +07:00
    return (datetime.now(timezone(timedelta(hours=7))) + timedelta(days=days)).isoformat()


@pytest.mark.asyncio
class TestDelegate:
    async def test_set_get_and_clear(self, client, db_session):
        boss = await _make_user(db_session, role="leader")
        peer = await _make_user(db_session, role="accountant", dept="ACCOUNTING")
        await _make_user(db_session, role="sale")  # không phải ứng viên

        r = await client.post(URL, json={"delegate_to": peer.id, "until": _until()}, headers=auth_header(boss))
        assert r.status_code == 200, r.text
        await db_session.refresh(boss)
        assert boss.delegate_to == peer.id
        assert boss.delegate_until.tzinfo is None  # lưu naive UTC (Postgres)
        assert boss.delegate_until > datetime.now(timezone.utc).replace(tzinfo=None)

        # Người nhận được báo
        notes = (await db_session.execute(select(Notification).where(Notification.user_id == peer.id))).scalars().all()
        assert any("ủy quyền" in n.title for n in notes)

        g = (await client.get(URL, headers=auth_header(boss))).json()
        assert g["can_delegate"] is True
        assert g["delegate_to"] == peer.id and g["delegate_name"] == peer.full_name
        assert g["until"].endswith("Z")
        roles = {c["role"] for c in g["candidates"]}
        assert "sale" not in roles and "data_entry" not in roles
        assert boss.id not in {c["id"] for c in g["candidates"]}

        r = await client.post(URL, json={"delegate_to": None}, headers=auth_header(boss))
        assert r.status_code == 200
        g = (await client.get(URL, headers=auth_header(boss))).json()
        assert g["delegate_to"] is None and g["until"] is None

    async def test_target_must_be_approver_role(self, client, db_session):
        """Không trao quyền duyệt (gồm đơn tiền) cho sale/thiết kế."""
        boss = await _make_user(db_session, role="leader")
        sale = await _make_user(db_session, role="sale")
        r = await client.post(URL, json={"delegate_to": sale.id, "until": _until()}, headers=auth_header(boss))
        assert r.status_code == 400
        await db_session.refresh(boss)
        assert boss.delegate_to is None

    async def test_past_until_rejected(self, client, db_session):
        boss = await _make_user(db_session, role="leader")
        peer = await _make_user(db_session, role="leader")
        r = await client.post(URL, json={"delegate_to": peer.id, "until": _until(-1)}, headers=auth_header(boss))
        assert r.status_code == 400

    async def test_non_approver_cannot_delegate(self, client, db_session):
        sale = await _make_user(db_session, role="sale")
        peer = await _make_user(db_session, role="leader")
        r = await client.post(URL, json={"delegate_to": peer.id, "until": _until()}, headers=auth_header(sale))
        assert r.status_code == 403
        g = (await client.get(URL, headers=auth_header(sale))).json()
        assert g["can_delegate"] is False and g["candidates"] == []
