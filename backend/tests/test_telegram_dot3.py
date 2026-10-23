"""Đợt 3 (23/10/2026): bot bấm chọn dự án + ghi nhận người Telegram để admin gán.

- /telegram/my-projects đúng phạm vi người dùng (cùng điều kiện với Kanban).
- /telegram/contacts/seen upsert, sai bí mật → 401.
- /users/telegram-contacts gợi ý theo tên không dấu, ẩn người đã gán.
- /users/{id}/link-telegram gán được, gán trùng → 400, người thường → 403.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.users import bo_dau
from app.config import get_settings
from app.models.project import Project
from app.models.telegram_contact import TelegramContact
from app.models.user import User
from app.middleware.auth import hash_password
from tests.conftest import _uid, auth_header


def _secret() -> dict:
    s = get_settings().TELEGRAM_AUTH_SECRET
    return {"X-Telegram-Bot-Secret": s} if s else {}


async def _seen(client, **kw):
    return await client.post("/api/v1/telegram/contacts/seen", json=kw, headers=_secret())


def test_bo_dau():
    assert bo_dau("  Nguyễn Văn  Ánh ") == "nguyen van anh"
    assert bo_dau("Đặng Thị Đào") == "dang thi dao"


@pytest.mark.asyncio
async def test_my_projects_dung_pham_vi(client: AsyncClient, db_session: AsyncSession, project, admin_user, sales_user, designer_user):
    # Dự án chưa có PIC đúng phòng thì ai cũng thấy (lối thoát «chưa phân công»)
    project.pm_id = designer_user.id
    cua_sale = Project(id=_uid(), code="JMH-SALE", name="Nhà chị B", client_name="B",
                       stage="design", status="active", sales_id=sales_user.id, pm_id=admin_user.id)
    xong = Project(id=_uid(), code="JMH-XONG", name="Đã bàn giao", client_name="C",
                   stage="handover", status="completed", sales_id=sales_user.id)
    db_session.add_all([cua_sale, xong])
    await db_session.commit()

    r = await client.get("/api/v1/telegram/my-projects", headers=auth_header(sales_user))
    assert r.status_code == 200
    assert [p["code"] for p in r.json()] == ["JMH-SALE"]  # không thấy JMH-TEST, không có dự án đã xong

    r = await client.get("/api/v1/telegram/my-projects", headers=auth_header(admin_user))
    assert {p["code"] for p in r.json()} == {"JMH-TEST", "JMH-SALE"}


@pytest.mark.asyncio
async def test_contact_seen_upsert(client: AsyncClient, db_session: AsyncSession):
    r = await _seen(client, tg_user_id=555001, first_name="Nguyen", last_name="Van A", chat_id=-100123, chat_title="JAMA Công trình")
    assert r.status_code == 200
    r = await _seen(client, tg_user_id=555001, username="nva_jama")
    assert r.status_code == 200
    c = await db_session.get(TelegramContact, 555001, populate_existing=True)
    assert c.username == "nva_jama"
    assert c.first_name == "Nguyen"  # lần sau thiếu tên không xóa tên cũ
    assert c.chat_title == "JAMA Công trình"


@pytest.mark.asyncio
async def test_contact_seen_sai_bi_mat(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(get_settings(), "TELEGRAM_AUTH_SECRET", "dung-bi-mat")
    r = await client.post("/api/v1/telegram/contacts/seen", json={"tg_user_id": 1},
                          headers={"X-Telegram-Bot-Secret": "sai"})
    assert r.status_code == 401
    r = await client.post("/api/v1/telegram/contacts/seen", json={"tg_user_id": 1},
                          headers={"X-Telegram-Bot-Secret": "dung-bi-mat"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_goi_y_va_gan(client: AsyncClient, db_session: AsyncSession, admin_user, sales_user):
    nv = User(id=_uid(), full_name="Nguyễn Văn A", email="anv@test.com", password_hash=hash_password("x12345678"),
              role="data_entry", department="OPS", is_active=True)
    nv2 = User(id=_uid(), full_name="Trần Thị Bình", email="tranbinh@test.com", password_hash=hash_password("x12345678"),
               role="data_entry", department="OPS", is_active=True)
    db_session.add_all([nv, nv2])
    await db_session.commit()

    await _seen(client, tg_user_id=555002, first_name="Nguyen", last_name="Van A")
    await _seen(client, tg_user_id=555003, username="tranbinh")       # khớp local-part email
    await _seen(client, tg_user_id=555004, first_name="Người", last_name="Lạ")
    await _seen(client, tg_user_id=900003, first_name="Sales")         # đã gán sales_user

    r = await client.get("/api/v1/users/telegram-contacts", headers=auth_header(admin_user))
    assert r.status_code == 200
    theo_id = {c["tg_user_id"]: c for c in r.json()}
    assert 900003 not in theo_id  # đã gán → ẩn
    assert theo_id[555002]["suggested_user_id"] == nv.id
    assert theo_id[555003]["suggested_user_id"] == nv2.id
    assert theo_id[555004]["suggested_user_id"] is None

    # Người không có quyền quản lý tài khoản
    r = await client.get("/api/v1/users/telegram-contacts", headers=auth_header(sales_user))
    assert r.status_code == 403
    r = await client.post(f"/api/v1/users/{nv.id}/link-telegram", json={"tg_user_id": 555002}, headers=auth_header(sales_user))
    assert r.status_code == 403

    r = await client.post(f"/api/v1/users/{nv.id}/link-telegram", json={"tg_user_id": 555002}, headers=auth_header(admin_user))
    assert r.status_code == 200
    assert (await db_session.get(User, nv.id, populate_existing=True)).telegram_user_id == 555002
    assert (await db_session.get(TelegramContact, 555002, populate_existing=True)).linked_user_id == nv.id

    # Gán trùng sang người khác → 400
    r = await client.post(f"/api/v1/users/{nv2.id}/link-telegram", json={"tg_user_id": 555002}, headers=auth_header(admin_user))
    assert r.status_code == 400

    r = await client.get("/api/v1/users/telegram-contacts", headers=auth_header(admin_user))
    assert 555002 not in {c["tg_user_id"] for c in r.json()}
