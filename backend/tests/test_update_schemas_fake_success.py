"""Quét lớp bug «fake-success» trên các schema *Update (QC toàn hệ thống 27/08/2026).

Cùng gốc rễ với lỗi «Chuyển sang Mất lead» vá sáng 27/08: FE gửi field mà schema
Update không khai báo → Pydantic bỏ qua im lặng → endpoint trả 200 với bản ghi
y nguyên → FE toast xanh «đã lưu». QC rà cả 4 cặp form-sửa và tìm thấy:

  1. ProjectUpdate thiếu 7 trường form «Sửa dự án» vẫn gửi: client_name,
     client_phone, address, project_type, total_value, start_date, target_end_date.
  2. ContractUpdate thiếu project_id — form sửa HĐ có ô chọn dự án.
  3. QuotationUpdate thiếu type + project_id — form sửa báo giá có cả hai ô.
  4. TransactionUpdate thiếu alias 'date' + user_id (audit 22/07 chỉ vá bản
     Create), VÀ endpoint setattr vào thuộc tính không phải cột (transaction_date/
     user_id không tồn tại trên model) → sửa ngày giao dịch CHƯA BAO GIỜ ăn.

Tất cả 4 schema nay khai đủ field + extra='forbid' (field lạ → 422 thay vì nuốt).
"""

import pytest
from sqlalchemy import select

from app.models.payroll import Transaction
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# 1. Dự án: 7 trường form sửa phải LƯU THẬT
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sua_du_an_doi_du_7_truong(client, admin_user, project):
    resp = await client.put(
        f"/api/v1/projects/{project.id}",
        json={
            "client_name": "Anh Bảy đổi tên",
            "client_phone": "0912345678",
            "address": "99 Lê Lợi, Q1",
            "project_type": "design",
            "total_value": 777000,
            "start_date": "2026-09-01",
            "target_end_date": "2026-12-31",
        },
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["client_name"] == "Anh Bảy đổi tên"
    assert body["client_phone"] == "0912345678"
    assert body["address"] == "99 Lê Lợi, Q1"
    assert body["project_type"] == "design"
    assert body["total_value"] == 777000
    assert (body["start_date"] or "").startswith("2026-09-01")
    assert (body["target_end_date"] or "").startswith("2026-12-31")


@pytest.mark.asyncio
async def test_sua_du_an_field_la_bi_chan_422(client, admin_user, project):
    resp = await client.put(
        f"/api/v1/projects/{project.id}",
        json={"truong_khong_ton_tai": 1},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 422, "field lạ phải 422, không được nuốt im lặng rồi trả 200"


# ---------------------------------------------------------------------------
# 2. Hợp đồng: đổi dự án qua form sửa phải LƯU THẬT
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sua_hop_dong_doi_du_an(client, admin_user, project, project_with_financials):
    p2 = project_with_financials
    resp = await client.post(
        "/api/v1/contracts",
        json={"code": "HD-QC-27-08", "project_id": project.id, "title": "HĐ QC"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    contract_id = resp.json()["id"]

    resp = await client.put(
        f"/api/v1/contracts/{contract_id}",
        json={"project_id": p2.id},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["project_id"] == p2.id, "đổi dự án phải ăn thật, không nuốt im lặng"


# ---------------------------------------------------------------------------
# 3. Báo giá: đổi loại + dự án qua form sửa phải LƯU THẬT
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sua_bao_gia_doi_loai_va_du_an(client, admin_user, project):
    resp = await client.post(
        "/api/v1/quotations",
        json={"type": "design", "title": "Báo giá QC"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    qt_id = resp.json()["id"]

    resp = await client.put(
        f"/api/v1/quotations/{qt_id}",
        json={"type": "construction", "project_id": project.id},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["type"] == "construction"
    assert body["project_id"] == project.id


# ---------------------------------------------------------------------------
# 4. Giao dịch thu chi: sửa ngày (key 'date' như FE gửi) + người liên quan phải ăn
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sua_giao_dich_doi_ngay_va_nguoi(client, db_session, admin_user, sales_user):
    resp = await client.post(
        "/api/v1/accounting/transactions",
        json={"type": "expense", "category": "misc", "amount": 500000, "date": "2026-08-01"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    txn_id = resp.json()["id"]

    resp = await client.put(
        f"/api/v1/accounting/transactions/{txn_id}",
        json={"date": "2026-08-15", "user_id": sales_user.id},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text

    txn = (await db_session.execute(select(Transaction).where(Transaction.id == txn_id))).scalar_one()
    await db_session.refresh(txn)
    assert txn.date.strftime("%Y-%m-%d") == "2026-08-15", (
        "sửa ngày giao dịch phải lưu thật — trước QC 27/08 chưa bao giờ ăn"
    )
    assert txn.related_user_id == sales_user.id


@pytest.mark.asyncio
async def test_sua_giao_dich_field_la_bi_chan_422(client, admin_user):
    resp = await client.post(
        "/api/v1/accounting/transactions",
        json={"type": "expense", "category": "misc", "amount": 100000},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200, resp.text
    txn_id = resp.json()["id"]

    resp = await client.put(
        f"/api/v1/accounting/transactions/{txn_id}",
        json={"khong_ton_tai": True},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 422
