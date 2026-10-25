"""Preflight CORS cho mọi phương thức frontend dùng (25/10/2026: thiếu PATCH →
công tắc «Khách thấy», sửa mẫu HĐ… báo «Failed to fetch»)."""

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE"])
async def test_preflight_cho_phep_phuong_thuc(client, method):
    r = await client.options(
        "/api/v1/media/abc",
        headers={
            "Origin": "https://crm.jamahome.vn",
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert r.status_code == 200, r.text
    assert method in r.headers["access-control-allow-methods"]
