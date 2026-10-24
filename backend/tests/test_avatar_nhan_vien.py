"""Ảnh đại diện nhân viên (24/10/2026): chính chủ/HR đổi, URL ký HMAC."""

import base64
import io

import pytest
from PIL import Image

from tests.conftest import auth_header


def _png_b64(w=800, h=500, mau=(200, 30, 30)) -> str:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), mau).save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


@pytest.mark.asyncio
async def test_chinh_chu_doi_anh_va_xem_duoc(client, sales_user):
    r = await client.put(
        f"/api/v1/hr/employees/{sales_user.id}/avatar",
        json={"data_base64": _png_b64()}, headers=auth_header(sales_user),
    )
    assert r.status_code == 200, r.text
    url = r.json()["avatar_url"]
    assert url.startswith(f"/media/avatar/{sales_user.id}/") and "?v=" in url

    img = await client.get("/api/v1" + url)
    assert img.status_code == 200
    assert img.headers["content-type"] == "image/jpeg"
    anh = Image.open(io.BytesIO(img.content))
    assert anh.size == (320, 320)  # cắt vuông

    me = await client.get("/api/v1/auth/me", headers=auth_header(sales_user))
    assert me.json()["avatar_url"] == url
    assert "avatar_ver" not in me.json()


@pytest.mark.asyncio
async def test_nguoi_khac_khong_phai_hr_bi_chan(client, sales_user, designer_user):
    r = await client.put(
        f"/api/v1/hr/employees/{sales_user.id}/avatar",
        json={"data_base64": _png_b64()}, headers=auth_header(designer_user),
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_ke_toan_doi_anh_cho_nhan_vien_va_hien_o_danh_sach(client, sales_user, accountant_user, admin_user):
    r = await client.put(
        f"/api/v1/hr/employees/{sales_user.id}/avatar",
        json={"data_base64": _png_b64()}, headers=auth_header(accountant_user),
    )
    assert r.status_code == 200
    ds = await client.get("/api/v1/users", params={"page_size": 500}, headers=auth_header(admin_user))
    hang = next(u for u in ds.json()["items"] if u["id"] == sales_user.id)
    assert hang["avatar_url"] == r.json()["avatar_url"]
    khac = next(u for u in ds.json()["items"] if u["id"] == admin_user.id)
    assert khac["avatar_url"] is None


@pytest.mark.asyncio
async def test_sai_chu_ky_404_va_xoa_anh(client, sales_user):
    r = await client.put(
        f"/api/v1/hr/employees/{sales_user.id}/avatar",
        json={"data_base64": _png_b64()}, headers=auth_header(sales_user),
    )
    assert r.status_code == 200
    bad = await client.get(f"/api/v1/media/avatar/{sales_user.id}/0000000000000000.jpg")
    assert bad.status_code == 404

    d = await client.delete(f"/api/v1/hr/employees/{sales_user.id}/avatar", headers=auth_header(sales_user))
    assert d.status_code == 200 and d.json()["avatar_url"] is None
    gone = await client.get("/api/v1" + r.json()["avatar_url"])
    assert gone.status_code == 404


@pytest.mark.asyncio
async def test_anh_hong_bi_tu_choi(client, sales_user):
    r = await client.put(
        f"/api/v1/hr/employees/{sales_user.id}/avatar",
        json={"data_base64": base64.b64encode(b"khong phai anh").decode()}, headers=auth_header(sales_user),
    )
    assert r.status_code == 422
