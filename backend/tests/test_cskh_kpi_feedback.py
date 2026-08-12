"""Điều phối KD (Admin CSKH) xem KPI đội + góp ý (quyết định chủ dự án 12/08/2026).

Bối cảnh: 3 nhân sự Điều phối KD mang vai trò tùy chỉnh `admin_cskh` (bộ phận SALES).
Ma trận Phân quyền đã bật `canViewKPI` + `canViewFeedback` cho họ từ trước, nhưng backend
vẫn chốt cứng `role in ("admin", "leader", "executive")` → vào trang là ăn 403.

Ranh giới quan trọng: chỉ vai trò tùy chỉnh **thuộc bộ phận KD** mới được nới —
vai trò tùy chỉnh ở bộ phận khác vẫn phải bị chặn, nếu không là nới quyền toàn hệ thống.
"""

import pytest

from app.models.feedback import Feedback
from tests.conftest import auth_header, _uid
from tests.test_lead_data_split import _create_custom_role_user


async def _seed_feedback(db_session, author) -> Feedback:
    """1 góp ý của nhân viên, KHÔNG gắn telegram_user_id để test không gọi bot thật."""
    fb = Feedback(
        id=_uid(), user_id=author.id, telegram_user_id=None,
        category="workflow_improvement", content="Form thêm lead nên nhớ nguồn gần nhất.",
        status="new",
    )
    db_session.add(fb)
    await db_session.flush()
    return fb


# ── KPI đội ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cskh_xem_duoc_kpi_doi(client, db_session, admin_user):
    cskh = await _create_custom_role_user(
        client, db_session, admin_user,
        role_key="admin_cskh", role_name="Admin CSKH", department="SALES",
    )

    resp = await client.get("/api/v1/kpi/team?period=2026-07", headers=auth_header(cskh))
    assert resp.status_code == 200, resp.text
    assert "members" in resp.json()


@pytest.mark.asyncio
async def test_vai_tro_tuy_chinh_ngoai_kd_khong_xem_kpi_doi(client, db_session, admin_user):
    """Nới quyền chỉ dành cho bộ phận KD — vai trò tùy chỉnh khác vẫn phải 403."""
    ops = await _create_custom_role_user(
        client, db_session, admin_user,
        role_key="giam_sat_kho", role_name="Giám sát kho", department="OPS",
    )

    resp = await client.get("/api/v1/kpi/team?period=2026-07", headers=auth_header(ops))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_sale_thuong_van_khong_xem_kpi_doi(client, sales_user):
    resp = await client.get("/api/v1/kpi/team?period=2026-07", headers=auth_header(sales_user))
    assert resp.status_code == 403


# ── Góp ý ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cskh_xem_va_tra_loi_gop_y(client, db_session, admin_user, sales_user):
    cskh = await _create_custom_role_user(
        client, db_session, admin_user,
        role_key="admin_cskh", role_name="Admin CSKH", department="SALES",
    )
    fb = await _seed_feedback(db_session, sales_user)

    resp = await client.get("/api/v1/feedback", headers=auth_header(cskh))
    assert resp.status_code == 200, resp.text
    assert any(i["id"] == fb.id for i in resp.json()["items"])

    resp = await client.put(
        f"/api/v1/feedback/{fb.id}",
        json={"status": "in_review", "admin_reply": "Đã ghi nhận, tuần sau làm."},
        headers=auth_header(cskh),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "in_review"


@pytest.mark.asyncio
async def test_vai_tro_tuy_chinh_ngoai_kd_khong_xem_gop_y(client, db_session, admin_user, sales_user):
    ops = await _create_custom_role_user(
        client, db_session, admin_user,
        role_key="giam_sat_kho", role_name="Giám sát kho", department="OPS",
    )
    fb = await _seed_feedback(db_session, sales_user)

    assert (await client.get("/api/v1/feedback", headers=auth_header(ops))).status_code == 403
    resp = await client.put(
        f"/api/v1/feedback/{fb.id}",
        json={"status": "done"},
        headers=auth_header(ops),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_sale_thuong_van_khong_xem_gop_y_toan_cong_ty(client, db_session, sales_user):
    await _seed_feedback(db_session, sales_user)

    resp = await client.get("/api/v1/feedback", headers=auth_header(sales_user))
    assert resp.status_code == 403
