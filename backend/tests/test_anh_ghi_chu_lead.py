"""Ảnh đính kèm ghi chú lead (23/10/2026) — thay ô dán link Google Drive.

- Ảnh lưu Postgres, KHÔNG gửi lên Kho ảnh Telegram (lead chỉ KD + BGĐ thấy).
- Backend chuẩn hoá lại: PNG → JPG, bỏ EXIF.
- Xem ảnh cần JWT + cùng phạm vi xem lead; người ngoài KD → 403.
"""

import base64
import io

import pytest
import pytest_asyncio
from httpx import AsyncClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from tests.conftest import _uid, auth_header


def _png_b64() -> str:
    buf = io.BytesIO()
    Image.new("RGBA", (40, 30), (200, 100, 50, 128)).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


@pytest_asyncio.fixture
async def lead(db_session: AsyncSession, sales_user) -> Lead:
    ld = Lead(id=_uid(), name="Anh Tuấn", phone="0901234567", stage="new", assigned_to=sales_user.id)
    db_session.add(ld)
    await db_session.commit()
    return ld


@pytest.mark.asyncio
async def test_tai_va_xem_anh(client: AsyncClient, lead, sales_user):
    h = auth_header(sales_user)
    r = await client.post(f"/api/v1/leads/{lead.id}/attachments", json={"data_base64": _png_b64()}, headers=h)
    assert r.status_code == 201, r.text
    anh = r.json()
    assert (anh["width"], anh["height"]) == (40, 30)

    r = await client.get(f"/api/v1/leads/{lead.id}/attachments/{anh['id']}", headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert r.content[:2] == b"\xff\xd8"  # PNG đã thành JPG
    assert "private" in r.headers["cache-control"]


@pytest.mark.asyncio
async def test_anh_khong_hop_le(client: AsyncClient, lead, sales_user):
    h = auth_header(sales_user)
    r = await client.post(f"/api/v1/leads/{lead.id}/attachments", json={"data_base64": "khong-phai-base64!"}, headers=h)
    assert r.status_code == 422
    r = await client.post(f"/api/v1/leads/{lead.id}/attachments",
                          json={"data_base64": base64.b64encode(b"chu thuong").decode()}, headers=h)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_ngoai_kinh_doanh_bi_chan(client: AsyncClient, lead, sales_user, designer_user):
    r = await client.post(f"/api/v1/leads/{lead.id}/attachments", json={"data_base64": _png_b64()},
                          headers=auth_header(sales_user))
    anh_id = r.json()["id"]
    h = auth_header(designer_user)
    r = await client.post(f"/api/v1/leads/{lead.id}/attachments", json={"data_base64": _png_b64()}, headers=h)
    assert r.status_code == 403
    r = await client.get(f"/api/v1/leads/{lead.id}/attachments/{anh_id}", headers=h)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_anh_sai_lead_404(client: AsyncClient, db_session: AsyncSession, lead, admin_user):
    h = auth_header(admin_user)
    r = await client.post(f"/api/v1/leads/{lead.id}/attachments", json={"data_base64": _png_b64()}, headers=h)
    anh_id = r.json()["id"]
    khac = Lead(id=_uid(), name="Chị Lan", phone="0907654321", stage="new")
    db_session.add(khac)
    await db_session.commit()
    r = await client.get(f"/api/v1/leads/{khac.id}/attachments/{anh_id}", headers=h)
    assert r.status_code == 404
