"""Chuyển lead sang «Mất» kèm lý do (lỗi user báo 27/08/2026).

Triệu chứng: bấm «🚫 Chuyển sang Mất lead», chọn lý do, hệ thống báo thành công
nhưng lead VẪN nằm ở cột cũ, không sang cột «Mất».

Gốc rễ: FE gọi `PUT /leads/{id}` với `{stage, lost_reason}`, mà `LeadUpdate`
KHÔNG khai báo hai trường đó. Pydantic mặc định BỎ QUA field lạ (schema không
đặt extra='forbid'), nên `model_dump(exclude_unset=True)` ra rỗng → endpoint
chỉ chạm `updated_at` rồi trả 200 với lead y nguyên. FE thấy 200 nên báo thành
công. Lý do mất cũng bay luôn.

Cách vá: dồn mọi chuyển giai đoạn về đúng một cửa `PUT /leads/{id}/stage` —
nơi đã có kiểm tra chuyển đổi hợp lệ, auto tạo Khách hàng/Dự án khi thắng deal,
và ghi lịch sử. Endpoint đó nay nhận thêm `lost_reason`.
"""

import pytest
from sqlalchemy import select

from app.models.lead import Lead
from tests.conftest import auth_header


LY_DO = "Ngân sách không phù hợp"


async def _tao_lead(client, user, stage=None):
    resp = await client.post(
        "/api/v1/leads",
        json={"name": "Chị Mai", "phone": "0901234567"},
        headers=auth_header(user),
    )
    assert resp.status_code == 200, resp.text
    lead_id = resp.json()["id"]
    if stage:
        resp = await client.put(
            f"/api/v1/leads/{lead_id}/stage",
            json={"new_stage": stage},
            headers=auth_header(user),
        )
        assert resp.status_code == 200, resp.text
    return lead_id


async def _doc_lead(db_session, lead_id) -> Lead:
    lead = (await db_session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one()
    await db_session.refresh(lead)
    return lead


# ---------------------------------------------------------------------------
# 1. Chính lỗi user báo: chuyển sang Mất phải ĐỔI THẬT stage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chuyen_sang_mat_doi_that_stage_va_luu_ly_do(client, db_session, admin_user):
    lead_id = await _tao_lead(client, admin_user, stage="interested")

    resp = await client.put(
        f"/api/v1/leads/{lead_id}/stage",
        json={"new_stage": "lost", "lost_reason": LY_DO},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["stage"] == "lost", "lead phải nằm ở cột Mất, không được ở lại cột cũ"
    assert body["lost_reason"] == LY_DO

    lead = await _doc_lead(db_session, lead_id)
    assert lead.stage == "lost"
    assert lead.lost_reason == LY_DO


# ---------------------------------------------------------------------------
# 2. Không có lý do thì chặn — đừng để lead rơi vào Mất mà không ai biết vì sao
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_thieu_ly_do_thi_chan(client, db_session, admin_user):
    lead_id = await _tao_lead(client, admin_user, stage="interested")

    for payload in ({"new_stage": "lost"}, {"new_stage": "lost", "lost_reason": "   "}):
        resp = await client.put(
            f"/api/v1/leads/{lead_id}/stage", json=payload, headers=auth_header(admin_user)
        )
        assert resp.status_code == 400, resp.text

    lead = await _doc_lead(db_session, lead_id)
    assert lead.stage == "interested", "bị chặn thì phải nằm nguyên cột cũ"


# ---------------------------------------------------------------------------
# 3. Lý do mất đi vào lịch sử hoạt động — mở thẻ lead là đọc được
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ly_do_vao_lich_su(client, admin_user):
    lead_id = await _tao_lead(client, admin_user, stage="potential")
    resp = await client.put(
        f"/api/v1/leads/{lead_id}/stage",
        json={"new_stage": "lost", "lost_reason": LY_DO},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get(f"/api/v1/leads/{lead_id}/activities", headers=auth_header(admin_user))
    contents = [a["content"] for a in resp.json()["items"] if a["type"] == "stage_change"]
    assert any(LY_DO in c for c in contents), contents


# ---------------------------------------------------------------------------
# 4. Kéo lead ra khỏi Mất thì xoá lý do cũ, khỏi hiện «Mất: ...» trên lead sống
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_khoi_phuc_lead_thi_xoa_ly_do(client, db_session, admin_user):
    lead_id = await _tao_lead(client, admin_user, stage="interested")
    resp = await client.put(
        f"/api/v1/leads/{lead_id}/stage",
        json={"new_stage": "lost", "lost_reason": LY_DO},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200

    resp = await client.put(
        f"/api/v1/leads/{lead_id}/stage",
        json={"new_stage": "interested"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["lost_reason"] is None

    lead = await _doc_lead(db_session, lead_id)
    assert lead.stage == "interested" and lead.lost_reason is None


# ---------------------------------------------------------------------------
# 5. Cửa PUT /leads/{id} KHÔNG được lặng lẽ nuốt stage rồi trả 200
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_put_lead_khong_nuot_stage_im_lang(client, db_session, admin_user):
    """Đúng lời gọi mà FE dùng trước đây. Dù vá kiểu nào cũng KHÔNG được phép
    vừa trả 200 vừa để nguyên stage — hoặc đổi thật, hoặc báo lỗi."""
    lead_id = await _tao_lead(client, admin_user, stage="interested")

    resp = await client.put(
        f"/api/v1/leads/{lead_id}",
        json={"stage": "lost", "lost_reason": LY_DO},
        headers=auth_header(admin_user),
    )
    lead = await _doc_lead(db_session, lead_id)
    if resp.status_code == 200:
        assert lead.stage == "lost", (
            "PUT /leads/{id} trả 200 nhưng stage y nguyên — đây chính là lỗi "
            "«báo thành công mà lead vẫn ở cột cũ»"
        )
    else:
        assert resp.status_code in (400, 422), resp.text
        assert lead.stage == "interested"


# ---------------------------------------------------------------------------
# 6. Đổi hàng loạt sang Mất cũng phải có lý do
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_sang_mat_can_ly_do(client, db_session, admin_user):
    lead_id = await _tao_lead(client, admin_user, stage="interested")

    resp = await client.post(
        "/api/v1/leads/bulk/stage",
        json={"lead_ids": [lead_id], "new_stage": "lost"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 400, resp.text
    lead = await _doc_lead(db_session, lead_id)
    assert lead.stage == "interested"

    resp = await client.post(
        "/api/v1/leads/bulk/stage",
        json={"lead_ids": [lead_id], "new_stage": "lost", "lost_reason": LY_DO},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    lead = await _doc_lead(db_session, lead_id)
    assert lead.stage == "lost" and lead.lost_reason == LY_DO
