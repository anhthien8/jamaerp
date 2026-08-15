"""Tests for Quotations API — sinh mã BG tự động, mã trùng, update hạng mục (kể cả mảng rỗng).

Hồi quy cho 2 lỗi vá 15/08/2026:
- create: check-then-insert không nguyên tử → trùng mã nổ 500 (giờ: tự bốc mã khác,
  mã người dùng tự nhập mà trùng thì 409).
- update: `items: []` lọt qua điều kiện truthiness → qt.items thành list
  → QuotationResponse (items: dict) nổ 500 (giờ: [] hợp lệ, lưu {"line_items": []}).
"""

import re
from datetime import datetime, timezone

import pytest

from tests.conftest import auth_header, _uid


def _quotation_payload(**overrides):
    payload = {
        "type": "design",
        "title": "Báo giá thiết kế căn hộ test",
        "items": [
            {"name": "Sofa phòng khách", "category": "phong_khach", "unit": "bộ", "quantity": 1, "unit_price": 25000000, "total": 25000000},
        ],
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
class TestQuotationCreate:
    async def test_khong_nhap_ma_tu_sinh_dang_bg_nam(self, client, admin_user):
        resp = await client.post(
            "/api/v1/quotations",
            json=_quotation_payload(),
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        year = datetime.now(timezone.utc).year
        assert re.fullmatch(rf"BG-{year}-(\d{{4}}|[0-9a-f]{{8}})", body["code"]), body["code"]
        assert body["status"] == "draft"
        # Server lưu full model_dump (có cả field default như description=None)
        # → chỉ so các field mình gửi lên
        line_items = body["items"]["line_items"]
        assert len(line_items) == 1
        sent = _quotation_payload()["items"][0]
        assert {k: line_items[0][k] for k in sent} == sent

    async def test_ma_tu_nhap_trung_bao_409_khong_no_500(self, client, admin_user):
        code = f"BG-TRUNG-{_uid()}"
        headers = auth_header(admin_user)
        first = await client.post(
            "/api/v1/quotations",
            json=_quotation_payload(code=code),
            headers=headers,
        )
        assert first.status_code == 200, first.text

        second = await client.post(
            "/api/v1/quotations",
            json=_quotation_payload(code=code, title="Bản trùng mã"),
            headers=headers,
        )
        assert second.status_code == 409, second.text
        assert code in second.json()["detail"]

        # Phiên DB vẫn dùng được sau savepoint rollback: tạo tiếp bản ghi khác OK
        third = await client.post(
            "/api/v1/quotations",
            json=_quotation_payload(code=f"BG-TRUNG-{_uid()}"),
            headers=headers,
        )
        assert third.status_code == 200, third.text

    async def test_tong_tien_tu_tinh_tu_hang_muc(self, client, admin_user):
        resp = await client.post(
            "/api/v1/quotations",
            json=_quotation_payload(
                items=[
                    {"name": "Giường ngủ", "category": "phong_ngu", "quantity": 2, "unit_price": 10000000, "total": 20000000},
                    {"name": "Tủ bếp", "category": "bep", "quantity": 1, "unit_price": 30000000, "total": 30000000},
                ]
            ),
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["total_amount"] == 50000000


@pytest.mark.asyncio
class TestQuotationUpdateItems:
    async def _create(self, client, user):
        resp = await client.post(
            "/api/v1/quotations",
            json=_quotation_payload(),
            headers=auth_header(user),
        )
        assert resp.status_code == 200, resp.text
        return resp.json()

    async def test_xoa_het_hang_muc_items_rong_van_luu_duoc(self, client, admin_user):
        qt = await self._create(client, admin_user)
        resp = await client.put(
            f"/api/v1/quotations/{qt['id']}",
            json={"items": []},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["items"] == {"line_items": []}

        # Đọc lại từ DB vẫn trả JSON hợp lệ (trước đây items=list làm response nổ 500)
        detail = await client.get(
            f"/api/v1/quotations/{qt['id']}",
            headers=auth_header(admin_user),
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["items"] == {"line_items": []}

    async def test_thay_hang_muc_moi_boc_thanh_line_items(self, client, admin_user):
        qt = await self._create(client, admin_user)
        resp = await client.put(
            f"/api/v1/quotations/{qt['id']}",
            json={
                "items": [
                    {"name": "Bàn ăn gỗ óc chó", "category": "custom", "unit": "cái", "quantity": 1, "unit_price": 45000000, "total": 45000000},
                ]
            },
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["items"]["line_items"][0]["name"] == "Bàn ăn gỗ óc chó"
        assert len(body["items"]["line_items"]) == 1

    async def test_update_khong_dinh_items_giu_nguyen_hang_muc(self, client, admin_user):
        qt = await self._create(client, admin_user)
        resp = await client.put(
            f"/api/v1/quotations/{qt['id']}",
            json={"title": "Đổi tên báo giá, giữ hạng mục"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["title"] == "Đổi tên báo giá, giữ hạng mục"
        assert body["items"] == qt["items"]
